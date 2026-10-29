"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { SourceMeta, Warnings } from "@/components/Sources";
import { api, ApiError } from "@/lib/api";
import type { SourceCard, Warning } from "@/lib/library";

type Detail = SourceCard & {
  warnings: Warning[];
  sections: { id: string; ref: string; heading: string; text: string; warnings: Warning[] }[];
};

export default function SourcePage() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api<Detail>(`/api/library/sources/${id}`).then(setD, (e) =>
      setErr(e instanceof ApiError && e.status === 404 ? "This source is not in the verified library." : "Could not load this source."),
    );
  }, [id]);

  // Scroll to a linked section once the text has rendered.
  useEffect(() => {
    if (d && location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
  }, [d]);

  if (err) return <div className="alert alert-error" role="alert">{err} <Link href="/library">Back to the library</Link></div>;
  if (!d) return <p aria-live="polite">Loading…</p>;

  return (
    <>
      <p><Link href="/library">← Legal Library</Link></p>
      <h1>{d.title}</h1>
      <Warnings warnings={d.warnings} />
      <div className="card"><SourceMeta s={d} /></div>
      <p className="muted">
        This is our verified copy of the official text, split into sections for search. Always rely on the original
        source for filing or formal use; it may contain amendments, footnotes or schedules not shown here.
      </p>
      <nav className="card" aria-label="Sections">
        <h2>Contents</h2>
        <ul>{d.sections.map((s) => <li key={s.id}><a href={`#s-${s.id}`}>{s.ref}{s.heading && ` — ${s.heading}`}</a></li>)}</ul>
      </nav>
      {d.sections.map((s) => (
        <section key={s.id} id={`s-${s.id}`} className="card">
          <h2>{s.ref}{s.heading && <> · {s.heading}</>}</h2>
          <Warnings warnings={s.warnings} />
          <div className="section-text">{s.text}</div>
        </section>
      ))}
    </>
  );
}
