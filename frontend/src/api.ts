// Typed API client. Responses are validated with zod so contract drift surfaces as a clear error.
import { z } from "zod";

const Asset = z.object({ id: z.string(), policy_id: z.string(), asset_type: z.string(), name: z.string(), details: z.record(z.string()) });
const Insurer = z.object({
  id: z.string(), name: z.string(), short_name: z.string(), claims_phone: z.string(), claims_email: z.string(),
  website: z.string(), address: z.string(), claims_hours: z.string(), brand_color: z.string(),
});
const PolicySummary = z.object({
  id: z.string(), insurer: Insurer, policy_number: z.string(), policy_type: z.string(), product_name: z.string(), status: z.string(),
  start_date: z.string(), end_date: z.string(), summary: z.string().nullable().optional(), wording_available: z.boolean(), assets: z.array(Asset),
});
const Coverage = z.object({ code: z.string(), name: z.string(), description: z.string(), limit_amount: z.number().nullable().optional(), limit_note: z.string().nullable().optional(), deductible_amount: z.number().nullable().optional() });
const Clause = z.object({ code: z.string(), text: z.string() });
const PolicyDetail = PolicySummary.extend({ insurer_label: z.string(), coverages: z.array(Coverage), exclusions: z.array(Clause), conditions: z.array(Clause) });
const ProfileSummary = z.object({ id: z.string(), full_name: z.string(), photo_url: z.string().nullable().optional(), city: z.string().nullable().optional(), is_sample: z.boolean(), policy_count: z.number() });
const ProfileDetail = ProfileSummary.extend({ policies: z.array(PolicySummary) });
const Attachment = z.object({ id: z.string(), original_filename: z.string(), content_type: z.string(), size_bytes: z.number(), uploaded_at: z.string() });

export const Guidance = z.object({
  suggested_category: z.string(), suggested_category_label: z.string(), category_confidence: z.enum(["low", "medium", "high"]),
  incident_summary: z.string(),
  relevant_coverages: z.array(z.object({ coverage_code: z.string(), coverage_name: z.string(), why_relevant: z.string(), policy_wording: z.string(), limit_note: z.string().nullable().optional(), deductible_amount: z.number().nullable().optional() })),
  possible_exclusions: z.array(z.object({ code: z.string(), policy_wording: z.string(), why_relevant: z.string() })),
  missing_information: z.array(z.string()), documents_to_collect: z.array(z.string()), next_steps: z.array(z.string()),
  limitations: z.array(z.string()), needs_adjuster_review: z.boolean(), attachment_notes: z.array(z.string()),
  image_observations: z.array(z.object({ filename: z.string(), observation: z.string(), matches_description: z.string() })).optional(),
  provider: z.string(), fallback_reason: z.string().nullable().optional(), disclaimer: z.string(),
});

const Appointment = z.object({
  id: z.string(), reference: z.string(), adjuster_id: z.string(), adjuster_name: z.string(), adjuster_phone: z.string(),
  adjuster_email: z.string(), adjuster_office: z.string(), policy_id: z.string(), claim_id: z.string().nullable().optional(),
  slot_start: z.string(), duration_minutes: z.number(), mode: z.string(), contact_name: z.string(), contact_phone: z.string(),
  meeting_location: z.string().nullable().optional(), meeting_link: z.string().nullable().optional(), instructions: z.array(z.string()),
  directions: z.string().nullable().optional(), shared_attachments: z.array(z.string()), status: z.string(), created_at: z.string(),
});
const Adjuster = z.object({
  id: z.string(), full_name: z.string(), specialization: z.string(), office_location: z.string(), phone: z.string(), email: z.string(),
  languages: z.string(), years_experience: z.number(), bio: z.string().nullable().optional(), insurer_name: z.string(),
  allowed_modes: z.array(z.string()), slots: z.array(z.string()),
});
const RepairPartner = z.object({
  id: z.string(), name: z.string(), kind: z.string(), address: z.string(), distance_km: z.number(), rating: z.number(),
  phone: z.string(), services: z.string(), hours: z.string(),
});
const ChatAction = z.object({ id: z.enum(["start_claim", "speak_adjuster", "find_garage", "ask_policy"]), label: z.string() });
const IntentOut = z.object({ reply: z.string(), intents: z.array(z.string()), actions: z.array(ChatAction), looks_like_incident: z.boolean(), provider: z.string(), auto_action: z.string().nullable().optional() });
const FollowUpOut = z.object({ done: z.boolean(), key: z.string().nullable().optional(), question: z.string().nullable().optional(), why: z.string().nullable().optional(), provider: z.string() });

