"use client";

import { useEffect, useState } from "react";
import { RequireAuth } from "@/components/RequireAuth";
import { api } from "@/lib/api";

type Mail = { subject: string; body: string; created_at: string };

function linkify(body: string) {
  return body.split(/(https?:\/\/\S+)/).map((part, i) =>
    /^https?:\/\//.test(part) ? <a key={i} href={part.replace(/^https?:\/\/[^/]+/, "")}>{part}</a> : part,
  );
}

export default function DevOutbox() {
  const [mails, setMails] = useState<Mail[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api<Mail[]>("/api/dev/outbox").then(setMails, () => setErr("The development outbox is not available on this server."));
  }, []);
  return (
    <RequireAuth>
      <h1>Development outbox <span className="badge badge-warn">Development only</span></h1>
      <p className="muted">No email provider is configured in development, so messages to your address are kept here instead of being sent.</p>
      {err && <div className="alert alert-error">{err}</div>}
      {mails?.length === 0 && <p>No messages.</p>}
      {mails?.map((m, i) => (
        <div key={i} className="card">
          <h2>{m.subject}</h2>
          <p className="muted">{new Date(m.created_at).toLocaleString()}</p>
          <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{linkify(m.body)}</pre>
        </div>
      ))}
    </RequireAuth>
  );
}
