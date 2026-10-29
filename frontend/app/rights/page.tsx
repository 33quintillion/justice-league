"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, MATTER_LABELS } from "@/lib/api";
import type { SourceCard } from "@/lib/library";

/**
 * Browse verified sources by area of life. Plain-language guides written by legal reviewers are a later
 * step; until then this shows only what is verified, and says so, rather than generating explanations.
 */
export default function RightsPage() {
  const [sources, setSources] = useState<SourceCard[] | null>(null);
  useEffect(() => {
    api<SourceCard[]>("/api/library/sources").then(setSources, () => setSources([]));
  }, []);

  const byArea = new Map<string, SourceCard[]>();
  for (const s of sources ?? []) for (const a of s.practice_areas) byArea.set(a, [...(byArea.get(a) ?? []), s]);

  return (
    <>
      <h1>My Legal Rights</h1>
      <p>
        Choose an area to see the verified laws and judgments we hold for it. This information is always free.
      </p>
      <div className="alert alert-info" role="note">
        Plain-language rights guides are being written and reviewed by legal researchers. Until each guide is ready, we
        show the verified official texts only, rather than an unreviewed summary.
      </div>
      {sources === null ? (
        <p aria-live="polite">Loading…</p>
      ) : (
        <div className="grid">
          {Object.entries(MATTER_LABELS).map(([k, label]) => {
            const list = byArea.get(k) ?? [];
            return (
              <section key={k} className="tile" aria-labelledby={`area-${k}`}>
                <h2 id={`area-${k}`}>{label}</h2>
                {list.length === 0 ? (
                  <p>No verified sources yet.</p>
                ) : (
                  <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
                    {list.map((s) => <li key={s.id}><Link href={`/library/sources/${s.id}`}>{s.title}</Link></li>)}
                  </ul>
                )}
                {list.length > 0 && <p><Link href={`/library?area=${k}`}>Search this area</Link></p>}
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}
