"use client";

import type { UserPublic } from "@canary-pact/contracts/generated";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { logout as logoutRequest } from "@/lib/auth";

type AuthContextValue = {
  user: UserPublic | null;
  loading: boolean;
  unavailable: boolean;
  setUser: (user: UserPublic) => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children, initialUser, unavailable }: {
  children: React.ReactNode;
  initialUser: UserPublic | null;
  unavailable: boolean;
}) {
  const [user, setUserState] = useState<UserPublic | null>(initialUser);

  useEffect(() => {
    if (!unavailable) setUserState(initialUser);
  }, [initialUser, unavailable]);

  const setUser = useCallback((nextUser: UserPublic) => {
    setUserState(nextUser);
  }, []);
  const logout = useCallback(async () => {
    await logoutRequest();
    setUserState(null);
  }, []);
  const value = useMemo(() => ({ user, loading: false, unavailable, setUser, logout }), [unavailable, logout, setUser, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
