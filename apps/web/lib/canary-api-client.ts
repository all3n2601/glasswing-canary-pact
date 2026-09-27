import type {
  QuickOfficePreview,
  Evidence,
  DepartmentSave,
  OrganizationSave,
  RunEventPage,
  DecisionBrief,
  DecisionCreated,
  DecisionDraft,
  DecisionPromptRequest,
  DecisionPackage,
  DepartmentContextItemCreate,
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
  officePreview: (input: QuickSimulateRequest) => request<QuickOfficePreview>("/simulate/office-preview", {method:"POST",body:JSON.stringify(input)}),
  packageHash: async (runId: string) => {
    const response = await fetch(`${API_ROOT}/runs/${encodeURIComponent(runId)}/package`, {cache:"no-store"});
    if (!response.ok) throw new CanaryApiError(response.status,"Could not retrieve the decision package for approval");
    const digest = await crypto.subtle.digest("SHA-256",new TextEncoder().encode(await response.text()));
    return [...new Uint8Array(digest)].map(value=>value.toString(16).padStart(2,"0")).join("");
  },
  officeEvidence: (runId: string, evidenceId: string, signal?: AbortSignal) => request<Evidence>(`/runs/${encodeURIComponent(runId)}/office-evidence/${encodeURIComponent(evidenceId)}`, {signal}),
  saveOrganization: (input: OrganizationSave) => request<OrganizationProfileView>("/organization/profile", {method:"POST",body:JSON.stringify(input)}),
  saveDepartment: (input: DepartmentSave) => request<OrganizationProfileView>("/departments/save", {method: "POST", body: JSON.stringify(input)}),
  officeGraph: (runId: string) => request<DomainGraph>(`/runs/${encodeURIComponent(runId)}/office-graph`),
  officeDepartment: (runId: string, id: string) => request<DepartmentDetail>(`/runs/${encodeURIComponent(runId)}/office-departments/${encodeURIComponent(id)}`),
  officeProfile: (runId: string) => request<OrganizationProfileView>(`/runs/${encodeURIComponent(runId)}/office-profile`),
  eventLog: (runId: string, after: number, signal?: AbortSignal) => request<RunEventPage>(`/runs/${encodeURIComponent(runId)}/event-log?after_sequence=${after}`, {signal}),
  health: () => request<HealthResponse>("/health"),
  company: () => request<Twin>("/company"),
  companyGraph: (level: "entity" | "domain" = "entity") => request<DomainGraph>(`/company/graph?level=${level}`),
  pressures: () => request<Pressure[]>("/company/pressures"),
  organization: () => request<Organization>("/organization"),
  organizationSettings: () => request<OrganizationSettings>("/organization/settings"),
  organizationProfile: () => request<OrganizationProfileView>("/organization/profile"),
  departments: () => request<DepartmentProfile[]>("/departments"),
  department: (departmentId: string) => request<DepartmentDetail>(`/departments/${encodeURIComponent(departmentId)}`),
  addDepartmentContext: (departmentId: string, input: DepartmentContextItemCreate) =>
    request<DepartmentDetail>(`/departments/${encodeURIComponent(departmentId)}/context`, { method: "POST", body: JSON.stringify(input) }),
  documents: (query = "") => request<Document[]>(`/documents${query ? `?${query}` : ""}`),
  document: (documentId: string) => request<Document>(`/documents/${encodeURIComponent(documentId)}`),
  createDecision: (brief: DecisionBrief) =>
    request<DecisionCreated>("/decisions", { method: "POST", body: JSON.stringify(brief) }),
  draftDecision: (input: DecisionPromptRequest) =>
    request<DecisionDraft>("/decisions/draft", { method: "POST", body: JSON.stringify(input) }),
  run: (runId: string, signal?: AbortSignal) => request<RunState>(`/runs/${encodeURIComponent(runId)}`, {signal}),
  package: (runId: string, signal?: AbortSignal) => request<DecisionPackage>(`/runs/${encodeURIComponent(runId)}/package`, {signal}),
  decide: (runId: string, decision: HumanDecisionRequest) => request<HumanDecision>(`/runs/${encodeURIComponent(runId)}/decision`, { method: "POST", body: JSON.stringify(decision) }),
  quickSimulate: (input: QuickSimulateRequest) => request<SimulationResult>("/simulate/quick", { method: "POST", body: JSON.stringify(input) }),
  compareFutures: (input: FuturesRequest) => request<FutureComparison>("/simulate/futures", { method: "POST", body: JSON.stringify(input) }),
  optimize: (input: OptimizeRequest) => request<PortfolioComparison>("/simulate/optimize", { method: "POST", body: JSON.stringify(input) }),
};

export async function waitForPackage(
  runId: string,
  timeoutMs = 300_000,
  onState?: (state: RunState) => void,
  signal?: AbortSignal,
): Promise<DecisionPackage> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    signal?.throwIfAborted();
    const state = await canaryApi.run(runId,signal);
    signal?.throwIfAborted();
    onState?.(state);
    if (state.status === "failed") throw new CanaryApiError(500, "The simulation run failed.");
    if (state.package_id) return canaryApi.package(runId,signal);
    await new Promise<void>((resolve, reject) => {
      const abort = () => {clearTimeout(timer);reject(signal?.reason ?? new DOMException("Canceled", "AbortError"));};
      const timer = setTimeout(() => {signal?.removeEventListener("abort",abort);resolve();},250);
      signal?.addEventListener("abort",abort,{once:true});
      if (signal?.aborted) abort();
    });
  }
  throw new CanaryApiError(504, "The simulation did not finish in time.");
}
