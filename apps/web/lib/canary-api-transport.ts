import "server-only";

export const API_URL = (process.env.CANARY_API_URL?.trim()
  || process.env.NEXT_PUBLIC_API_URL?.trim()
  || "http://localhost:8000").replace(/\/+$/, "");

// Server-rendered pages need the same outage recovery as browser-side reads.
// Keep this GET-only: retrying a write can create duplicate runs or accounts.
export async function readBackend(path: string, headers: HeadersInit): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    try {
      const response = await fetch(`${API_URL}${path}`, {
        headers,
        cache: "no-store",
        signal: AbortSignal.timeout(5_000),
      });
      if (![408, 429, 502, 503, 504].includes(response.status)) return response;
      if (attempt === 1) {
        console.warn("Canary backend read unavailable", { path, status: response.status });
        return response;
      }
      await response.body?.cancel();
    } catch (error) {
      if (attempt === 1) {
        // Do not log credentials, response bodies, or the configured backend URL.
        console.warn("Canary backend read unavailable", {
          path, reason: error instanceof Error ? error.name : "NetworkError",
        });
        throw error;
      }
    }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
}
