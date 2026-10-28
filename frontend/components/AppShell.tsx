"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { LANGUAGES, useI18n } from "@/lib/i18n";

const NAV = [
  { href: "/", key: "nav.home" },
  { href: "/ask", key: "nav.ask" },
  { href: "/rights", key: "nav.rights" },
  { href: "/advocate", key: "nav.advocate" },
  { href: "/lawyer", key: "nav.lawyer" },
  { href: "/judge", key: "nav.judge" },
  { href: "/documents", key: "nav.documents" },
  { href: "/find-lawyer", key: "nav.findLawyer" },
  { href: "/legal-aid", key: "nav.legalAid" },
  { href: "/cases", key: "nav.cases" },
  { href: "/library", key: "nav.library" },
  { href: "/settings", key: "nav.settings" },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const { t, lang, setLang } = useI18n();
  const { me, setMe } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => setOpen(false), [pathname]);

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  const isStaff = !!me && me.roles.length > 0;

  async function signOut() {
    await api("/api/auth/logout", { method: "POST" }).catch(() => {});
    setMe(null);
    router.push("/");
  }

  async function changeLang(code: string) {
    setLang(code);
    if (me) await api("/api/account/settings", { method: "PATCH", body: { preferred_language: code } }).catch(() => {});
  }

  return (
    <>
      <a href="#main" className="skip-link">{t("nav.skip")}</a>
      <div className="emergency" role="note">
        <a href="tel:112">{t("emergency.banner")}</a>
      </div>
      <header className="topbar">
        <button
          className="menu-btn"
          aria-expanded={open}
          aria-controls="sidenav"
          onClick={() => setOpen((o) => !o)}
        >
          <span aria-hidden="true">☰</span> {t("nav.menu")}
        </button>
        <Link href="/" className="brand" aria-label="JUSTICE AI home">
          <span className="brand-mark" aria-hidden="true">⚖</span>
          <span>JUSTICE <span className="brand-ai">AI</span></span>
        </Link>
        <div className="topbar-right">
          <label className="lang">
            <span className="visually-hidden">{t("lang.label")}</span>
            <select value={lang} onChange={(e) => changeLang(e.target.value)}>
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>{l.label}</option>
              ))}
            </select>
          </label>
          {me ? (
            <>
              <span className="who" title={me.email}>{me.display_name || me.email}</span>
              <button className="btn btn-ghost" onClick={signOut}>{t("auth.signOut")}</button>
            </>
          ) : (
            <>
              <Link className="btn btn-ghost" href="/login">{t("auth.signIn")}</Link>
              <Link className="btn" href="/register">{t("auth.register")}</Link>
            </>
          )}
        </div>
      </header>
      <div className="layout">
        <nav id="sidenav" className={`sidenav ${open ? "open" : ""}`} aria-label="Main">
          <ul>
            {NAV.map((n) => (
              <li key={n.href}>
                <Link href={n.href} onClick={() => setOpen(false)} aria-current={isActive(n.href) ? "page" : undefined}>{t(n.key)}</Link>
              </li>
            ))}
            {isStaff && (
              <li className="nav-sep">
                <Link href="/admin" onClick={() => setOpen(false)} aria-current={isActive("/admin") ? "page" : undefined}>{t("nav.admin")}</Link>
              </li>
            )}
          </ul>
        </nav>
        <main id="main" tabIndex={-1}>
          {me && !me.email_verified && <VerifyBanner />}
          {children}
          <footer className="footer">
            <p>{t("disclaimer.short")}</p>
            <p className="muted">Jurisdiction: India. Other countries will be added only once their sources are verified.</p>
          </footer>
        </main>
      </div>
    </>
  );
}

function VerifyBanner() {
  const [state, setState] = useState<"idle" | "sent" | "error">("idle");
  return (
    <div className="alert alert-info" role="status">
      Please verify your email address to create case workspaces. Check your inbox for the link.{" "}
      <button
        className="linklike"
        disabled={state === "sent"}
        onClick={() =>
          api("/api/auth/resend-verification", { method: "POST" }).then(
            () => setState("sent"),
            () => setState("error"),
          )
        }
      >
        {state === "sent" ? "Sent again." : "Resend email"}
      </button>
      {state === "error" && " Could not resend right now; try again later."}
      {process.env.NODE_ENV !== "production" && (
        <>
          {" "}
          <Link href="/dev/outbox">Open development outbox</Link> (development only: no real email is sent)
        </>
      )}
    </div>
  );
}
