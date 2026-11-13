import { useEffect, useState } from "react";
import { api, ApiError, type InsurerWithLines, type ProfileDetail } from "../api";
import { Alert, Spinner } from "./ui";

const TYPE_LABEL: Record<string, string> = { auto: "Car", home: "Home", gadget: "Gadget / device" };
const FIELDS: Record<string, [string, string][]> = {
  auto: [["Registration", "e.g. DEMO-7788"], ["Colour", "e.g. Blue"], ["Usage", "e.g. Private / commuting"]],
  home: [["Address", "e.g. 7 River Lane, Riverton"], ["Type", "e.g. 1-bedroom apartment"], ["Occupancy", "e.g. Owner-occupied"]],
  gadget: [["Serial", "e.g. SN-12345"], ["Purchased", "e.g. 2026-08"]],
};
const ASSET_LABEL: Record<string, [string, string]> = {
  auto: ["Car (year, make, model)", "e.g. 2019 Honda Jazz"],
  home: ["Property name", "e.g. Apartment 2C, 7 River Lane"],
  gadget: ["Device", "e.g. 13\" Tablet"],
};

export default function AddPolicyForm({ onAdded, onCancel }: { onAdded: (p: ProfileDetail, number: string) => void; onCancel: () => void }) {
  const [insurers, setInsurers] = useState<InsurerWithLines[] | null>(null);
  const [type, setType] = useState("auto");
  const [insurerId, setInsurerId] = useState("");
  const [number, setNumber] = useState("");
  const [assetName, setAssetName] = useState("");
  const [details, setDetails] = useState<Record<string, string>>({});
  const [start, setStart] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api.insurers().then(setInsurers).catch((e: ApiError) => setError(e.message)); }, []);
  const options = insurers?.filter((i) => i.lines.includes(type)) ?? [];
  useEffect(() => { setInsurerId(options[0]?.id ?? ""); setDetails({}); }, [type, insurers]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const n = number.trim().toUpperCase();
    if (!/^[A-Z0-9][A-Z0-9-]{5,19}$/.test(n)) return setError("Policy number: 6–20 letters, numbers or dashes (as printed on your policy schedule).");
    if (assetName.trim().length < 3) return setError(`Please enter the ${type === "auto" ? "car" : "insured item"}.`);
    setBusy(true);
    try {
      const p = await api.addPolicy({ policy_type: type, insurer_id: insurerId, policy_number: n, asset_name: assetName.trim(), asset_details: details, start_date: start || null });
      onAdded(p, n);
    } catch (err) {
      setError((err as ApiError).message);
      setBusy(false);
    }
  }

  return (
    <section className="card border-brand-600" aria-labelledby="add-h" data-testid="add-policy-form">
      <h2 id="add-h" className="h2">Add a policy</h2>
      <p className="mt-1 text-sm text-slate-600">Enter the details from your policy schedule. In this demo the cover wording is copied from the insurer's sample product and isn't verified with the insurer.</p>
      {!insurers && !error && <div className="mt-3"><Spinner label="Loading insurers…" /></div>}
      <form onSubmit={submit} className="mt-4 grid gap-3 sm:grid-cols-2" noValidate>
        <div><label htmlFor="ap-type" className="label">Policy type</label>
          <select id="ap-type" className="input" value={type} onChange={(e) => setType(e.target.value)} data-testid="ap-type">
            {Object.entries(TYPE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select></div>
        <div><label htmlFor="ap-ins" className="label">Insurer</label>
          <select id="ap-ins" className="input" value={insurerId} onChange={(e) => setInsurerId(e.target.value)} disabled={!options.length}>
            {options.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
          </select></div>
        <div><label htmlFor="ap-num" className="label">Policy number</label>
          <input id="ap-num" className="input font-mono uppercase" value={number} onChange={(e) => setNumber(e.target.value)} placeholder="e.g. NSM-778812" maxLength={20} data-testid="ap-number" /></div>
        <div><label htmlFor="ap-start" className="label">Start date <span className="font-normal text-slate-500">(optional)</span></label>
          <input id="ap-start" type="date" className="input" value={start} onChange={(e) => setStart(e.target.value)} /></div>
        <div className="sm:col-span-2"><label htmlFor="ap-asset" className="label">{ASSET_LABEL[type][0]}</label>
          <input id="ap-asset" className="input" value={assetName} onChange={(e) => setAssetName(e.target.value)} placeholder={ASSET_LABEL[type][1]} maxLength={100} data-testid="ap-asset" /></div>
        {FIELDS[type].map(([k, ph]) => (
          <div key={k}><label htmlFor={`ap-${k}`} className="label">{k} <span className="font-normal text-slate-500">(optional)</span></label>
            <input id={`ap-${k}`} className="input" value={details[k] ?? ""} placeholder={ph} maxLength={100}
              onChange={(e) => setDetails({ ...details, [k]: e.target.value })} /></div>
        ))}
        {error && <div className="sm:col-span-2"><Alert tone="error">{error}</Alert></div>}
        <div className="flex gap-3 sm:col-span-2">
          <button className="btn-primary" disabled={busy || !insurerId} data-testid="ap-submit">{busy ? "Adding…" : "Add policy"}</button>
          <button type="button" className="btn-secondary" onClick={onCancel}>Cancel</button>
        </div>
      </form>
    </section>
  );
}
