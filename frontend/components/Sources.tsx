import { Fragment } from "react";
import type { SourceCard, Warning } from "@/lib/library";
import { AUTHORITY_LABELS, SOURCE_TYPE_LABELS } from "@/lib/library";

/** Renders search highlights (⟦…⟧ markers from the API) as <mark> without ever using innerHTML. */
export function Snippet({ text }: { text: string }) {
  return (
    <>
      {text.split(/(⟦[^⟧]*⟧)/).map((part, i) =>
        part.startsWith("⟦") ? <mark key={i}>{part.slice(1, -1)}</mark> : <Fragment key={i}>{part}</Fragment>,
      )}
    </>
  );
}

export function Warnings({ warnings }: { warnings: Warning[] }) {
  if (!warnings.length) return null;
  return (
    <ul className="warnings">
      {warnings.map((w, i) => (
        <li key={i} className={w.level === "severe" ? "warn-severe" : "warn-caution"}>
          <span aria-hidden="true">{w.level === "severe" ? "⚠" : "ⓘ"}</span> {w.text}
        </li>
      ))}
    </ul>
  );
}

const fmt = (d: string | null) => (d ? new Date(d).toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "numeric" }) : "—");

/** Source metadata shown beside every authority, with the official link. */
export function SourceMeta({ s }: { s: SourceCard }) {
  return (
    <div className="source-meta">
      <div className="row">
        <span className="badge">{SOURCE_TYPE_LABELS[s.source_type] ?? s.source_type}</span>
        <span className="badge">{AUTHORITY_LABELS[s.authority_level] ?? s.authority_level}</span>
        <span className="badge">{s.jurisdiction_code === "IN" ? "Central (India)" : s.jurisdiction_code}</span>
        <span className="badge badge-ok">Verified {fmt(s.last_verified_at)}</span>
      </div>
      <dl className="meta">
        {s.citation && (<><dt>Citation</dt><dd>{s.citation}</dd></>)}
        <dt>Legal status</dt><dd>{s.legal_status.replaceAll("_", " ")}</dd>
        <dt>Effective from</dt><dd>{fmt(s.effective_date)}</dd>
        <dt>Our copy obtained</dt><dd>{fmt(s.document_retrieved_at)}</dd>
      </dl>
      <a className="btn btn-small btn-secondary" href={s.official_url} target="_blank" rel="noopener noreferrer">
        View Original Source ↗
      </a>
    </div>
  );
}