const ClaimEvent = z.object({ status: z.string(), title: z.string(), detail: z.string().nullable().optional(), actor: z.string(), created_at: z.string() });
const Claim = z.object({
  id: z.string(), claim_number: z.string(), policyholder_id: z.string(), policy_id: z.string(), policy_number: z.string(), policy_type: z.string(),
  asset_id: z.string(), asset_name: z.string(), category: z.string(), category_label: z.string(),
  incident_date: z.string().nullable().optional(), incident_location: z.string().nullable().optional(),
  description: z.string(), summary: z.string(), next_steps: z.array(z.string()), documents_to_collect: z.array(z.string()),
  status: z.string(), created_at: z.string(), updated_at: z.string(), attachments: z.array(Attachment), events: z.array(ClaimEvent),
  upcoming: z.array(z.string()), ai_suggestion: z.record(z.unknown()).nullable().optional(),
  appointments: z.array(Appointment),
});
const Health = z.object({ status: z.string(), ai_mode: z.string(), max_upload_mb: z.number(), max_files: z.number() });
const InsurerWithLines = Insurer.extend({ lines: z.array(z.string()) });
const AuthOut = z.object({ token: z.string(), username: z.string(), profile: ProfileDetail });
const AssistantAnswer = z.object({ answer: z.string(), sources: z.array(z.string()), provider: z.string(), disclaimer: z.string() });

export type Asset = z.infer<typeof Asset>;
export type PolicySummary = z.infer<typeof PolicySummary>;
export type PolicyDetail = z.infer<typeof PolicyDetail>;
export type ProfileSummary = z.infer<typeof ProfileSummary>;
export type ProfileDetail = z.infer<typeof ProfileDetail>;
export type Attachment = z.infer<typeof Attachment>;
export type Guidance = z.infer<typeof Guidance>;
export type Claim = z.infer<typeof Claim>;
export type Health = z.infer<typeof Health>;
export type AssistantAnswer = z.infer<typeof AssistantAnswer>;
export type Insurer = z.infer<typeof Insurer>;
export type Appointment = z.infer<typeof Appointment>;
export type Adjuster = z.infer<typeof Adjuster>;
export type RepairPartner = z.infer<typeof RepairPartner>;
export type ChatAction = z.infer<typeof ChatAction>;
export type IntentOut = z.infer<typeof IntentOut>;
export type FollowUpOut = z.infer<typeof FollowUpOut>;

export interface BookingInput {
  adjuster_id: string; policyholder_id: string; policy_id: string; claim_id?: string | null; slot_start: string;
  mode: string; contact_name: string; contact_phone: string; meeting_location?: string | null; attachment_ids: string[];
}

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

// Session token: kept in memory and in sessionStorage (cleared when the tab closes).
const TOKEN_KEY = "insurendclaim.token";
let token: string | null = typeof sessionStorage !== "undefined" ? sessionStorage.getItem(TOKEN_KEY) : null;
let onUnauthorized: (() => void) | null = null;
export const session = {
  get: () => token,
  set: (t: string | null) => {
    token = t;
    if (typeof sessionStorage === "undefined") return;
    if (t) sessionStorage.setItem(TOKEN_KEY, t); else sessionStorage.removeItem(TOKEN_KEY);
  },
  onUnauthorized: (fn: () => void) => { onUnauthorized = fn; },
};

async function request<T>(schema: z.ZodType<T>, path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  try {
    res = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError("Can't reach the EPAM powered InsureNdClaim server. Is the backend running on port 8000?", 0);
  }
  const body = await res.json().catch(() => null);
  if (res.status === 401 && !path.startsWith("/api/auth/login")) { session.set(null); onUnauthorized?.(); }
  if (res.status === 204) return undefined as T;
  if (!res.ok) throw new ApiError(body?.detail ? String(body.detail) : `Request failed (HTTP ${res.status})`, res.status);
  const parsed = schema.safeParse(body);
  if (!parsed.success) throw new ApiError("The server returned data in an unexpected format.", res.status);
  return parsed.data;
}

