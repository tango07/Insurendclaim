import { useCallback, useEffect, useState } from "react";
import { api, ApiError, session, type Claim, type Health, type ProfileDetail } from "./api";
import AddPolicyForm from "./components/AddPolicyForm";
import AdjusterDirectory from "./components/AdjusterDirectory";
import AssistantPanel from "./components/AssistantPanel";
import ChatAssistant from "./components/ChatAssistant";
import ClaimDetail from "./components/ClaimDetail";
import Dashboard from "./components/Dashboard";
import LoginPage from "./components/LoginPage";
import { Alert, Avatar, Spinner } from "./components/ui";

type View =
  | { name: "profiles" }
  | { name: "dashboard" }
  | { name: "chat"; key: number; policyId?: string; assetId?: string; claimId?: string | null; startWith?: "adjuster" | "claim" }
  | { name: "claim"; claimId: string; justSubmitted: boolean };

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthErr, setHealthErr] = useState<string | null>(null);
  const [profile, setProfile] = useState<ProfileDetail | null>(null);
  const [profileErr, setProfileErr] = useState<string | null>(null);
  const [view, setView] = useState<View>({ name: "profiles" });
  const [focusPolicy, setFocusPolicy] = useState<string | undefined>();
  const [claimForAssistant, setClaimForAssistant] = useState<Claim | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(!!session.get());
  const [adding, setAdding] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [dashKey, setDashKey] = useState(0);

  const loggedOut = useCallback((msg?: string) => {
    session.set(null);
    setProfile(null); setUsername(null); setView({ name: "profiles" });
    if (msg) setProfileErr(msg);
  }, []);

  useEffect(() => {
    api.health().then(setHealth).catch((e: ApiError) => setHealthErr(e.message));
    session.onUnauthorized(() => loggedOut("Your session has expired. Please log in again."));
    if (session.get()) {
      api.me().then((r) => { setProfile(r.profile); setUsername(r.username); setView({ name: "dashboard" }); })
        .catch(() => session.set(null)).finally(() => setRestoring(false));
    }
  }, [loggedOut]);

  function onAuthenticated(token: string, p: ProfileDetail, user?: string) {
    session.set(token);
    setProfileErr(null);
    setProfile(p); setUsername(user ?? null); setView({ name: "dashboard" });
    if (!user) api.me().then((r) => setUsername(r.username)).catch(() => {});
  }

  async function logout() {
    try { await api.logout(); } catch { /* ignore */ }
    loggedOut();
  }

  useEffect(() => {
    if (view.name === "claim") api.claim(view.claimId).then(setClaimForAssistant).catch(() => setClaimForAssistant(null));
    else setClaimForAssistant(null);
  }, [view]);

  const openChat = (opts: Omit<Extract<View, { name: "chat" }>, "name" | "key">) => setView({ name: "chat", key: Date.now(), ...opts });

  return (
    <div className="min-h-screen pb-24">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:rounded focus:bg-white focus:p-2">Skip to content</a>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div>
            <h1 className="text-xl font-bold text-brand-900" aria-label="EPAM powered InsureNdClaim">
              <span className="mr-1.5 align-middle text-[11px] font-semibold uppercase tracking-wider text-slate-500">EPAM powered</span>
              InsureNd<span className="text-brand-600">Claim</span>
            </h1>
            <p className="text-xs text-slate-500">Claims assistance demo · fictional insurers and sample data</p>
          </div>
          <div className="flex items-center gap-3">
            {health && (
              <span className={`badge ${health.ai_mode === "mock" ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-800"}`} data-testid="ai-mode">
                AI: {health.ai_mode === "mock" ? "Mock mode (no API key)" : health.ai_mode}
              </span>
            )}
            {profile && view.name !== "profiles" && (
              <div className="flex items-center gap-2">
                <Avatar name={profile.full_name} url={profile.photo_url} size={36} />
                <div className="text-sm">
                  <p className="font-medium" data-testid="current-profile">{profile.full_name}</p>
                  <p className="text-xs text-slate-500">@{username ?? "…"} · <button className="btn-link text-xs" onClick={logout} data-testid="logout">Log out</button></p>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto max-w-6xl px-4 py-6">
        {healthErr && <div className="mb-4"><Alert tone="error" title="Backend not reachable">{healthErr}</Alert></div>}
        {profileErr && <div className="mb-4"><Alert tone="error">{profileErr}</Alert></div>}

        {view.name === "profiles" && (restoring ? <Spinner label="Restoring your session…" /> : <LoginPage onAuthenticated={(t, p) => onAuthenticated(t, p)} />)}
        {view.name !== "profiles" && !profile && <Spinner label="Loading profile…" />}

        {profile && view.name === "dashboard" && (
          <>
            <div className="mb-6 flex flex-wrap items-center gap-4 rounded-2xl bg-brand-900 p-5 text-white">
              <Avatar name={profile.full_name} url={profile.photo_url} size={64} />
              <div className="flex-1">
                <h2 className="text-2xl font-semibold">Hi, {profile.full_name.split(" ")[0]}</h2>
                <p className="text-sm text-brand-100">Had an incident? Chat with ClaimAssist. It'll ask a few questions, prepare your claim, and can book an adjuster.</p>
              </div>
              <button className="btn bg-white text-brand-900 hover:bg-brand-50" onClick={() => openChat({})} data-testid="open-chat">Chat with ClaimAssist</button>
            </div>
            {notice && <div className="mb-4"><Alert tone="success">{notice}</Alert></div>}
            {adding ? (
              <div className="mb-6"><AddPolicyForm onCancel={() => setAdding(false)}
                onAdded={(p, n) => { setProfile(p); setAdding(false); setDashKey((k) => k + 1); setNotice(`Policy ${n} added to your profile.`); }} /></div>
            ) : (
              <div className="mb-4 flex justify-end"><button className="btn-secondary" onClick={() => { setAdding(true); setNotice(null); }} data-testid="add-policy">+ Add a policy</button></div>
            )}
            <Dashboard key={dashKey} profile={profile} onFocusPolicy={setFocusPolicy}
              onStartClaim={(policyId, assetId) => { setFocusPolicy(policyId); openChat({ policyId, assetId }); }}
              onOpenClaim={(claimId) => setView({ name: "claim", claimId, justSubmitted: false })} />
            <div className="mt-6"><AdjusterDirectory refreshKey={dashKey} onBook={() => openChat({})} /></div>
          </>
        )}

        {profile && view.name === "chat" && (
          <ChatAssistant key={view.key} profile={profile} initialPolicyId={view.policyId} initialAssetId={view.assetId}
            linkedClaimId={view.claimId} startWith={view.startWith}
            maxMb={health?.max_upload_mb ?? 10} maxFiles={health?.max_files ?? 10} aiMode={health?.ai_mode}
            onOpenClaim={(claimId) => setView({ name: "claim", claimId, justSubmitted: true })}
            onBack={() => setView({ name: "dashboard" })} />
        )}

        {profile && view.name === "claim" && (
          <ClaimDetail claimId={view.claimId} justSubmitted={view.justSubmitted} onBack={() => setView({ name: "dashboard" })}
            onSpeakAdjuster={(c) => openChat({ policyId: c.policy_id, assetId: c.asset_id, claimId: c.id, startWith: "adjuster" })} />
        )}
      </main>

      {profile && (view.name === "dashboard" || view.name === "claim") && (
        <AssistantPanel key={`${profile.id}-${claimForAssistant?.id ?? focusPolicy ?? ""}`} policies={profile.policies}
          defaultPolicyId={claimForAssistant?.policy_id ?? focusPolicy} claimId={claimForAssistant?.id} />
      )}
    </div>
  );
}
