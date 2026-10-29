"use client";

import { useState, type FormEvent } from "react";
import { FormError } from "@/components/FormError";
import { Warnings } from "@/components/Sources";
import { api, apiForm, MATTER_LABELS } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Warning } from "@/lib/library";
import { useLoad } from "@/lib/useLoad";

type Source = {
  id: string; title: string; source_type: string; authority_level: string; jurisdiction_code: string;
  official_url: string; publisher: string; citation: string; effective_date: string | null; legal_status: string;
  review_status: string; notes: string; created_by: string | null; last_verified_at: string | null;
  practice_areas: string[]; link_status: string; link_checked_at: string | null;
};
type Doc = { id: string; filename: string; media_type: string; sha256: string; size_bytes: number; retrieved_from_url: string;
  retrieved_at: string; uploaded_by: string | null; uploaded_at: string; is_current: boolean; extracted_chars: number };
type Detail = { source: Source; documents: Doc[]; sections: { id: string; ref: string; heading: string; text: string }[];
  relations: { kind: string; section_ref: string; by_title: string }[]; warnings: Warning[] };

const STATUSES = ["unknown", "in_force", "amended", "partially_in_force", "repealed", "stayed", "overruled"];
const RELATIONS = ["amends", "repeals", "overrules", "stays", "substitutes", "clarifies", "conflicts_with"];
const today = () => new Date().toISOString().slice(0, 10);

function reviewBadge(s: string) {
  return `badge ${s === "verified" ? "badge-ok" : s === "rejected" ? "badge-err" : "badge-warn"}`;
}

