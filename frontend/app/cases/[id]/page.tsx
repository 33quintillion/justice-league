"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { FormError } from "@/components/FormError";
import { RequireAuth } from "@/components/RequireAuth";
import { api, ApiError, MATTER_LABELS, STAGE_LABELS } from "@/lib/api";
import { useJurisdictions } from "@/lib/useJurisdictions";

type CaseEvent = { id: string; event_date: string; description: string; is_deadline: boolean; origin: string };
type CaseDetail = {
  id: string; title: string; matter_type: string; jurisdiction_code: string; stage: string; status: string;
  summary: string; desired_outcome: string; events: CaseEvent[]; updated_at: string;
};

export default function CasePage() {
  return (
    <RequireAuth>
      <CaseView />
    </RequireAuth>
  );
}

function CaseView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [c, setC] = useState<CaseDetail | null>(null);
  const [loadError, setLoadError] = useState("");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(
    () =>
      api<CaseDetail>(`/api/cases/${id}`).then(setC, (e) =>
        setLoadError(e instanceof ApiError && e.status === 404 ? "Case not found." : "Could not load this case."),
      ),
    [id],
  );
  useEffect(() => {
    load();
  }, [load]);

  if (loadError) return <div className="alert alert-error" role="alert">{loadError} <Link href="/cases">Back to My Cases</Link></div>;
  if (!c) return <p aria-live="polite">Loading…</p>;

  async function act(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e);
    }
  }

  async function deleteCase() {
    if (!window.confirm(`Delete "${c!.title}" and its timeline permanently? This cannot be undone.`)) return;
    try {
      await api(`/api/cases/${id}`, { method: "DELETE" });
      router.push("/cases");
    } catch (e) {
      setError(e);
    }
  }

  return (
    <>
      <p><Link href="/cases">← My Cases</Link></p>
      <h1>{c.title}</h1>
      <p className="row">
        <span className="badge">{MATTER_LABELS[c.matter_type] ?? c.matter_type}</span>
        <span className="badge">{c.jurisdiction_code}</span>
        <span className="badge">{STAGE_LABELS[c.stage] ?? c.stage}</span>
        <span className={`badge ${c.status === "open" ? "badge-ok" : ""}`}>{c.status}</span>
      </p>
      <FormError error={error} />

      {editing ? (
        <EditCase c={c} onDone={() => { setEditing(false); load(); }} onError={setError} />
      ) : (
        <div className="card">
          <h2>Your account of what happened</h2>
          <p style={{ whiteSpace: "pre-wrap" }}>{c.summary || <span className="muted">Not written yet.</span>}</p>
          <h3>Outcome you want</h3>
          <p style={{ whiteSpace: "pre-wrap" }}>{c.desired_outcome || <span className="muted">Not written yet.</span>}</p>
          <div className="row">
            <button className="btn btn-secondary" onClick={() => setEditing(true)}>Edit details</button>
            <button
              className="btn btn-secondary"
              onClick={() => act(() => api(`/api/cases/${id}`, { method: "PATCH", body: { status: c.status === "open" ? "closed" : "open" } }))}
            >
              {c.status === "open" ? "Close case" : "Reopen case"}
            </button>
          </div>
        </div>
      )}

      <div className="card">
        <h2>Timeline</h2>
        <p className="muted">
          Add events in any order; they are sorted by date. Reminders here do not replace official court notices or a
          lawyer&apos;s deadline management.
        </p>
        {c.events.length === 0 ? (
          <p>No events yet.</p>
        ) : (
          <ol className="timeline">
            {c.events.map((e) => (
              <li key={e.id} className={e.is_deadline ? "deadline" : ""}>
                <strong>{new Date(e.event_date + "T00:00:00").toLocaleDateString()}</strong>
                {e.is_deadline && <> <span className="badge badge-err">Deadline</span></>}
                <div style={{ whiteSpace: "pre-wrap" }}>{e.description}</div>
                <button
                  className="linklike muted"
                  aria-label={`Remove event from ${e.event_date}`}
                  onClick={() => act(() => api(`/api/cases/${id}/events/${e.id}`, { method: "DELETE" }))}
                >
                  Remove
                </button>
              </li>
            ))}
          </ol>
        )}
        <AddEvent onAdd={(body) => act(() => api(`/api/cases/${id}/events`, { method: "POST", body }))} />
      </div>

      <div className="card">
        <h2>Delete case</h2>
        <p className="muted">Permanently removes this case and its timeline.</p>
        <button className="btn btn-danger" onClick={deleteCase}>Delete case</button>
      </div>
    </>
  );
}

function AddEvent({ onAdd }: { onAdd: (body: object) => Promise<void> }) {
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    await onAdd({ event_date: f.get("event_date"), description: f.get("description"), is_deadline: f.get("is_deadline") === "on" });
    form.reset();
  }
  return (
    <form className="stack" onSubmit={submit} style={{ marginTop: "1rem" }}>
      <h3>Add an event</h3>
      <label className="field">Date<input type="date" name="event_date" required /></label>
      <label className="field">What happened<textarea name="description" required maxLength={5000} style={{ minHeight: "4rem" }} /></label>
      <label className="check"><input type="checkbox" name="is_deadline" /><span>This is a deadline or hearing date</span></label>
      <div><button className="btn">Add event</button></div>
    </form>
  );
}

function EditCase({ c, onDone, onError }: { c: CaseDetail; onDone: () => void; onError: (e: unknown) => void }) {
  const jurisdictions = useJurisdictions();
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    try {
      await api(`/api/cases/${c.id}`, { method: "PATCH", body: Object.fromEntries(new FormData(e.currentTarget)) });
      onDone();
    } catch (err) {
      onError(err);
    }
  }
  if (jurisdictions.length === 0) return <p aria-live="polite">Loading…</p>;
  return (
    <div className="card">
      <h2>Edit details</h2>
      <form className="stack" onSubmit={submit}>
        <label className="field">Title<input name="title" defaultValue={c.title} required maxLength={200} /></label>
        <label className="field">Area of law
          <select name="matter_type" defaultValue={c.matter_type}>
            {Object.entries(MATTER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="field">Jurisdiction
          <select name="jurisdiction_code" defaultValue={c.jurisdiction_code}>
            {jurisdictions.map((j) => <option key={j.code} value={j.code}>{j.name}</option>)}
          </select>
        </label>
        <label className="field">Stage
          <select name="stage" defaultValue={c.stage}>
            {Object.entries(STAGE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="field">What happened<textarea name="summary" defaultValue={c.summary} maxLength={20000} /></label>
        <label className="field">Outcome you want<textarea name="desired_outcome" defaultValue={c.desired_outcome} maxLength={5000} /></label>
        <div className="row">
          <button className="btn">Save</button>
          <button type="button" className="btn btn-secondary" onClick={onDone}>Cancel</button>
        </div>
      </form>
    </div>
  );
}
