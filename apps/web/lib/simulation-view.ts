import { officePosition } from "./office-layout";
import type { OrganizationProfile } from "@canary-pact/contracts";
import type { DecisionPackage, Impact, SimulationResult } from "@canary-pact/contracts/generated";

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
  peaksAt?: number;
  severity: "Not assessed" | "Protected" | "Low" | "Medium" | "High";
  confidence?: number;
  summary: string;
  workflows: string[];
  kpis: Array<{ label: string; value: string }>;
  dependencyPath: string[];
  evidence: string[];
  mitigation: string;
}

export function buildDepartmentSimulation(profile: OrganizationProfile): DepartmentSimulationView[] {
  let fallbackIndex = 0;
  return profile.departments
    .filter((department) => department.active ?? department.enabled)
    .map((department) => ({
      departmentId: department.department_id,
      name: department.name,
      mission: department.mission,
      headcount: department.actual_fte,
      annualBudgetUsd: department.annual_budget_usd,
      utilisation: department.utilisation,
      maturityLevel: department.maturity_level,
      position: officePosition(fallbackIndex++),
      tone: "neutral",
      label: "Not assessed",
      strength: 0.25,
      startsAt: Number.POSITIVE_INFINITY,
      severity: "Not assessed",
      confidence: undefined,
      summary: "This department has not been assessed in the selected scenario.",
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

export function applyDecisionPackage(baseline: DepartmentSimulationView[], decisionPackage: DecisionPackage | null, selectedResult?: SimulationResult): DepartmentSimulationView[] {
  const result = selectedResult ?? decisionPackage?.portfolios.recommended?.result ?? decisionPackage?.portfolios.naive.result;
  if (!result) return baseline;
  const impacts = result.impacts ?? [];
  const summaries = new Map((decisionPackage?.department_impacts ?? []).map((summary) => [summary.department_id, summary]));
  const sourceDepartments = new Set(
    (decisionPackage?.brief.candidate_interventions ?? [])
      .map((intervention) => intervention.target_entity_id)
      .filter((id) => baseline.some((department) => department.departmentId === id)),
  );
  const implementation = decisionPackage?.implementation?.[0]?.action;

  return baseline.map((department) => {
    const departmentImpacts = impacts.filter((impact) => impact.affected_department === department.departmentId);
    const summary = selectedResult ? undefined : summaries.get(department.departmentId);
    if (!summary && departmentImpacts.length === 0) return department;
    const severity = Math.max(summary?.severity ?? 0, ...departmentImpacts.map((impact) => impact.severity));
    const tone: DepartmentImpactTone = departmentImpacts.some((impact) => impact.polarity === "harm")
      ? "negative"
      : departmentImpacts.some((impact) => impact.polarity === "benefit")
        ? "positive"
        : sourceDepartments.has(department.departmentId) ? "source" : "neutral";
    const confidences = departmentImpacts.map((impact) => impact.confidence);
    const path = departmentImpacts.map((impact) => impact.dependency_path ?? []).sort((left, right) => right.length - left.length)[0] ?? [];

    return {
      ...department,
      tone,
      label: summary?.headline ?? departmentImpacts[0]?.metric.replaceAll("_", " ") ?? "Modeled impact",
      strength: Math.max(0.25, Math.min(1, severity / 5)),
      startsAt: Math.min(...departmentImpacts.map((impact) => impact.first_effect_day)),
      peaksAt: Math.max(...departmentImpacts.map((impact) => impact.peak_effect_day)),
      severity: severityLabel(severity),
      confidence: confidences.length ? confidences.reduce((sum, value) => sum + value, 0) / confidences.length : undefined,
      summary: summary?.headline ?? [...new Set(departmentImpacts.map((impact) => impact.metric.replaceAll("_", " ")))].join(", "),
      workflows: [...new Set(departmentImpacts.map((impact) => impact.affected_entity).filter(id=>id.startsWith("wf_")))],
      kpis: departmentImpacts.slice(0, 2).map((impact) => ({ label: impact.metric.replaceAll("_", " "), value: formatImpact(impact) })),
      dependencyPath: path.length ? path : [department.name],
      evidence: [...new Set(departmentImpacts.flatMap((impact) => impact.evidence_refs ?? []))],
      mitigation: selectedResult ? "Inspect the package for proposed mitigations; only a rerun establishes their effects." : implementation ?? "No specific mitigation was supplied.",
    };
  });
}
