import type { DepartmentProfile, OrganizationProfile } from "@canary-pact/contracts";
import type { DecisionPackage, Impact } from "@canary-pact/contracts/generated";

import { organizationProfile } from "./organization-data";

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

type ScenarioOverride = Omit<DepartmentSimulationView, keyof DepartmentProfile | "departmentId" | "name" | "mission" | "headcount" | "annualBudgetUsd" | "utilisation" | "maturityLevel" | "position">;

const scenarioOverrides: Record<string, ScenarioOverride> = {
  dept_engineering: {
    tone: "source", label: "Source decision", strength: 0.86, startsAt: 0, severity: "High", confidence: 0.92,
    summary: "The proposed 20% capacity reduction begins here and reduces delivery capacity across commitment-critical work.",
    workflows: ["Platform delivery", "Incident response", "Release planning"],
    kpis: [{ label: "Capacity change", value: "−20%" }, { label: "Delivery delay", value: "+5 weeks" }],
    dependencyPath: ["Engineering capacity", "Product roadmap", "Customer commitments"],
    evidence: ["Approved scenario input", "Synthetic capacity plan"],
    mitigation: "Protect platform and commitment-critical teams before reducing lower-priority work.",
  },
  dept_finance: {
    tone: "positive", label: "Cost savings +$3.0M", strength: 0.62, startsAt: 4, severity: "Low", confidence: 0.96,
    summary: "The proposal produces an immediate operating-cost benefit before downstream delivery and revenue effects appear.",
    workflows: ["Operating plan", "Quarterly forecast"],
    kpis: [{ label: "Annual savings", value: "+$3.0M" }, { label: "Net value", value: "−$1.2M" }],
    dependencyPath: ["Engineering capacity", "Payroll forecast", "Operating margin"],
    evidence: ["Approved workforce plan", "Synthetic finance forecast"],
    mitigation: "Track displaced cost and revenue exposure alongside gross savings.",
  },
  dept_people: {
    tone: "negative", label: "Knowledge coverage at risk", strength: 0.48, startsAt: 14, severity: "Medium", confidence: 0.76,
    summary: "Reduced role coverage increases concentration of institutional knowledge and manager workload.",
    workflows: ["Workforce planning", "Knowledge transfer"],
    kpis: [{ label: "Roles affected", value: "8" }, { label: "Backup gaps", value: "2" }],
    dependencyPath: ["Engineering roles", "Knowledge owners", "Critical workflows"],
    evidence: ["Synthetic role map", "Knowledge ownership matrix"],
    mitigation: "Complete documentation and backup-owner training before capacity changes take effect.",
  },
  dept_operations: {
    tone: "negative", label: "Coverage pressure", strength: 0.55, startsAt: 22, severity: "Medium", confidence: 0.79,
    summary: "Operations retains critical coverage, but absorbs additional coordination and escalation work.",
    workflows: ["Incident escalation", "Business continuity"],
    kpis: [{ label: "Utilisation", value: "112%" }, { label: "Recovery risk", value: "+18%" }],
    dependencyPath: ["Engineering support", "Incident escalation", "Service recovery"],
    evidence: ["Synthetic incident rota", "Workflow dependency map"],
    mitigation: "Reserve explicit engineering support windows for operational escalations.",
  },
  dept_ai_data: {
    tone: "negative", label: "Model support slows", strength: 0.58, startsAt: 31, severity: "Medium", confidence: 0.75,
    summary: "Shared engineering dependencies slow model-feature delivery and data-platform maintenance.",
    workflows: ["Feature delivery", "Data quality monitoring"],
    kpis: [{ label: "Release delay", value: "+3 weeks" }, { label: "Utilisation", value: "108%" }],
    dependencyPath: ["Engineering capacity", "Data platform", "Model delivery"],
    evidence: ["Synthetic roadmap", "Platform dependency map"],
    mitigation: "Protect data-platform maintenance and defer non-critical model experiments.",
  },
  dept_marketing: {
    tone: "negative", label: "Launch timing shifts", strength: 0.42, startsAt: 39, severity: "Low", confidence: 0.68,
    summary: "Campaign sequencing becomes uncertain when product milestones move beyond the planned launch window.",
    workflows: ["Launch campaign", "Demand planning"],
    kpis: [{ label: "Campaigns exposed", value: "2" }, { label: "Pipeline timing", value: "+4 weeks" }],
    dependencyPath: ["Product roadmap", "Launch calendar", "Demand generation"],
    evidence: ["Synthetic campaign calendar", "Roadmap sequencing model"],
    mitigation: "Shift campaign spend toward evergreen demand until release dates stabilize.",
  },
  dept_sales: {
    tone: "negative", label: "Commitments at risk", strength: 0.66, startsAt: 48, severity: "High", confidence: 0.78,
    summary: "Four enterprise commitments depend on milestones now moving outside their expected delivery window.",
    workflows: ["Enterprise commitments", "Renewal planning"],
    kpis: [{ label: "Accounts exposed", value: "4" }, { label: "Revenue at risk", value: "$4.2M" }],
    dependencyPath: ["Product milestones", "Sales commitments", "Enterprise revenue"],
    evidence: ["Synthetic commitments ledger", "Roadmap sequencing model"],
    mitigation: "Protect the two commitment-critical initiatives and renegotiate dates early.",
  },
  dept_customer: {
    tone: "negative", label: "Churn risk +3%", strength: 0.5, startsAt: 64, severity: "High", confidence: 0.74,
    summary: "Delayed commitments increase renewal friction and customer escalation volume.",
    workflows: ["Renewal management", "Customer escalation"],
    kpis: [{ label: "Churn exposure", value: "+3%" }, { label: "Accounts exposed", value: "4" }],
    dependencyPath: ["Delivery delay", "Customer commitments", "Renewal risk"],
    evidence: ["Synthetic renewal book", "Customer commitment ledger"],
    mitigation: "Create account-level recovery plans before the delayed milestones are communicated.",
  },
  dept_compliance: {
    tone: "neutral", label: "Controls remain protected", strength: 0.3, startsAt: 72, severity: "Protected", confidence: 0.91,
    summary: "No modeled control fails, provided protected incident and access-review coverage remains in place.",
    workflows: ["Access review", "Control monitoring"],
    kpis: [{ label: "Controls breached", value: "0" }, { label: "Coverage", value: "100%" }],
    dependencyPath: ["Protected capacity", "Control operations", "Compliance coverage"],
    evidence: ["Synthetic control register", "Protected-work constraint"],
    mitigation: "Keep control ownership and incident-response capacity outside the reduction scope.",
  },
};

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
};

