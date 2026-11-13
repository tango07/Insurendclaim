import { useEffect, useState } from "react";
import { api, ApiError, type Adjuster } from "../api";
import { slotLabel } from "./ChatAssistant";
import { Alert, Avatar, Spinner } from "./ui";

/** Adjusters (from the database) for every insurer the user holds a policy with. */
export default function AdjusterDirectory({ refreshKey, onBook }: { refreshKey: number; onBook: () => void }) {
  const [list, setList] = useState<Adjuster[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.myAdjusters().then(setList).catch((e: ApiError) => setErr(e.message)); }, [refreshKey]);

  const byInsurer = (list ?? []).reduce<Record<string, Adjuster[]>>((acc, a) => ((acc[a.insurer_name] ??= []).push(a), acc), {});
  return (
    <section className="card" aria-labelledby="adj-h" data-testid="adjuster-directory">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="adj-h" className="h2">Your adjusters</h2>
        <button className="btn-secondary" onClick={onBook}>Book via ClaimAssist</button>
      </div>
      <p className="mt-1 text-sm text-slate-600">Specialist adjusters at your insurers (fictional).</p>
      {err && <div className="mt-3"><Alert tone="error">{err}</Alert></div>}
      {!list && !err && <div className="mt-3"><Spinner label="Loading adjusters…" /></div>}
      {list?.length === 0 && <p className="mt-3 text-sm text-slate-600">Add a policy to see its adjusters.</p>}
      <div className="mt-3 space-y-4">
        {Object.entries(byInsurer).map(([ins, adjs]) => (
          <div key={ins}>
            <h3 className="text-sm font-semibold text-slate-700">{ins}</h3>
            <ul className="mt-2 grid gap-3 md:grid-cols-2">
              {adjs.map((a) => (
                <li key={a.id} className="flex gap-3 rounded-lg border border-slate-200 p-3 text-sm">
                  <Avatar name={a.full_name} size={40} />
                  <div className="min-w-0">
                    <p className="font-medium">{a.full_name} <span className="badge bg-slate-100 capitalize text-slate-700">{a.specialization}</span></p>
                    <p className="text-xs text-slate-600">📍 {a.office_location}</p>
                    <p className="text-xs text-slate-600">📞 {a.phone} · ✉️ {a.email}</p>
                    <p className="text-xs text-slate-500">{a.years_experience} yrs · {a.languages}</p>
                    <p className="mt-1 text-xs"><span className="font-medium">Next available:</span> {a.slots[0] ? slotLabel(a.slots[0]) : "none this week"}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
