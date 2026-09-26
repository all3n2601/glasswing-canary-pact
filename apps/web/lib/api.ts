import type { CompanyTwin, ScenarioRequest, ScenarioResult } from "@canary-pact/contracts";
import type { AgentOutput } from "@canary-pact/contracts/generated";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getCompany(): Promise<CompanyTwin> {
  const response = await fetch(`${API_URL}/scenarios/company`, { cache: "no-store" });
  if (!response.ok) throw new Error("Could not load the company twin");
  const company = await response.json();
  return {
    id: company.organization.id,
    name: company.organization.display_name,
    version: company.version.twin_version,
    entities: company.entities.map((entity: Record<string, unknown>) => ({
      id: entity.id,
      kind: entity.type,
      name: entity.name,
      departmentId: entity.department_id,
      annualCost: entity.annual_cost_usd,
      metadata: {},
    })),
    dependencies: company.edges.map((edge: Record<string, unknown>) => ({
      source: edge.source,
      target: edge.target,
      relationship: edge.relation,
      importance: edge.strength,
      substitutability: edge.substitutability,
      confidence: edge.confidence,
      evidence: Array.isArray(edge.evidence_refs) ? edge.evidence_refs.join(", ") : "",
    })),
  } as CompanyTwin;
}

async function apiError(response: Response, fallback: string): Promise<Error> {
  try {
    const body = (await response.json()) as { detail?: string };
    return new Error(body.detail ?? fallback);
  } catch {
    return new Error(fallback);
  }
}

export async function simulateScenario(request: ScenarioRequest): Promise<ScenarioResult> {
  const response = await fetch(`${API_URL}/scenarios/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: request.title,
      objective: request.objective,
      remove_entity_ids: request.removeEntityIds,
      savings_target: request.savingsTarget,
      constraints: request.constraints,
    }),
  });
  if (!response.ok) throw await apiError(response, "Simulation failed");
  const result = await response.json();
  return {
    scenarioId: result.scenario_id,
    status: result.status,
    grossSavings: result.gross_savings,
    transitionCost: result.transition_cost,
    netSavings: result.net_savings,
    impacts: result.impacts.map((impact: Record<string, unknown>) => ({
      entityId: impact.entity_id,
      department: impact.department,
      description: impact.description,
      level: impact.level,
      severity: impact.severity,
      confidence: impact.confidence,
      path: impact.path,
    })),
    violations: result.violations,
    recommendation: result.recommendation,
  } as ScenarioResult;
}

export async function getScenarioAssessments(
  scenarioId: string,
): Promise<Record<string, AgentOutput>> {
  const response = await fetch(`${API_URL}/scenarios/${scenarioId}/assessments`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw await apiError(response, "Could not load department assessments");
  }
  return response.json() as Promise<Record<string, AgentOutput>>;
}