function fallbackPosition(index: number): [number, number, number] {
  const angle = (index * Math.PI) / 4;
  return [Math.cos(angle) * 10.5, 0.08, Math.sin(angle) * 7.4];
}

const emptyScenario = (department: DepartmentProfile) => ({
  tone: "neutral" as const,
  label: "No material impact",
  strength: 0.25,
  startsAt: 90,
  severity: "Protected" as const,
  confidence: undefined,
  summary: "No material impact has been reported for this department.",
  workflows: [],
  kpis: [],
  dependencyPath: [department.name],
  evidence: [],
  mitigation: "Continue monitoring as the scenario changes.",
});

export function buildDepartmentSimulation(profile: OrganizationProfile): DepartmentSimulationView[] {
  return profile.departments
    .filter((department) => department.enabled)
    .map((department, index) => ({
      departmentId: department.department_id,
      name: department.name,
      mission: department.mission,
      headcount: department.actual_fte,
      annualBudgetUsd: department.annual_budget_usd,
      utilisation: department.utilisation,
      maturityLevel: department.maturity_level,
      position: fixedPositions[department.department_id] ?? fallbackPosition(index - Object.keys(fixedPositions).length),
      ...emptyScenario(department),
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

export function applyDecisionPackage(
  baseline: DepartmentSimulationView[],
  decisionPackage: DecisionPackage,
): DepartmentSimulationView[] {
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
    const harmCount = departmentImpacts.filter((impact) => impact.polarity === "harm").length;
    const benefitCount = departmentImpacts.filter((impact) => impact.polarity === "benefit").length;
    const tone: DepartmentImpactTone = sourceDepartments.has(department.departmentId)
      ? "source"
      : harmCount > 0
        ? "negative"
        : benefitCount > 0
          ? "positive"
          : "neutral";
    const confidences = departmentImpacts.map((impact) => impact.confidence);
    const path = departmentImpacts
      .map((impact) => impact.dependency_path ?? [])
      .sort((left, right) => right.length - left.length)[0] ?? [];

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
      kpis: departmentImpacts.slice(0, 2).map((impact) => ({
        label: impact.metric.replaceAll("_", " "),
        value: formatImpact(impact),
      })),
      dependencyPath: path.length ? path : [department.name],
      evidence: [...new Set(departmentImpacts.flatMap((impact) => impact.evidence_refs ?? []))],
      mitigation: implementation ?? "Continue monitoring this department against the decision package.",
    };
  });
}

export const demoDepartmentSimulation: DepartmentSimulationView[] = organizationProfile.departments
  .filter((department) => department.enabled)
  .map((department, index) => {
    const scenario = scenarioOverrides[department.department_id] ?? emptyScenario(department);

    return {
      departmentId: department.department_id,
      name: department.name,
      mission: department.mission,
      headcount: department.actual_fte,
      annualBudgetUsd: department.annual_budget_usd,
      utilisation: department.utilisation,
      maturityLevel: department.maturity_level,
      position: fixedPositions[department.department_id] ?? fallbackPosition(index - Object.keys(fixedPositions).length),
      ...scenario,
    };
  });
