"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

export function useLoad<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const reload = useCallback(async () => {
    if (path) await api<T>(path).then(setData, setError);
  }, [path]);
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, error, setError, reload };
}
