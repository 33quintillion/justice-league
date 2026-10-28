"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { FormError } from "@/components/FormError";
import { RequireAuth } from "@/components/RequireAuth";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Jurisdiction } from "@/lib/useJurisdictions";

const TABS = [
  { id: "users", label: "Users", perm: "users.read" },
  { id: "sources", label: "Legal sources", perm: "sources.read" },
  { id: "plans", label: "Plans", perm: "plans.manage" },
  { id: "flags", label: "Feature flags", perm: "flags.manage" },
  { id: "jurisdictions", label: "Jurisdictions", perm: "jurisdictions.manage" },
  { id: "audit", label: "Audit log", perm: "audit.read" },
  { id: "health", label: "System health", perm: "health.read" },
] as const;
const ROLES = ["sysadmin", "legal_researcher", "content_reviewer", "support", "billing_admin"];

export default function AdminPage() {
  return (
    <RequireAuth>
      <Admin />
    </RequireAuth>
  );
}

function Admin() {
  const { can } = useAuth();
  const tabs = TABS.filter((t) => can(t.perm));
  const [tab, setTab] = useState<string>(tabs[0]?.id ?? "");
  if (tabs.length === 0)
    return <div className="alert alert-error" role="alert">You do not have access to the admin console.</div>;
  return (
    <>
      <h1>Admin console</h1>
      <p className="muted">Every change here is recorded in the audit log. The console shows account metadata only; it cannot open users&apos; case contents.</p>
      <div className="tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>
      <div role="tabpanel">
        {tab === "users" && <Users />}
        {tab === "sources" && <Sources />}
        {tab === "plans" && <Plans />}
        {tab === "flags" && <Flags />}
        {tab === "jurisdictions" && <Jurisdictions />}
        {tab === "audit" && <Audit />}
        {tab === "health" && <Health />}
      </div>
    </>
  );
}

function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const reload = useCallback(() => api<T>(path).then(setData, setError), [path]);
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, error, setError, reload };
}

type AdminUser = { id: string; email: string; display_name: string; email_verified: boolean; is_suspended: boolean;
  roles: string[]; plan_code: string; created_at: string; case_count: number };

