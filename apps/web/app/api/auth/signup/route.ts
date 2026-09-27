import type { AuthToken, SignupRequest } from "@canary-pact/contracts/generated";
import { NextResponse } from "next/server";

import { apiUnavailable, backendResponse, callAuthApi, setAuthCookie } from "@/lib/auth-server";

export async function POST(request: Request) {
  try {
    const signup = JSON.parse(await request.text()) as SignupRequest;
    const signupResponse = await callAuthApi("/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(signup),
    });
    const signupBody = await signupResponse.text();
    if (!signupResponse.ok) return backendResponse(signupResponse, signupBody);

    const loginResponse = await callAuthApi("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: signup.email, password: signup.password }),
    });
    const loginBody = await loginResponse.text();
    if (!loginResponse.ok) return backendResponse(loginResponse, loginBody);

    const token = JSON.parse(loginBody) as AuthToken;
    await setAuthCookie(token);
    return NextResponse.json({ user: token.user, expires_at: token.expires_at }, { status: 201 });
  } catch (error) {
    if (error instanceof SyntaxError) return NextResponse.json({ detail: "Invalid sign-up request" }, { status: 400 });
    return apiUnavailable();
  }
}
