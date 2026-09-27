import type { AgentAssessment, DecisionBrief, DecisionPackage, Event, HumanDecision, ReviewIssue, SimulationResult } from "@canary-pact/contracts/generated";

export const REVIEW_STAGES = ["Proposal", "Findings", "Challenge", "Response", "Recalculation", "Decision"] as const;

// A bounded reading order for recorded findings, not a risk score or a new recommendation.
export function decisionHighlights(assessments: AgentAssessment[], pkg: DecisionPackage) {
  const latest = new Map<string, AgentAssessment>();
  const planId = pkg.recommendation?.plan_id;
  for (const assessment of assessments) {
    if (assessment.pass_type === "challenge" || assessment.status !== "ok" || !assessment.output) continue;
    // An inaction recommendation has no plan; its concerns still describe the proposed change.
    if (planId && assessment.plan_id !== planId) continue;
    const previous = latest.get(assessment.agent_id);
    if (previous?.pass_type === "response" && assessment.pass_type !== "response") continue;
    latest.set(assessment.agent_id, assessment);
  }
  const seen = new Set<string>();
  const risks = [...latest.values()].flatMap(assessment => {
    const finding = [...(assessment.output?.act_now_view.failure_modes ?? [])]
      .sort((a, b) => b.severity - a.severity)
      .find(item => item.text.trim() && !seen.has(item.text.trim()));
    if (!finding) return [];
    seen.add(finding.text.trim());
    return [{assessment, finding}];
  }).sort((a, b) => b.finding.severity - a.finding.severity).slice(0, 3);
  const questions = [...new Set([
    ...risks.flatMap(({assessment}) => (assessment.output?.questions ?? []).slice(0, 1).map(q => q.text)),
    ...(pkg.missing_information ?? []).map(q => q.text),
    ...(pkg.open_questions ?? []),
  ].filter(text => text?.trim()))].slice(0, 3);
  return {risks, questions};
}

export function reviewSnapshot(events: Event[], fallbackPackage?: DecisionPackage | null) {
  const assessments = new Map<string, AgentAssessment>();
  const issues = new Map<string, ReviewIssue>();
  let brief: DecisionBrief | undefined = fallbackPackage?.brief;
  let decisionPackage = fallbackPackage;
  let initial: SimulationResult | undefined;
  let latest: SimulationResult | undefined;
  let agentsStarted = false;
  let stage = 0;
  const dependencies: {source: string; target: string; evidence: string[]; assessmentId: string}[] = [];
  let failure: string | undefined;
  let humanDecision: HumanDecision | undefined;
  for (const event of events) {
    const p = event.payload;
    if (event.type === "run_created" && "statement" in p) brief = p as DecisionBrief;
    if (event.type === "agent_started" && "agent_id" in p) {
      agentsStarted = true;
      stage = "pass_type" in p && p.pass_type === "response" ? 3 : p.agent_id === "challenger" ? 2 : 1;
      if ("review_issues" in p) for (const issue of p.review_issues ?? []) issues.set(issue.issue_id, issue);
    }
    if ((event.type === "agent_completed" || event.type === "challenge_raised") && "assessment_id" in p) {
      const assessment = p as AgentAssessment;
      assessments.set(assessment.assessment_id, assessment);
      for (const issue of assessment.review_issues ?? []) issues.set(issue.issue_id, issue);
    }
    if (event.type === "simulation_completed" && "result_id" in p && "value" in p && p.future === "act_now") {
      latest = p as SimulationResult;
      if (!agentsStarted) initial = latest;
      else if (stage >= 2) stage = 4;
    }
    if (event.type === "dependency_validated" && "edge" in p)
      dependencies.push({source: p.edge.source, target: p.edge.target, evidence: p.edge.evidence_refs ?? [], assessmentId: p.assessment_id});
    if (event.type === "package_ready" && "package_id" in p) {decisionPackage = p as DecisionPackage; stage = 5;}
    if (event.type === "run_failed" && "reason" in p) failure = String(p.reason);
    if (event.type === "human_decision_recorded" && "decided_at" in p) humanDecision = p as HumanDecision;
  }
  if (decisionPackage) stage = 5;
  return {brief, decisionPackage, initial, latest, stage, dependencies, failure, humanDecision,
    assessments: [...assessments.values()], issues: [...issues.values()]};
}
