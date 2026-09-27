import type { LoginRequest, SignupRequest, UserPublic } from "@canary-pact/contracts/generated";

type AuthResponse = { user: UserPublic; expires_at: string };

export function safeReturnTo(value?: string) {
  // Backslashes and control characters can normalize into an external URL.
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || /[\\\x00-\x20]/.test(value)) return "/simulate";
  const pathname = new URL(value, "https://canary.invalid").pathname;
  if (/^\/(login|signup|api)(\/|$)/.test(pathname)) return "/simulate";
  return value;
}

async function authError(response: Response, fallback: string): Promise<Error> {
  try {
    const body = (await response.json()) as { detail?: string | Array<{ msg?: string }> };
    if (typeof body.detail === "string") return new Error(body.detail);
    return new Error(body.detail?.[0]?.msg ?? fallback);
  } catch {
    return new Error(fallback);
  }
}

async function submitAuth(path: "login" | "signup", request: LoginRequest | SignupRequest): Promise<AuthResponse> {
  const response = await fetch(`/api/auth/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw await authError(response, "Could not authenticate");
  return response.json() as Promise<AuthResponse>;
}

export function login(request: LoginRequest) { return submitAuth("login", request); }
export function signup(request: SignupRequest) { return submitAuth("signup", request); }

export async function getCurrentUser(): Promise<UserPublic | null> {
  const response = await fetch("/api/auth/me", { cache: "no-store" });
  if (response.status === 204 || response.status === 401) return null;
  if (!response.ok) throw await authError(response, "Could not load your account");
  return response.json() as Promise<UserPublic>;
}

export async function logout(): Promise<void> {
  const response = await fetch("/api/auth/logout", { method: "POST" });
  if (!response.ok) throw await authError(response, "Could not sign out");
}
