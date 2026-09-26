import type { CompanyTwin, ScenarioRequest, ScenarioResult } from "@canary-pact/contracts";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getCompany(): Promise<CompanyTwin> {
  const response = await fetch(`${API_URL}/company`, { cache: "no-store" });
  if (!response.ok) throw new Error("Could not load the company twin");
  return response.json() as Promise<CompanyTwin>;
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
  if (!response.ok) throw new Error("Simulation failed");
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

