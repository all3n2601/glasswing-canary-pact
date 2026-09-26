import "server-only";

import type { AuthToken } from "@canary-pact/contracts/generated";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export const AUTH_COOKIE = "canary_session";

const API_URL = process.env.CANARY_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function callAuthApi(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_URL}/auth${path}`, {
    ...init,
    cache: "no-store",
    headers: { Accept: "application/json", ...init?.headers },
  });
}

export async function authToken(): Promise<string | null> {
  return (await cookies()).get(AUTH_COOKIE)?.value ?? null;
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
