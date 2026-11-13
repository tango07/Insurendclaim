import { useState } from "react";
import { api, ApiError, type PolicySummary } from "../api";
import { Spinner } from "./ui";

interface Msg { role: "user" | "assistant"; text: string; sources?: string[]; error?: boolean }

const SUGGESTIONS = ["What is my deductible?", "Is flood covered?", "What do I need to do after a theft?", "What happens next with my claim?"];

export default function AssistantPanel({ policies, defaultPolicyId, claimId }: { policies: PolicySummary[]; defaultPolicyId?: string; claimId?: string | null }) {
  const [open, setOpen] = useState(false);
  const [policyId, setPolicyId] = useState(defaultPolicyId ?? policies[0]?.id ?? "");
  const [q, setQ] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);

  if (!policies.length) return null;

  async function ask(question: string) {
    if (question.trim().length < 3 || busy) return;
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setQ("");
    setBusy(true);
    try {
      const a = await api.ask(policyId, question, claimId);
      setMsgs((m) => [...m, { role: "assistant", text: a.answer, sources: a.sources }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", text: (e as ApiError).message, error: true }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed bottom-4 right-4 z-20 w-[calc(100%-2rem)] max-w-sm">
      {open ? (
        <section className="card flex max-h-[70vh] flex-col p-0" aria-label="Policy assistant">
          <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <div><p className="font-semibold">Policy assistant</p><p className="text-xs text-slate-500">Answers from sample policy data only</p></div>
            <button className="btn-link" onClick={() => setOpen(false)} aria-label="Close assistant">Close</button>
          </header>
          <div className="px-4 pt-3">
            <label htmlFor="as-pol" className="label text-xs">Ask about</label>
            <select id="as-pol" className="input py-1" value={policyId} onChange={(e) => setPolicyId(e.target.value)}>
              {policies.map((p) => <option key={p.id} value={p.id}>{p.product_name}</option>)}
            </select>
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm" aria-live="polite">
            {msgs.length === 0 && (
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.filter((s) => claimId || !s.includes("claim")).map((s) => (
                  <button key={s} className="badge bg-slate-100 text-slate-700 hover:bg-slate-200" onClick={() => ask(s)}>{s}</button>
                ))}
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={m.role === "user" ? "ml-8 rounded-lg bg-brand-50 p-2" : `mr-4 rounded-lg p-2 ${m.error ? "bg-red-50 text-red-900" : "bg-slate-100"}`}>
                <p>{m.text}</p>
                {m.sources && m.sources.length > 0 && <p className="mt-1 text-xs text-slate-500">Sources: {m.sources.join(", ")}</p>}
              </div>
            ))}
            {busy && <Spinner label="Thinking…" />}
          </div>
          <form className="flex gap-2 border-t border-slate-200 p-3" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
            <label htmlFor="as-q" className="sr-only">Your question</label>
            <input id="as-q" className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about your cover…" maxLength={500} />
            <button className="btn-primary" disabled={busy || q.trim().length < 3}>Ask</button>
          </form>
          <p className="px-4 pb-3 text-[11px] text-slate-500">Guidance only. Not a coverage decision.</p>
        </section>
      ) : (
        <button className="btn-primary float-right shadow-lg" onClick={() => setOpen(true)}>Ask about my policy</button>
      )}
    </div>
  );
}
