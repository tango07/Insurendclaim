import { useEffect, useState } from "react";
import { api, ApiError, type Appointment, type Claim, type Insurer, type PolicyDetail, type PolicySummary, type ProfileDetail } from "../api";
import { slotLabel } from "./ChatAssistant";
import { Alert, assetIcon, fmtDate, money, SourceTag, Spinner, StatusBadge } from "./ui";

interface Props {
  profile: ProfileDetail;
  onStartClaim: (policyId: string, assetId: string) => void;
  onOpenClaim: (claimId: string) => void;
  onFocusPolicy: (policyId: string) => void;
}

export default function Dashboard({ profile, onStartClaim, onOpenClaim, onFocusPolicy }: Props) {
  const [claims, setClaims] = useState<Claim[] | null>(null);
  const [claimsErr, setClaimsErr] = useState<string | null>(null);

  const [appts, setAppts] = useState<Appointment[]>([]);

  useEffect(() => {
    api.claims(profile.id).then(setClaims).catch((e: ApiError) => setClaimsErr(e.message));
    api.appointments(profile.id).then(setAppts).catch(() => setAppts([]));
  }, [profile.id]);

  return (
    <div className="space-y-6">
      {appts.length > 0 && (
        <section className="card" aria-labelledby="ap-h">
          <h2 id="ap-h" className="h2">Upcoming adjuster appointments</h2>
          <ul className="mt-2 divide-y divide-slate-100 text-sm">
            {appts.map((a) => (
              <li key={a.id} className="flex flex-wrap justify-between gap-2 py-2">
                <span><span className="font-medium">{slotLabel(a.slot_start)}</span> with {a.adjuster_name} · {a.mode === "onsite" ? "On-site inspection" : a.mode === "video" ? "Video call" : a.mode === "audio" ? "Phone call" : "Chat"}</span>
                <span className="font-mono text-xs text-slate-500">{a.reference}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section aria-labelledby="pol-h">
        <h2 id="pol-h" className="h2 mb-3">Your policies and insured assets</h2>
        {profile.policies.length === 0 ? (
          <div className="card text-sm text-slate-600">
            <p className="font-medium text-slate-800">No policies linked to this profile yet.</p>
            <p className="mt-1">In this demo, policies come from the insurer. Create a new profile with "Attach sample policies" ticked to try the claim flow.</p>
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {profile.policies.map((p) => <PolicyCard key={p.id} policy={p} onStartClaim={onStartClaim} onFocus={onFocusPolicy} />)}
          </div>
        )}
      </section>

      <section aria-labelledby="cl-h" className="card">
        <h2 id="cl-h" className="h2">Your claims</h2>
        {claimsErr && <div className="mt-3"><Alert tone="error" title="Couldn't load claims">{claimsErr}</Alert></div>}
        {!claims && !claimsErr && <div className="mt-3"><Spinner label="Loading claims…" /></div>}
        {claims?.length === 0 && <p className="mt-2 text-sm text-slate-600">No claims yet. When something happens, start a claim from the insured asset above.</p>}
        {claims && claims.length > 0 && (
          <ul className="mt-3 divide-y divide-slate-100" data-testid="claims-list">
            {claims.map((c) => (
              <li key={c.id}>
                <button onClick={() => onOpenClaim(c.id)} className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 py-3 text-left hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600">
                  <span className="font-mono text-sm">{c.claim_number}</span>
                  <span className="flex-1 text-sm">{c.category_label} · {c.asset_name}</span>
                  <span className="text-xs text-slate-500">Submitted {fmtDate(c.created_at)}</span>
                  <StatusBadge status={c.status} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function PolicyCard({ policy, onStartClaim, onFocus }: { policy: PolicySummary; onStartClaim: Props["onStartClaim"]; onFocus: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<PolicyDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) onFocus(policy.id);
    if (next && !detail) api.policy(policy.id).then(setDetail).catch((e: ApiError) => setErr(e.message));
  }

  return (
    <article className="card flex flex-col" aria-labelledby={`p-${policy.id}`} data-testid={`policy-${policy.policy_type}`}>
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 id={`p-${policy.id}`} className="font-semibold">{policy.product_name}</h3>
          <p className="text-xs text-slate-500">
            <span className="font-mono">{policy.policy_number}</span> · {fmtDate(policy.start_date)} – {fmtDate(policy.end_date)}
          </p>
        </div>
        <StatusBadge status={policy.status} />
      </header>
      {policy.summary && <p className="mt-2 text-sm text-slate-600">{policy.summary}</p>}
      <InsurerBlock insurer={policy.insurer} />
      {!policy.wording_available && (
        <div className="mt-3"><Alert tone="warn">Policy wording isn't loaded for this policy. The assistant can't give coverage guidance, so an adjuster will review any claim.</Alert></div>
      )}

      {policy.assets.map((a) => (
        <div key={a.id} className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Insured {a.asset_type}</p>
          <p className="mt-0.5 font-medium"><span aria-hidden>{assetIcon(a.asset_type)} </span>{a.name}</p>
          <dl className="mt-1 grid grid-cols-2 gap-x-3 text-xs text-slate-600">
            {Object.entries(a.details).map(([k, v]) => (<div key={k}><dt className="inline font-medium">{k}: </dt><dd className="inline">{v}</dd></div>))}
          </dl>
          <button className="btn-primary mt-3 w-full sm:w-auto" onClick={() => onStartClaim(policy.id, a.id)} data-testid={`start-claim-${policy.policy_type}`}>
            Get help with this {a.asset_type}
          </button>
        </div>
      ))}

      <button className="btn-link mt-4 self-start" aria-expanded={open} onClick={toggle}>
        {open ? "Hide policy details" : "View coverage, deductibles & exclusions"}
      </button>
      {open && (
        <div className="mt-3 space-y-4 text-sm">
          {err && <Alert tone="error">{err}</Alert>}
          {!detail && !err && <Spinner label="Loading policy…" />}
          {detail && <PolicyDetails d={detail} />}
        </div>
      )}
    </article>
  );
}

export function InsurerBlock({ insurer }: { insurer: Insurer }) {
  return (
    <div className="mt-3 rounded-lg border-l-4 bg-white p-3 text-xs ring-1 ring-slate-200" style={{ borderLeftColor: insurer.brand_color }} data-testid="insurer-block">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">Your insurer</p>
      <p className="font-semibold text-slate-900">{insurer.name}</p>
      <div className="mt-1 grid gap-x-3 gap-y-0.5 text-slate-600 sm:grid-cols-2">
        <span>📞 Claims: {insurer.claims_phone}</span>
        <span>✉️ {insurer.claims_email}</span>
        <span>🕘 {insurer.claims_hours}</span>
        <span>📍 {insurer.address}</span>
      </div>
    </div>
  );
}

function PolicyDetails({ d }: { d: PolicyDetail }) {
  return (
    <>
      <p className="text-xs text-slate-500"><SourceTag source="policy" /> {d.insurer_label}. Fictional wording for demo purposes.</p>
      {d.coverages.length === 0 ? (
        <Alert tone="warn">No coverage wording is available for this policy in the demo.</Alert>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Coverages</caption>
            <thead className="text-xs uppercase text-slate-500">
              <tr><th className="py-1 pr-3">Cover</th><th className="py-1 pr-3">Limit</th><th className="py-1">Deductible</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100 align-top">
              {d.coverages.map((c) => (
                <tr key={c.code}>
                  <td className="py-2 pr-3"><p className="font-medium">{c.name}</p><p className="text-xs text-slate-600">{c.description}</p></td>
                  <td className="py-2 pr-3 text-xs">{c.limit_note ?? money(c.limit_amount)}</td>
                  <td className="py-2 text-xs">{money(c.deductible_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {d.exclusions.length > 0 && (
        <div>
          <h4 className="font-medium">Exclusions (what's not covered)</h4>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-700">{d.exclusions.map((e) => <li key={e.code}>{e.text}</li>)}</ul>
        </div>
      )}
      {d.conditions.length > 0 && (
        <div>
          <h4 className="font-medium">Claim conditions (what you need to do)</h4>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-700">{d.conditions.map((c) => <li key={c.code}>{c.text}</li>)}</ul>
        </div>
      )}
    </>
  );
}
