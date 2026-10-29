"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import { FormError } from "@/components/FormError";
import { api } from "@/lib/api";
import type { AIStatus, Answer, AnswerSummary, Role, Statement, Urgency } from "@/lib/ai";
import { SECTIONS, STATUS_LABELS } from "@/lib/ai";
import { useAuth } from "@/lib/auth";

type CaseLite = { id: string; title: string; status: string };

export function AIRole(props: { role: Role; title: string; intro: string; safeguards: string[]; placeholder: string }) {
  return (
    <Suspense>
      <AIRoleInner {...props} />
    </Suspense>
  );
}

function AIRoleInner({ role, title, intro, safeguards, placeholder }: { role: Role; title: string; intro: string; safeguards: string[]; placeholder: string }) {
  const { me, loading } = useAuth();
  const params = useSearchParams();
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [consent, setConsent] = useState<boolean | null>(null);
  const [usage, setUsage] = useState<{ used: number; limit: number | null } | null>(null);
  const [cases, setCases] = useState<CaseLite[] | null>(null);
  const [history, setHistory] = useState<AnswerSummary[]>([]);
  const [caseId, setCaseId] = useState(params.get("case") ?? "");
  const [urgency, setUrgency] = useState<Urgency | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const spec = status?.roles[role];

  useEffect(() => {
    api<AIStatus>("/api/ai/status").then(setStatus, setError);
  }, []);

  useEffect(() => {
    if (!me) return;
    api<{ consent_ai_processing: boolean }>("/api/account/settings").then((s) => setConsent(s.consent_ai_processing), () => {});
    api<{ used: number; limit: number | null }>("/api/ai/usage").then(setUsage, () => {});
    api<AnswerSummary[]>(`/api/ai/answers/mine?role=${role}`).then(setHistory, () => {});
    if (role === "advocate" || role === "judge") api<CaseLite[]>("/api/cases").then((c) => setCases(c.filter((x) => x.status === "open")), () => {});
  }, [me, role]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const question = String(new FormData(e.currentTarget).get("question") ?? "").trim();
    setError(null);
    setAnswer(null);
    setBusy(true);
    // Urgent-help guidance first: it needs no AI and must never wait for an answer.
    api<Urgency>("/api/ai/urgency", { method: "POST", body: { text: question } }).then(setUrgency, () => {});
    try {
      const a = await api<Answer>(`/api/ai/${role}`, { method: "POST", body: { question, case_id: caseId || null } });
      setAnswer(a);
      setHistory((h) => [{ id: a.id, role: a.role, question: a.question, status: a.status, case_id: a.case_id, created_at: a.created_at }, ...h]);
      api<{ used: number; limit: number | null }>("/api/ai/usage").then(setUsage, () => {});
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function open(id: string) {
    setError(null);
    setUrgency(null);
    try {
      setAnswer(await api<Answer>(`/api/ai/answers/${id}`));
    } catch (err) {
      setError(err);
    }
  }

  async function remove(id: string) {
    if (!window.confirm("Delete this answer? Its content is erased and cannot be recovered.")) return;
    try {
      await api(`/api/ai/answers/${id}`, { method: "DELETE" });
      setHistory((h) => h.filter((x) => x.id !== id));
      if (answer?.id === id) setAnswer(null);
    } catch (err) {
      setError(err);
    }
  }

  let blocker: React.ReactNode = null;
  if (!status || loading) blocker = <p className="muted">Loading…</p>;
  else if (!spec?.enabled) blocker = (
    <div className="alert alert-info" role="status">{title} is built but not switched on yet. Administrators turn it on once it has been reviewed.</div>
  );
  else if (!status.configured) blocker = (
    <div className="alert alert-info" role="status">The AI service is not configured on this server yet, so {title} cannot generate answers. Nothing here will pretend to answer.</div>
  );
  else if (!me) blocker = <div className="alert alert-info"><Link href="/login">Sign in</Link> to use {title}. The <Link href="/library">Legal Library</Link> and <Link href="/rights">Know Your Rights</Link> are free without an account.</div>;
  else if (!me.email_verified) blocker = <div className="alert alert-info">Verify your email address to use {title}.</div>;
  else if (consent === false) blocker = (
    <div className="alert alert-info">To use {title}, allow AI processing in <Link href="/settings">Settings</Link>. Emergency help, rights information and the library stay available without it.</div>
  );
  else if (spec.needs_case && cases && cases.length === 0) blocker = (
    <div className="alert alert-info">{title} works on one of your cases. <Link href="/cases">Create a case</Link> first.</div>
  );

  return (
    <>
      <h1>{title}</h1>
      {role === "judge" && status && <p className="alert alert-error" role="note"><strong>{status.judge_label}</strong></p>}
      <p>{intro}</p>
      <details className="card">
        <summary><strong>How {title} keeps answers honest</strong></summary>
        <ul>{safeguards.map((s) => <li key={s}>{s}</li>)}</ul>
      </details>

      {urgency && urgency.level !== "none" && <UrgencyBanner u={urgency} />}

      {blocker ?? (
        <form className="card stack" onSubmit={submit} style={{ maxWidth: "none" }}>
          {spec?.needs_case && (
            <label className="field">Case
              <select value={caseId} onChange={(e) => setCaseId(e.target.value)} required>
                <option value="">Choose one of your cases</option>
                {cases?.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
              </select>
            </label>
          )}
          <label className="field">{spec?.needs_case ? "What would you like to know about this case?" : "Your question"}
            <textarea name="question" required minLength={5} maxLength={4000} placeholder={placeholder} />
          </label>
          <div className="row">
            <button className="btn" disabled={busy}>{busy ? "Checking sources and preparing an answer…" : spec?.needs_case ? "Analyse" : "Ask"}</button>
            {usage && <span className="muted">{usage.limit === null ? `${usage.used} answers this month` : `${usage.used} of ${usage.limit} answers used this month`}</span>}
          </div>
        </form>
      )}
      <FormError error={error} />
      {answer && <AnswerView a={answer} />}

      {history.length > 0 && (
        <section className="card" aria-labelledby="hist">
          <h2 id="hist">Your previous {title} answers</h2>
          <p className="muted">Only you can see these. Staff cannot read them.</p>
          <ul>
            {history.map((h) => (
              <li key={h.id}>
                <button className="linklike" onClick={() => open(h.id)}>{h.question}</button>{" "}
                <span className="muted">· {new Date(h.created_at).toLocaleString()} · {STATUS_LABELS[h.status] ?? h.status}</span>{" "}
                <button className="btn btn-secondary btn-small" onClick={() => remove(h.id)} aria-label={`Delete answer: ${h.question}`}>Delete</button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

function UrgencyBanner({ u }: { u: Urgency }) {
  return (
    <div className={`alert ${u.level === "emergency" ? "alert-error" : "alert-info"}`} role="alert">
      <p><strong>{u.level === "emergency" ? "This may be an emergency." : "This looks urgent."}</strong></p>
      <ul>{u.messages.map((m) => <li key={m}>{m}</li>)}</ul>
      <p>
        {u.call && <><a className="btn btn-danger" href={`tel:${u.call}`}>Call {u.call}</a>{" "}</>}
        {u.legal_aid_path && <Link href={u.legal_aid_path}>Free legal aid</Link>}
      </p>
    </div>
  );
}

function Cites({ ids, onPick }: { ids: string[]; onPick: (id: string) => void }) {
  if (!ids.length) return null;
  return (
    <>
      {" "}
      {ids.map((id) => (
        <a key={id} href={`#src-${id}`} className="badge badge-ok" onClick={() => onPick(id)} title="See the source">{id}</a>
      ))}
    </>
  );
}

export function AnswerView({ a }: { a: Answer }) {
  const [openSrc, setOpenSrc] = useState<string | null>(null);
  const r = a.response;
  const c = a.checks;
  const unverified = c.unverified_citations ?? [];
  return (
    <section className="card" aria-live="polite" aria-label={`${a.title} answer`}>
      {a.label && <p className="alert alert-error" role="note"><strong>{a.label}</strong></p>}
      {a.urgency?.level && a.urgency.level !== "none" && <UrgencyBanner u={a.urgency} />}
      <p>
        <span className={`badge ${a.status === "answered" ? "badge-ok" : "badge-warn"}`}>{STATUS_LABELS[a.status] ?? a.status}</span>
      </p>
      {typeof r.summary === "string" && r.summary && <p><strong>{r.summary}</strong></p>}

      {SECTIONS[a.role].map((s) => {
        const v = r[s.key];
        if (!v || (Array.isArray(v) && v.length === 0)) return null;
        return (
          <div key={s.key}>
            <h3>{s.title}</h3>
            {s.kind === "text" && <p>{v as string}</p>}
            {s.kind === "list" && <ul>{(v as string[]).map((t, i) => <li key={i}>{t}</li>)}</ul>}
            {s.kind === "statements" && (
              <ul>{(v as Statement[]).map((st, i) => <li key={i}>{st.text}<Cites ids={st.source_ids} onPick={setOpenSrc} /></li>)}</ul>
            )}
          </div>
        );
      })}

      {(unverified.length > 0 || (c.removed?.length ?? 0) > 0 || !!c.links_removed || !!c.numbers_removed) && (
        <div className="alert alert-info">
          <p><strong>Our checks changed or flagged parts of this answer</strong></p>
          <ul>
            {c.removed?.filter((x) => x.text).map((x, i) => <li key={`r${i}`}>Removed: “{x.text}”. {x.reason}</li>)}
            {c.removed?.filter((x) => !x.text).map((x, i) => <li key={`s${i}`}>{x.reason}</li>)}
            {unverified.map((u, i) => <li key={`u${i}`}>Could not verify “{u.text}”. {u.message}</li>)}
            {!!c.links_removed && <li>{c.links_removed} link(s) removed because they were not the official link of a verified source.</li>}
            {!!c.numbers_removed && <li>{c.numbers_removed} numeric estimate(s) removed. We do not give percentages or odds.</li>}
          </ul>
        </div>
      )}

      {a.sources.length > 0 && (
        <>
          <h3>Sources</h3>
          <p className="muted">The verified sections we gave the AI. Sections it relied on are marked “cited”.</p>
          <ul className="stack" style={{ maxWidth: "none", listStyle: "none", paddingLeft: 0 }}>
            {a.sources.map((s) => (
              <li key={s.label} id={`src-${s.label}`}>
                <details open={openSrc === s.label}>
                  <summary>
                    <span className={`badge ${s.cited ? "badge-ok" : ""}`}>{s.label}{s.cited ? " · cited" : ""}</span>{" "}
                    <strong>{s.ref}</strong>, {s.title}
                  </summary>
                  <p className="section-text">{s.text}</p>
                  <p className="muted">
                    <a href={s.official_url} target="_blank" rel="noopener noreferrer">View original source ↗</a>
                    {s.source_id && <> · <Link href={`/library/sources/${s.source_id}${s.section_id ? `#s-${s.section_id}` : ""}`}>Open in library</Link></>}
                    {s.document_sha256 && <> · document version <code>{s.document_sha256.slice(0, 12)}</code></>}
                  </p>
                </details>
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="disclaimer">{a.disclaimer}</p>
      {a.llm_called && <p className="muted">Generated by {a.model} · prompt {a.prompt_version}{c.served_by_fallback_model ? " · answered by a fallback model" : ""}</p>}
    </section>
  );
}
