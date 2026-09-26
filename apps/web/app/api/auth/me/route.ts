import { NextResponse } from "next/server";

import { apiUnavailable, authToken, backendResponse, callAuthApi, clearAuthCookie } from "@/lib/auth-server";

export async function GET() {
  const token = await authToken();
  if (!token) return new NextResponse(null, { status: 204 });

  try {
    const response = await callAuthApi("/me", { headers: { Authorization: `Bearer ${token}` } });
    const body = await response.text();
    if (response.status === 401) await clearAuthCookie();
    return backendResponse(response, body);
  } catch {
    return apiUnavailable();
  }
}
