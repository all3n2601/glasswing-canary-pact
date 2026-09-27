"""Engine metrics, hard constraints, and the goal check (plan section 11.5; schema v2.2.0 sections 6.2, 7.4, rule 12).

Each engine-computable metric is read from the scenario's harm impacts (losses in [0, 1]):

- annual_savings_usd, net_value_usd: the ``ValueBreakdown`` gross and net.
- revenue_impact_pct: ``100 * loss`` on the constraint's ``scope_entity_id``, else the largest KPI loss.
- customer_impact_pct: ``100 *`` the largest loss on a customer segment or customer-facing entity.
- compliance_controls_broken: mandatory controls with loss >= ``BROKEN_LOSS``.
- stranded_workflows: reported workflows left below their minimum qualified owners.
- critical_systems_degraded: critical systems with any reported loss.
- max_capacity_loss_pct: ``100 *`` the largest loss on a role or department.
- critical_coverage_pct: the share (0-100) of critical datasets that still have a provider whose
  own loss is below ``BROKEN_LOSS``.

A ``scope_entity_id`` restricts any metric to that entity. A plan is feasible only when every
hard constraint passes and the brief's goal is met; each failure becomes a rejection reason
(plan section 4.1: "reject portfolios with less than $2B gross savings").
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contracts_py.decision import Constraint, DecisionBrief, Goal
from contracts_py.engine import ConstraintResult, Impact, ValueBreakdown, WorkflowCoverage
from contracts_py.enums import Criticality, EntityType, Polarity, Relation
from contracts_py.twin import Entity, Twin

BROKEN_LOSS = 0.5
OPERATORS = {"<=": lambda v, t: v <= t, ">=": lambda v, t: v >= t, "==": lambda v, t: abs(v - t) < 1e-9}


@dataclass(frozen=True)
class Metric:
    value: float
    impact_ids: list[str] = field(default_factory=list)
    entity_ids: list[str] = field(default_factory=list)


class ScenarioMetrics:
    """Every engine metric of one evaluated scenario, optionally scoped to one entity."""

    def __init__(self, twin: Twin, impacts: list[Impact], value: ValueBreakdown,
                 coverage: list[WorkflowCoverage]) -> None:
        self.twin = twin
        self.ents = {e.id: e for e in twin.entities}
        self.harms = [(i, self.ents[i.affected_entity]) for i in impacts if i.polarity is Polarity.harm]
        self.value = value
        self.coverage = coverage

    def _harms(self, scope: str | None, keep) -> list[tuple[Impact, Entity]]:
        return [(i, e) for i, e in self.harms if (scope is None or e.id == scope) and keep(e)]

    def _largest_pct(self, harms: list[tuple[Impact, Entity]]) -> Metric:
        if not harms:
            return Metric(0.0)
        worst = max(harms, key=lambda pair: (pair[0].magnitude, pair[1].id))[0]
        return Metric(round(100 * worst.magnitude, 4), [worst.impact_id], [worst.affected_entity])

    def _count(self, harms: list[tuple[Impact, Entity]]) -> Metric:
        return Metric(float(len(harms)), [i.impact_id for i, _ in harms], [e.id for _, e in harms])

    def _critical_coverage(self, scope: str | None) -> Metric:
        loss = {i.affected_entity: i.magnitude for i, _ in self.harms}
        providers: dict[str, list[str]] = {}
        for edge in self.twin.edges:
            if edge.relation is Relation.PROVIDES:
                providers.setdefault(edge.target, []).append(edge.source)
        critical = sorted(d for d, e in self.ents.items() if e.type is EntityType.dataset
                          and e.criticality is Criticality.critical and d in providers and scope in (None, d))
        if not critical:
            return Metric(100.0)
        uncovered = [d for d in critical if all(loss.get(p, 0.0) >= BROKEN_LOSS for p in providers[d])]
        by_entity = {i.affected_entity: i.impact_id for i, _ in self.harms}
        return Metric(round(100 * (len(critical) - len(uncovered)) / len(critical), 4),
                      [by_entity[d] for d in uncovered if d in by_entity], uncovered)

    def metric(self, name: str, scope: str | None = None) -> Metric:
        match name:
            case "annual_savings_usd":
                return Metric(float(self.value.gross_savings_usd))
            case "net_value_usd":
                return Metric(float(self.value.net_value_usd))
            case "revenue_impact_pct":
                return self._largest_pct(self._harms(scope, lambda e: scope is not None or e.type is EntityType.kpi))
            case "customer_impact_pct":
                return self._largest_pct(self._harms(scope, lambda e: e.type is EntityType.customer_segment
                                                     or bool(e.customer_facing)))
            case "compliance_controls_broken":
                return self._count([(i, e) for i, e in self._harms(scope, lambda e: e.type is EntityType.control
                                                                   and bool(e.mandatory))
                                    if i.magnitude >= BROKEN_LOSS])
            case "stranded_workflows":
                ids = [c.workflow_id for c in self.coverage if c.stranded and scope in (None, c.workflow_id)]
                return Metric(float(len(ids)), [i.impact_id for i, e in self.harms if e.id in ids], ids)
            case "critical_systems_degraded":
                return self._count(self._harms(scope, lambda e: e.type is EntityType.system
                                               and e.criticality is Criticality.critical))
            case "max_capacity_loss_pct":
                return self._largest_pct(self._harms(scope, lambda e: e.type in (EntityType.role,
                                                                                 EntityType.department)))
            case "critical_coverage_pct":
                return self._critical_coverage(scope)
        raise ValueError(f"unknown engine metric {name}")


def _format(metric: str, value: float) -> str:
    if metric.endswith("_usd"):
        return f"${value:,.0f}"
    if metric.endswith("_pct"):
        return f"{value:.2f}%"
    return f"{value:g}"


def evaluate_constraints(constraints: list[Constraint], metrics: ScenarioMetrics) -> list[ConstraintResult]:
    results = []
    for c in constraints:
        m = metrics.metric(c.metric, c.scope_entity_id)
        passed = OPERATORS[c.operator](m.value, c.threshold)
        where = f" on {c.scope_entity_id}" if c.scope_entity_id else ""
        named = f" ({', '.join(m.entity_ids)})" if m.entity_ids else ""
        verdict = "passes" if passed else "fails"
        results.append(ConstraintResult(
            constraint_id=c.id, metric=c.metric, operator=c.operator, threshold=c.threshold, value=m.value,
            hard=c.hard, passed=passed, impact_ids=m.impact_ids,
            explanation=(f"{c.metric}{where} is {_format(c.metric, m.value)}{named}; it must be {c.operator} "
                         f"{_format(c.metric, c.threshold)}, so the {'hard' if c.hard else 'soft'} "
                         f"constraint {verdict}"),
        ))
    return results


def goal_value(goal: Goal, value: ValueBreakdown) -> float | None:
    if goal.metric == "annual_savings_usd":
        return float(value.gross_savings_usd if goal.basis == "gross" else value.net_value_usd)
    if goal.metric == "net_value_usd":
        return float(value.net_value_usd)
    return None


def goal_met(goal: Goal, value: ValueBreakdown) -> bool | None:
    actual = goal_value(goal, value)
    if actual is None:
        return None
    return actual >= goal.target if goal.direction == "at_least" else actual <= goal.target


def rejection_reasons(brief: DecisionBrief, value: ValueBreakdown, met: bool,
                      results: list[ConstraintResult]) -> list[str]:
    reasons = [f"{r.constraint_id}: {r.explanation}" for r in results if r.hard and not r.passed]
    if not met:
        actual = goal_value(brief.goal, value)
        shown = _format(brief.goal.metric, actual) if actual is not None else "not computable"
        reasons.insert(0, f"goal: {brief.goal.basis} {brief.goal.metric} is {shown}; the target is "
                          f"{brief.goal.direction.replace('_', ' ')} {_format(brief.goal.metric, brief.goal.target)}")
    return reasons
