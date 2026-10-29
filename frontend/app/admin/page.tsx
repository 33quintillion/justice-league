"use client";

import { useState, type FormEvent } from "react";
import { FormError } from "@/components/FormError";
import { RequireAuth } from "@/components/RequireAuth";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Jurisdiction } from "@/lib/useJurisdictions";
import { Sources } from "@/components/admin/Sources";
import { useLoad } from "@/lib/useLoad";

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
  // Optimistic, like the consent checkboxes: show the new state at once and roll back if saving fails.
  const [pending, setPending] = useState<Record<string, boolean>>({});
  function toggle(key: string, enabled: boolean) {
    setPending((p) => ({ ...p, [key]: enabled }));
    api(`/api/admin/flags/${key}`, { method: "PUT", body: { enabled } })
      .then(reload, setError)
      .finally(() => setPending((p) => { const { [key]: _, ...rest } = p; return rest; }));
  }
  return (
    <>
      <FormError error={error} />
      <div className="card">
        {data?.map((f) => (
          <label key={f.key} className="check" style={{ marginBottom: ".6rem" }}>
            <input type="checkbox" checked={pending[f.key] ?? f.enabled} onChange={(e) => toggle(f.key, e.target.checked)} />
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
