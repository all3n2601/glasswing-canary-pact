import "server-only";

import type { AuthToken, UserPublic } from "@canary-pact/contracts/generated";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { NextResponse } from "next/server";
import { cache } from "react";

export const AUTH_COOKIE = "canary_session";

const API_URL = process.env.CANARY_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function callAuthApi(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_URL}/auth${path}`, {
    ...init,
    cache: "no-store",
    signal: init?.signal ?? AbortSignal.timeout(5_000),
    headers: { Accept: "application/json", ...init?.headers },
  });
}

export async function authToken(): Promise<string | null> {
  return (await cookies()).get(AUTH_COOKIE)?.value ?? null;
}

// Deduplicate verification within a render, never across users or requests.
export const getSession = cache(async (): Promise<{ user: UserPublic | null; unavailable: boolean }> => {
  const token = await authToken();
  if (!token) return { user: null, unavailable: false };
  try {
    const response = await callAuthApi("/me", { headers: { Authorization: `Bearer ${token}` } });
    if (response.status === 401) return { user: null, unavailable: false };
    if (!response.ok) return { user: null, unavailable: true };
    return { user: await response.json() as UserPublic, unavailable: false };
  } catch {
    return { user: null, unavailable: true };
  }
});

// Call before fetching workspace data, outside page-level try/catch blocks.
// An outage must not be mistaken for an expired session.
export async function requireUser(returnTo: string): Promise<UserPublic | null> {
  const session = await getSession();
  if (session.unavailable) return null;
  if (!session.user) redirect(`/login?next=${encodeURIComponent(returnTo)}`);
  return session.user;
}

export function apiUnavailable() {
  return NextResponse.json(
    { detail: "Authentication is temporarily unavailable. Please try again." },
    { status: 503 },
  );
}

export function backendResponse(response: Response, body: string) {
  return new NextResponse(body || null, {
    status: response.status,
    headers: body ? { "Content-Type": response.headers.get("content-type") ?? "application/json" } : undefined,
  });
}

export async function setAuthCookie(token: AuthToken) {
  (await cookies()).set(AUTH_COOKIE, token.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    expires: new Date(token.expires_at),
    priority: "high",
  });
}

export async function clearAuthCookie() {
  (await cookies()).delete(AUTH_COOKIE);
}
