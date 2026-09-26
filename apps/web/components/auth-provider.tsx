"use client";

import type { UserPublic } from "@canary-pact/contracts/generated";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { getCurrentUser, logout as logoutRequest } from "@/lib/auth";

type AuthContextValue = {
  user: UserPublic | null;
  loading: boolean;
  setUser: (user: UserPublic) => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUserState] = useState<UserPublic | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void getCurrentUser()
      .then((currentUser) => { if (active) setUserState(currentUser); })
      .catch(() => { if (active) setUserState(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const setUser = useCallback((nextUser: UserPublic) => {
    setUserState(nextUser);
    setLoading(false);
  }, []);
  const logout = useCallback(async () => {
    await logoutRequest();
    setUserState(null);
  }, []);
  const value = useMemo(() => ({ user, loading, setUser, logout }), [loading, logout, setUser, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
