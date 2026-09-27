"""Deterministic simulation and optimization over a supplied company twin.

The engine contains rules and formulas only. Every company-specific value is
read from ``Twin`` or ``DecisionBrief``; no demo result is embedded here.
"""

from __future__ import annotations

import itertools
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

import networkx as nx

from company_twin import build_graph
from contracts_py.decision import CandidatePlan, Constraint, DecisionBrief, Intervention, Scenario
from contracts_py.engine import (
    BlastEdge, BlastNode, BlastRadius, CompanyOutcome, ConstraintResult, DepartmentImpactSummary,
    FutureComparison, FutureRow, Impact, KnowledgeCoverage, Portfolio, PortfolioComparison,
    PressureTrigger, RiskComponents, RiskScore, SimulationResult, ValueBreakdown, WorkflowCoverage,
)
from contracts_py.enums import (
    ActionType, ClaimStatus, Criticality, Direction, EntityType, Future, ImpactCategory, ImpactLevel,
    Origin, Polarity, PressureKind, Relation, RiskLevel,
)
from contracts_py.twin import OrganizationSettings, Twin, ValidationIssue


CRITICALITY_SEVERITY = {
    Criticality.low: 1,
    Criticality.medium: 2,
    Criticality.high: 4,
    Criticality.critical: 5,
}


def _id(prefix: str, *parts: str) -> str:
    raw = "_".join(parts)
    return prefix + (raw if len(prefix) + len(raw) <= 80 else sha256(raw.encode()).hexdigest()[:16])


def _settings(settings: OrganizationSettings | None) -> OrganizationSettings:
    return settings or OrganizationSettings()


def _selected(brief: DecisionBrief, plan: CandidatePlan | None) -> list[Intervention]:
    if plan is None:
        return []
    wanted = set(plan.intervention_ids)
    return [item for item in brief.candidate_interventions if item.id in wanted]


def _annual_savings(entity: Any, intervention: Intervention) -> int:
    annual = entity.annual_cost_usd or 0
    if intervention.type in (ActionType.reduce_capacity, ActionType.add_capacity):
        amount = (intervention.amount_pct or 0) / 100
        value = round(annual * amount)
        return value if intervention.type is ActionType.reduce_capacity else -value
    if intervention.type in (ActionType.remove_vendor, ActionType.remove_roles, ActionType.stop_project):
        return annual if annual else (entity.remaining_cost_usd or 0)
    return 0


def _impact_category(entity_type: EntityType) -> ImpactCategory:
    if entity_type is EntityType.control:
        return ImpactCategory.compliance
    if entity_type in (EntityType.kpi, EntityType.customer_segment):
        return ImpactCategory.business
    if entity_type is EntityType.workflow:
        return ImpactCategory.operational
    if entity_type in (EntityType.knowledge_asset, EntityType.role, EntityType.person_token):
        return ImpactCategory.ownership
    return ImpactCategory.technical


def _level(distance: int, lag: int) -> ImpactLevel:
    if lag > 0 and distance > 1:
        return ImpactLevel.delayed
    if distance <= 0:
        return ImpactLevel.direct
    if distance == 1:
        return ImpactLevel.dependent
    return ImpactLevel.second_order


def _path_edges(graph: nx.DiGraph, path: list[str]) -> list[str]:
    return [str(graph.edges[left, right]["id"]) for left, right in zip(path, path[1:])]


def _sources_for_intervention(twin: Twin, intervention: Intervention) -> list[tuple[str, str]]:
    entities = {entity.id: entity for entity in twin.entities}
    target = entities[intervention.target_entity_id]
    if target.type is EntityType.role and intervention.type is ActionType.remove_roles:
        tokens = [entity.id for entity in twin.entities if entity.role_id == target.id]
        return [(token, target.id) for token in tokens] or [(target.id, target.id)]
    return [(target.id, target.id)]


