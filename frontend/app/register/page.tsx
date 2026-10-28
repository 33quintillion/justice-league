"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { FormError } from "@/components/FormError";
import { api, type Me } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function RegisterPage() {
  const { t } = useI18n();
  const { setMe } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const me = await api<Me>("/api/auth/register", {
        method: "POST",
        body: {
          email: f.get("email"),
          password: f.get("password"),
          display_name: f.get("display_name") ?? "",
          accept_terms: f.get("accept_terms") === "on",
        },
      });
      setMe(me);
      router.push("/cases");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ maxWidth: "38rem" }}>
      <h1>{t("auth.register")}</h1>
      <p className="muted">
        We only ask for what we need to secure your account. Please do not put passwords, banking details or unrelated
        sensitive information into JUSTICE AI.
      </p>
      <FormError error={error} />
      <form className="stack" onSubmit={submit}>
        <label className="field">
          {t("auth.displayName")}
          <input name="display_name" autoComplete="name" maxLength={120} />
        </label>
        <label className="field">
          {t("auth.email")}
          <input name="email" type="email" autoComplete="email" required />
        </label>
        <label className="field">
          {t("auth.password")}
          <span className="hint">At least 10 characters. A short phrase is easier to remember.</span>
          <input name="password" type="password" autoComplete="new-password" minLength={10} required />
        </label>
        <label className="check">
          <input name="accept_terms" type="checkbox" required />
          <span>
            I understand JUSTICE AI gives legal information, not legal advice, and I accept the terms and privacy notice.
            My private case information is never used to train AI models unless I separately opt in.
          </span>
        </label>
        <div>
          <button className="btn" disabled={busy}>{busy ? "Creating…" : t("auth.register")}</button>
        </div>
      </form>
      <p className="muted" style={{ marginTop: "1rem" }}>
        {t("auth.haveAccount")} <Link href="/login">{t("auth.signIn")}</Link>
      </p>
    </div>
  );
}
