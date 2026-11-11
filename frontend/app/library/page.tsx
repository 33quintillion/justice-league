"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import { FormError } from "@/components/FormError";
import { Snippet, SourceMeta, Warnings } from "@/components/Sources";
import { api, MATTER_LABELS } from "@/lib/api";
import type { SearchResponse, SourceCard } from "@/lib/library";
import { SOURCE_TYPE_LABELS } from "@/lib/library";
import { useJurisdictions } from "@/lib/useJurisdictions";

export default function LibraryPage() {
  return (
    <Suspense>
      <Library />
    </Suspense>
  );
}

function Library() {
  const params = useSearchParams();
  const router = useRouter();
  const jurisdictions = useJurisdictions();
  const q = params.get("q") ?? "";
  const jur = params.get("jurisdiction") ?? "";
  const area = params.get("area") ?? "";
  const type = params.get("type") ?? "";
  const [res, setRes] = useState<SearchResponse | null>(null);
  const [all, setAll] = useState<SourceCard[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setError(null);
    if (q.trim().length < 2) {
      setRes(null);
      api<SourceCard[]>("/api/library/sources").then(setAll, setError);
      return;
    }
    const sp = new URLSearchParams({ q });
    if (jur) sp.set("jurisdiction", jur);
    if (area) sp.set("practice_area", area);
    if (type) sp.set("source_type", type);
    setBusy(true);
    api<SearchResponse>(`/api/library/search?${sp}`).then(setRes, setError).finally(() => setBusy(false));
  }, [q, jur, area, type]);

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const sp = new URLSearchParams();
    for (const k of ["q", "jurisdiction", "area", "type"]) {
      const v = String(f.get(k) ?? "").trim();
      if (v) sp.set(k, v);
    }
    router.push(`/library?${sp}`);
  }

  return (
    <>
      <h1>Legal Library</h1>
      <p>
        Search the official legal texts our reviewers have verified. Every result links to its original source. The
        library is still small, so if nothing matches, that does not mean no law applies.
      </p>
      <form className="card" onSubmit={submit} role="search" key={`${q}|${jur}|${area}|${type}`}>
        <div className="search-bar">
          <label className="visually-hidden" htmlFor="q">Search the law</label>
          <input id="q" name="q" type="search" defaultValue={q} placeholder="e.g. refund of security deposit" minLength={2} maxLength={300} />
          <button className="btn" disabled={busy}>{busy ? "Searching…" : "Search"}</button>
        </div>
        <div className="filters">
          <label className="field">Where
            <select name="jurisdiction" defaultValue={jur}>
              <option value="">All of India</option>
              {jurisdictions.map((j) => (
                <option key={j.code} value={j.code}>{j.kind === "country" ? "Central law only" : `${j.name} (+ central law)`}</option>
              ))}
            </select>
          </label>
          <label className="field">Area
            <select name="area" defaultValue={area}>
              <option value="">All areas</option>
              {Object.entries(MATTER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className="field">Type
            <select name="type" defaultValue={type}>
              <option value="">All types</option>
              {Object.entries(SOURCE_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
        </div>
      </form>
      <FormError error={error} />

      {res && (
        <section aria-live="polite" aria-label="Search results">
          {res.notes.map((n) => <div key={n} className="alert alert-info">{n}</div>)}
          {res.results.map((r) => (
            <article key={r.section_id} className="card result">
              <h3>
                <span className="ref">{r.ref}</span>
                {r.heading && <> · {r.heading}</>}
              </h3>
              <p className="muted">
                <Link href={`/library/sources/${r.source.id}#s-${r.section_id}`}>{r.source.title}</Link>
              </p>
              <p><Snippet text={r.snippet} /></p>
              <Warnings warnings={r.warnings} />
              <SourceMeta s={r.source} />
            </article>
          ))}
        </section>
      )}

      {!res && all && (
        <section aria-label="All verified sources">
          <h2>Verified sources ({all.length})</h2>
          {all.length === 0 ? (
            <div className="card"><p>No sources have been verified yet. Our legal researchers add them from official government websites, and each one is checked by a second reviewer before it appears here.</p></div>
          ) : (
            all.map((s) => (
              <article key={s.id} className="card">
                <h3><Link href={`/library/sources/${s.id}`}>{s.title}</Link></h3>
                <Warnings warnings={s.warnings ?? []} />
                <SourceMeta s={s} />
              </article>
            ))
          )}
        </section>
      )}

      <CitationChecker />
    </>
  );
}

type Finding = { kind: string; text: string; status: string; message: string; source_id: string | null; section_id: string | null; official_url: string | null };

function CitationChecker() {
  const [out, setOut] = useState<{ all_verified: boolean; checked: number; findings: Finding[] } | null>(null);
  const [error, setError] = useState<unknown>(null);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    try {
      setOut(await api("/api/library/verify-citations", { method: "POST", body: { text: new FormData(e.currentTarget).get("text") } }));
    } catch (err) {
      setError(err);
    }
  }
  const label: Record<string, string> = {
    verified: "Verified", section_not_found: "Section not found", source_not_verified: "Not yet verified", not_found: "Cannot verify",
  };
  return (
    <section className="card" aria-labelledby="checker">
      <h2 id="checker">Check citations in a text</h2>
      <p className="muted">Paste a notice, a draft or an answer you received. We check section references, case citations and quotations against the verified library. Your text is not stored.</p>
      <form className="stack" onSubmit={submit} style={{ maxWidth: "none" }}>
        <label className="field">Text to check<textarea name="text" required maxLength={50000} /></label>
        <div><button className="btn">Check citations</button></div>
      </form>
      <FormError error={error} />
      {out && (
        <div aria-live="polite" style={{ marginTop: "1rem" }}>
          {out.checked === 0 ? (
            <p>No section references, case citations or quotations were found in this text.</p>
          ) : (
            <>
              <p><strong>{out.all_verified ? "Every citation matched a verified source." : "Some citations could not be verified. Do not rely on them until you have checked the official source."}</strong></p>
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>Citation</th><th>Result</th><th>Details</th></tr></thead>
                  <tbody>
                    {out.findings.map((f, i) => (
                      <tr key={i}>
                        <td>{f.kind === "quotation" ? `“${f.text}”` : f.text}</td>
                        <td><span className={`badge ${f.status === "verified" ? "badge-ok" : f.status === "not_found" ? "badge-err" : "badge-warn"}`}>{label[f.status] ?? f.status}</span></td>
                        <td>
                          {f.message}
                          {f.source_id && f.status === "verified" && (
                            <> <Link href={`/library/sources/${f.source_id}${f.section_id ? `#s-${f.section_id}` : ""}`}>Open</Link></>
                          )}
                          {f.official_url && <> · <a href={f.official_url} target="_blank" rel="noopener noreferrer">Official source ↗</a></>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
