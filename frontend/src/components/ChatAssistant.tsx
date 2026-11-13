import { useEffect, useRef, useState } from "react";
import {
  api, ApiError, type Adjuster, type Appointment, type Attachment, type ChatAction, type Claim, type Guidance,
  type ProfileDetail, type RepairPartner,
} from "../api";
import ClaimReview from "./ClaimReview";
import { assetIcon, Avatar, fmtDate } from "./ui";

/* ClaimAssist: a chat-first front door. Routing is a small state machine; AI is used for
   follow-up phrasing, the claim summary, and policy Q&A (each falls back to rules). */

type Stage = "pick_asset" | "menu" | "claim_describe" | "claim_followup" | "claim_review" | "question"
  | "adj_pick" | "adj_slot" | "adj_contact" | "adj_mode" | "adj_location";

type Widget =
  | { kind: "assets" }
  | { kind: "actions"; actions: ChatAction[] }
  | { kind: "followup"; key: string; why?: string | null }
  | { kind: "review"; guidance: Guidance | null; description: string; attachments: Attachment[]; answered: string[] }
  | { kind: "claim_done"; claim: Claim }
  | { kind: "adjusters"; list: Adjuster[] }
  | { kind: "slots"; adjuster: Adjuster }
  | { kind: "contact" }
  | { kind: "modes"; adjuster: Adjuster }
  | { kind: "location" }
  | { kind: "appointment"; appt: Appointment }
  | { kind: "garages"; list: RepairPartner[] }
  | { kind: "examples" };

interface Msg { id: number; from: "bot" | "user"; text?: string; widget?: Widget; active: boolean; sources?: string[] }

