import type {
  DecisionBrief,
  DecisionCreated,
  DecisionDraft,
  DecisionPromptRequest,
  DecisionPackage,
  DepartmentDetail,
  DepartmentProfile,
  Document,
  DomainGraph,
  FutureComparison,
  FuturesRequest,
  HealthResponse,
  HumanDecision,
  HumanDecisionRequest,
  OptimizeRequest,
  Organization,
  OrganizationProfileView,
  OrganizationSettings,
  PortfolioComparison,
  Pressure,
  QuickSimulateRequest,
  ReplayInfo,
  ReplayStarted,
  RunState,
  SimulationResult,
  Twin,
} from "@canary-pact/contracts/generated";

const API_ROOT = "/api/canary";

export class CanaryApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "CanaryApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new CanaryApiError(response.status, payload?.detail ?? `Canary API request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const canaryApi = {
  health: () => request<HealthResponse>("/health"),
  company: () => request<Twin>("/company"),
  companyGraph: (level: "entity" | "domain" = "entity") => request<DomainGraph>(`/company/graph?level=${level}`),
  pressures: () => request<Pressure[]>("/company/pressures"),
  organization: () => request<Organization>("/organization"),
  organizationSettings: () => request<OrganizationSettings>("/organization/settings"),
  organizationProfile: () => request<OrganizationProfileView>("/organization/profile"),
  departments: () => request<DepartmentProfile[]>("/departments"),
  department: (departmentId: string) => request<DepartmentDetail>(`/departments/${encodeURIComponent(departmentId)}`),
  documents: (query = "") => request<Document[]>(`/documents${query ? `?${query}` : ""}`),
  document: (documentId: string) => request<Document>(`/documents/${encodeURIComponent(documentId)}`),
  createDecision: (brief: DecisionBrief, llmMode?: "live" | "replay" | "mock") =>
    request<DecisionCreated>(`/decisions${llmMode ? `?llm_mode=${llmMode}` : ""}`, { method: "POST", body: JSON.stringify(brief) }),
  draftDecision: (input: DecisionPromptRequest) =>
    request<DecisionDraft>("/decisions/draft", { method: "POST", body: JSON.stringify(input) }),
  run: (runId: string) => request<RunState>(`/runs/${encodeURIComponent(runId)}`),
  package: (runId: string) => request<DecisionPackage>(`/runs/${encodeURIComponent(runId)}/package`),
  decide: (runId: string, decision: HumanDecisionRequest) => request<HumanDecision>(`/runs/${encodeURIComponent(runId)}/decision`, { method: "POST", body: JSON.stringify(decision) }),
  quickSimulate: (input: QuickSimulateRequest) => request<SimulationResult>("/simulate/quick", { method: "POST", body: JSON.stringify(input) }),
  compareFutures: (input: FuturesRequest) => request<FutureComparison>("/simulate/futures", { method: "POST", body: JSON.stringify(input) }),
  optimize: (input: OptimizeRequest) => request<PortfolioComparison>("/simulate/optimize", { method: "POST", body: JSON.stringify(input) }),
  replays: () => request<ReplayInfo[]>("/replays"),
  playReplay: (name: string, speed: 1 | 2 | 4 = 4) => request<ReplayStarted>(`/replays/${encodeURIComponent(name)}/play?speed=${speed}`, { method: "POST" }),
};

export async function waitForPackage(
  runId: string,
  timeoutMs = 30_000,
  onState?: (state: RunState) => void,
): Promise<DecisionPackage> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const state = await canaryApi.run(runId);
    onState?.(state);
    if (state.status === "failed") throw new CanaryApiError(500, "The simulation run failed.");
    if (state.package_id) return canaryApi.package(runId);
    await new Promise((resolve) => window.setTimeout(resolve, 250));
  }
  throw new CanaryApiError(504, "The simulation did not finish in time.");
}
