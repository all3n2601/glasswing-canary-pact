"""Risk score (plan section 11.7; schema v2.2.0 section 7.5, rule 10).

Each component is its weight from ``settings.risk_weights`` times a share in [0, 1], so the
score is the exact sum of its components and the level comes from
``settings.risk_level_thresholds``:

- financial: the full weight when the brief's goal is missed; otherwise the share of gross
  savings eaten by the other value lines (transition, added, rebound, business loss, pressure).
- capability_workflow: the largest of: the largest loss on a workflow, system, role, or knowledge
  asset; ``STRANDED_SHARE`` per stranded workflow; ``STRANDED_SHARE`` per degraded critical system.
- customer_revenue: for each ``revenue_impact_pct`` / ``customer_impact_pct`` hard or soft
  constraint with an upper bound, ``value / threshold``; with no such constraint, the largest loss
  on a KPI, customer segment, or customer-facing entity. The largest share counts.
- compliance_control: the full weight when a mandatory control is broken (loss >= ``BROKEN_LOSS``);
  otherwise the largest loss on any control.
- execution_uncertainty: the mean ``1 - confidence`` of harm impacts plus ``HYPOTHESIS_SHARE`` per
  impact that is still a hypothesis.

Full mode refines the financial share with the P10/P50 spread (plan E-03).
"""

from __future__ import annotations

from contracts_py.decision import Constraint
from contracts_py.engine import Impact, RiskComponents, RiskScore
from contracts_py.enums import ClaimStatus, EntityType, Polarity, RiskLevel
from contracts_py.twin import OrganizationSettings

from .constraints import BROKEN_LOSS, ScenarioMetrics

STRANDED_SHARE = 0.5
HYPOTHESIS_SHARE = 0.1
CAPABILITY_TYPES = {EntityType.workflow, EntityType.system, EntityType.role, EntityType.knowledge_asset}
CUSTOMER_TYPES = {EntityType.kpi, EntityType.customer_segment}
CUSTOMER_METRICS = ("revenue_impact_pct", "customer_impact_pct")


def _customer_share(metrics: ScenarioMetrics, constraints: list[Constraint]) -> float:
    bounded = [c for c in constraints if c.metric in CUSTOMER_METRICS and c.operator == "<=" and c.threshold > 0]
    if bounded:
        return max(metrics.metric(c.metric, c.scope_entity_id).value / c.threshold for c in bounded)
    return max((i.magnitude for i, e in metrics.harms if e.type in CUSTOMER_TYPES or e.customer_facing), default=0.0)


def risk_score(metrics: ScenarioMetrics, impacts: list[Impact], *, goal_missed: bool,
               constraints: list[Constraint], settings: OrganizationSettings) -> RiskScore:
    w = settings.risk_weights
    value = metrics.value
    harms = metrics.harms

    costs = value.gross_savings_usd - value.net_value_usd
    financial = 1.0 if goal_missed else costs / max(value.gross_savings_usd, 1)
    capability = max(
        max((i.magnitude for i, e in harms if e.type in CAPABILITY_TYPES), default=0.0),
        STRANDED_SHARE * metrics.metric("stranded_workflows").value,
        STRANDED_SHARE * metrics.metric("critical_systems_degraded").value,
    )
    controls = [(i.magnitude, bool(e.mandatory)) for i, e in harms if e.type is EntityType.control]
    broken = any(m >= BROKEN_LOSS and mandatory for m, mandatory in controls)
    compliance = 1.0 if broken else max((m for m, _ in controls), default=0.0)
    harm_impacts = [i for i in impacts if i.polarity is Polarity.harm]
    hypotheses = sum(1 for i in impacts if i.status is ClaimStatus.hypothesis)
    uncertainty = (sum(1 - i.confidence for i in harm_impacts) / len(harm_impacts) if harm_impacts else 0.0)
    uncertainty += HYPOTHESIS_SHARE * hypotheses

    def part(weight: float, share: float) -> float:
        return round(weight * min(1.0, max(0.0, share)), 4)

    components = RiskComponents(
        financial=part(w.financial, financial),
        capability_workflow=part(w.capability_workflow, capability),
        customer_revenue=part(w.customer_revenue, _customer_share(metrics, constraints)),
        compliance_control=part(w.compliance_control, compliance),
        execution_uncertainty=part(w.execution_uncertainty, uncertainty),
    )
    score = (components.financial + components.capability_workflow + components.customer_revenue
             + components.compliance_control + components.execution_uncertainty)
    t = settings.risk_level_thresholds
    level = (RiskLevel.critical if score >= t.critical else RiskLevel.high if score >= t.high
             else RiskLevel.medium if score >= t.medium else RiskLevel.low)
    return RiskScore(score=score, level=level, settings_version=settings.settings_version, components=components)