const MODE_LABEL: Record<string, string> = { audio: "Phone call", video: "Video call (Teams/Zoom)", onsite: "On-site inspection", chat: "Chat" };
const MODE_HINT: Record<string, string> = { audio: "Adjuster calls your number", video: "Show the damage on camera", onsite: "Adjuster comes to you", chat: "Message in this portal" };
const SKIP = /^(skip|later|don'?t know|dont know|not sure|no idea|n\/?a|pass)\.?$/i;
const ALLOWED_EXT = [".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf", ".txt"];
const EXAMPLES: Record<string, string> = {
  auto: "My car was hit in a parking lot while I was shopping. The rear bumper is dented and the left tail light is cracked.",
  home: "Water is dripping through my kitchen ceiling. The neighbour upstairs says a pipe under their sink burst this morning.",
  gadget: "I dropped my work laptop at home and the screen cracked badly. It still turns on.",
};

export const slotLabel = (s: string) => {
  const d = new Date(s);
  return d.toLocaleString("en-US", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
};

interface Props {
  profile: ProfileDetail;
  initialPolicyId?: string;
  initialAssetId?: string;
  linkedClaimId?: string | null;
  startWith?: "adjuster" | "claim";
  maxMb: number;
  maxFiles: number;
  aiMode?: string;
  onOpenClaim: (claimId: string) => void;
  onBack: () => void;
}

export default function ChatAssistant({ profile, initialPolicyId, initialAssetId, linkedClaimId, startWith, maxMb, maxFiles, aiMode = "mock", onOpenClaim, onBack }: Props) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [stage, setStage] = useState<Stage>("menu");
  const [policyId, setPolicyId] = useState(initialPolicyId);
  const [assetId, setAssetId] = useState(initialAssetId);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  // claim intake
  const [pendingIncident, setPendingIncident] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [asked, setAsked] = useState<string[]>([]);
  const [answered, setAnswered] = useState<string[]>([]);
  const [currentQ, setCurrentQ] = useState<{ key: string; question: string } | null>(null);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [claim, setClaim] = useState<Claim | null>(null);
  // adjuster booking
  const [adjuster, setAdjuster] = useState<Adjuster | null>(null);
  const [slot, setSlot] = useState<string | null>(null);
  const [contact, setContact] = useState<{ name: string; phone: string } | null>(null);

  const nextId = useRef(1);
  const started = useRef(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const policy = profile.policies.find((p) => p.id === policyId);
  const asset = policy?.assets.find((a) => a.id === assetId);
  const insurer = policy?.insurer.short_name ?? "your insurer";
  const first = profile.full_name.split(" ")[0];
  const claimId = claim?.id ?? linkedClaimId ?? null;

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, busy]);

  function push(...items: Omit<Msg, "id" | "active">[]) {
    setMsgs((prev) => {
      const interactive = items.some((i) => i.widget && i.widget.kind !== "review");
      const base = interactive ? prev.map((m) => (m.widget?.kind === "review" ? m : { ...m, active: false })) : prev;
      return [...base, ...items.map((i) => ({ ...i, id: nextId.current++, active: true }))];
    });
  }
  const bot = (text: string, widget?: Widget, sources?: string[]) => push({ from: "bot", text, widget, sources });
  const user = (text: string) => push({ from: "user", text });
  const deactivate = (id: number) => setMsgs((prev) => prev.map((m) => (m.id === id ? { ...m, active: false } : m)));

  function menuActions(): ChatAction[] {
    return [{ id: "start_claim", label: "Start a claim" }, { id: "speak_adjuster", label: "Speak with an adjuster" },
      { id: "find_garage", label: "Find a partner garage" }, { id: "ask_policy", label: "Ask about my cover" }];
  }

  function welcome(pId: string, aId: string) {
    const p = profile.policies.find((x) => x.id === pId)!;
    const a = p.assets.find((x) => x.id === aId)!;
    bot(`I can help with your ${a.name}. It's covered by ${p.product_name}, insured by ${p.insurer.name}. ` +
      `Tell me what happened in your own words, or choose an option below.`, { kind: "actions", actions: menuActions() });
    setStage("menu");
  }

  // --- start --------------------------------------------------------------------
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (profile.policies.length === 0) {
      bot(`Hi ${first}, I'm ClaimAssist. There are no policies on this profile yet, so I can't start a claim. Please contact your insurer.`);
      return;
    }
    bot(`Hi ${first}, I'm ClaimAssist, your claims helper. I'll guide you step by step. Nothing is sent to your insurer until you confirm.`);
    if (initialPolicyId && initialAssetId) {
      if (startWith === "adjuster") void speakAdjuster(initialPolicyId);
      else welcome(initialPolicyId, initialAssetId);
    } else {
      bot("Which insured item is this about?", { kind: "assets" });
      setStage("pick_asset");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function pickAsset(msgId: number, pId: string, aId: string, name: string) {
    deactivate(msgId);
    user(name);
    setPolicyId(pId);
    setAssetId(aId);
    welcome(pId, aId);
  }

  // --- free text ------------------------------------------------------------------
  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    user(text);
    if (stage === "pick_asset" || !policyId) return bot("Please pick one of the insured items above first.");
    if (stage === "claim_describe") return void beginFollowUps(text);
    if (stage === "claim_followup") return void answerFollowUp(text);
    if (stage === "adj_location") return void book("onsite", text);
    if (stage === "adj_contact") return bot("Please use the form above to share your name and contact number.");
    if (stage === "adj_slot") return bot("Please pick one of the time slots above, or choose another adjuster.");
    if (stage === "question") return void askPolicy(text);
    await routeIntent(text);
  }

  async function routeIntent(text: string) {
    setBusy("Thinking…");
    try {
      const r = await api.intent(policyId!, text);
      if (r.intents.length === 1 && r.intents[0] === "question") return void (await askPolicy(text));
      if (r.looks_like_incident) setPendingIncident(text);
      if (r.auto_action === "speak_adjuster") {
        setBusy(null);
        if (r.looks_like_incident) bot("I'm sorry to hear that. I hope everyone is safe.");
        return void (await speakAdjuster(policyId!));
      }
      bot(r.reply, { kind: "actions", actions: r.actions.length ? r.actions : menuActions() });
      setStage("menu");
    } catch (e) {
      bot(`Sorry, something went wrong: ${(e as ApiError).message}`, { kind: "actions", actions: menuActions() });
    } finally {
      setBusy(null);
    }
  }

  async function askPolicy(q: string) {
    setBusy("Checking your policy…");
    try {
      const a = await api.ask(policyId!, q, claimId);
      bot(a.answer, undefined, a.sources);
    } catch (e) {
      bot(`I couldn't answer that right now (${(e as ApiError).message}). An adjuster can help.`);
    } finally {
      setBusy(null);
    }
  }

  function onAction(msgId: number, a: ChatAction) {
    deactivate(msgId);
    user(a.label);
    if (a.id === "start_claim") startClaim();
    else if (a.id === "speak_adjuster") void speakAdjuster(policyId!);
    else if (a.id === "find_garage") void showGarages();
    else { bot(`Sure. What would you like to know about your ${policy?.product_name}?`); setStage("question"); }
  }

  // --- claim conversation -------------------------------------------------------
  function startClaim() {
    setAsked([]); setAnswered([]); setClaim(null);
    if (pendingIncident) {
      bot(`I'll start from what you told me: "${pendingIncident}". I just need a few more details. You can skip any question.`);
      void beginFollowUps(pendingIncident);
    } else {
      bot("Tell me what happened, in your own words: what was damaged, and how. You can attach photos at any time with the paperclip.", { kind: "examples" });
      setStage("claim_describe");
    }
  }

  async function beginFollowUps(text: string) {
    if (text.length < 15) {
      bot("Could you tell me a little more? A sentence or two is ideal.");
      setStage("claim_describe");
      return;
    }
    setPendingIncident(null);
    setDescription(text);
    await nextQuestion(text, [], [], attachments);
  }

  async function nextQuestion(desc: string, askedNow: string[], answeredNow: string[], atts: Attachment[]) {
    setAsked(askedNow); setAnswered(answeredNow);
    setBusy("Thinking…");
    try {
      const q = await api.followUp({ policy_id: policyId!, asset_id: assetId!, description: desc, asked_keys: askedNow, attachment_ids: atts.map((a) => a.id) });
      setBusy(null);
      if (q.done || !q.key || !q.question) return void (await finishIntake(desc, answeredNow, atts));
      setCurrentQ({ key: q.key, question: q.question });
      bot(q.question, { kind: "followup", key: q.key, why: q.why });
      setStage("claim_followup");
    } catch (e) {
      setBusy(null);
      bot(`I couldn't prepare the next question (${(e as ApiError).message}). Let's go straight to the summary.`);
      await finishIntake(desc, answeredNow, atts);
    }
  }

  async function answerFollowUp(text: string, atts = attachments) {
    if (!currentQ) return;
    const askedNow = [...asked, currentQ.key];
    if (SKIP.test(text)) return void nextQuestion(description, askedNow, answered, atts);
    const desc = `${description}\n- ${currentQ.question.split("?")[0]}? ${text}`;
    setDescription(desc);
    await nextQuestion(desc, askedNow, [...answered, currentQ.key], atts);
  }

  function skipQuestion(msgId: number) {
    deactivate(msgId);
    user("Skip");
    void answerFollowUp("skip");
  }

  async function finishIntake(desc: string, answeredNow: string[], atts: Attachment[]) {
    setCurrentQ(null);
    bot("Thanks, that's everything I need. I'm preparing your claim summary from your policy wording…");
    setBusy("Preparing your claim summary…");
    try {
      const g = await api.suggest({ policy_id: policyId!, asset_id: assetId!, description: desc, attachment_ids: atts.map((a) => a.id), answered_keys: answeredNow });
      bot(`Here's what I've put together. It's a suggestion, so please check it and change anything that isn't right before submitting to ${insurer}.`,
        { kind: "review", guidance: g, description: desc, attachments: atts, answered: answeredNow });
    } catch (e) {
      bot(`I couldn't generate the summary (${(e as ApiError).message}). You can fill it in yourself below.`,
        { kind: "review", guidance: null, description: desc, attachments: atts, answered: answeredNow });
    } finally {
      setBusy(null);
      setStage("claim_review");
    }
  }

  function onSubmitted(c: Claim) {
    setClaim(c);
    bot(`Done. Your claim ${c.claim_number} has been submitted to ${insurer}. Status: Submitted. What would you like to do next?`, { kind: "claim_done", claim: c });
    setStage("menu");
  }

  // --- attachments ------------------------------------------------------------------
  async function addFiles(list: FileList | null) {
    if (!list || !list.length) return;
    const files = Array.from(list);
    if (fileRef.current) fileRef.current.value = "";
    const bad = files.filter((f) => !ALLOWED_EXT.includes(f.name.slice(f.name.lastIndexOf(".")).toLowerCase()) || f.size > maxMb * 1048576 || f.size === 0);
    if (bad.length) return bot(`I can't accept ${bad.map((f) => f.name).join(", ")}. Use JPG, PNG, WEBP, HEIC, PDF or TXT files of up to ${maxMb} MB each.`);
    if (attachments.length + files.length > maxFiles) return bot(`You can attach up to ${maxFiles} files.`);
    setBusy("Uploading…");
    try {
      const up = await api.upload(files);
      const all = [...attachments, ...up];
      setAttachments(all);
      user(`📎 Attached: ${up.map((a) => a.original_filename).join(", ")}`);
      const imgs = up.filter((a) => a.content_type.startsWith("image/")).length;
      bot(`Got ${up.length === 1 ? "it" : `all ${up.length}`}. ${imgs ? (aiMode !== "mock" ? "I'll look at your photos when I prepare the claim summary, and they'll be shared with your adjuster." : "I can't analyse photos in demo mock mode, but they'll go with your claim and be shared with your adjuster.") : "They'll be attached to your claim."}`);
      setBusy(null);
      if (stage === "claim_followup" && currentQ?.key === "photos") await answerFollowUp(`${up.length} file(s) attached`, all);
    } catch (e) {
      setBusy(null);
      bot(`Upload failed: ${(e as ApiError).message}`);
    }
  }

  // --- adjuster journey (slide steps 3–7) ------------------------------------------
  async function speakAdjuster(pId: string) {
    bot("Sure, let me find a suitable adjuster for you.");
    setBusy("Finding adjusters…");
    try {
      const list = await api.adjusters(pId);
      if (!list.length) bot(`There's no adjuster available online for this policy. Please call ${insurer}.`);
      else bot(`These ${list[0].insurer_name.replace(" (fictional)", "")} adjusters specialise in ${list[0].specialization} claims:`, { kind: "adjusters", list });
      setStage("adj_pick");
    } catch (e) {
      bot(`I couldn't load adjusters: ${(e as ApiError).message}`);
    } finally {
      setBusy(null);
    }
  }

  function pickAdjuster(msgId: number, a: Adjuster) {
    deactivate(msgId);
    user(`I'd like ${a.full_name}`);
    setAdjuster(a);
    bot(`Great. You've chosen ${a.full_name} (${a.specialization}, ${a.office_location}). Please choose a time slot.`, { kind: "slots", adjuster: a });
    setStage("adj_slot");
  }

  function pickSlot(msgId: number, s: string) {
    deactivate(msgId);
    user(slotLabel(s));
    setSlot(s);
    bot(`I've noted ${slotLabel(s)} with ${adjuster!.full_name}. Please share your full name and a contact number so the adjuster can reach you.`, { kind: "contact" });
    setStage("adj_contact");
  }

  function submitContact(msgId: number, name: string, phone: string) {
    deactivate(msgId);
    user(`${name}, ${phone}`);
    setContact({ name, phone });
    bot(`Thanks, ${name.split(" ")[0]}. How would you like to meet ${adjuster!.full_name.split(" ")[0]}?`, { kind: "modes", adjuster: adjuster! });
    setStage("adj_mode");
  }

  function pickMode(msgId: number, mode: string) {
    deactivate(msgId);
    user(MODE_LABEL[mode]);
    if (mode === "onsite") {
      bot(`Where should ${adjuster!.full_name.split(" ")[0]} inspect the ${asset?.asset_type === "vehicle" ? "car" : "damage"}? Type an address, or pick one below.`, { kind: "location" });
      setStage("adj_location");
    } else void book(mode, null);
  }

  async function book(mode: string, location: string | null) {
    if (!adjuster || !slot || !contact) return;
    setBusy("Booking your appointment…");
    try {
      const appt = await api.book({
        adjuster_id: adjuster.id, policyholder_id: profile.id, policy_id: policyId!, claim_id: claimId, slot_start: slot, mode,
        contact_name: contact.name, contact_phone: contact.phone, meeting_location: location, attachment_ids: attachments.map((a) => a.id),
      });
      const n = appt.shared_attachments.length;
      bot(`You're booked. ${appt.adjuster_name} has been told to expect you${n ? ` and can already see your ${n} uploaded file${n > 1 ? "s" : ""}` : ""}.`, { kind: "appointment", appt });
      bot("Anything else I can help with?", { kind: "actions", actions: claimId ? menuActions().filter((a) => a.id !== "start_claim") : menuActions() });
      setStage("menu");
    } catch (e) {
      const err = e as ApiError;
      if (err.status === 409) {
        bot(`${err.message} Here are the latest times for ${adjuster.full_name}:`);
        const fresh = (await api.adjusters(policyId!)).find((a) => a.id === adjuster.id);
        if (fresh) { setAdjuster(fresh); bot("Choose a new slot:", { kind: "slots", adjuster: fresh }); setStage("adj_slot"); }
      } else {
        bot(`I couldn't book that: ${err.message}`);
        if (mode === "onsite") setStage("adj_location");
      }
    } finally {
      setBusy(null);
    }
  }

  async function showGarages() {
    setBusy("Finding partner repairers…");
    try {
      const list = await api.repairPartners(policyId!);
      bot(list.length ? `${insurer}'s partner repairers near you. Partners can send estimates directly to ${insurer}:` : "No partner repairers are listed for this insurer.", { kind: "garages", list });
      bot("Would you like to do anything else?", { kind: "actions", actions: menuActions().filter((a) => a.id !== "find_garage") });
    } catch (e) {
      bot(`I couldn't load partners: ${(e as ApiError).message}`);
    } finally {
      setBusy(null);
    }
  }

  // --- render ------------------------------------------------------------------------
  const placeholder: Record<Stage, string> = {
    pick_asset: "Pick an item above…", menu: "Describe what happened, or ask a question…", claim_describe: "What happened?",
    claim_followup: "Type your answer, or 'skip'…", claim_review: "Ask a question about your claim…", question: "Ask about your cover…",
    adj_pick: "Choose an adjuster above…", adj_slot: "Choose a time above…", adj_contact: "Use the form above…",
    adj_mode: "Choose how to meet…", adj_location: "Where should the adjuster come?",
  };

  return (
    <div className="mx-auto max-w-3xl">
      <button className="btn-link mb-3" onClick={onBack}>← Back to policies</button>
      <section className="card flex h-[calc(100vh-190px)] min-h-[520px] flex-col p-0" aria-label="ClaimAssist chat">
        <header className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-3">
            <span aria-hidden className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 font-bold text-white">CA</span>
            <div>
              <p className="font-semibold">ClaimAssist</p>
              <p className="text-xs text-slate-500">{asset ? <>{assetIcon(asset.asset_type)} {asset.name} · {policy!.policy_number} · {policy!.insurer.short_name}</> : "Guidance only. Not a coverage decision."}</p>
            </div>
          </div>
          {policy && <span className="badge text-white" style={{ background: policy.insurer.brand_color }}>{policy.insurer.short_name}</span>}
        </header>

        <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 px-4 py-4" aria-live="polite" data-testid="chat-log">
          {msgs.map((m) => (
            <div key={m.id} className={m.from === "user" ? "flex justify-end" : "flex gap-2"}>
              {m.from === "bot" && <span aria-hidden className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-600 text-[10px] font-bold text-white">CA</span>}
              <div className={m.from === "user" ? "max-w-[80%] rounded-2xl rounded-br-sm bg-brand-600 px-3 py-2 text-sm text-white" : `${m.widget?.kind === "review" ? "w-full" : "max-w-[90%]"} space-y-2`}>
                {m.from === "user" ? m.text : (
                  <>
                    {m.text && <div className="rounded-2xl rounded-tl-sm bg-white px-3 py-2 text-sm shadow-sm ring-1 ring-slate-200">
                      <p className="whitespace-pre-wrap">{m.text}</p>
                      {m.sources && m.sources.length > 0 && <p className="mt-1 text-xs text-slate-500">Sources: {m.sources.join(", ")}</p>}
                    </div>}
                    {m.widget && renderWidget(m)}
                  </>
                )}
              </div>
            </div>
          ))}
          {busy && <p className="pl-9 text-xs text-slate-500" role="status"><span className="animate-pulse">●●●</span> {busy}</p>}
          <div ref={endRef} />
        </div>

        <form onSubmit={send} className="flex items-center gap-2 border-t border-slate-200 p-3">
          <label className="btn-secondary cursor-pointer px-3" title="Attach photos or documents">
            <span aria-hidden>📎</span><span className="sr-only">Attach photos or documents</span>
            <input ref={fileRef} type="file" multiple className="sr-only" accept={ALLOWED_EXT.join(",")} data-testid="chat-file"
              onChange={(e) => addFiles(e.target.files)} disabled={!policyId || !!busy} />
          </label>
          <label htmlFor="chat-input" className="sr-only">Message</label>
          <input id="chat-input" className="input" value={input} onChange={(e) => setInput(e.target.value)} placeholder={placeholder[stage]}
            maxLength={2000} autoComplete="off" data-testid="chat-input" />
          <button className="btn-primary" disabled={!input.trim() || !!busy} data-testid="chat-send">Send</button>
        </form>
        <p className="px-4 pb-2 text-[11px] text-slate-500">Demo with fictional data. Please don't share real medical, ID or bank details.</p>
      </section>
    </div>
  );

  function renderWidget(m: Msg) {
    const w = m.widget!;
    const off = !m.active || !!busy;
    const chip = "rounded-full border border-brand-600 bg-white px-3 py-1.5 text-sm font-medium text-brand-700 hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600";
    switch (w.kind) {
      case "assets":
        return (
          <div className="grid gap-2 sm:grid-cols-2">
            {profile.policies.flatMap((p) => p.assets.map((a) => (
              <button key={a.id} disabled={off} onClick={() => pickAsset(m.id, p.id, a.id, a.name)} data-testid={`chat-asset-${p.policy_type}`}
                className="rounded-xl border border-slate-200 bg-white p-3 text-left text-sm hover:border-brand-600 disabled:opacity-50">
                <p className="font-medium">{assetIcon(a.asset_type)} {a.name}</p>
                <p className="text-xs text-slate-500">{p.product_name} · {p.insurer.short_name}</p>
              </button>)))}
          </div>
        );
      case "actions":
        return <div className="flex flex-wrap gap-2">{w.actions.map((a) => <button key={a.id} className={chip} disabled={off} onClick={() => onAction(m.id, a)} data-testid={`act-${a.id}`}>{a.label}</button>)}</div>;
      case "examples":
        return policy && EXAMPLES[policy.policy_type] && m.active ? (
          <button className="text-left text-xs text-brand-700 underline" onClick={() => setInput(EXAMPLES[policy.policy_type])}>Use an example description</button>
        ) : null;
      case "followup":
        return (
          <div className="flex flex-wrap items-center gap-2">
            {w.key === "photos" && <button className={chip} disabled={off} onClick={() => fileRef.current?.click()}>Attach photos</button>}
            <button className={chip} disabled={off} onClick={() => skipQuestion(m.id)} data-testid="skip-q">Skip</button>
            {w.why && <span className="text-xs text-slate-500">Why I ask: {w.why}</span>}
          </div>
        );
      case "review":
        return (
          <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
            <ClaimReview policyholderId={profile.id} policy={policy!} asset={asset!} description={w.description} attachments={w.attachments}
              answeredKeys={w.answered} guidance={w.guidance} onSubmitted={onSubmitted} />
          </div>
        );
      case "claim_done":
        return (
          <div className="flex flex-wrap gap-2">
            <button className={chip} onClick={() => onOpenClaim(w.claim.id)} data-testid="view-claim">View claim status &amp; timeline</button>
            <button className={chip} disabled={off} onClick={() => { deactivate(m.id); user("Speak with an adjuster"); void speakAdjuster(policyId!); }} data-testid="act-speak_adjuster">Speak with an adjuster</button>
            <button className={chip} disabled={off} onClick={() => { deactivate(m.id); user("Find a partner garage"); void showGarages(); }}>Find a partner garage</button>
          </div>
        );
      case "adjusters":
        return (
          <ul className="space-y-2" data-testid="adjuster-list">
            {w.list.map((a) => (
              <li key={a.id} className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
                <div className="flex items-start gap-3">
                  <Avatar name={a.full_name} size={40} />
                  <div className="flex-1">
                    <p className="font-semibold">{a.full_name}</p>
                    <p className="text-xs text-slate-600">{a.specialization[0].toUpperCase() + a.specialization.slice(1)} specialist · {a.years_experience} yrs · {a.languages}</p>
                    <p className="text-xs text-slate-600">📍 {a.office_location}</p>
                    {a.bio && <p className="mt-1 text-xs text-slate-500">{a.bio}</p>}
                    <p className="mt-1 text-xs"><span className="font-medium">Next available:</span> {a.slots.slice(0, 3).map(slotLabel).join(" · ") || "none this week"}</p>
                    <p className="text-xs text-slate-500">Meets by: {a.allowed_modes.map((x) => MODE_LABEL[x]).join(", ")}</p>
                  </div>
                  <button className="btn-primary px-3 py-1.5" disabled={off || !a.slots.length} onClick={() => pickAdjuster(m.id, a)} data-testid={`pick-${a.id}`}>Choose</button>
                </div>
              </li>
            ))}
          </ul>
        );
      case "slots": {
        const byDay = w.adjuster.slots.slice(0, 12).reduce<Record<string, string[]>>((acc, s) => ((acc[s.slice(0, 10)] ??= []).push(s), acc), {});
        return (
          <div className="space-y-2 rounded-xl bg-white p-3 ring-1 ring-slate-200" data-testid="slot-list">
            {Object.entries(byDay).map(([day, ss]) => (
              <div key={day}>
                <p className="text-xs font-medium text-slate-500">{fmtDate(day)}</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {ss.map((s) => <button key={s} className={chip} disabled={off} onClick={() => pickSlot(m.id, s)}>{new Date(s).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</button>)}
                </div>
              </div>
            ))}
            {m.active && <button className="btn-link text-xs" disabled={!!busy} onClick={() => { deactivate(m.id); void speakAdjuster(policyId!); }}>Choose a different adjuster</button>}
          </div>
        );
      }
      case "contact":
        return <ContactForm disabled={off} defaultName={profile.full_name} onSubmit={(n, p) => submitContact(m.id, n, p)} />;
      case "modes":
        return (
          <div className="grid gap-2 sm:grid-cols-2" data-testid="mode-list">
            {(["audio", "video", "onsite", "chat"] as const).map((md) => {
              const ok = w.adjuster.allowed_modes.includes(md);
              return (
                <button key={md} disabled={off || !ok} onClick={() => pickMode(m.id, md)} data-testid={`mode-${md}`}
                  className="rounded-xl border border-slate-200 bg-white p-3 text-left text-sm hover:border-brand-600 disabled:opacity-40">
                  <p className="font-medium">{MODE_LABEL[md]}</p>
                  <p className="text-xs text-slate-500">{ok ? MODE_HINT[md] : "Not offered by this adjuster"}</p>
                </button>
              );
            })}
          </div>
        );
      case "location": {
        const home = profile.policies.find((p) => p.policy_type === "home")?.assets[0]?.name;
        const opts = [home && `${home} (home)`, asset?.asset_type === "property" ? asset.name : null].filter(Boolean) as string[];
        return m.active ? (
          <div className="flex flex-wrap gap-2">
            {[...new Set(opts)].map((o) => <button key={o} className={chip} disabled={off} onClick={() => { deactivate(m.id); user(o); void book("onsite", o); }} data-testid="loc-home">{o}</button>)}
          </div>
        ) : null;
      }
      case "appointment":
        return <AppointmentCard appt={w.appt} />;
      case "garages":
        return (
          <ul className="space-y-2" data-testid="garage-list">
            {w.list.map((g) => (
              <li key={g.id} className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
                <div className="flex justify-between gap-2"><p className="font-semibold">{g.name}</p><span className="text-xs text-slate-500">{g.distance_km} km · ★ {g.rating}</span></div>
                <p className="text-xs text-slate-600">📍 {g.address} · {g.hours}</p>
                <p className="text-xs text-slate-600">{g.services}</p>
                <p className="text-xs">📞 {g.phone}</p>
              </li>
            ))}
            <li className="text-xs text-slate-500">Fictional partner list. Distances are approximate from your insured address.</li>
          </ul>
        );
    }
  }
}

function ContactForm({ defaultName, disabled, onSubmit }: { defaultName: string; disabled: boolean; onSubmit: (name: string, phone: string) => void }) {
  const [name, setName] = useState(defaultName);
  const [phone, setPhone] = useState("");
  const [err, setErr] = useState<string | null>(null);
  return (
    <form className="space-y-2 rounded-xl bg-white p-3 ring-1 ring-slate-200" data-testid="contact-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim().length < 2) return setErr("Please enter your full name.");
        if (!/^\+?[0-9][0-9 ()-]{6,19}$/.test(phone.trim())) return setErr("Please enter a valid phone number, e.g. +1 555 0199 123.");
        setErr(null);
        onSubmit(name.trim(), phone.trim());
      }}>
      <div className="grid gap-2 sm:grid-cols-2">
        <div><label htmlFor="c-name" className="label text-xs">Full name</label><input id="c-name" className="input" value={name} onChange={(e) => setName(e.target.value)} disabled={disabled} /></div>
        <div><label htmlFor="c-phone" className="label text-xs">Contact number</label><input id="c-phone" className="input" value={phone} onChange={(e) => setPhone(e.target.value)} disabled={disabled} placeholder="+1 555 0199 123" inputMode="tel" /></div>
      </div>
      {err && <p className="text-xs text-red-700" role="alert">{err}</p>}
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] text-slate-500">Shared only with your adjuster. For the demo, use a fictional number.</p>
        <button className="btn-primary px-3 py-1.5" disabled={disabled} data-testid="contact-submit">Continue</button>
      </div>
    </form>
  );
}

