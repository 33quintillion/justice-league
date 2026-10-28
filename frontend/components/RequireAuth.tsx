"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <p aria-live="polite">Loading…</p>;
  if (!me)
    return (
      <div className="card">
        <h1>Please sign in</h1>
        <p>This page holds private information, so you need to be signed in to see it.</p>
        <p>
          <Link className="btn" href="/login">Sign in</Link>{" "}
          <Link className="btn btn-secondary" href="/register">Create account</Link>
        </p>
      </div>
    );
  return <>{children}</>;
}
