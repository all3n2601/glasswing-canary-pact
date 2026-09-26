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

export type Sector =
  | "technology_saas"
  | "financial_services"
  | "healthcare"
  | "professional_services"
  | "retail_consumer"
  | "manufacturing"
  | "public_sector"
  | "other";

export type BusinessModel = "b2b" | "b2c" | "b2b2c" | "marketplace" | "public_service" | "mixed";
export type SizeBand = "startup" | "smb" | "mid_market" | "enterprise" | "large_enterprise";
export type RiskAppetite = "conservative" | "balanced" | "aggressive";

export interface StrategicPriority {
  id: string;
  text: string;
  rank: number;
  kpi_ids: string[];
}

export interface Organization {
  id: string;
  legal_name: string;
  display_name: string;
  sector: Sector;
  sub_sector?: string;
  secondary_sectors: Sector[];
  business_model: BusinessModel;
  size_band: SizeBand;
  headquarters_country: string;
  operating_regions: string[];
  annual_revenue_usd: number;
  total_annual_budget_usd: number;
  total_headcount_fte: number;
  fiscal_year_start_month: number;
  regulatory_frameworks: string[];
  strategic_priorities: StrategicPriority[];
  description: string;
  evidence_refs: string[];
}

export interface DepartmentProfile {
  department_id: string;
  name: string;
  mission: string;
  actual_fte: number;
  annual_budget_usd: number;
  utilisation: number;
  maturity_level: number;
  enabled: boolean;
}

export interface OrganizationSettings {
  settings_id: string;
  organization_id: string;
  settings_version: number;
  updated_by: string;
  updated_at: string;
  display_currency: string;
  money_display_scale: "auto" | "K" | "M" | "B";
  timezone: string;
  locale: string;
  default_horizon_days: number;
  default_futures: Array<"act_now" | "inaction" | "delay">;
  default_delay_days: number;
  propagation_max_hops: number;
  min_impact_threshold: number;
  risk_appetite: RiskAppetite;
  risk_weights: {
    financial: number;
    capability_workflow: number;
    customer_revenue: number;
    compliance_control: number;
    execution_uncertainty: number;
  };
  optimizer_objective: "max_net_value" | "min_risk" | "balanced";
  always_protected_entity_ids: string[];
  require_human_approval: true;
  anonymize_people: true;
  llm_mode: "live" | "replay" | "mock";
  doc_staleness_days: number;
}

export interface OrganizationProfile {
  schema_version: "2.0.0";
  organization: Organization;
  departments: DepartmentProfile[];
  settings: OrganizationSettings;
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
