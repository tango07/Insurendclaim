import { useEffect, useState } from "react";
import { api, ApiError, type Claim } from "../api";
import { AppointmentCard } from "./ChatAssistant";
import { Alert, fmtDate, fmtDateTime, SourceTag, Spinner, StatusBadge } from "./ui";

interface Props { claimId: string; justSubmitted: boolean; onBack: () => void; onSpeakAdjuster: (c: Claim) => void }

export default function ClaimDetail({ claimId, justSubmitted, onBack, onSpeakAdjuster }: Props) {
  const [claim, setClaim] = useState<Claim | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.claim(claimId).then(setClaim).catch((e: ApiError) => setErr(e.message));
  }, [claimId]);

  if (err) return <Alert tone="error" title="Couldn't load claim">{err}</Alert>;
  if (!claim) return <Spinner label="Loading claim…" />;

  return (
    <div className="space-y-6">
      <button className="btn-link" onClick={onBack}>← Back to policies and claims</button>
      {justSubmitted && (
        <Alert tone="success" title="Claim submitted">
          Your claim number is <span className="font-mono font-semibold" data-testid="claim-number">{claim.claim_number}</span>. Keep it for reference.
          This is a demo, so no real claim has been filed.
        </Alert>
      )}

      <section className="card" aria-labelledby="cd-h">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 id="cd-h" className="h2">{claim.category_label}: {claim.asset_name}</h2>
            <p className="text-sm text-slate-600"><span className="font-mono">{claim.claim_number}</span> · Policy <span className="font-mono">{claim.policy_number}</span></p>
          </div>
          <span data-testid="claim-status"><StatusBadge status={claim.status} /></span>
        </div>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
          <div><dt className="text-slate-500">Incident date</dt><dd>{fmtDate(claim.incident_date)}</dd></div>
          <div><dt className="text-slate-500">Location</dt><dd>{claim.incident_location ?? "—"}</dd></div>
          <div><dt className="text-slate-500">Submitted</dt><dd>{fmtDateTime(claim.created_at)}</dd></div>
        </dl>
        <div className="mt-4 space-y-3 text-sm">
          <div><p className="mb-1 flex items-center gap-2 font-medium">Summary <span className="text-xs font-normal text-slate-500">(reviewed by you)</span></p><p>{claim.summary}</p></div>
          <div><p className="mb-1 flex items-center gap-2 font-medium">Your description <SourceTag source="user" /></p><p className="text-slate-700">{claim.description}</p></div>
          {claim.attachments.length > 0 && (
            <div><p className="mb-1 font-medium">Attachments ({claim.attachments.length})</p>
              <ul className="list-disc pl-5 text-slate-700">{claim.attachments.map((a) => <li key={a.id}>{a.original_filename}</li>)}</ul></div>
          )}
        </div>
      </section>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="card" aria-labelledby="tl-h">
          <h3 id="tl-h" className="h2">Timeline</h3>
          <ol className="mt-4 space-y-4 border-l-2 border-slate-200 pl-5" data-testid="timeline">
            {claim.events.map((e, i) => (
              <li key={i} className="relative">
                <span aria-hidden className="absolute -left-[27px] top-1 h-3 w-3 rounded-full bg-brand-600 ring-4 ring-white" />
                <p className="text-sm font-medium">{e.title}</p>
                <p className="text-xs text-slate-500">{fmtDateTime(e.created_at)} · {e.actor}</p>
                {e.detail && <p className="text-sm text-slate-700">{e.detail}</p>}
              </li>
            ))}
            {claim.upcoming.map((u) => (
              <li key={u} className="relative">
                <span aria-hidden className="absolute -left-[27px] top-1 h-3 w-3 rounded-full border-2 border-slate-300 bg-white ring-4 ring-white" />
                <p className="text-sm text-slate-500">{u}</p>
                <p className="text-xs text-slate-400">Expected step (typical, not guaranteed)</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="card space-y-4" aria-labelledby="nx-h">
          <h3 id="nx-h" className="h2">What to do next</h3>
          {claim.next_steps.length > 0 ? (
            <ol className="list-decimal space-y-1 pl-5 text-sm">{claim.next_steps.map((s) => <li key={s}>{s}</li>)}</ol>
          ) : <p className="text-sm text-slate-600">Wait for the claims handler to contact you.</p>}
          {claim.documents_to_collect.length > 0 && (
            <div>
              <h4 className="text-sm font-medium">Documents to have ready</h4>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">{claim.documents_to_collect.map((d) => <li key={d}>{d}</li>)}</ul>
            </div>
          )}
          <p className="text-xs text-slate-500">Steps and documents were suggested by the assistant and confirmed by you. The adjuster may ask for different items.</p>
          <button className="btn-primary" onClick={() => onSpeakAdjuster(claim)} data-testid="claim-speak-adjuster">Speak with an adjuster about this claim</button>
        </section>
      </div>

      {claim.appointments.length > 0 && (
        <section className="space-y-3" aria-label="Adjuster appointments">
          <h3 className="h2">Adjuster appointments</h3>
          {claim.appointments.map((a) => <AppointmentCard key={a.id} appt={a} />)}
        </section>
      )}
    </div>
  );
}
