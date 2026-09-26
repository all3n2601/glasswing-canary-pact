import { NextResponse } from "next/server";

import { authToken, callAuthApi, clearAuthCookie } from "@/lib/auth-server";

export async function POST() {
  const token = await authToken();
  try {
    if (token) await callAuthApi("/logout", { method: "POST", headers: { Authorization: `Bearer ${token}` } });
  } catch {
    // The local session is still cleared if the API is temporarily unavailable.
  } finally {
    await clearAuthCookie();
  }
  return new NextResponse(null, { status: 204 });
}