export function AppointmentCard({ appt }: { appt: Appointment }) {
  return (
    <div className="rounded-xl border-2 border-emerald-300 bg-emerald-50 p-3 text-sm" data-testid="appointment-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold text-emerald-900">Appointment confirmed</p>
        <span className="font-mono text-xs" data-testid="appt-ref">{appt.reference}</span>
      </div>
      <dl className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
        <div><dt className="inline text-slate-600">Adjuster: </dt><dd className="inline font-medium">{appt.adjuster_name}</dd></div>
        <div><dt className="inline text-slate-600">When: </dt><dd className="inline font-medium">{slotLabel(appt.slot_start)} ({appt.duration_minutes} min)</dd></div>
        <div><dt className="inline text-slate-600">How: </dt><dd className="inline">{MODE_LABEL[appt.mode]}</dd></div>
        <div><dt className="inline text-slate-600">Adjuster phone: </dt><dd className="inline">{appt.adjuster_phone}</dd></div>
      </dl>
      {appt.meeting_link && <p className="mt-2 text-sm">Meeting link: <a className="text-brand-700 underline" href={appt.meeting_link} onClick={(e) => e.preventDefault()}>{appt.meeting_link}</a> <span className="text-xs text-slate-500">(demo link)</span></p>}
      {appt.directions && <p className="mt-2 rounded bg-white p-2 text-xs text-slate-700"><span className="font-medium">Location &amp; directions:</span> {appt.directions}</p>}
      <p className="mt-2 font-medium">Before the appointment</p>
      <ul className="list-disc space-y-0.5 pl-5 text-xs text-slate-700">{appt.instructions.map((i) => <li key={i}>{i}</li>)}</ul>
      {appt.shared_attachments.length > 0 && <p className="mt-2 text-xs text-slate-600">Shared with adjuster: {appt.shared_attachments.join(", ")}</p>}
    </div>
  );
}
