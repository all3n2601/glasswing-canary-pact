import type { AuthToken } from "@canary-pact/contracts/generated";
import { NextResponse } from "next/server";

import { apiUnavailable, backendResponse, callAuthApi, setAuthCookie } from "@/lib/auth-server";

export async function POST(request: Request) {
  try {
    const response = await callAuthApi("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await request.text(),
    });
    const body = await response.text();
    if (!response.ok) return backendResponse(response, body);

    const token = JSON.parse(body) as AuthToken;
    await setAuthCookie(token);
    return NextResponse.json({ user: token.user, expires_at: token.expires_at });
  } catch {
    return apiUnavailable();
  }
}