def _intervention_impacts(
    twin: Twin, brief: DecisionBrief, scenario: Scenario, intervention: Intervention
) -> list[Impact]:
    entities = {entity.id: entity for entity in twin.entities}
    graph = build_graph(twin)
    impacts: list[Impact] = []
    seen: set[tuple[str, str]] = set()
    for graph_source, public_source in _sources_for_intervention(twin, intervention):
        paths = {graph_source: [graph_source]}
        paths.update({target: nx.shortest_path(graph, graph_source, target) for target in nx.descendants(graph, graph_source)})
        for affected_id, raw_path in paths.items():
            affected = entities[affected_id]
            key = (intervention.id, affected_id)
            if key in seen or affected.type is EntityType.person_token:
                continue
            seen.add(key)
            public_path = [public_source, *raw_path[1:]]
            edge_ids = _path_edges(graph, raw_path)
            edges = [graph.edges[left, right] for left, right in zip(raw_path, raw_path[1:])]
            lag = sum(int(edge["lag_days"]) for edge in edges)
            confidence = min((float(edge["confidence"]) for edge in edges), default=1.0)
            substitutability = min((float(edge["substitutability"]) for edge in edges), default=1.0)
            severity = CRITICALITY_SEVERITY[affected.criticality]
            if substitutability >= 0.7 and affected_id != public_source:
                severity = max(1, severity - 2)
            evidence = list(dict.fromkeys(ref for edge in edges for ref in edge["evidence_refs"]))
            start = intervention.start_day + (scenario.delay_days if scenario.future is Future.delay else 0) + lag
            direct = affected_id == public_source
            impacts.append(Impact(
                impact_id=_id("imp_", scenario.scenario_id, intervention.id, affected_id),
                decision_id=brief.decision_id,
                scenario_id=scenario.scenario_id,
                source_entity=public_source,
                source_kind="intervention",
                source_ref=intervention.id,
                affected_entity=affected_id,
                affected_department=affected.department_id,
                level=_level(len(raw_path) - 1, lag),
                category=ImpactCategory.financial if direct else _impact_category(affected.type),
                polarity=Polarity.benefit if direct else Polarity.harm,
                direction=Direction.decrease,
                metric="annual_cost_usd" if direct else "dependency_capacity",
                magnitude=float(_annual_savings(affected, intervention) if direct else 1 - substitutability),
                unit="usd" if direct else "ratio",
                value_usd=_annual_savings(affected, intervention) if direct else (
                    round((affected.failure_cost_per_day_usd or 0) * max(1, severity) * 30) or None
                ),
                severity=severity,
                first_effect_day=start,
                peak_effect_day=max(start, min(brief.horizon_days, start + max(30, lag))),
                confidence=confidence,
                dependency_path=public_path,
                edge_path=edge_ids,
                evidence_refs=evidence,
                assumptions=[] if edges else ["Direct financial effect derived from the target entity cost."],
                constraint_refs=[],
                origin=Origin.engine,
                status=ClaimStatus.computed,
            ))
    return impacts


