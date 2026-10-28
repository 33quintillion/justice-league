"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, type Me } from "./api";
import { useI18n } from "./i18n";

type Ctx = {
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<void>;
  setMe: (m: Me | null) => void;
  can: (perm: string) => boolean;
};

const AuthContext = createContext<Ctx>({
  me: null,
  loading: true,
  refresh: async () => {},
  setMe: () => {},
  can: () => false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const { setLang } = useI18n();

  const refresh = useCallback(async () => {
    try {
      setMe(await api<Me>("/api/auth/me"));
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // A signed-in user's saved language wins over the device default.
  useEffect(() => {
    if (!me) return;
    api<{ preferred_language: string }>("/api/account/settings")
      .then((s) => setLang(s.preferred_language))
      .catch(() => {});
  }, [me?.id, setLang]); // eslint-disable-line react-hooks/exhaustive-deps

  const can = useCallback((perm: string) => !!me?.permissions.includes(perm), [me]);
  return <AuthContext.Provider value={{ me, loading, refresh, setMe, can }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
