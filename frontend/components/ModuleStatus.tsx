"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/**
 * Honest placeholder for a module that is not built yet: says what it will do, which phase delivers it,
 * and whether its feature flag is on. It offers no buttons that pretend to work.
 */
export function ModuleStatus(props: {
  title: string;
  flag: string;
  phase: string;
  purpose: string;
  planned: string[];
  safeguards?: string[];
  freeForever?: boolean;
}) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  useEffect(() => {
    api<Record<string, boolean>>("/api/features").then((f) => setEnabled(!!f[props.flag]), () => setEnabled(null));
  }, [props.flag]);

  return (
    <>
      <h1>
        {props.title} <span className="badge badge-warn">Not available yet · {props.phase}</span>
      </h1>
      <p>{props.purpose}</p>
      <div className="alert alert-info" role="status">
        This module is still being built, so it cannot answer questions or produce documents yet. We would rather
        show you nothing than an answer that is not grounded in verified legal sources.
        {enabled && " (Its feature flag is switched on, but the module code has not shipped in this build.)"}
      </div>
      <div className="card">
        <h2>What it will do</h2>
        <ul>{props.planned.map((p) => <li key={p}>{p}</li>)}</ul>
      </div>
      {props.safeguards && (
        <div className="card">
          <h2>Safeguards</h2>
          <ul>{props.safeguards.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
      )}
      {props.freeForever && (
        <p className="muted">This information will always be free. Essential rights and emergency information are never behind a paid plan.</p>
      )}
      <p>
        Meanwhile you can <Link href="/cases">organise your matter in My Cases</Link>.
      </p>
    </>
  );
}
