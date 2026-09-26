import { NextResponse } from "next/server";

import { authToken } from "@/lib/auth-server";

const API_URL = process.env.CANARY_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const ALLOWED_PATHS = [
  /^health$/,
  /^company$/,
  /^company\/graph$/,
  /^company\/pressures$/,
  /^organization$/,
  /^organization\/settings$/,
  /^organization\/profile$/,
  /^departments$/,
  /^departments\/[A-Za-z0-9_-]+$/,
  /^documents$/,
  /^documents\/[A-Za-z0-9_-]+$/,
  /^decisions$/,
  /^decisions\/draft$/,
  /^runs\/[A-Za-z0-9_-]+$/,
  /^runs\/[A-Za-z0-9_-]+\/package$/,
  /^runs\/[A-Za-z0-9_-]+\/decision$/,
  /^simulate\/(quick|futures|optimize)$/,
  /^replays$/,
  /^replays\/[A-Za-z0-9_-]+\/play$/,
];

function allowed(path: string) {
  return ALLOWED_PATHS.some((pattern) => pattern.test(path));
}

async function proxy(request: Request, context: RouteContext<"/api/canary/[...path]">) {
  const { path: segments } = await context.params;
  const path = segments.join("/");
  if (!allowed(path)) return NextResponse.json({ detail: "API path is not available" }, { status: 404 });

  const incomingUrl = new URL(request.url);
  const token = await authToken();
  const headers = new Headers({ Accept: "application/json" });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  try {
    const response = await fetch(`${API_URL}/${path}${incomingUrl.search}`, {
      method: request.method,
      headers,
      body: request.method === "GET" ? undefined : await request.text(),
      cache: "no-store",
    });
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: { "Content-Type": response.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Canary API is temporarily unavailable" }, { status: 503 });
  }
}

export const GET = proxy;
export const POST = proxy;
