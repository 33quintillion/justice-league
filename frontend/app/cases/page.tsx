"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { FormError } from "@/components/FormError";
import { RequireAuth } from "@/components/RequireAuth";
import { api, MATTER_LABELS, STAGE_LABELS } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useJurisdictions } from "@/lib/useJurisdictions";

type CaseSummary = {
  id: string; title: string; matter_type: string; jurisdiction_code: string; stage: string; status: string; updated_at: string;
};

export default function CasesPage() {
  const { t } = useI18n();
  return (
    <RequireAuth>
      <h1>{t("cases.title")}</h1>
      <p>Each case is a private workspace: only you can see it. Our staff cannot open your case contents.</p>
      <CaseList />
    </RequireAuth>
  );
}

function CaseList() {
  const { me } = useAuth();
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const load = useCallback(() => api<CaseSummary[]>("/api/cases").then(setCases), []);
  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <div className="row" style={{ marginBottom: "1rem" }}>
        <button className="btn" onClick={() => setShowForm((s) => !s)} aria-expanded={showForm} disabled={!me?.email_verified}>
          {showForm ? "Cancel" : "New case"}
        </button>
        {!me?.email_verified && <span className="muted">Verify your email to create a case.</span>}
      </div>
      {showForm && <NewCaseForm />}
      {cases === null ? (
        <p aria-live="polite">Loading…</p>
      ) : cases.length === 0 ? (
        <div className="card"><p>You have no cases yet.</p></div>
      ) : (
        <div className="table-wrap card">
          <table className="data">
            <thead>
              <tr><th>Title</th><th>Area</th><th>Jurisdiction</th><th>Stage</th><th>Status</th><th>Updated</th></tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td><Link href={`/cases/${c.id}`}>{c.title}</Link></td>
                  <td>{MATTER_LABELS[c.matter_type] ?? c.matter_type}</td>
                  <td>{c.jurisdiction_code}</td>
                  <td>{STAGE_LABELS[c.stage] ?? c.stage}</td>
                  <td><span className={`badge ${c.status === "open" ? "badge-ok" : ""}`}>{c.status}</span></td>
                  <td>{new Date(c.updated_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function NewCaseForm() {
  const router = useRouter();
  const jurisdictions = useJurisdictions();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setError(null);
    try {
      const c = await api<{ id: string }>("/api/cases", { method: "POST", body: f });
      router.push(`/cases/${c.id}`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>New case</h2>
      <p className="muted">Only fill in what you know. You can add dates and details later. Avoid passwords or bank details.</p>
      <FormError error={error} />
      <form className="stack" onSubmit={submit}>
        <label className="field">
          Short title
          <input name="title" required maxLength={200} placeholder="e.g. Refund for defective washing machine" />
        </label>
        <label className="field">
          Area of law
          <select name="matter_type" required defaultValue="">
            <option value="" disabled>Choose the closest match</option>
            {Object.entries(MATTER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="field">
          Where did this happen?
          <span className="hint">The state or union territory matters: some laws and procedures differ by state.</span>
          <select name="jurisdiction_code" required defaultValue="IN">
            {jurisdictions.map((j) => (
              <option key={j.code} value={j.code}>{j.kind === "country" ? `${j.name} (not sure / central law)` : j.name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Current stage
          <select name="stage" defaultValue="not_started">
            {Object.entries(STAGE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="field">
          What happened? <span className="hint">In your own words. Optional.</span>
          <textarea name="summary" maxLength={20000} />
        </label>
        <label className="field">
          What outcome do you want? <span className="hint">Optional.</span>
          <textarea name="desired_outcome" maxLength={5000} />
        </label>
        <div><button className="btn" disabled={busy}>{busy ? "Creating…" : "Create case"}</button></div>
      </form>
    </div>
  );
}
