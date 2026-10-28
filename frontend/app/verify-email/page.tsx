"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function Verify() {
  const token = useSearchParams().get("token");
  const { refresh } = useAuth();
  const [state, setState] = useState<"working" | "done" | "error">("working");
  const [msg, setMsg] = useState("");
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    if (!token) {
      setState("error");
      setMsg("This link is missing its verification token.");
      return;
    }
    api("/api/auth/verify-email", { method: "POST", body: { token } }).then(
      () => {
        setState("done");
        refresh();
      },
      (e) => {
        setState("error");
        setMsg(e instanceof ApiError ? e.message : "Verification failed.");
      },
    );
  }, [token, refresh]);

  return (
    <div className="card" style={{ maxWidth: "36rem" }}>
      <h1>Email verification</h1>
      {state === "working" && <p aria-live="polite">Verifying…</p>}
      {state === "done" && (
        <div className="alert alert-ok" role="status">
          <p>Your email address is verified. <Link href="/cases">Go to My Cases</Link></p>
        </div>
      )}
      {state === "error" && <div className="alert alert-error" role="alert"><p>{msg}</p></div>}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Verify />
    </Suspense>
  );
}
