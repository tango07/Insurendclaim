import { useState } from "react";
import { api, ApiError, type ProfileDetail } from "../api";
import { Alert } from "./ui";

interface Props { onAuthenticated: (token: string, profile: ProfileDetail) => void }

export default function LoginPage({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fullName, setFullName] = useState("");
  const [city, setCity] = useState("");
  const [withSample, setWithSample] = useState(true);
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!username.trim() || !password) return setError("Please enter your username and password.");
    if (mode === "register") {
      if (fullName.trim().length < 2) return setError("Please enter your full name.");
      const un = username.trim();
      if (un.length < 3) return setError("Username must be at least 3 characters.");
      if (/\s/.test(un)) return setError("Username can't contain spaces. Try e.g. akshay.kumar.");
      const bad = [...new Set(un.replace(/[A-Za-z0-9._@+-]/g, ""))];
      if (bad.length) return setError(`Username can't contain: ${bad.join(" ")}. Use letters, numbers, . _ - @ or +.`);
      if (!/[A-Za-z]/.test(password) || !/\d/.test(password) || !/[^A-Za-z0-9\s]/.test(password)) return setError("Password must contain a letter, a number and a special symbol (e.g. @ # $ !).");
      if (password !== confirm) return setError("Passwords don't match.");
    }
    setBusy(true);
    try {
      const r = mode === "login"
        ? await api.login(username.trim(), password)
        : await api.register({ username: username.trim(), password, full_name: fullName.trim(), city: city.trim() || null, with_sample_policies: withSample });
      onAuthenticated(r.token, r.profile);
    } catch (err) {
      setError((err as ApiError).message);
      setBusy(false);
    }
  }

  const switchTo = (m: "login" | "register") => { setMode(m); setError(null); setPassword(""); setConfirm(""); };

  return (
    <div className="mx-auto grid max-w-4xl items-stretch gap-6 md:grid-cols-2">
      <section className="hidden flex-col justify-between rounded-2xl bg-brand-900 p-8 text-white md:flex">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-brand-100">EPAM powered</p>
          <p className="text-3xl font-bold" aria-label="EPAM powered InsureNdClaim">InsureNd<span className="text-brand-100">Claim</span></p>
          <p className="mt-3 text-brand-100">Understand your cover, start a claim in a conversation, and book an adjuster, all in one place.</p>
        </div>
        <ul className="space-y-2 text-sm text-brand-100">
          <li>✓ See your policies from every insurer</li>
          <li>✓ AI-guided claim intake grounded in your policy wording</li>
          <li>✓ Speak with a specialist adjuster by phone, video or on site</li>
        </ul>
      </section>

      <section className="card" aria-labelledby="auth-h">
        <div className="mb-4 flex rounded-lg bg-slate-100 p-1 text-sm" role="tablist">
          {(["login", "register"] as const).map((m) => (
            <button key={m} role="tab" aria-selected={mode === m} onClick={() => switchTo(m)} data-testid={`tab-${m}`}
              className={`flex-1 rounded-md py-1.5 font-medium ${mode === m ? "bg-white shadow-sm" : "text-slate-600"}`}>
              {m === "login" ? "Log in" : "Create account"}
            </button>
          ))}
        </div>
        <h2 id="auth-h" className="h2">{mode === "login" ? "Welcome back" : "Create your account"}</h2>

        <form onSubmit={submit} className="mt-4 space-y-3" noValidate>
          {mode === "register" && (
            <>
              <div><label htmlFor="r-name" className="label">Full name</label>
                <input id="r-name" className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" maxLength={80} /></div>
              <div><label htmlFor="r-city" className="label">City <span className="font-normal text-slate-500">(optional)</span></label>
                <input id="r-city" className="input" value={city} onChange={(e) => setCity(e.target.value)} maxLength={80} /></div>
            </>
          )}
          <div><label htmlFor="u" className="label">Username</label>
            <input id="u" className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" maxLength={50} data-testid="username" />
            {mode === "register" && <p className="mt-1 text-xs text-slate-500">3–50 characters: letters, numbers, . _ - @ + (an email address works).</p>}</div>
          <div>
            <label htmlFor="pw" className="label">Password</label>
            <div className="flex gap-2">
              <input id="pw" type={showPw ? "text" : "password"} className="input" value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"} maxLength={128} data-testid="password" />
              <button type="button" className="btn-secondary px-3" onClick={() => setShowPw(!showPw)} aria-pressed={showPw}>{showPw ? "Hide" : "Show"}</button>
            </div>
            {mode === "register" && <p className="mt-1 text-xs text-slate-500">Must contain a letter, a number and a special symbol (e.g. @ # $ !).</p>}
          </div>
          {mode === "register" && (
            <>
              <div><label htmlFor="pw2" className="label">Confirm password</label>
                <input id="pw2" type={showPw ? "text" : "password"} className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" /></div>
              <label className="flex items-start gap-2 text-sm">
                <input type="checkbox" className="mt-0.5" checked={withSample} onChange={(e) => setWithSample(e.target.checked)} />
                Start with sample car and home policies (demo)
              </label>
            </>
          )}
          {error && <Alert tone="error">{error}</Alert>}
          <button className="btn-primary w-full" disabled={busy} data-testid="auth-submit">
            {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>

        {mode === "login" && (
          <div className="mt-5 rounded-lg border border-dashed border-slate-300 p-3 text-xs text-slate-600">
            <p className="font-medium text-slate-700">Demo accounts (fictional)</p>
            <p className="mt-1">
              <button className="btn-link text-xs" onClick={() => { setUsername("daniel"); setPassword("Daniel@123"); }} data-testid="demo-daniel">daniel / Daniel@123</button>
              {"  ·  "}
              <button className="btn-link text-xs" onClick={() => { setUsername("priya"); setPassword("Priya@123"); }}>priya / Priya@123</button>
            </p>
          </div>
        )}
        <p className="mt-3 text-[11px] text-slate-500">Demo app. Don't reuse a real password.</p>
      </section>
    </div>
  );
}
