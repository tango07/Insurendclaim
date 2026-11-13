"""Pydantic API schemas (request/response contracts)."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------- Profiles & policies ----------
class ProfileCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    city: Optional[str] = Field(default=None, max_length=80)
    with_sample_policies: bool = True

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v


class RegisterIn(ProfileCreate):
    username: str = Field(min_length=1, max_length=50, description="3-50 letters, numbers, . _ - @ + (email addresses allowed)")
    password: str = Field(min_length=1, max_length=128)  # rule enforced in auth.password_problem


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class AddPolicyIn(BaseModel):
    policy_type: Literal["auto", "home", "gadget"]
    insurer_id: str
    policy_number: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{5,19}$", description="6-20 letters, numbers or dashes")
    asset_name: str = Field(min_length=3, max_length=100)
    asset_details: dict[str, str] = Field(default_factory=dict, max_length=8)
    start_date: Optional[date] = None

    @field_validator("asset_details")
    @classmethod
    def short_values(cls, v: dict[str, str]) -> dict[str, str]:
        if any(len(k) > 40 or len(x) > 100 for k, x in v.items()):
            raise ValueError("Asset details are too long")
        return {k.strip(): x.strip() for k, x in v.items()}


class ProfileSummary(BaseModel):
    id: str
    full_name: str
    photo_url: Optional[str] = None
    city: Optional[str] = None
    is_sample: bool
    policy_count: int


class Asset(BaseModel):
    id: str
    policy_id: str
    asset_type: str
    name: str
    details: dict[str, str]


class Coverage(BaseModel):
    code: str
    name: str
    description: str
    limit_amount: Optional[float] = None
    limit_note: Optional[str] = None
    deductible_amount: Optional[float] = None


class Clause(BaseModel):
    code: str
    text: str


class Insurer(BaseModel):
    id: str
    name: str
    short_name: str
    claims_phone: str
    claims_email: str
    website: str
    address: str
    claims_hours: str
    brand_color: str


class PolicySummary(BaseModel):
    id: str
    insurer: Insurer
    policy_number: str
    policy_type: str
    product_name: str
    status: str
    start_date: str
    end_date: str
    summary: Optional[str] = None
    wording_available: bool
    assets: list[Asset]


class PolicyDetail(PolicySummary):
    insurer_label: str
    coverages: list[Coverage]
    exclusions: list[Clause]
    conditions: list[Clause]


class ProfileDetail(ProfileSummary):
    policies: list[PolicySummary]


# ---------- Attachments ----------
class AttachmentOut(BaseModel):
    id: str
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_at: str


# ---------- Claims ----------
class ClaimDraftInput(BaseModel):
    """Input for the AI suggestion. Only incident data + IDs; no profile PII."""
    policy_id: str
    asset_id: str
    description: str = Field(min_length=15, max_length=6000)
    incident_date: Optional[date] = None
    incident_location: Optional[str] = Field(default=None, max_length=200)
    attachment_ids: list[str] = Field(default_factory=list, max_length=10)
    answered_keys: list[str] = Field(default_factory=list, max_length=20)  # follow-up questions the user answered in chat

    @field_validator("incident_date")
    @classmethod
    def not_future(cls, v: Optional[date]) -> Optional[date]:
        if v and v > date.today():
            raise ValueError("Incident date cannot be in the future")
        return v


class ClaimSubmit(ClaimDraftInput):
    policyholder_id: str
    category: str = Field(min_length=2, max_length=40)
    summary: str = Field(min_length=10, max_length=1500)
    next_steps: list[str] = Field(default_factory=list, max_length=20)
    documents_to_collect: list[str] = Field(default_factory=list, max_length=20)
    ai_suggestion: Optional[dict] = None  # original AI output snapshot for audit


class ClaimEvent(BaseModel):
    status: str
    title: str
    detail: Optional[str] = None
    actor: str
    created_at: str


class ClaimOut(BaseModel):
    id: str
    claim_number: str
    policyholder_id: str
    policy_id: str
    policy_number: str
    policy_type: str
    asset_id: str
    asset_name: str
    category: str
    category_label: str
    incident_date: Optional[str] = None
    incident_location: Optional[str] = None
    description: str
    summary: str
    next_steps: list[str]
    documents_to_collect: list[str]
    status: str
    created_at: str
    updated_at: str
    attachments: list[AttachmentOut] = []
    events: list[ClaimEvent] = []
    upcoming: list[str] = []
    ai_suggestion: Optional[dict] = None
    appointments: list["AppointmentOut"] = []


# ---------- Chat: intent + follow-up questions ----------
class IntentIn(BaseModel):
    policy_id: str
    message: str = Field(min_length=1, max_length=2000)


class ChatAction(BaseModel):
    id: Literal["start_claim", "speak_adjuster", "find_garage", "ask_policy"]
    label: str


class IntentOut(BaseModel):
    reply: str
    intents: list[str]
    actions: list[ChatAction]
    looks_like_incident: bool  # message can be reused as the claim's first description
    provider: str
    auto_action: Optional[Literal["speak_adjuster"]] = None  # UI should run this immediately


class FollowUpIn(BaseModel):
    policy_id: str
    asset_id: str
    description: str = Field(min_length=1, max_length=6000)
    asked_keys: list[str] = Field(default_factory=list, max_length=20)
    attachment_ids: list[str] = Field(default_factory=list, max_length=10)


class FollowUpOut(BaseModel):
    done: bool
    key: Optional[str] = None
    question: Optional[str] = None
    why: Optional[str] = None
    provider: str


# ---------- Adjusters, partners, appointments ----------
class Adjuster(BaseModel):
    id: str
    full_name: str
    specialization: str
    office_location: str
    phone: str
    email: str
    languages: str
    years_experience: int
    bio: Optional[str] = None
    insurer_name: str
    allowed_modes: list[str]
    slots: list[str]  # local ISO "YYYY-MM-DDTHH:MM"


class RepairPartner(BaseModel):
    id: str
    name: str
    kind: str
    address: str
    distance_km: float
    rating: float
    phone: str
    services: str
    hours: str


class AppointmentCreate(BaseModel):
    adjuster_id: str
    policyholder_id: str
    policy_id: str
    claim_id: Optional[str] = None
    slot_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")
    mode: Literal["audio", "video", "onsite", "chat"]
    contact_name: str = Field(min_length=2, max_length=80)
    contact_phone: str = Field(pattern=r"^\+?[0-9][0-9 ()\-]{6,19}$")
    meeting_location: Optional[str] = Field(default=None, max_length=200)
    attachment_ids: list[str] = Field(default_factory=list, max_length=10)


class AppointmentOut(BaseModel):
    id: str
    reference: str
    adjuster_id: str
    adjuster_name: str
    adjuster_phone: str
    adjuster_email: str
    adjuster_office: str
    policy_id: str
    claim_id: Optional[str] = None
    slot_start: str
    duration_minutes: int
    mode: str
    contact_name: str
    contact_phone: str
    meeting_location: Optional[str] = None
    meeting_link: Optional[str] = None
    instructions: list[str]
    directions: Optional[str] = None
    shared_attachments: list[str]
    status: str
    created_at: str


# ---------- Assistant ----------
class AssistantQuestion(BaseModel):
    policy_id: str
    question: str = Field(min_length=3, max_length=500)
    claim_id: Optional[str] = None


class AssistantAnswer(BaseModel):
    answer: str
    sources: list[str]
    provider: str
    disclaimer: str


class ErrorOut(BaseModel):
    detail: str
    kind: Literal["validation", "not_found", "file", "ai", "server"] = "server"


ClaimOut.model_rebuild()


class AuthOut(BaseModel):
    token: str
    username: str
    profile: ProfileDetail


class InsurerWithLines(Insurer):
    lines: list[str]
