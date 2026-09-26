export type EntityKind =
  | "department"
  | "vendor"
  | "dataset"
  | "workflow"
  | "employee"
  | "system"
  | "kpi";

export interface Entity {
  id: string;
  kind: EntityKind;
  name: string;
  departmentId?: string;
  annualCost?: number;
  metadata: Record<string, unknown>;
}

export interface Dependency {
  source: string;
  target: string;
  relationship: string;
  importance: number;
  substitutability: number;
  confidence: number;
  evidence: string;
}

export interface CompanyTwin {
  id: string;
  name: string;
  version: string;
  entities: Entity[];
  dependencies: Dependency[];
}

export interface ScenarioRequest {
  title: string;
  objective: string;
  removeEntityIds: string[];
  savingsTarget: number;
  constraints: Record<string, number | string | boolean>;
}

export interface Impact {
  entityId: string;
  department: string;
  description: string;
  level: "direct" | "indirect" | "second_order";
  severity: "low" | "medium" | "high" | "critical";
  confidence: number;
  path: string[];
}

export interface ScenarioResult {
  scenarioId: string;
  status: "feasible" | "infeasible" | "needs_review";
  grossSavings: number;
  transitionCost: number;
  netSavings: number;
  impacts: Impact[];
  violations: string[];
  recommendation: string;
}

