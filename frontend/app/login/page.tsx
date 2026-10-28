"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { FormError } from "@/components/FormError";
import { api, type Me } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

function LoginForm() {
  const { t } = useI18n();
  const { setMe } = useAuth();
  const router = useRouter();
  const next = useSearchParams().get("next");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const me = await api<Me>("/api/auth/login", {
        method: "POST",
        body: { email: f.get("email"), password: f.get("password") },
      });
      setMe(me);
      // Only same-site relative paths are honoured, to avoid open redirects.
      router.push(next && next.startsWith("/") && !next.startsWith("//") ? next : "/cases");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ maxWidth: "36rem" }}>
      <h1>{t("auth.signIn")}</h1>
      <FormError error={error} />
      <form className="stack" onSubmit={submit}>
        <label className="field">
          {t("auth.email")}
          <input name="email" type="email" autoComplete="email" required />
        </label>
        <label className="field">
          {t("auth.password")}
          <input name="password" type="password" autoComplete="current-password" required />
        </label>
        <div>
          <button className="btn" disabled={busy}>{busy ? "Signing in…" : t("auth.signIn")}</button>
        </div>
      </form>
      <p className="muted" style={{ marginTop: "1rem" }}>
        {t("auth.noAccount")} <Link href="/register">{t("auth.register")}</Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
