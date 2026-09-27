import type { OrganizationProfile } from "@canary-pact/contracts";
import type { DecisionPackage, Impact } from "@canary-pact/contracts/generated";

export type DepartmentImpactTone = "source" | "positive" | "negative" | "neutral";

export interface DepartmentSimulationView {
  departmentId: string;
  name: string;
  mission: string;
  headcount: number;
  annualBudgetUsd: number;
  utilisation: number;
  maturityLevel: number;
  position: [number, number, number];
  tone: DepartmentImpactTone;
  label: string;
  strength: number;
  startsAt: number;
  severity: "Protected" | "Low" | "Medium" | "High";
  confidence?: number;
  summary: string;
  workflows: string[];
  kpis: Array<{ label: string; value: string }>;
  dependencyPath: string[];
  evidence: string[];
  mitigation: string;
}

const fixedPositions: Record<string, [number, number, number]> = {
  dept_finance: [-7.6, 0.08, -5.65],
  dept_engineering: [0, 0.08, -5.65],
  dept_ai_data: [7.6, 0.08, -5.65],
  dept_marketing: [-8.6, 0.08, 0],
  dept_operations: [-4.4, 0.08, 5.65],
  dept_people: [4.4, 0.08, -0.3],
  dept_compliance: [8.6, 0.08, 0],
  dept_sales: [0, 0.08, 5.65],
  dept_customer: [7.6, 0.08, 5.65],
  dept_customer_success: [7.6, 0.08, 5.65],
};

function fallbackPosition(index: number): [number, number, number] {
  const positions: Array<[number, number, number]> = [
    [-10.4, 0.08, -3.1],
    [-10.4, 0.08, 3.1],
    [10.4, 0.08, -3.1],
    [10.4, 0.08, 3.1],
    [-4.4, 0.08, -0.3],
    [4.4, 0.08, 3.25],
  ];
  return positions[index % positions.length];
}

export function buildDepartmentSimulation(profile: OrganizationProfile): DepartmentSimulationView[] {
  let fallbackIndex = 0;
  return profile.departments
    .filter((department) => department.enabled)
    .map((department) => ({
      departmentId: department.department_id,
      name: department.name,
      mission: department.mission,
      headcount: department.actual_fte,
      annualBudgetUsd: department.annual_budget_usd,
      utilisation: department.utilisation,
      maturityLevel: department.maturity_level,
      position: fixedPositions[department.department_id] ?? fallbackPosition(fallbackIndex++),
      tone: "neutral",
      label: "No material impact",
      strength: 0.25,
      startsAt: 90,
      severity: "Protected",
      confidence: undefined,
      summary: "No material impact has been reported for this department.",
      workflows: [],
      kpis: [],
      dependencyPath: [department.name],
      evidence: [],
      mitigation: "Continue monitoring as the scenario changes.",
    }));
}

function severityLabel(severity: number): DepartmentSimulationView["severity"] {
  if (severity >= 4) return "High";
  if (severity >= 2.5) return "Medium";
  return severity > 0 ? "Low" : "Protected";
}

function formatImpact(impact: Impact) {
  const amount = Math.abs(impact.magnitude);
  const formatted = impact.unit === "usd"
    ? `$${amount >= 1_000_000 ? `${(amount / 1_000_000).toFixed(1)}M` : `${Math.round(amount / 1_000)}K`}`
    : `${Number.isInteger(amount) ? amount : amount.toFixed(2)} ${impact.unit}`;
  return `${impact.direction === "decrease" ? "−" : "+"}${formatted}`;
}

export function applyDecisionPackage(baseline: DepartmentSimulationView[], decisionPackage: DecisionPackage): DepartmentSimulationView[] {
  const result = decisionPackage.portfolios.recommended?.result ?? decisionPackage.portfolios.naive.result;
  const impacts = result.impacts ?? [];
  const summaries = new Map((decisionPackage.department_impacts ?? []).map((summary) => [summary.department_id, summary]));
  const sourceDepartments = new Set(
    decisionPackage.brief.candidate_interventions
      .map((intervention) => intervention.target_entity_id)
      .filter((id) => baseline.some((department) => department.departmentId === id)),
  );
  const implementation = decisionPackage.implementation?.[0]?.action;

  return baseline.map((department) => {
    const departmentImpacts = impacts.filter((impact) => impact.affected_department === department.departmentId);
    const summary = summaries.get(department.departmentId);
    if (!summary && departmentImpacts.length === 0) return department;
    const severity = Math.max(summary?.severity ?? 0, ...departmentImpacts.map((impact) => impact.severity));
    const tone: DepartmentImpactTone = sourceDepartments.has(department.departmentId)
      ? "source"
      : departmentImpacts.some((impact) => impact.polarity === "harm")
        ? "negative"
        : departmentImpacts.some((impact) => impact.polarity === "benefit")
          ? "positive"
          : "neutral";
    const confidences = departmentImpacts.map((impact) => impact.confidence);
    const path = departmentImpacts.map((impact) => impact.dependency_path ?? []).sort((left, right) => right.length - left.length)[0] ?? [];

    return {
      ...department,
      tone,
      label: summary?.headline ?? departmentImpacts[0]?.metric.replaceAll("_", " ") ?? "Modeled impact",
      strength: Math.max(0.25, Math.min(1, severity / 5)),
      startsAt: Math.min(...departmentImpacts.map((impact) => impact.first_effect_day), 90),
      severity: severityLabel(severity),
      confidence: confidences.length ? confidences.reduce((sum, value) => sum + value, 0) / confidences.length : undefined,
      summary: summary?.headline ?? departmentImpacts.map((impact) => impact.metric.replaceAll("_", " ")).join(", "),
      workflows: [...new Set(departmentImpacts.map((impact) => impact.affected_entity))].slice(0, 4),
      kpis: departmentImpacts.slice(0, 2).map((impact) => ({ label: impact.metric.replaceAll("_", " "), value: formatImpact(impact) })),
      dependencyPath: path.length ? path : [department.name],
      evidence: [...new Set(departmentImpacts.flatMap((impact) => impact.evidence_refs ?? []))],
      mitigation: implementation ?? "Continue monitoring this department against the decision package.",
    };
  });
}