function Users() {
  const { can, me } = useAuth();
  const [q, setQ] = useState("");
  const { data, error, setError, reload } = useLoad<AdminUser[]>(`/api/admin/users?q=${encodeURIComponent(q)}`);
  const [selected, setSelected] = useState<AdminUser | null>(null);
  const [msg, setMsg] = useState("");

  async function submit(e: FormEvent<HTMLFormElement>, kind: "roles" | "suspension" | "subscription") {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const reason = f.get("reason");
    const body =
      kind === "roles" ? { roles: f.getAll("roles"), reason }
      : kind === "suspension" ? { suspended: !selected!.is_suspended, reason }
      : { plan_code: f.get("plan_code"), reason };
    setError(null);
    setMsg("");
    try {
      const u = await api<AdminUser>(`/api/admin/users/${selected!.id}/${kind}`, { method: "PUT", body });
      setSelected(u);
      setMsg("Saved and recorded in the audit log.");
      reload();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <>
      <label className="field" style={{ maxWidth: "24rem" }}>Search by email
        <input value={q} onChange={(e) => setQ(e.target.value)} type="search" />
      </label>
      <FormError error={error} />
      {msg && <div className="alert alert-ok" role="status">{msg}</div>}
      <div className="table-wrap card">
        <table className="data">
          <thead><tr><th>Email</th><th>Verified</th><th>Plan</th><th>Roles</th><th>Cases</th><th>Status</th><th /></tr></thead>
          <tbody>
            {data?.map((u) => (
              <tr key={u.id}>
                <td>{u.email}<div className="muted">{u.display_name}</div></td>
                <td>{u.email_verified ? "Yes" : "No"}</td>
                <td>{u.plan_code}</td>
                <td>{u.roles.join(", ") || "—"}</td>
                <td>{u.case_count}</td>
                <td>{u.is_suspended ? <span className="badge badge-err">Suspended</span> : <span className="badge badge-ok">Active</span>}</td>
                <td><button className="btn btn-small btn-secondary" onClick={() => { setSelected(u); setMsg(""); }}>Manage</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selected && (
        <div className="card">
          <h2>Manage {selected.email}</h2>
          <p className="muted">Each change needs a reason, which is stored in the audit log.</p>
          {can("roles.manage") && (
            <form className="stack" onSubmit={(e) => submit(e, "roles")} key={`r-${selected.id}-${selected.roles.join()}`}>
              <fieldset><legend><strong>Staff roles</strong></legend>
                {ROLES.map((r) => (
                  <label key={r} className="check"><input type="checkbox" name="roles" value={r} defaultChecked={selected.roles.includes(r)} /><span>{r}</span></label>
                ))}
              </fieldset>
              <label className="field">Reason<input name="reason" required minLength={5} /></label>
              <div><button className="btn">Save roles</button></div>
            </form>
          )}
          {can("subscriptions.manage") && (
            <form className="stack" onSubmit={(e) => submit(e, "subscription")} style={{ marginTop: "1rem" }}>
              <label className="field">Plan
                <select name="plan_code" defaultValue={selected.plan_code}>
                  {["free", "premium", "professional", "institutional"].map((p) => <option key={p}>{p}</option>)}
                </select>
              </label>
              <label className="field">Reason<input name="reason" required minLength={5} /></label>
              <div><button className="btn">Change plan</button></div>
            </form>
          )}
          {can("users.suspend") && selected.id !== me?.id && (
            <form className="stack" onSubmit={(e) => submit(e, "suspension")} style={{ marginTop: "1rem" }}>
              <label className="field">Reason<input name="reason" required minLength={5} /></label>
              <div><button className={`btn ${selected.is_suspended ? "" : "btn-danger"}`}>{selected.is_suspended ? "Reinstate account" : "Suspend account"}</button></div>
            </form>
          )}
        </div>
      )}
    </>
  );
}

type Source = { id: string; title: string; source_type: string; authority_level: string; jurisdiction_code: string;
  official_url: string; publisher: string; citation: string; effective_date: string | null; legal_status: string;
  review_status: string; notes: string; created_by: string | null; last_verified_at: string | null };

function Sources() {
  const { can, me } = useAuth();
  const { data, error, setError, reload } = useLoad<Source[]>("/api/admin/sources");
  const [msg, setMsg] = useState("");

  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form));
    setError(null);
    try {
      await api("/api/admin/sources", { method: "POST", body: { ...f, effective_date: f.effective_date || null } });
      form.reset();
      setMsg("Source added and sent for review.");
      reload();
    } catch (err) {
      setError(err);
    }
  }

  async function review(id: string, decision: "verified" | "rejected") {
    const notes = window.prompt(`Review note for marking this source ${decision} (what did you check?)`);
    if (!notes) return;
    setError(null);
    try {
      await api(`/api/admin/sources/${id}/review`, { method: "POST", body: { decision, notes } });
      setMsg(`Source marked ${decision}.`);
      reload();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <>
      <p className="muted">Phase 2 stores source metadata and runs the review workflow. Fetching, parsing and indexing source text arrives in Phase 3.</p>
      <FormError error={error} />
      {msg && <div className="alert alert-ok" role="status">{msg}</div>}
      <div className="table-wrap card">
        <table className="data">
          <thead><tr><th>Title</th><th>Type</th><th>Jurisdiction</th><th>Legal status</th><th>Review</th><th /></tr></thead>
          <tbody>
            {data?.length === 0 && <tr><td colSpan={6}>No sources yet.</td></tr>}
            {data?.map((s) => (
              <tr key={s.id}>
                <td><a href={s.official_url} target="_blank" rel="noopener noreferrer">{s.title}</a>
                  {s.citation && <div className="muted">{s.citation}</div>}</td>
                <td>{s.source_type}<div className="muted">{s.authority_level}</div></td>
                <td>{s.jurisdiction_code}</td>
                <td>{s.legal_status}</td>
                <td><span className={`badge ${s.review_status === "verified" ? "badge-ok" : s.review_status === "rejected" ? "badge-err" : "badge-warn"}`}>{s.review_status}</span>
                  {s.last_verified_at && <div className="muted">{new Date(s.last_verified_at).toLocaleDateString()}</div>}</td>
                <td>
                  {can("sources.review") && s.review_status === "pending_review" && s.created_by !== me?.id && (
                    <div className="row">
                      <button className="btn btn-small" onClick={() => review(s.id, "verified")}>Verify</button>
                      <button className="btn btn-small btn-secondary" onClick={() => review(s.id, "rejected")}>Reject</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {can("sources.write") && (
        <div className="card">
          <h2>Add a source</h2>
          <p className="muted">Only https links on official government domains are accepted. A different person must verify it.</p>
          <form className="stack" onSubmit={create}>
            <label className="field">Title<input name="title" required minLength={3} /></label>
            <label className="field">Official URL<input name="official_url" type="url" required placeholder="https://www.indiacode.nic.in/…" /></label>
            <label className="field">Type<select name="source_type">{["legislation", "rule_regulation", "notification_gazette", "judgment", "official_guidance"].map((x) => <option key={x}>{x}</option>)}</select></label>
            <label className="field">Authority<select name="authority_level">{["legislation", "regulation", "binding", "persuasive", "general_guidance"].map((x) => <option key={x}>{x}</option>)}</select></label>
            <label className="field">Jurisdiction code<input name="jurisdiction_code" defaultValue="IN" required /></label>
            <label className="field">Publisher<input name="publisher" /></label>
            <label className="field">Citation (e.g. Act number, case number)<input name="citation" /></label>
            <label className="field">Effective date<input name="effective_date" type="date" /></label>
            <label className="field">Legal status<select name="legal_status">{["unknown", "in_force", "amended", "partially_in_force", "repealed", "stayed", "overruled"].map((x) => <option key={x}>{x}</option>)}</select></label>
            <div><button className="btn">Add for review</button></div>
          </form>
        </div>
      )}
    </>
  );
}

type Plan = { code: string; name: string; price_minor: number | null; billing_interval: string | null; entitlements: Record<string, unknown>; is_public: boolean };

function Plans() {
  const { data, error, setError, reload } = useLoad<Plan[]>("/api/admin/plans");
  const [msg, setMsg] = useState("");
  async function save(e: FormEvent<HTMLFormElement>, code: string) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setError(null);
    try {
      const price = String(f.get("price"));
      const body = {
        entitlements: JSON.parse(String(f.get("entitlements"))),
        ...(price === "" ? { clear_price: true } : { price_minor: Math.round(Number(price) * 100) }),
      };
      await api(`/api/admin/plans/${code}`, { method: "PATCH", body });
      setMsg(`Plan ${code} saved.`);
      reload();
    } catch (err) {
      setError(err instanceof SyntaxError ? new Error("Entitlements must be valid JSON") : err);
    }
  }
  return (
    <>
      <FormError error={error} />
      {msg && <div className="alert alert-ok" role="status">{msg}</div>}
      {data?.map((p) => (
        <form key={p.code} className="card stack" onSubmit={(e) => save(e, p.code)}>
          <h2>{p.name} <span className="badge">{p.is_public ? "public" : "by agreement"}</span></h2>
          <label className="field">Price in ₹ per {p.billing_interval ?? "period"} <span className="hint">Leave empty for &quot;not yet announced&quot;.</span>
            <input name="price" type="number" min={0} step="0.01" defaultValue={p.price_minor === null ? "" : p.price_minor / 100} disabled={p.code === "free"} />
          </label>
          <label className="field">Entitlements (JSON; null means unlimited)
            <textarea name="entitlements" defaultValue={JSON.stringify(p.entitlements, null, 2)} style={{ fontFamily: "monospace" }} />
          </label>
          <div><button className="btn">Save {p.name}</button></div>
        </form>
      ))}
    </>
  );
}

type Flag = { key: string; description: string; enabled: boolean };

function Flags() {
  const { data, error, setError, reload } = useLoad<Flag[]>("/api/admin/flags");
  return (
    <>
      <FormError error={error} />
      <div className="card">
        {data?.map((f) => (
          <label key={f.key} className="check" style={{ marginBottom: ".6rem" }}>
            <input type="checkbox" checked={f.enabled} onChange={(e) =>
              api(`/api/admin/flags/${f.key}`, { method: "PUT", body: { enabled: e.target.checked } }).then(reload, setError)} />
            <span><strong>{f.key}</strong> — {f.description}</span>
          </label>
        ))}
      </div>
    </>
  );
}

function Jurisdictions() {
  const { data, error, setError, reload } = useLoad<Jurisdiction[]>("/api/admin/jurisdictions");
  return (
    <>
      <FormError error={error} />
      <p className="muted">Disabled jurisdictions are hidden from users and cannot be chosen for new cases.</p>
      <div className="table-wrap card">
        <table className="data">
          <thead><tr><th>Code</th><th>Name</th><th>Kind</th><th>Enabled</th></tr></thead>
          <tbody>
            {data?.map((j) => (
              <tr key={j.code}>
                <td>{j.code}</td><td>{j.name}</td><td>{j.kind}</td>
                <td><input type="checkbox" aria-label={`Enable ${j.name}`} checked={j.enabled} disabled={j.code === "IN"}
                  onChange={(e) => api(`/api/admin/jurisdictions/${j.code}`, { method: "PATCH", body: { enabled: e.target.checked } }).then(reload, setError)} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

type AuditRow = { id: number; created_at: string; actor_id: string | null; action: string; target_type: string; target_id: string; details: object; ip: string };

function Audit() {
  const { data, error } = useLoad<AuditRow[]>("/api/admin/audit?limit=200");
  return (
    <>
      <FormError error={error} />
      <p className="muted">Append-only: the database rejects edits and deletions of audit records.</p>
      <div className="table-wrap card">
        <table className="data">
          <thead><tr><th>When</th><th>Action</th><th>Actor</th><th>Target</th><th>Details</th></tr></thead>
          <tbody>
            {data?.map((a) => (
              <tr key={a.id}>
                <td>{new Date(a.created_at).toLocaleString()}</td>
                <td>{a.action}</td>
                <td className="muted">{a.actor_id?.slice(0, 8) ?? "system"}</td>
                <td className="muted">{a.target_type} {a.target_id.slice(0, 8)}</td>
                <td><code style={{ fontSize: ".8rem" }}>{JSON.stringify(a.details)}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Health() {
  const { data, error } = useLoad<{ database: string; alembic_revision: string; counts: Record<string, number> }>("/api/admin/health");
  return (
    <>
      <FormError error={error} />
      {data && (
        <div className="card">
          <p>Database: <span className="badge badge-ok">{data.database}</span> · Schema revision: <code>{data.alembic_revision}</code></p>
          <ul>{Object.entries(data.counts).map(([k, v]) => <li key={k}>{k.replaceAll("_", " ")}: {v}</li>)}</ul>
        </div>
      )}
    </>
  );
}
