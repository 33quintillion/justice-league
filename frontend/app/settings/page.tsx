"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { FormError } from "@/components/FormError";
import { RequireAuth } from "@/components/RequireAuth";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { LANGUAGES, useI18n } from "@/lib/i18n";
import { useJurisdictions } from "@/lib/useJurisdictions";

type Settings = {
  display_name: string; preferred_language: string; country_code: string; state_code: string | null;
  retention_days: number | null; consent_ai_processing: boolean; consent_training_use: boolean;
  consent_updated_at: string | null;
};
type Plan = { code: string; name: string; description: string; price_minor: number | null; currency: string;
  billing_interval: string | null; entitlements: Record<string, number | boolean | null> };

export default function SettingsPage() {
  const { t } = useI18n();
  return (
    <RequireAuth>
      <h1>{t("settings.title")}</h1>
      <SettingsBody />
    </RequireAuth>
  );
}

function SettingsBody() {
  const { me, refresh, setMe } = useAuth();
  const { setLang } = useI18n();
  const router = useRouter();
  const jurisdictions = useJurisdictions();
  const [s, setS] = useState<Settings | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState("");

  useEffect(() => {
    api<Settings>("/api/account/settings").then(setS, setError);
    api<Plan[]>("/api/plans").then(setPlans, () => {});
  }, []);

  if (!s) return <FormError error={error} />;

  async function save(body: Record<string, unknown>, label: string) {
    setError(null);
    const previous = s;
    // Optimistic for checkboxes, so the control responds immediately; rolled back on failure.
    setS((cur) => (cur ? ({ ...cur, ...body } as Settings) : cur));
    setSaved("");
    try {
      const next = await api<Settings>("/api/account/settings", { method: "PATCH", body });
      setS(next);
      setLang(next.preferred_language);
      setSaved(`${label} saved.`);
      refresh();
    } catch (e) {
      setS(previous);
      setError(e);
    }
  }

  function saveProfile(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const state = String(f.get("state_code"));
    const retention = String(f.get("retention"));
    save(
      {
        display_name: f.get("display_name"),
        preferred_language: f.get("preferred_language"),
        ...(state ? { state_code: state } : { clear_state: true }),
        ...(retention === "keep" ? { keep_until_deleted: true } : { retention_days: Number(retention) }),
      },
      "Profile",
    );
  }

  async function deleteAccount(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setError(null);
    try {
      await api("/api/account/delete", { method: "POST", body: { password: f.get("password"), confirm_text: f.get("confirm_text") } });
      setMe(null);
      router.push("/");
    } catch (err) {
      setError(err);
    }
  }

  const states = jurisdictions.filter((j) => j.parent_code === "IN");
  const myPlan = plans.find((p) => p.code === me?.plan_code);

  return (
    <>
      <div aria-live="polite">{saved && <div className="alert alert-ok">{saved}</div>}</div>
      <FormError error={error} />

      <section className="card">
        <h2>Profile and jurisdiction</h2>
        <p className="muted">Signed in as {me?.email}{me?.email_verified ? " (verified)" : " (not verified)"}.</p>
        {/* Rendered only once the state list has loaded, so the saved state is selectable as the default. */}
        {states.length === 0 ? <p aria-live="polite">Loading…</p> : (
        <form className="stack" onSubmit={saveProfile}>
          <label className="field">Name<input name="display_name" defaultValue={s.display_name} maxLength={120} /></label>
          <label className="field">Language
            <select name="preferred_language" defaultValue={s.preferred_language}>
              {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>
          </label>
          <label className="field">Country<input value="India" disabled /></label>
          <label className="field">State or union territory
            <span className="hint">Used as the default for new cases. Each case still asks where it happened.</span>
            <select name="state_code" defaultValue={s.state_code ?? ""}>
              <option value="">Not set</option>
              {states.map((j) => <option key={j.code} value={j.code}>{j.name}</option>)}
            </select>
          </label>
          <label className="field">Keep my case data
            <select name="retention" defaultValue={s.retention_days === null ? "keep" : String(s.retention_days)}>
              <option value="keep">Until I delete it</option>
              <option value="90">Delete closed cases after 90 days</option>
              <option value="365">Delete closed cases after 1 year</option>
              <option value="1095">Delete closed cases after 3 years</option>
            </select>
            <span className="hint">Automatic purging runs as a scheduled job, which is not yet enabled in this build.</span>
          </label>
          <div><button className="btn">Save profile</button></div>
        </form>
        )}
      </section>

      <section className="card">
        <h2>Consent</h2>
        <label className="check">
          <input type="checkbox" checked={s.consent_ai_processing}
            onChange={(e) => save({ consent_ai_processing: e.target.checked }, "Consent")} />
          <span>Allow JUSTICE AI to process my case information with AI models to answer my questions. (Required for AI features once they launch.)</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={s.consent_training_use}
            onChange={(e) => save({ consent_training_use: e.target.checked }, "Consent")} />
          <span>Allow my de-identified conversations to be used to improve the service. Off by default; private case documents are never used for training.</span>
        </label>
        {s.consent_updated_at && <p className="muted">Last changed {new Date(s.consent_updated_at).toLocaleString()}.</p>}
      </section>

      <section className="card">
        <h2>Plan</h2>
        <p>Current plan: <strong>{myPlan?.name ?? me?.plan_code}</strong></p>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Plan</th><th>Price</th><th>Open cases</th><th>AI questions / month</th></tr></thead>
            <tbody>
              {plans.map((p) => (
                <tr key={p.code}>
                  <td><strong>{p.name}</strong><div className="muted">{p.description}</div></td>
                  <td>{p.price_minor === 0 ? "Free" : p.price_minor === null ? "Pricing not yet announced"
                    : `${(p.price_minor / 100).toLocaleString("en-IN", { style: "currency", currency: p.currency })} / ${p.billing_interval}`}</td>
                  <td>{p.entitlements.max_open_cases ?? "Unlimited"}</td>
                  <td>{p.entitlements.ai_questions_per_month ?? "Unlimited"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted">Online payment is not available yet. Emergency information and public legal rights are always free.</p>
      </section>

      <section className="card">
        <h2>Your data</h2>
        <div className="row">
          <a className="btn btn-secondary" href="/api/account/export" download>Download my data (JSON)</a>
          <button className="btn btn-secondary" onClick={async () => {
            await api("/api/auth/logout-all", { method: "POST" }).catch(setError);
            setMe(null);
            router.push("/login");
          }}>Sign out of all devices</button>
        </div>
      </section>

      <section className="card">
        <h2>Delete account</h2>
        <p>This permanently deletes your account, settings and every case. A minimal security record that the deletion happened is kept.</p>
        <form className="stack" onSubmit={deleteAccount}>
          <label className="field">Password<input name="password" type="password" autoComplete="current-password" required /></label>
          <label className="field">Type DELETE MY ACCOUNT to confirm<input name="confirm_text" required autoComplete="off" /></label>
          <div><button className="btn btn-danger">Delete my account</button></div>
        </form>
      </section>
    </>
  );
}
