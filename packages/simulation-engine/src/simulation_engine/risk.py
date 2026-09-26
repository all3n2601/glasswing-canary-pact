"""Risk score (plan section 11.7; schema v2.2.0 section 7.5).

Each component is its weight from ``settings.risk_weights`` times a share in [0, 1], so the
score is the exact sum of its components:

- financial: share of gross savings eaten by the other value lines (transition, added, rebound,
  business loss, pressure cost); the full weight when the brief's goal is missed.
- capability_workflow: the largest capacity loss on a workflow, system, role, or knowledge asset.
- customer_revenue: the largest loss on a KPI, customer segment, or customer-facing entity.
- compliance_control: the full weight when a mandatory control loses at least
  ``CONTROL_BROKEN_LOSS``; otherwise the largest loss on any control.
- execution_uncertainty: the mean ``1 - confidence`` of harm impacts.

Full mode refines the financial share with the P10/P50 spread (plan E-03).
"""

from __future__ import annotations

from contracts_py.engine import Impact, RiskComponents, RiskScore, ValueBreakdown
from contracts_py.enums import EntityType, Polarity, RiskLevel
from contracts_py.twin import OrganizationSettings, Twin

CONTROL_BROKEN_LOSS = 0.5

CAPABILITY_TYPES = {EntityType.workflow, EntityType.system, EntityType.role, EntityType.knowledge_asset}
CUSTOMER_TYPES = {EntityType.kpi, EntityType.customer_segment}


def risk_score(twin: Twin, impacts: list[Impact], value: ValueBreakdown, *, goal_missed: bool,
               settings: OrganizationSettings) -> RiskScore:
    ents = {e.id: e for e in twin.entities}
    harms = [(i, ents[i.affected_entity]) for i in impacts if i.polarity is Polarity.harm]
    w = settings.risk_weights

    costs = value.gross_savings_usd - value.net_value_usd
    financial_share = 1.0 if goal_missed else min(1.0, max(0.0, costs / max(value.gross_savings_usd, 1)))
    capability = max((i.magnitude for i, e in harms if e.type in CAPABILITY_TYPES), default=0.0)
    customer = max((i.magnitude for i, e in harms if e.type in CUSTOMER_TYPES or e.customer_facing), default=0.0)
    controls = [(i.magnitude, bool(e.mandatory)) for i, e in harms if e.type is EntityType.control]
    broken = any(m >= CONTROL_BROKEN_LOSS and mandatory for m, mandatory in controls)
    compliance = 1.0 if broken else max((m for m, _ in controls), default=0.0)
    uncertainty = sum(1 - i.confidence for i, _ in harms) / len(harms) if harms else 0.0

    components = RiskComponents(
        financial=round(w.financial * financial_share, 4),
        capability_workflow=round(w.capability_workflow * min(1.0, capability), 4),
        customer_revenue=round(w.customer_revenue * min(1.0, customer), 4),
        compliance_control=round(w.compliance_control * compliance, 4),
        execution_uncertainty=round(w.execution_uncertainty * uncertainty, 4),
    )
    score = (components.financial + components.capability_workflow + components.customer_revenue
             + components.compliance_control + components.execution_uncertainty)
    t = settings.risk_level_thresholds
    level = (RiskLevel.critical if score >= t.critical else RiskLevel.high if score >= t.high
             else RiskLevel.medium if score >= t.medium else RiskLevel.low)
    return RiskScore(score=score, level=level, settings_version=settings.settings_version, components=components)
