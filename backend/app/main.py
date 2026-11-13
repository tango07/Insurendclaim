"""EPAM powered InsureNdClaim API (FastAPI)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import sqlite3

from . import auth
from . import repositories as repo
from . import scheduling
from .ai import assistant as assistant_mod
from .ai import chat as chat_mod
from .ai.schemas import ClaimGuidance
from .ai.service import GuidanceService, build_request, dump, load_images
from .catalog import label_for
from .config import Settings, get_settings
from .db import connect, init_db
from .models import (AddPolicyIn, AuthOut, InsurerWithLines, LoginIn, RegisterIn, Adjuster, AppointmentCreate, AppointmentOut, AssistantAnswer, AssistantQuestion, AttachmentOut,
                     ClaimDraftInput, ClaimOut, ClaimSubmit, FollowUpIn, FollowUpOut, IntentIn, IntentOut, PolicyDetail,
                     ProfileCreate, ProfileDetail, ProfileSummary, RepairPartner)
from .seed import INSURER_LINES, add_policy_from_template, seed
from .storage import FileValidationError, LocalStorage, validate_file

logging.basicConfig(level=logging.INFO)

UPCOMING = {
    "submitted": ["Initial review by a claims handler (typically 1-2 business days)", "An adjuster contacts you to confirm details",
                  "Assessment of documents, photos and estimates", "Decision and next steps communicated to you"],
    "in_review": ["An adjuster contacts you to confirm details", "Assessment of documents, photos and estimates",
                  "Decision and next steps communicated to you"],
}


def create_app(settings: Settings | None = None, guidance: GuidanceService | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        conn = connect(settings.db_path)
        init_db(conn)
        seed(conn)
        auth.ensure_demo_users(conn)
        conn.close()
        yield

    app = FastAPI(title="EPAM powered InsureNdClaim API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.storage = LocalStorage(settings.upload_dir)
    app.state.guidance = guidance or GuidanceService(settings)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        msgs = []
        for e in exc.errors():
            loc = ".".join(str(x) for x in e["loc"] if x not in ("body", "query", "path"))
            msgs.append(f"{loc}: {e['msg']}" if loc else e["msg"])
        return JSONResponse(status_code=422, content={"detail": "; ".join(msgs), "kind": "validation"})

    def get_db():
        conn = connect(settings.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def not_found(what: str):
        raise HTTPException(status_code=404, detail=f"{what} not found")

    def claim_out(c: dict) -> dict:
        return c | {"category_label": label_for(c["category"]), "upcoming": UPCOMING.get(c["status"], [])}

    # ---------- auth ----------
    def current_user(authorization: str | None = Header(default=None), conn=Depends(get_db)) -> dict:
        token = (authorization or "").removeprefix("Bearer ").strip()
        user = auth.user_for_token(conn, token) if token else None
        if not user:
            raise HTTPException(401, "Please log in to continue.")
        return user

    def ensure_self(user: dict, profile_id: str) -> None:
        if user["policyholder_id"] != profile_id:
            raise HTTPException(403, "You can only access your own profile.")

    def owned_policy(conn, user: dict, policy_id: str) -> dict:
        p = repo.get_policy(conn, policy_id)
        if not p or p["policyholder_id"] != user["policyholder_id"]:
            not_found("Policy")  # 404 rather than 403: don't reveal other people's policies
        return p

    @app.post("/api/auth/register", response_model=AuthOut, status_code=201)
    def register(body: RegisterIn, conn=Depends(get_db)):
        if problem := auth.username_problem(body.username):
            raise HTTPException(400, problem)
        if problem := auth.password_problem(body.password):
            raise HTTPException(400, problem)
        if auth.username_taken(conn, body.username):
            raise HTTPException(409, "That username is already taken.")
        prof = repo.create_profile(conn, body.full_name, body.city, body.with_sample_policies, commit=False)
        uid = auth.create_user(conn, body.username, body.password, prof["id"])
        token = auth.start_session(conn, uid)
        return {"token": token, "username": body.username, "profile": repo.get_profile(conn, prof["id"])}

    @app.post("/api/auth/login", response_model=AuthOut)
    def login(body: LoginIn, conn=Depends(get_db)):
        u = auth.authenticate(conn, body.username, body.password)
        if not u:
            raise HTTPException(401, "Incorrect username or password.")
        return {"token": auth.start_session(conn, u["id"]), "username": u["username"], "profile": repo.get_profile(conn, u["policyholder_id"])}

    @app.get("/api/auth/me", response_model=AuthOut)
    def me(authorization: str | None = Header(default=None), user=Depends(current_user), conn=Depends(get_db)):
        return {"token": (authorization or "").removeprefix("Bearer ").strip(), "username": user["username"],
                "profile": repo.get_profile(conn, user["policyholder_id"])}

    @app.post("/api/auth/logout", status_code=204)
    def logout(authorization: str | None = Header(default=None), conn=Depends(get_db)):
        token = (authorization or "").removeprefix("Bearer ").strip()
        if token:
            auth.end_session(conn, token)

    # ---------- meta ----------
    @app.get("/api/health")
    def health():
        return {"status": "ok", "ai_mode": app.state.guidance.mode,
                "max_upload_mb": settings.max_upload_mb, "max_files": settings.max_files_per_request}

    # ---------- profiles ----------
    @app.get("/api/profiles/{profile_id}", response_model=ProfileDetail)
    def get_profile(profile_id: str, user=Depends(current_user), conn=Depends(get_db)):
        ensure_self(user, profile_id)
        return repo.get_profile(conn, profile_id) or not_found("Profile")

    @app.get("/api/profiles/{profile_id}/claims", response_model=list[ClaimOut])
    def list_claims(profile_id: str, user=Depends(current_user), conn=Depends(get_db)):
        ensure_self(user, profile_id)
        return [claim_out(c) for c in repo.list_claims(conn, profile_id)]

    # ---------- policies ----------
    @app.get("/api/insurers", response_model=list[InsurerWithLines])
    def insurers(conn=Depends(get_db)):
        return [i | {"lines": INSURER_LINES.get(i["id"], [])} for i in repo.list_insurers(conn)]

    @app.post("/api/me/policies", response_model=ProfileDetail, status_code=201)
    def add_policy(body: AddPolicyIn, user=Depends(current_user), conn=Depends(get_db)):
        if body.policy_type not in INSURER_LINES.get(body.insurer_id, []):
            raise HTTPException(400, "That insurer doesn't offer this type of policy in the demo.")
        if repo.policy_number_exists(conn, body.policy_number):
            raise HTTPException(409, f"Policy number {body.policy_number} is already registered.")
        details = {k: v for k, v in body.asset_details.items() if v}
        add_policy_from_template(conn, user["policyholder_id"], body.policy_type, body.insurer_id, body.policy_number,
                                 body.asset_name, details, body.start_date)
        return repo.get_profile(conn, user["policyholder_id"])

    @app.get("/api/me/adjusters", response_model=list[Adjuster])
    def my_adjusters(user=Depends(current_user), conn=Depends(get_db)):
        """Adjuster directory for every insurer/line the user holds a policy with."""
        seen, out = set(), []
        for p in repo.list_policies(conn, user["policyholder_id"]):
            for a in repo.list_adjusters(conn, p["insurer_id"], repo.SPECIALIZATION_FOR.get(p["policy_type"])):
                if a["id"] not in seen:
                    seen.add(a["id"])
                    out.append(_adjuster_out(conn, a))
        return out

    @app.get("/api/policies/{policy_id}", response_model=PolicyDetail)
    def get_policy(policy_id: str, user=Depends(current_user), conn=Depends(get_db)):
        return owned_policy(conn, user, policy_id)

    # ---------- attachments ----------
    @app.post("/api/attachments", response_model=list[AttachmentOut], status_code=201)
    async def upload(files: list[UploadFile] = File(...), user=Depends(current_user), conn=Depends(get_db)):
        if len(files) > settings.max_files_per_request:
            raise HTTPException(400, f"Too many files: maximum is {settings.max_files_per_request} per upload.")
        staged, errors = [], []
        for f in files:
            data = await f.read(settings.max_upload_bytes + 1)
            try:
                ct = validate_file(f.filename or "", f.content_type, data, settings.max_upload_bytes)
                staged.append((f.filename, ct, data))
            except FileValidationError as e:
                errors.append(str(e))
        if errors:  # all-or-nothing so the user isn't left with a partial upload
            raise HTTPException(status_code=400, detail=" ".join(errors))
        out = []
        for name, ct, data in staged:
            key = app.state.storage.save(data, name)
            out.append(repo.create_attachment(conn, name, ct, len(data), key, user["policyholder_id"]))
        return out

    # ---------- claims ----------
    def _resolve(conn, user: dict, policy_id: str, asset_id: str, attachment_ids: list[str]):
        policy = owned_policy(conn, user, policy_id)
        asset = repo.get_asset(conn, asset_id) or not_found("Insured asset")
        if asset["policy_id"] != policy_id:
            raise HTTPException(400, "The selected asset is not insured under the selected policy.")
        for aid in attachment_ids:
            a = repo.get_attachment(conn, aid)
            if not a or a["owner_id"] != user["policyholder_id"]:
                raise HTTPException(400, f"Attachment {aid} not found. Please upload it again.")
            if a["claim_id"]:
                raise HTTPException(400, f"Attachment {a['original_filename']} is already linked to another claim.")
        return policy, asset

    @app.post("/api/claims/suggest", response_model=ClaimGuidance)
    def suggest(body: ClaimDraftInput, user=Depends(current_user), conn=Depends(get_db)):
        policy, asset = _resolve(conn, user, body.policy_id, body.asset_id, body.attachment_ids)
        req, tags = build_request(conn, app.state.storage, policy, asset, body.description, body.incident_date,
                                  body.incident_location, body.attachment_ids, body.answered_keys)
        images, skipped = load_images(repo.get_attachments(conn, body.attachment_ids), app.state.storage)
        try:
            return app.state.guidance.suggest(req, tags, images, skipped)
        except Exception:  # last-resort guard; service already falls back to mock on provider errors
            logging.exception("guidance failed")
            raise HTTPException(503, "The guidance service is unavailable. You can still fill in the claim details yourself.")

    @app.post("/api/claims", response_model=ClaimOut, status_code=201)
    def submit(body: ClaimSubmit, user=Depends(current_user), conn=Depends(get_db)):
        policy, _ = _resolve(conn, user, body.policy_id, body.asset_id, body.attachment_ids)
        if body.policyholder_id != user["policyholder_id"]:
            raise HTTPException(403, "You can only submit claims for your own profile.")
        data = body.model_dump()
        data["incident_date"] = body.incident_date.isoformat() if body.incident_date else None
        data["next_steps"] = [s.strip() for s in body.next_steps if s.strip()]
        data["documents_to_collect"] = [s.strip() for s in body.documents_to_collect if s.strip()]
        cid = repo.create_claim(conn, data)
        return claim_out(repo.get_claim(conn, cid))

    @app.get("/api/claims/{claim_id}", response_model=ClaimOut)
    def get_claim(claim_id: str, user=Depends(current_user), conn=Depends(get_db)):
        c = repo.get_claim(conn, claim_id)
        if not c or c["policyholder_id"] != user["policyholder_id"]:
            not_found("Claim")
        return claim_out(c)

    # ---------- chat: intent + follow-ups ----------
    @app.post("/api/chat/intent", response_model=IntentOut)
    def chat_intent(body: IntentIn, user=Depends(current_user), conn=Depends(get_db)):
        policy = owned_policy(conn, user, body.policy_id)
        return chat_mod.detect(body.message, policy["policy_type"], policy["insurer"]["short_name"])

    @app.post("/api/claims/follow-up", response_model=FollowUpOut)
    def follow_up(body: FollowUpIn, user=Depends(current_user), conn=Depends(get_db)):
        policy, asset = _resolve(conn, user, body.policy_id, body.asset_id, body.attachment_ids)
        req, _ = build_request(conn, app.state.storage, policy, asset, body.description, None, None, body.attachment_ids)
        return app.state.guidance.follow_up(req, body.asked_keys)

    # ---------- insurer services: adjusters, partners, appointments ----------
    def _adjuster_out(conn, a: dict) -> dict:
        ins = repo.get_insurer(conn, a["insurer_id"])
        return a | {"insurer_name": ins["name"], "allowed_modes": scheduling.allowed_modes(a),
                    "slots": scheduling.generate_slots(a["id"], repo.booked_slots(conn, a["id"]))}

    @app.get("/api/policies/{policy_id}/adjusters", response_model=list[Adjuster])
    def adjusters(policy_id: str, user=Depends(current_user), conn=Depends(get_db)):
        policy = owned_policy(conn, user, policy_id)
        spec = repo.SPECIALIZATION_FOR.get(policy["policy_type"])
        return [_adjuster_out(conn, a) for a in repo.list_adjusters(conn, policy["insurer_id"], spec)]

    @app.get("/api/policies/{policy_id}/repair-partners", response_model=list[RepairPartner])
    def partners(policy_id: str, user=Depends(current_user), conn=Depends(get_db)):
        policy = owned_policy(conn, user, policy_id)
        return repo.list_repair_partners(conn, policy["insurer_id"])

    @app.post("/api/appointments", response_model=AppointmentOut, status_code=201)
    def book(body: AppointmentCreate, user=Depends(current_user), conn=Depends(get_db)):
        if body.policyholder_id != user["policyholder_id"]:
            raise HTTPException(403, "You can only book appointments for your own profile.")
        policy = owned_policy(conn, user, body.policy_id)
        adj = repo.get_adjuster(conn, body.adjuster_id) or not_found("Adjuster")
        if adj["insurer_id"] != policy["insurer_id"]:
            raise HTTPException(400, "This adjuster works for a different insurer than the selected policy.")
        if body.mode not in scheduling.allowed_modes(adj):
            raise HTTPException(400, f"{adj['full_name']} works remotely and can't do {scheduling.MODE_LABEL[body.mode].lower()}s.")
        if body.slot_start not in scheduling.generate_slots(adj["id"], repo.booked_slots(conn, adj["id"])):
            raise HTTPException(409, "That slot is no longer available. Please choose another time.")
        if body.mode == "onsite" and not (body.meeting_location or "").strip():
            raise HTTPException(400, "Please tell us where the on-site inspection should take place.")
        claim = None
        if body.claim_id:
            claim = repo.get_claim(conn, body.claim_id) or not_found("Claim")
            if claim["policy_id"] != body.policy_id:
                raise HTTPException(400, "The claim is not on the selected policy.")
        shared = list(dict.fromkeys(body.attachment_ids + ([a["id"] for a in claim["attachments"]] if claim else [])))
        if len([a for a in repo.get_attachments(conn, shared) if a["owner_id"] == user["policyholder_id"]]) != len(shared):
            raise HTTPException(400, "One of the attachments could not be found. Please upload it again.")
        details = scheduling.build_appointment_details(body.mode, adj, policy["policy_type"], body.contact_phone,
                                                       body.meeting_location, claim, len(shared))
        data = body.model_dump() | details | {
            "shared_attachment_ids": shared, "adjuster_name": adj["full_name"],
            "slot_label": scheduling.slot_label(body.slot_start), "mode_label": scheduling.MODE_LABEL[body.mode]}
        try:
            aid = repo.create_appointment(conn, data)
        except sqlite3.IntegrityError:
            raise HTTPException(409, "That slot was just taken. Please choose another time.")
        return repo.get_appointment(conn, aid)

    @app.get("/api/profiles/{profile_id}/appointments", response_model=list[AppointmentOut])
    def appointments(profile_id: str, user=Depends(current_user), conn=Depends(get_db)):
        ensure_self(user, profile_id)
        return repo.list_appointments(conn, profile_id)

    # ---------- assistant ----------
    @app.post("/api/assistant", response_model=AssistantAnswer)
    def ask(body: AssistantQuestion, user=Depends(current_user), conn=Depends(get_db)):
        policy = owned_policy(conn, user, body.policy_id)
        claim = repo.get_claim(conn, body.claim_id) if body.claim_id else None
        if claim and claim["policyholder_id"] != user["policyholder_id"]:
            claim = None
        adjs = repo.list_adjusters(conn, policy["insurer_id"], repo.SPECIALIZATION_FOR.get(policy["policy_type"]))
        appts = repo.list_appointments(conn, policy["policyholder_id"])
        return assistant_mod.answer(body.question, policy, claim, app.state.guidance.provider, adjs, appts)

    return app


app = create_app()