def _coverage(twin: Twin, interventions: list[Intervention]) -> tuple[list[WorkflowCoverage], list[KnowledgeCoverage]]:
    entities = {entity.id: entity for entity in twin.entities}
    removed_roles = {item.target_entity_id for item in interventions if item.type is ActionType.remove_roles}
    person_role = {entity.id: entity.role_id for entity in twin.entities
                   if entity.type is EntityType.person_token and entity.role_id}
    owners: dict[str, list[str]] = {}
    holders: dict[str, list[str]] = {}
    dependent_workflows: dict[str, list[str]] = {}
    for edge in twin.edges:
        if edge.relation is Relation.OWNS:
            owners.setdefault(edge.target, []).append(edge.source)
        elif edge.relation is Relation.KNOWS:
            holders.setdefault(edge.target, []).append(edge.source)
        elif (edge.relation is Relation.SUPPORTS and edge.source in entities and edge.target in entities
              and entities[edge.source].type is EntityType.knowledge_asset
              and entities[edge.target].type is EntityType.workflow):
            dependent_workflows.setdefault(edge.source, []).append(edge.target)

    workflows = []
    # Absence of person-level ownership edges means ownership was not modeled;
    # it must not be interpreted as proof that the workflow is stranded.
    for workflow in (entity for entity in twin.entities
                     if entity.type is EntityType.workflow and entity.id in owners):
        before = owners.get(workflow.id, [])
        after = [person for person in before if person_role.get(person) not in removed_roles]
        minimum = workflow.min_qualified_owners or 0
        workflows.append(WorkflowCoverage(
            workflow_id=workflow.id,
            criticality=workflow.criticality,
            owners_before=[person_role.get(person, person) for person in before],
            owners_after=[person_role.get(person, person) for person in after],
            min_qualified_owners=minimum,
            backup_count_after=max(0, len(after) - minimum),
            documented_pct=workflow.documented_pct or 0,
            stranded=len(after) < minimum,
            reasons=["Qualified owner capacity falls below the workflow minimum."] if len(after) < minimum else [],
            owner_capacity_fte_before=float(len(before)),
            owner_capacity_fte_after=float(len(after)),
            exception_documented_pct=workflow.exception_documented_pct,
            automation_pct=workflow.automation_pct,
            training_days_required=workflow.time_to_train_days,
            replacement_cost_usd=workflow.replacement_cost_usd,
        ))

    knowledge = []
    for asset in (entity for entity in twin.entities if entity.type is EntityType.knowledge_asset):
        before = holders.get(asset.id, [])
        after = [person for person in before if person_role.get(person) not in removed_roles]
        knowledge.append(KnowledgeCoverage(
            knowledge_id=asset.id,
            holders_before=[person_role.get(person, person) for person in before],
            holders_after=[person_role.get(person, person) for person in after],
            holder_capacity_fte_before=float(len(before)),
            holder_capacity_fte_after=float(len(after)),
            documented_pct=asset.documented_pct or 0,
            lost=bool(before) and not after,
            dependent_workflow_ids=dependent_workflows.get(asset.id, []),
            reasons=["Every modeled holder role is removed."] if before and not after else [],
        ))
    return workflows, knowledge


def _pressure_target_cost(twin: Twin, target_id: str) -> int:
    entities = {entity.id: entity for entity in twin.entities}
    target = entities[target_id]
    if target.annual_cost_usd:
        return target.annual_cost_usd
    return sum(entities[edge.source].annual_cost_usd or 0 for edge in twin.edges if edge.target == target_id)


def _pressures(
    twin: Twin, brief: DecisionBrief, scenario: Scenario, interventions: list[Intervention]
) -> tuple[list[PressureTrigger], int]:
    active = set(brief.active_pressure_ids) if brief.active_pressure_ids is not None else None
    selected = {(item.type, item.target_entity_id) for item in interventions}
    triggers, total = [], 0
    for pressure in twin.pressures:
        if active is not None and pressure.id not in active:
            continue
        neutralised = any((ref.intervention_type, ref.target_entity_id) in selected for ref in pressure.neutralised_by)
        effective = neutralised and not (scenario.future is Future.delay and pressure.start_day < scenario.delay_days)
        cost, events = 0, 0.0
        if not effective:
            months = max(0.0, (brief.horizon_days - pressure.start_day) / 30)
            if pressure.kind is PressureKind.hazard:
                events = months * (pressure.monthly_probability or 0)
                cost = round(events * (pressure.cost_per_event_usd or pressure.consequence_cost_usd or 0))
            elif pressure.kind is PressureKind.renewal_step and pressure.start_day <= brief.horizon_days:
                cost = round(_pressure_target_cost(twin, pressure.target_entity_id) * (pressure.step_pct or 0) / 100)
            elif pressure.kind is PressureKind.cost_growth:
                cost = round(_pressure_target_cost(twin, pressure.target_entity_id) * (pressure.rate or 0) * months / 2)
        triggers.append(PressureTrigger(pressure_id=pressure.id, expected_events=events,
                                        expected_cost_usd=cost, neutralised=effective))
        total += cost
    return triggers, total


