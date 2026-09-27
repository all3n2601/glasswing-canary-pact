from contracts_py.decision import CandidatePlan, DecisionBrief, Scenario
from contracts_py.engine import (
    BlastEdge,
    BlastNode,
    BlastRadius,
    CompanyOutcome,
    ConstraintResult,
    DepartmentImpactSummary,
    FutureComparison,
    FutureRow,
    Impact,
    Portfolio,
    PortfolioComparison,
    RiskComponents,
    RiskScore,
    SimulationResult,
    ValueBreakdown,
)
from contracts_py.enums import (
    ClaimStatus,
    Direction,
    EntityType,
    Future,
    ImpactCategory,
    ImpactLevel,
    Origin,
    Polarity,
    RiskLevel,
)
from contracts_py.twin import Twin

from canary_api.events import utc_now

ASSUMPTION = (
    "General decision assessment: department exposure is intentionally unquantified until evidence-backed "
    "deterministic rules are available."
)
PLAN_ID = "plan_prompt_assessment"


def is_general(brief: DecisionBrief) -> bool:
    return any(i.params.get("prompt_generated") is True for i in brief.candidate_interventions)


def plan(brief: DecisionBrief) -> CandidatePlan:
    return CandidatePlan(plan_id=PLAN_ID, label="Assess the proposed decision", source="user",
                         intervention_ids=[i.id for i in brief.candidate_interventions])


def _zero_value() -> ValueBreakdown:
    return ValueBreakdown(gross_savings_usd=0, transition_cost_usd=0, added_cost_usd=0, rebound_cost_usd=0,
                          expected_business_loss_usd=0, pressure_cost_usd=0, avoided_failure_cost_usd=0,
                          net_value_usd=0)


def _risk() -> RiskScore:
    return RiskScore(score=50, level=RiskLevel.medium, settings_version=1,
                     components=RiskComponents(financial=0, capability_workflow=0, customer_revenue=0,
                                               compliance_control=0, execution_uncertainty=50))


def _impacts(brief: DecisionBrief, twin: Twin, scenario: Scenario) -> list[Impact]:
    if scenario.future is Future.inaction:
        return []
    first = brief.candidate_interventions[0]
    impacts = []
    for index, department in enumerate(e for e in twin.entities if e.type is EntityType.department):
        impacts.append(Impact(
            impact_id=f"imp_assess_{index}", decision_id=brief.decision_id, scenario_id=scenario.scenario_id,
            source_entity=first.target_entity_id, source_kind="intervention", source_ref=first.id,
            affected_entity=department.id, affected_department=department.id, level=ImpactLevel.direct,
            category=ImpactCategory.operational, polarity=Polarity.harm, direction=Direction.no_change,
            metric="unquantified_department_exposure", magnitude=0, unit="unknown", value_usd=None,
            severity=1, first_effect_day=0, peak_effect_day=brief.horizon_days, confidence=0.25,
            dependency_path=[first.target_entity_id, department.id] if first.target_entity_id != department.id else [department.id],
            edge_path=[f"assessment_scope_{index}"] if first.target_entity_id != department.id else [],
            evidence_refs=department.evidence_refs, assumptions=[ASSUMPTION], origin=Origin.engine,
            status=ClaimStatus.hypothesis,
        ))
    return impacts


def result(brief: DecisionBrief, twin: Twin, scenario: Scenario, candidate: CandidatePlan | None) -> SimulationResult:
    impacts = _impacts(brief, twin, scenario)
    constraints = [ConstraintResult(
        constraint_id=c.id, metric=c.metric, operator=c.operator, threshold=c.threshold, value=0,
        hard=c.hard, passed=False, explanation=f"{c.description}: not yet quantified for this general decision."
    ) for c in brief.constraints]
    return SimulationResult(
        result_id=f"res_{scenario.scenario_id}", run_id=scenario.run_id, scenario_id=scenario.scenario_id,
        future=scenario.future, plan_id=scenario.plan_id, mode="full", seed=brief.seed,
        intervention_ids=[] if candidate is None else candidate.intervention_ids, value=_zero_value(),
        goal_met=False, constraint_results=constraints, impacts=impacts, risk=_risk(),
        affected_department_ids=[e.id for e in twin.entities if e.type is EntityType.department],
        feasible=False, rejection_reasons=["Quantified feasibility is unavailable until the required evidence and rules are supplied."],
        assumptions=[ASSUMPTION], computed_at=utc_now(),
    )


def portfolios(brief: DecisionBrief, twin: Twin, run_id: str) -> PortfolioComparison:
    candidate = plan(brief)
    scenario = Scenario(scenario_id=f"scn_{run_id}_act_now_{PLAN_ID}", run_id=run_id, future=Future.act_now,
                        plan_id=PLAN_ID, delay_days=0, baseline_twin_version=twin.version.twin_version,
                        created_at=utc_now())
    return PortfolioComparison(evaluated_count=1,
                               naive=Portfolio(plan_id=PLAN_ID, intervention_ids=candidate.intervention_ids,
                                               result=result(brief, twin, scenario, candidate)))


def futures(brief: DecisionBrief, twin: Twin, candidate: CandidatePlan, run_id: str) -> FutureComparison:
    rows = []
    for future in (Future.act_now, Future.inaction, Future.delay):
        plan_id = None if future is Future.inaction else candidate.plan_id
        scenario_id = f"scn_{run_id}_{future.value}_{plan_id or 'none'}"
        rows.append(FutureRow(future=future, plan_id=plan_id, result_id=f"res_{scenario_id}",
                              label=future.value.replace("_", " ").title(), net_value_p50_usd=0,
                              delta_vs_inaction_p10_usd=0, delta_vs_inaction_p50_usd=0,
                              delta_vs_inaction_p90_usd=0, p_better_than_inaction=0, feasible=False,
                              risk_score=50))
    return FutureComparison(comparison_id=f"cmp_{run_id}", decision_id=brief.decision_id, run_id=run_id,
                            reference_result_id=rows[1].result_id, rows=rows, best_row_index=None,
                            headline="Every department assessed the proposal; quantified feasibility remains unknown.")


def blast(simulation: SimulationResult, twin: Twin) -> BlastRadius:
    decision_id = simulation.impacts[0].decision_id if simulation.impacts else "dec_general"
    nodes = [BlastNode(node_id=decision_id, kind="decision", headline="Proposed company decision")]
    edges = []
    summaries = []
    for department in (e for e in twin.entities if e.type is EntityType.department):
        impact_ids = [i.impact_id for i in simulation.impacts if i.affected_department == department.id]
        nodes.append(BlastNode(node_id=department.id, kind="department", department_id=department.id,
                               entity_id=department.id, headline="Department assessment required", severity=1,
                               impact_ids=impact_ids))
        edges.append(BlastEdge(source=decision_id, target=department.id, label="assessment scope",
                               level=ImpactLevel.direct, critical_constraint=False))
        summaries.append(DepartmentImpactSummary(department_id=department.id,
                                                  headline="Exposure requires evidence-backed assessment",
                                                  polarity=Polarity.harm, severity=1, impact_ids=impact_ids))
    return BlastRadius(run_id=simulation.run_id, scenario_id=simulation.scenario_id, future=simulation.future,
                       plan_id=simulation.plan_id, root_node_id=decision_id, nodes=nodes, edges=edges,
                       departments=summaries, outcome=CompanyOutcome(net_value_usd=0, risk_level=RiskLevel.medium,
                       headline="No numerical recommendation is available for this unquantified decision."))