export function Sources() {
  const { can } = useAuth();
  const [filter, setFilter] = useState("");
  const { data, error, setError, reload } = useLoad<Source[]>(`/api/admin/sources${filter}`);
  const [open, setOpen] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const body = { ...Object.fromEntries(fd), practice_areas: fd.getAll("practice_areas"), effective_date: fd.get("effective_date") || null };
    setError(null);
    try {
      const s = await api<Source>("/api/admin/sources", { method: "POST", body });
      form.reset();
      setMsg("Source added. Upload the official document next.");
      await reload();
      setOpen(s.id);
    } catch (err) {
      setError(err);
    }
  }

  async function checkLinks() {
    setError(null);
    try {
      const c = await api<Record<string, number>>("/api/admin/sources/check-links", { method: "POST" });
      setMsg(`Link check finished: ${c.ok} ok, ${c.broken} broken, ${c.unreachable} unreachable.`);
      reload();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <>
      <p className="muted">
        Researchers download official files by hand (respecting each site&apos;s terms) and upload them here. A different
        reviewer verifies each source before it is published in the Legal Library.
      </p>
      <div className="row" style={{ marginBottom: "1rem" }}>
        <label className="field" style={{ minWidth: "14rem" }}>Show
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">All sources</option>
            <option value="?review_status=pending_review">Waiting for review</option>
            <option value="?review_status=verified">Verified</option>
            <option value="?stale=true">Re-verification due</option>
            <option value="?review_status=rejected">Rejected</option>
          </select>
        </label>
        {can("sources.write") && <button className="btn btn-secondary" onClick={checkLinks}>Check official links</button>}
      </div>
      <FormError error={error} />
      {msg && <div className="alert alert-ok" role="status">{msg}</div>}
      <div className="table-wrap card">
        <table className="data">
          <thead><tr><th>Title</th><th>Type</th><th>Jurisdiction</th><th>Legal status</th><th>Review</th><th>Link</th><th /></tr></thead>
          <tbody>
            {data?.length === 0 && <tr><td colSpan={7}>No sources.</td></tr>}
            {data?.map((s) => (
              <tr key={s.id}>
                <td>{s.title}{s.citation && <div className="muted">{s.citation}</div>}</td>
                <td>{s.source_type}</td>
                <td>{s.jurisdiction_code}</td>
                <td>{s.legal_status}</td>
                <td><span className={reviewBadge(s.review_status)}>{s.review_status}</span></td>
                <td><span className={`badge ${s.link_status === "ok" ? "badge-ok" : s.link_status === "unchecked" ? "" : "badge-err"}`}>{s.link_status}</span></td>
                <td><button className="btn btn-small btn-secondary" onClick={() => setOpen(open === s.id ? null : s.id)}>{open === s.id ? "Close" : "Open"}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && <SourcePanel id={open} sources={data ?? []} onChange={(m) => { setMsg(m); reload(); }} />}
      {can("sources.write") && (
        <div className="card">
          <h2>Add a source</h2>
          <p className="muted">Only https links on official government domains are accepted.</p>
          <form className="stack" onSubmit={create}>
            <label className="field">Title<input name="title" required minLength={3} /></label>
            <label className="field">Official URL<input name="official_url" type="url" required placeholder="https://www.indiacode.nic.in/…" /></label>
            <label className="field">Type<select name="source_type">{["legislation", "rule_regulation", "notification_gazette", "judgment", "official_guidance"].map((x) => <option key={x}>{x}</option>)}</select></label>
            <label className="field">Authority<select name="authority_level">{["legislation", "regulation", "binding", "persuasive", "general_guidance"].map((x) => <option key={x}>{x}</option>)}</select></label>
            <label className="field">Jurisdiction code<input name="jurisdiction_code" defaultValue="IN" required /></label>
            <label className="field">Publisher<input name="publisher" /></label>
            <label className="field">Citation (Act number, or case citation such as neutral citation)<input name="citation" /></label>
            <label className="field">Effective date<input name="effective_date" type="date" /></label>
            <label className="field">Legal status<select name="legal_status">{STATUSES.map((x) => <option key={x}>{x}</option>)}</select></label>
            <label className="field">Practice areas <span className="hint">Hold Ctrl/Cmd to choose several.</span>
              <select name="practice_areas" multiple size={6}>
                {Object.entries(MATTER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <div><button className="btn">Add source</button></div>
          </form>
        </div>
      )}
    </>
  );
}

function SourcePanel({ id, sources, onChange }: { id: string; sources: Source[]; onChange: (msg: string) => void }) {
  const { can, me } = useAuth();
  const { data: d, error, setError, reload } = useLoad<Detail>(`/api/admin/sources/${id}`);
  const [showAll, setShowAll] = useState(false);

  async function run(fn: () => Promise<unknown>, msg: string, form?: HTMLFormElement) {
    setError(null);
    try {
      await fn();
      form?.reset();
      await reload();
      onChange(msg);
    } catch (err) {
      setError(err);
    }
  }

  if (!d) return <div className="card"><FormError error={error} />{!error && <p>Loading…</p>}</div>;
  const s = d.source;
  const current = d.documents.find((x) => x.is_current);
  const isAuthor = s.created_by === me?.id || current?.uploaded_by === me?.id;

  return (
    <div className="card" aria-label={`Source ${s.title}`}>
      <h2>{s.title} <span className={reviewBadge(s.review_status)}>{s.review_status}</span></h2>
      <p><a href={s.official_url} target="_blank" rel="noopener noreferrer">{s.official_url}</a></p>
      <Warnings warnings={d.warnings} />
      <FormError error={error} />

      <h3>Documents</h3>
      {d.documents.length === 0 ? <p>No official document uploaded yet. It cannot be verified until one is.</p> : (
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>File</th><th>Obtained from</th><th>SHA-256</th><th>Text</th><th /></tr></thead>
            <tbody>
              {d.documents.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.filename} {doc.is_current && <span className="badge badge-ok">current</span>}<div className="muted">{doc.retrieved_at}</div></td>
                  <td className="muted" style={{ wordBreak: "break-all" }}>{doc.retrieved_from_url}</td>
                  <td><code style={{ fontSize: ".75rem" }}>{doc.sha256.slice(0, 16)}…</code></td>
                  <td>{doc.extracted_chars.toLocaleString()} chars</td>
                  <td><a href={`/api/admin/sources/${s.id}/documents/${doc.id}/original`}>Original</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {can("sources.write") && (
        <form className="stack" style={{ marginTop: "1rem" }} onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          run(() => apiForm(`/api/admin/sources/${s.id}/documents`, new FormData(form)), "Document uploaded and sent for review.", form);
        }}>
          <h3>Upload official document</h3>
          <label className="field">File (PDF or UTF-8 text, up to 25 MB)<input name="file" type="file" accept=".pdf,.txt,application/pdf,text/plain" required /></label>
          <label className="field">Downloaded from (official URL)<input name="retrieved_from_url" type="url" required defaultValue={s.official_url} /></label>
          <label className="field">Downloaded on<input name="retrieved_at" type="date" required defaultValue={today()} max={today()} /></label>
          <div><button className="btn">Upload</button></div>
        </form>
      )}

      <h3>Sections ({d.sections.length})</h3>
      <p className="muted">Check that the split matches the official layout before verifying.</p>
      <ol>
        {(showAll ? d.sections : d.sections.slice(0, 8)).map((sec) => (
          <li key={sec.id}><strong>{sec.ref}</strong>{sec.heading && ` — ${sec.heading}`}<div className="muted">{sec.text.slice(0, 180)}{sec.text.length > 180 && "…"}</div></li>
        ))}
      </ol>
      {d.sections.length > 8 && <button className="linklike" onClick={() => setShowAll((x) => !x)}>{showAll ? "Show fewer" : `Show all ${d.sections.length}`}</button>}

      {can("sources.review") && s.review_status !== "verified" && (
        isAuthor ? <p className="muted">You added or uploaded this source, so someone else must review it.</p> : (
          <form className="stack" style={{ marginTop: "1rem" }} onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const fd = new FormData(form);
            const decision = (e.nativeEvent as SubmitEvent).submitter?.getAttribute("value");
            run(() => api(`/api/admin/sources/${s.id}/review`, { method: "POST", body: { decision, notes: fd.get("notes") } }), `Source marked ${decision}.`, form);
          }}>
            <h3>Review</h3>
            <label className="field">What did you check against the official source?<textarea name="notes" required minLength={5} style={{ minHeight: "4rem" }} /></label>
            <div className="row">
              <button className="btn" name="decision" value="verified">Verify</button>
              <button className="btn btn-secondary" name="decision" value="rejected">Reject</button>
            </div>
          </form>
        )
      )}

      {can("sources.write") && (
        <>
          <form className="stack" style={{ marginTop: "1rem" }} onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const fd = new FormData(form);
            run(() => api(`/api/admin/sources/${s.id}`, { method: "PATCH", body: {
              legal_status: fd.get("legal_status"), effective_date: fd.get("effective_date") || null,
              practice_areas: fd.getAll("practice_areas"), reason: fd.get("reason"),
            } }), "Metadata updated; the source needs review again.");
          }}>
            <h3>Correct metadata</h3>
            <label className="field">Legal status<select name="legal_status" defaultValue={s.legal_status}>{STATUSES.map((x) => <option key={x}>{x}</option>)}</select></label>
            <label className="field">Effective date<input name="effective_date" type="date" defaultValue={s.effective_date ?? ""} /></label>
            <label className="field">Practice areas
              <select name="practice_areas" multiple size={5} defaultValue={s.practice_areas}>
                {Object.entries(MATTER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label className="field">Reason<input name="reason" required minLength={5} /></label>
            <div><button className="btn btn-secondary">Save and send for review</button></div>
          </form>

          <form className="stack" style={{ marginTop: "1rem" }} onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const fd = new FormData(form);
            run(() => api(`/api/admin/sources/${s.id}/relations`, { method: "POST", body: {
              target_source_id: fd.get("target"), kind: fd.get("kind"), target_section_ref: fd.get("section") ?? "",
              effective_date: fd.get("effective_date") || null, note: fd.get("note") ?? "",
            } }), "Relation recorded.", form);
          }}>
            <h3>This source affects another</h3>
            <label className="field">Effect<select name="kind">{RELATIONS.map((k) => <option key={k}>{k}</option>)}</select></label>
            <label className="field">Affected source
              <select name="target" required>{sources.filter((x) => x.id !== s.id).map((x) => <option key={x.id} value={x.id}>{x.title}</option>)}</select>
            </label>
            <label className="field">Section (blank for the whole source)<input name="section" maxLength={30} /></label>
            <label className="field">From date<input name="effective_date" type="date" /></label>
            <label className="field">Note<input name="note" /></label>
            <div><button className="btn btn-secondary">Record effect</button></div>
          </form>
        </>
      )}
      {d.relations.length > 0 && (
        <>
          <h3>Affected by</h3>
          <ul>{d.relations.map((r, i) => <li key={i}>{r.by_title} {r.kind} {r.section_ref ? `section ${r.section_ref}` : "the whole source"}</li>)}</ul>
        </>
      )}
      {s.notes && (<><h3>Review history</h3><pre className="muted" style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{s.notes}</pre></>)}
    </div>
  );
}