def _metric_values(twin: Twin, value: ValueBreakdown, impacts: list[Impact],
                   workflows: list[WorkflowCoverage]) -> dict[str, float]:
    entities = {entity.id: entity for entity in twin.entities}
    harmful = [impact for impact in impacts if impact.polarity is Polarity.harm and impact.severity >= 3]
    broken_controls = {impact.affected_entity for impact in harmful
                       if entities[impact.affected_entity].type is EntityType.control
                       and entities[impact.affected_entity].mandatory}
    critical_datasets = {entity.id for entity in twin.entities
                         if entity.type is EntityType.dataset and entity.criticality is Criticality.critical}
    affected_critical = critical_datasets & {impact.affected_entity for impact in harmful}
    customer_harms = [impact for impact in harmful if entities[impact.affected_entity].customer_facing
                      or entities[impact.affected_entity].type is EntityType.customer_segment]
    revenue_harms = [impact for impact in harmful if entities[impact.affected_entity].type is EntityType.kpi]
    capacity_losses = [impact.magnitude * 100 for impact in impacts
                       if impact.metric == "dependency_capacity" and impact.polarity is Polarity.harm]
    return {
        "annual_savings_usd": float(value.gross_savings_usd),
        "net_value_usd": float(value.net_value_usd),
        "revenue_impact_pct": min(100.0, sum(impact.severity for impact in revenue_harms) * 0.5),
        "customer_impact_pct": min(100.0, sum(impact.severity for impact in customer_harms) * 0.5),
        "compliance_controls_broken": float(len(broken_controls)),
        "stranded_workflows": float(sum(
            item.stranded and len(item.owners_before) >= item.min_qualified_owners
            for item in workflows
        )),
        "critical_systems_degraded": float(sum(
            entities[impact.affected_entity].type is EntityType.system
            and entities[impact.affected_entity].criticality is Criticality.critical for impact in harmful
        )),
        "max_capacity_loss_pct": max(capacity_losses, default=0.0),
        "critical_coverage_pct": 100.0 if not critical_datasets else (
            100.0 * (len(critical_datasets) - len(affected_critical)) / len(critical_datasets)
        ),
    }


def _passes(value: float, operator: str, threshold: float) -> bool:
    return {"<=": value <= threshold, ">=": value >= threshold, "==": value == threshold}[operator]


def _constraints(constraints: list[Constraint], metrics: dict[str, float],
                 impacts: list[Impact]) -> list[ConstraintResult]:
    return [ConstraintResult(
        constraint_id=constraint.id,
        metric=constraint.metric,
        operator=constraint.operator,
        threshold=constraint.threshold,
        value=metrics[constraint.metric],
        hard=constraint.hard,
        passed=_passes(metrics[constraint.metric], constraint.operator, constraint.threshold),
        explanation=(f"{constraint.metric} is {metrics[constraint.metric]:g}; "
                     f"required {constraint.operator} {constraint.threshold:g}."),
        impact_ids=[impact.impact_id for impact in impacts if impact.severity >= 4],
    ) for constraint in constraints]


def _risk(impacts: list[Impact], constraints: list[ConstraintResult],
          settings: OrganizationSettings) -> RiskScore:
    weights = settings.risk_weights
    harmful = [impact for impact in impacts if impact.polarity is Polarity.harm]
    average_severity = sum(impact.severity for impact in harmful) / max(1, len(harmful)) / 5
    uncertainty = sum(1 - impact.confidence for impact in harmful) / max(1, len(harmful))
    compliance = sum(not row.passed and row.metric == "compliance_controls_broken" for row in constraints)
    customer = sum(impact.category is ImpactCategory.business for impact in harmful) / max(1, len(harmful))
    components = RiskComponents(
        financial=0,
        capability_workflow=round(weights.capability_workflow * average_severity, 4),
        customer_revenue=round(weights.customer_revenue * customer, 4),
        compliance_control=round(min(weights.compliance_control, weights.compliance_control * compliance), 4),
        execution_uncertainty=round(weights.execution_uncertainty * uncertainty, 4),
    )
    score = round(sum(components.model_dump().values()), 4)
    thresholds = settings.risk_level_thresholds
    level = RiskLevel.low
    if score >= thresholds.critical:
        level = RiskLevel.critical
    elif score >= thresholds.high:
        level = RiskLevel.high
    elif score >= thresholds.medium:
        level = RiskLevel.medium
    return RiskScore(score=score, level=level, settings_version=settings.settings_version, components=components)


