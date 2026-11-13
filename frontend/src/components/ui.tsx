import type { ReactNode } from "react";

export function Avatar({ name, url, size = 48 }: { name: string; url?: string | null; size?: number }) {
  const initials = name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  if (url) return <img src={url} alt={`Profile photo of ${name}`} width={size} height={size} className="rounded-full object-cover" />;
  return (
    <span role="img" aria-label={`Profile placeholder for ${name}`} style={{ width: size, height: size, fontSize: size / 2.6 }}
      className="inline-flex shrink-0 items-center justify-center rounded-full bg-brand-100 font-semibold text-brand-700">
      {initials}
    </span>
  );
}

type Tone = "info" | "warn" | "error" | "success";
const toneCls: Record<Tone, string> = {
  info: "border-sky-200 bg-sky-50 text-sky-900",
  warn: "border-amber-300 bg-amber-50 text-amber-900",
  error: "border-red-300 bg-red-50 text-red-900",
  success: "border-emerald-300 bg-emerald-50 text-emerald-900",
};
export function Alert({ tone = "info", title, children }: { tone?: Tone; title?: string; children?: ReactNode }) {
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`rounded-lg border px-4 py-3 text-sm ${toneCls[tone]}`}>
      {title && <p className="font-semibold">{title}</p>}
      {children && <div className={title ? "mt-1" : ""}>{children}</div>}
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-slate-600">
      <span aria-hidden className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" />
      {label}
    </span>
  );
}

// Provenance labels: distinguishes policy facts, user-provided details and AI suggestions.
export type Source = "policy" | "user" | "ai" | "system";
const srcCls: Record<Source, [string, string]> = {
  policy: ["bg-slate-800 text-white", "Policy wording"],
  user: ["bg-sky-100 text-sky-800", "You provided"],
  ai: ["bg-violet-100 text-violet-800", "AI suggestion"],
  system: ["bg-slate-100 text-slate-700", "System"],
};
export function SourceTag({ source }: { source: Source }) {
  const [cls, label] = srcCls[source];
  return <span className={`badge ${cls}`}>{label}</span>;
}

export const money = (n?: number | null) => (n == null ? "n/a" : `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`);

const STATUS: Record<string, [string, string]> = {
  submitted: ["Submitted", "bg-sky-100 text-sky-800"],
  in_review: ["In review", "bg-amber-100 text-amber-800"],
  info_requested: ["Info requested", "bg-orange-100 text-orange-800"],
  closed: ["Closed", "bg-slate-200 text-slate-700"],
  active: ["Active", "bg-emerald-100 text-emerald-800"],
  pending: ["Pending", "bg-amber-100 text-amber-800"],
};
export function StatusBadge({ status }: { status: string }) {
  const [label, cls] = STATUS[status] ?? [status, "bg-slate-100 text-slate-700"];
  return <span className={`badge ${cls}`}>{label}</span>;
}

export const fmtDate = (iso?: string | null) =>
  iso ? new Date(iso.length === 10 ? iso + "T00:00:00" : iso).toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" }) : "—";
export const fmtDateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-US", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

export const assetIcon = (t: string) => (t === "vehicle" ? "🚗" : t === "property" ? "🏠" : "💻");
