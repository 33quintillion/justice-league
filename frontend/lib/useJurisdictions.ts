"use client";

import { useEffect, useState } from "react";
import { api } from "./api";

export type Jurisdiction = { code: string; name: string; kind: string; parent_code: string | null; enabled: boolean };

export function useJurisdictions() {
  const [list, setList] = useState<Jurisdiction[]>([]);
  useEffect(() => {
    api<Jurisdiction[]>("/api/jurisdictions").then(setList, () => setList([]));
  }, []);
  return list;
}