const json = (data: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

export interface DraftInput {
  policy_id: string; asset_id: string; description: string;
  incident_date?: string | null; incident_location?: string | null; attachment_ids: string[]; answered_keys?: string[];
}
export interface SubmitInput extends DraftInput {
  policyholder_id: string; category: string; summary: string; next_steps: string[]; documents_to_collect: string[]; ai_suggestion?: Guidance | null;
}

export interface RegisterInput { username: string; password: string; full_name: string; city: string | null; with_sample_policies: boolean }
export interface AddPolicyInput { policy_type: string; insurer_id: string; policy_number: string; asset_name: string; asset_details: Record<string, string>; start_date?: string | null }
export type InsurerWithLines = z.infer<typeof InsurerWithLines>;

export const api = {
  health: () => request(Health, "/api/health"),
  login: (username: string, password: string) => request(AuthOut, "/api/auth/login", json({ username, password })),
  register: (d: RegisterInput) => request(AuthOut, "/api/auth/register", json(d)),
  me: () => request(AuthOut, "/api/auth/me"),
  logout: () => request(z.any(), "/api/auth/logout", { method: "POST" }),
  profile: (id: string) => request(ProfileDetail, `/api/profiles/${id}`),
  insurers: () => request(z.array(InsurerWithLines), "/api/insurers"),
  addPolicy: (d: AddPolicyInput) => request(ProfileDetail, "/api/me/policies", json(d)),
  myAdjusters: () => request(z.array(Adjuster), "/api/me/adjusters"),
  policy: (id: string) => request(PolicyDetail, `/api/policies/${id}`),
  claims: (profileId: string) => request(z.array(Claim), `/api/profiles/${profileId}/claims`),
  claim: (id: string) => request(Claim, `/api/claims/${id}`),
  upload: (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return request(z.array(Attachment), "/api/attachments", { method: "POST", body: fd });
  },
  suggest: (d: DraftInput) => request(Guidance, "/api/claims/suggest", json(d)),
  submit: (d: SubmitInput) => request(Claim, "/api/claims", json(d)),
  intent: (policy_id: string, message: string) => request(IntentOut, "/api/chat/intent", json({ policy_id, message })),
  followUp: (d: { policy_id: string; asset_id: string; description: string; asked_keys: string[]; attachment_ids: string[] }) =>
    request(FollowUpOut, "/api/claims/follow-up", json(d)),
  adjusters: (policyId: string) => request(z.array(Adjuster), `/api/policies/${policyId}/adjusters`),
  repairPartners: (policyId: string) => request(z.array(RepairPartner), `/api/policies/${policyId}/repair-partners`),
  book: (d: BookingInput) => request(Appointment, "/api/appointments", json(d)),
  appointments: (profileId: string) => request(z.array(Appointment), `/api/profiles/${profileId}/appointments`),
  ask: (policy_id: string, question: string, claim_id?: string | null) =>
    request(AssistantAnswer, "/api/assistant", json({ policy_id, question, claim_id: claim_id ?? null })),
};

// Category options per policy type (mirrors backend/app/catalog.py).
export const CATEGORY_OPTIONS: Record<string, [string, string][]> = {
  auto: [["collision", "Collision"], ["glass", "Glass / windshield damage"], ["theft", "Theft / burglary"], ["vandalism", "Vandalism"], ["weather", "Weather / natural event"], ["flood", "Flood / surface water"], ["fire", "Fire / smoke"], ["breakdown", "Breakdown / roadside assistance"], ["liability", "Third-party liability"], ["other", "Other / unsure"]],
  home: [["water", "Water damage (leak / burst pipe)"], ["fire", "Fire / smoke"], ["theft", "Theft / burglary"], ["vandalism", "Vandalism"], ["weather", "Weather / natural event"], ["flood", "Flood / surface water"], ["accidental_damage", "Accidental damage"], ["liability", "Third-party liability"], ["other", "Other / unsure"]],
  gadget: [["accidental_damage", "Accidental damage"], ["theft", "Theft / burglary"], ["other", "Other / unsure"]],
};
