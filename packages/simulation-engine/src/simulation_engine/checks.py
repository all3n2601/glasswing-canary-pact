"""Cross-field checks on engine outputs (schema v2.2.0 section 12, rules 8-14).

``contracts_py`` validators already enforce most of these rules when a model is built, but a
model can still be mutated after construction or built with ``model_construct``. ``check_result``
re-checks every rule explicitly against the twin, so the API can refuse an output before it is
published. It never raises for a bad output; it returns one ``ValidationIssue`` per problem.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from contracts_py.engine import (
    BlastRadius,
    FutureComparison,
    Impact,
    KnowledgeCoverage,
    MitigationComparison,
    PortfolioComparison,
    RiskScore,
    SimulationResult,
    ValueBreakdown,
    WorkflowCoverage,
)
from contracts_py.enums import ClaimStatus, Future, Origin
from contracts_py.twin import Twin, ValidationIssue


def _error(rule: int | str, message: str, ids: list[str] | None = None) -> ValidationIssue:
    return ValidationIssue(rule=rule, severity="error", message=message, ids=ids or [])


def _warning(rule: int | str, message: str, ids: list[str] | None = None) -> ValidationIssue:
    return ValidationIssue(rule=rule, severity="warning", message=message, ids=ids or [])


def _percentiles_ok(p10: int | None, p50: int | None, p90: int | None) -> str | None:
    present = [p is not None for p in (p10, p50, p90)]
    if any(present) and not all(present):
        return "p10, p50 and p90 must be all set or all null"
    if all(present) and not p10 <= p50 <= p90:  # type: ignore[operator]
        return f"expected p10 <= p50 <= p90, got {p10}, {p50}, {p90}"
    return None


def _check_impact(impact: Impact, twin: Twin, entity_ids: set[str], edges: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    ref = [impact.impact_id]
    for field in ("source_entity", "affected_entity"):
        entity_id = getattr(impact, field)
        if entity_id not in entity_ids:
            issues.append(_error(8, f"impact {impact.impact_id}: {field} {entity_id} is not in the twin", ref))
    if impact.affected_department is not None and impact.affected_department not in entity_ids:
        issues.append(_error(8, f"impact {impact.impact_id}: unknown department {impact.affected_department}", ref))
    if impact.peak_effect_day < impact.first_effect_day:
        issues.append(_error(8, f"impact {impact.impact_id}: peak_effect_day is before first_effect_day", ref))
    if impact.origin is Origin.engine and impact.status is not ClaimStatus.computed:
        issues.append(_error(8, f"impact {impact.impact_id}: engine impacts must be computed, got {impact.status}", ref))

    path, edge_path = impact.dependency_path, impact.edge_path
    if len(edge_path) != max(len(path) - 1, 0):
        issues.append(_error(8, f"impact {impact.impact_id}: edge_path must be one shorter than dependency_path", ref))
        return issues
    if not path:
        return issues
    if path[0] != impact.source_entity or path[-1] != impact.affected_entity:
        issues.append(_error(8, f"impact {impact.impact_id}: dependency_path must run source_entity -> affected_entity",
                             ref))
    unknown = [n for n in path if n not in entity_ids]
    if unknown:
        issues.append(_error(8, f"impact {impact.impact_id}: dependency_path has unknown entities {unknown}", ref))
    for i, edge_id in enumerate(edge_path):
        edge = edges.get(edge_id)
        if edge is None:
            # Validated agent edges live on the scenario clone, not the baseline.
            issues.append(_warning(8, f"impact {impact.impact_id}: edge {edge_id} is not in this twin", ref))
            continue
        if (edge.source, edge.target) != (path[i], path[i + 1]):
            issues.append(_error(8, f"impact {impact.impact_id}: edge {edge_id} does not connect "
                                    f"{path[i]} -> {path[i + 1]}", ref))
    return issues


def _check_value(value: ValueBreakdown, result_id: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    expected = (
        value.gross_savings_usd
        - value.transition_cost_usd
        - value.added_cost_usd
        - value.rebound_cost_usd
        - value.expected_business_loss_usd
        - value.pressure_cost_usd
        + value.avoided_failure_cost_usd
    )
    if value.net_value_usd != expected:
        issues.append(_error(9, f"result {result_id}: net_value_usd {value.net_value_usd} does not equal its "
                                f"components {expected}", [result_id]))
    if value.monthly_net_usd and value.monthly_net_usd[-1] != value.net_value_usd:
        issues.append(_error(9, f"result {result_id}: last monthly_net_usd must equal net_value_usd", [result_id]))
    problem = _percentiles_ok(value.p10_net_value_usd, value.p50_net_value_usd, value.p90_net_value_usd)
    if problem:
        issues.append(_error(10, f"result {result_id}: {problem}", [result_id]))
    return issues


def _check_risk(risk: RiskScore, result_id: str) -> list[ValidationIssue]:
    c = risk.components
    total = c.financial + c.capability_workflow + c.customer_revenue + c.compliance_control + c.execution_uncertainty
    if not math.isclose(risk.score, total, abs_tol=1e-6):
        return [_error(10, f"result {result_id}: risk score {risk.score} does not equal its components {total}",
                       [result_id])]
    if not 0 <= risk.score <= 100:
        return [_error(10, f"result {result_id}: risk score {risk.score} is outside 0-100", [result_id])]
    return []


def _check_workflow(coverage: WorkflowCoverage, result_id: str) -> list[ValidationIssue]:
    expected = len(coverage.owners_after) < coverage.min_qualified_owners
    if coverage.stranded != expected:
        return [_error(11, f"result {result_id}: workflow {coverage.workflow_id} stranded={coverage.stranded} but "
                           f"{len(coverage.owners_after)} owners remain for a minimum of "
                           f"{coverage.min_qualified_owners}", [coverage.workflow_id])]
    return []


def _check_knowledge(coverage: KnowledgeCoverage, result_id: str) -> list[ValidationIssue]:
    # Schema section 7.15: lost == (no holder capacity left and documented_pct < 0.5).
    expected = coverage.holder_capacity_fte_after == 0 and coverage.documented_pct < 0.5
    if coverage.lost != expected:
        return [_error(11, f"result {result_id}: knowledge {coverage.knowledge_id} lost={coverage.lost} disagrees "
                           "with its holder capacity and documentation", [coverage.knowledge_id])]
    return []


def _check_simulation(result: SimulationResult, twin: Twin) -> list[ValidationIssue]:
    entity_ids = {e.id for e in twin.entities}
    edges = {e.id: e for e in twin.edges}
    rid = result.result_id
    issues: list[ValidationIssue] = []

    impact_counts = Counter(i.impact_id for i in result.impacts)
    duplicates = sorted(i for i, n in impact_counts.items() if n > 1)
    if duplicates:
        issues.append(_error(8, f"result {rid}: duplicate impact ids", duplicates))
    for impact in result.impacts:
        issues += _check_impact(impact, twin, entity_ids, edges)

    issues += _check_value(result.value, rid)
    issues += _check_risk(result.risk, rid)
    for wf in result.workflow_coverage:
        issues += _check_workflow(wf, rid)
    for kn in result.knowledge_coverage:
        issues += _check_knowledge(kn, rid)

    failed_hard = [c.constraint_id for c in result.constraint_results if c.hard and not c.passed]
    if failed_hard and result.feasible:
        issues.append(_error(12, f"result {rid}: hard constraints failed but the result is feasible", failed_hard))
    if not result.feasible and not result.rejection_reasons:
        issues.append(_error(12, f"result {rid}: an infeasible result needs rejection_reasons", [rid]))
    if result.mode == "full" and result.seed is None:
        issues.append(_error(12, f"result {rid}: full mode needs a seed", [rid]))
    if result.future is Future.inaction and result.intervention_ids:
        issues.append(_error(7, f"result {rid}: the inaction future cannot apply interventions", [rid]))
    unknown_depts = sorted(set(result.affected_department_ids) - entity_ids)
    if unknown_depts:
        issues.append(_error(8, f"result {rid}: unknown affected departments", unknown_depts))
    return issues


def _check_futures(comparison: FutureComparison) -> list[ValidationIssue]:
    cid = comparison.comparison_id
    issues: list[ValidationIssue] = []
    counts = Counter(row.future for row in comparison.rows if row.future is not Future.alternative)
    repeated = sorted(f.value for f, n in counts.items() if n > 1)
    if repeated:
        issues.append(_error(13, f"comparison {cid}: more than one row for futures {repeated}", [cid]))
    alternatives = Counter(row.plan_id for row in comparison.rows if row.future is Future.alternative)
    if any(n > 1 for n in alternatives.values()):
        issues.append(_error(13, f"comparison {cid}: more than one alternative row for the same plan", [cid]))
    if Future.inaction not in counts:
        issues.append(_error(13, f"comparison {cid}: missing the inaction row", [cid]))
    for row in comparison.rows:
        if not 0 <= row.p_better_than_inaction <= 1:
            issues.append(_error(13, f"comparison {cid}: p_better_than_inaction outside [0, 1]", [row.result_id]))
        problem = _percentiles_ok(row.delta_vs_inaction_p10_usd, row.delta_vs_inaction_p50_usd,
                                  row.delta_vs_inaction_p90_usd)
        if problem:
            issues.append(_error(10, f"comparison {cid}: {problem}", [row.result_id]))
        if row.future is Future.inaction:
            deltas = (row.delta_vs_inaction_p10_usd, row.delta_vs_inaction_p50_usd, row.delta_vs_inaction_p90_usd)
            if any(deltas) or row.p_better_than_inaction != 0:
                issues.append(_error(13, f"comparison {cid}: the inaction row must have zero delta and p = 0",
                                     [row.result_id]))
    if comparison.best_row_index is not None and comparison.best_row_index >= len(comparison.rows):
        issues.append(_error(13, f"comparison {cid}: best_row_index is out of range", [cid]))
    return issues


def _check_portfolios(comparison: PortfolioComparison, twin: Twin) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    portfolios = [comparison.naive, *([comparison.recommended] if comparison.recommended else []),
                  *comparison.alternatives]
    for portfolio in portfolios:
        issues += _check_simulation(portfolio.result, twin)
        if portfolio.result.plan_id != portfolio.plan_id:
            issues.append(_error(12, f"portfolio {portfolio.plan_id}: result belongs to plan "
                                     f"{portfolio.result.plan_id}", [portfolio.plan_id]))
        if sorted(portfolio.result.intervention_ids) != sorted(portfolio.intervention_ids):
            issues.append(_error(12, f"portfolio {portfolio.plan_id}: intervention_ids differ from its result",
                                 [portfolio.plan_id]))
    if comparison.recommended is not None and not comparison.recommended.result.feasible:
        issues.append(_error(12, "the recommended portfolio must be feasible", [comparison.recommended.plan_id]))
    ranks = [p.rank for p in portfolios if p.rank is not None]
    if len(ranks) != len(set(ranks)):
        issues.append(_error(12, "portfolio ranks must be unique", sorted({p.plan_id for p in portfolios})))
    if comparison.evaluated_count < len({p.plan_id for p in portfolios}):
        issues.append(_error(12, "evaluated_count is smaller than the portfolios returned", []))
    return issues


def _check_mitigation(comparison: MitigationComparison, twin: Twin) -> list[ValidationIssue]:
    issues = _check_simulation(comparison.before, twin) + _check_simulation(comparison.after, twin)
    if comparison.feasible_before != comparison.before.feasible:
        issues.append(_error(12, "feasible_before disagrees with the before result", [comparison.plan_id_before]))
    if comparison.feasible_after != comparison.after.feasible:
        issues.append(_error(12, "feasible_after disagrees with the after result", [comparison.plan_id_after]))
    return issues


def _check_blast(blast: BlastRadius, twin: Twin) -> list[ValidationIssue]:
    entity_ids = {e.id for e in twin.entities}
    issues: list[ValidationIssue] = []
    node_counts = Counter(n.node_id for n in blast.nodes)
    duplicates = sorted(n for n, count in node_counts.items() if count > 1)
    if duplicates:
        issues.append(_error(14, "blast radius has duplicate node ids", duplicates))
    if blast.root_node_id not in node_counts:
        issues.append(_error(14, f"root node {blast.root_node_id} is not among the nodes", [blast.root_node_id]))
    for edge in blast.edges:
        missing = [n for n in (edge.source, edge.target) if n not in node_counts]
        if missing:
            issues.append(_error(14, f"blast edge {edge.source} -> {edge.target} references missing nodes", missing))
    for node in blast.nodes:
        for ref in (node.entity_id, node.department_id):
            if ref is not None and ref not in entity_ids:
                issues.append(_error(14, f"blast node {node.node_id} references unknown entity {ref}", [node.node_id]))
    for summary in blast.departments:
        if summary.department_id not in entity_ids:
            issues.append(_error(14, f"unknown department {summary.department_id}", [summary.department_id]))
    return issues


def check_result(
    obj: SimulationResult | FutureComparison | PortfolioComparison | MitigationComparison | BlastRadius,
    twin: Twin,
) -> list[ValidationIssue]:
    """Return every rule 8-14 violation in an engine output (schema v2.2.0 sections 7.13, 12)."""
    if isinstance(obj, SimulationResult):
        return _check_simulation(obj, twin)
    if isinstance(obj, FutureComparison):
        return _check_futures(obj)
    if isinstance(obj, PortfolioComparison):
        return _check_portfolios(obj, twin)
    if isinstance(obj, MitigationComparison):
        return _check_mitigation(obj, twin)
    if isinstance(obj, BlastRadius):
        return _check_blast(obj, twin)
    return [_error("type", f"check_result does not know engine output type {type(obj).__name__}")]