def _monthly(net: int, horizon_days: int) -> list[int]:
    months = max(1, (horizon_days + 29) // 30)
    return [round(net * month / months) for month in range(1, months + 1)]


def simulate(twin: Twin, brief: DecisionBrief, scenario: Scenario, plan: CandidatePlan | None, mode: str, *,
             settings: OrganizationSettings | None = None) -> SimulationResult:
    run_settings = _settings(settings)
    interventions = _selected(brief, plan)
    entities = {entity.id: entity for entity in twin.entities}
    impacts = [impact for intervention in interventions
               for impact in _intervention_impacts(twin, brief, scenario, intervention)]
    fraction = (max(0.0, (brief.horizon_days - scenario.delay_days) / brief.horizon_days)
                if scenario.future is Future.delay else 1.0)
    gross = round(sum(_annual_savings(entities[item.target_entity_id], item) for item in interventions) * fraction)
    transition = sum((entities[item.target_entity_id].one_time_exit_cost_usd or 0)
                     + (entities[item.target_entity_id].migration_cost_usd or 0) + item.one_time_cost_usd
                     for item in interventions)
    added = sum(max(0, -_annual_savings(entities[item.target_entity_id], item)) for item in interventions)
    workflows, knowledge = _coverage(twin, interventions)
    pressure_triggers, pressure_cost = _pressures(twin, brief, scenario, interventions)
    business_loss = sum(impact.value_usd or 0 for impact in impacts
                        if impact.polarity is Polarity.harm
                        and impact.category in (ImpactCategory.business, ImpactCategory.operational))
    net = gross - transition - added - business_loss - pressure_cost
    value = ValueBreakdown(
        gross_savings_usd=gross, transition_cost_usd=transition, added_cost_usd=added, rebound_cost_usd=0,
        expected_business_loss_usd=business_loss, pressure_cost_usd=pressure_cost,
        avoided_failure_cost_usd=0, net_value_usd=net, monthly_net_usd=_monthly(net, brief.horizon_days),
        p10_net_value_usd=round(net - abs(net) * 0.2), p50_net_value_usd=net,
        p90_net_value_usd=round(net + abs(net) * 0.2),
    )
    metrics = _metric_values(twin, value, impacts, workflows)
    constraint_results = _constraints(brief.constraints, metrics, impacts)
    goal_value = metrics.get(brief.goal.metric, float(value.net_value_usd))
    goal_met = goal_value >= brief.goal.target if brief.goal.direction == "at_least" else goal_value <= brief.goal.target
    hard_failures = [row for row in constraint_results if row.hard and not row.passed]
    return SimulationResult(
        result_id=_id("res_", scenario.scenario_id), run_id=scenario.run_id, scenario_id=scenario.scenario_id,
        future=scenario.future, plan_id=scenario.plan_id, mode=mode, seed=brief.seed,  # type: ignore[arg-type]
        intervention_ids=[item.id for item in interventions], value=value, goal_met=goal_met,
        constraint_results=constraint_results, impacts=impacts, workflow_coverage=workflows,
        knowledge_coverage=knowledge, pressures_triggered=pressure_triggers,
        risk=_risk(impacts, constraint_results, run_settings),
        affected_department_ids=sorted({impact.affected_department for impact in impacts if impact.affected_department}),
        feasible=goal_met and not hard_failures,
        rejection_reasons=[row.explanation for row in hard_failures] + ([] if goal_met else [
            f"Goal {brief.goal.metric} did not reach {brief.goal.target:g}."
        ]),
        assumptions=[
            "Dependency losses use graph substitutability, criticality, confidence and lag values.",
            "Financial values are deterministic expected values over the requested horizon.",
            *(["The proposed change is unquantified; the engine reports graph scope without inventing value effects."]
              if any(item.type is ActionType.assess_change for item in brief.candidate_interventions) else []),
        ],
        computed_at=datetime.now(timezone.utc),
    )


def quick_impact(twin: Twin, interventions: list[Intervention], *, brief: DecisionBrief | None = None,
                 settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> SimulationResult:
    if brief is None:
        raise ValueError("brief is required for deterministic quick impact")
    plan = CandidatePlan(plan_id="plan_user", label="User selection",
                         intervention_ids=[item.id for item in interventions], source="user")
    scenario = Scenario(scenario_id=f"scn_{run_id}_act_now_plan_user", run_id=run_id, future=Future.act_now,
                        plan_id=plan.plan_id, delay_days=0, baseline_twin_version=twin.version.twin_version,
                        created_at=datetime.now(timezone.utc))
    return simulate(twin, brief, scenario, plan, "quick", settings=settings)


def _scenario(twin: Twin, brief: DecisionBrief, run_id: str, future: Future,
              plan: CandidatePlan | None) -> Scenario:
    plan_id = plan.plan_id if plan and future is not Future.inaction else None
    return Scenario(scenario_id=f"scn_{run_id}_{future.value}_{plan_id or 'none'}", run_id=run_id,
                    future=future, plan_id=plan_id, delay_days=brief.delay_days if future is Future.delay else 0,
                    baseline_twin_version=twin.version.twin_version, created_at=datetime.now(timezone.utc))


def _candidate_plan(interventions: list[Intervention], source: str) -> CandidatePlan:
    ids = [item.id for item in interventions]
    digest = sha256("|".join(sorted(ids)).encode()).hexdigest()[:12]
    return CandidatePlan(plan_id=f"plan_{digest}", label=f"{len(ids)} selected interventions",
                         intervention_ids=ids, source=source)  # type: ignore[arg-type]


def optimize(twin: Twin, brief: DecisionBrief, *, settings: OrganizationSettings | None = None,
             run_id: str = "run_adhoc") -> PortfolioComparison:
    candidates = brief.candidate_interventions
    combinations = [list(combo) for size in range(len(candidates) + 1)
                    for combo in itertools.combinations(candidates, size)]
    portfolios = []
    for combo in combinations:
        plan = _candidate_plan(combo, "enumerated")
        result = simulate(twin, brief, _scenario(twin, brief, run_id, Future.act_now, plan), plan, "full",
                          settings=settings)
        portfolios.append(Portfolio(plan_id=plan.plan_id, intervention_ids=plan.intervention_ids, result=result))
    entity_by_id = {entity.id: entity for entity in twin.entities}
    ordered = sorted(candidates, key=lambda item: _annual_savings(entity_by_id[item.target_entity_id], item), reverse=True)
    running, naive_selected = 0, []
    for item in ordered:
        if running >= brief.goal.target:
            break
        naive_selected.append(item)
        running += _annual_savings(entity_by_id[item.target_entity_id], item)
    naive_plan = _candidate_plan(naive_selected, "naive")
    naive = next(portfolio for portfolio in portfolios if portfolio.plan_id == naive_plan.plan_id)
    feasible = sorted((portfolio for portfolio in portfolios if portfolio.result.feasible),
                      key=lambda item: (item.result.value.net_value_usd, -item.result.risk.score), reverse=True)
    recommended = feasible[0] if feasible else None
    if recommended:
        recommended.rank = 1
    alternatives = []
    for rank, portfolio in enumerate(feasible[1:4], 2):
        portfolio.rank = rank
        alternatives.append(portfolio)
    return PortfolioComparison(evaluated_count=len(portfolios), naive=naive,
                               recommended=recommended, alternatives=alternatives)


def compare_futures(twin: Twin, brief: DecisionBrief, plan: CandidatePlan, *,
                    alternatives: list[CandidatePlan] | None = None,
                    settings: OrganizationSettings | None = None,
                    run_id: str = "run_adhoc") -> FutureComparison:
    futures = list(dict.fromkeys([Future.act_now, Future.inaction, *brief.futures]))
    results = {future: simulate(twin, brief, _scenario(
        twin, brief, run_id, future, None if future is Future.inaction else plan
    ), None if future is Future.inaction else plan, "full", settings=settings)
        for future in futures if future is not Future.alternative}
    reference = results[Future.inaction]
    rows = []
    for future, result in results.items():
        delta = result.value.net_value_usd - reference.value.net_value_usd
        spread = round(abs(delta) * 0.2)
        rows.append(FutureRow(
            future=future, plan_id=result.plan_id, result_id=result.result_id,
            label={Future.act_now: "Act now", Future.inaction: "Do nothing", Future.delay: "Delay"}[future],
            net_value_p50_usd=result.value.net_value_usd,
            delta_vs_inaction_p10_usd=delta - spread, delta_vs_inaction_p50_usd=delta,
            delta_vs_inaction_p90_usd=delta + spread,
            p_better_than_inaction=0.5 if delta == 0 else (0.9 if delta > 0 else 0.1),
            breakeven_day=0 if delta >= 0 else None,
            cost_of_delay_usd=(results[Future.act_now].value.net_value_usd - result.value.net_value_usd
                               if future is Future.delay else None),
            feasible=result.feasible, risk_score=result.risk.score,
            monthly_delta_usd=[value - base for value, base
                               in zip(result.value.monthly_net_usd, reference.value.monthly_net_usd)],
        ))
    feasible_indexes = [index for index, row in enumerate(rows) if row.feasible]
    best = max(feasible_indexes, key=lambda index: rows[index].net_value_p50_usd) if feasible_indexes else None
    headline = "No evaluated future satisfies the goal and hard constraints."
    if best is not None:
        winner = rows[best]
        headline = f"{winner.label} has the highest feasible net value ({winner.net_value_p50_usd:,} USD)."
    return FutureComparison(comparison_id=f"cmp_{run_id}", decision_id=brief.decision_id, run_id=run_id,
                            reference_result_id=reference.result_id, rows=rows,
                            best_row_index=best, headline=headline)


def blast_radius(result: SimulationResult, twin: Twin) -> BlastRadius:
    entities = {entity.id: entity for entity in twin.entities}
    decision_id = result.impacts[0].decision_id if result.impacts else "dec_unquantified"
    nodes = [BlastNode(node_id=decision_id, kind="decision", headline="Proposed decision")]
    edges = []
    node_ids = {decision_id}
    for impact in result.impacts:
        if impact.affected_entity not in node_ids:
            node_ids.add(impact.affected_entity)
            nodes.append(BlastNode(node_id=impact.affected_entity, kind="entity",
                                   department_id=impact.affected_department, entity_id=impact.affected_entity,
                                   headline=f"{entities[impact.affected_entity].name}: {impact.metric}",
                                   level=impact.level, category=impact.category, polarity=impact.polarity,
                                   severity=impact.severity, value_usd=impact.value_usd,
                                   first_effect_day=impact.first_effect_day, impact_ids=[impact.impact_id]))
        edges.append(BlastEdge(source=decision_id, target=impact.affected_entity, label=impact.source_ref,
                               level=impact.level, critical_constraint=bool(impact.constraint_refs)))
    if "kpi_company" not in node_ids:
        nodes.append(BlastNode(node_id="kpi_company", kind="outcome", headline="Company outcome",
                               value_usd=result.value.net_value_usd))
    grouped: dict[str, list[Impact]] = {}
    for impact in result.impacts:
        if impact.affected_department:
            grouped.setdefault(impact.affected_department, []).append(impact)
    departments = [DepartmentImpactSummary(
        department_id=department_id, headline=f"{len(items)} computed impacts",
        polarity=Polarity.harm if any(item.polarity is Polarity.harm for item in items) else Polarity.benefit,
        severity=max(item.severity for item in items), impact_ids=[item.impact_id for item in items],
    ) for department_id, items in sorted(grouped.items())]
    return BlastRadius(
        run_id=result.run_id, scenario_id=result.scenario_id, future=result.future, plan_id=result.plan_id,
        root_node_id=decision_id, nodes=nodes, edges=edges, departments=departments,
        outcome=CompanyOutcome(net_value_usd=result.value.net_value_usd, risk_level=result.risk.level,
                               headline=f"Net value {result.value.net_value_usd:,} USD; risk {result.risk.level.value}."),
    )


def check_result(obj: Any, twin: Twin) -> list[ValidationIssue]:
    known = {entity.id for entity in twin.entities}
    issues = []
    if isinstance(obj, SimulationResult):
        for impact in obj.impacts:
            missing = [item for item in impact.dependency_path if item not in known]
            if missing:
                issues.append(ValidationIssue(rule="impact_path", severity="error",
                                              message="impact path contains unknown entities", ids=missing))
    return issues
