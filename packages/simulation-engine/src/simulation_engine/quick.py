"""Quick-mode impact (plan section 11.1; schema v2.2.0 section 7.13).

``quick_impact`` is the agents' tool: one deterministic midpoint pass that applies the
interventions to a scenario clone, propagates their losses and gains, and prices the value lines
the interventions themselves move. It targets < 100 ms on the full fixture.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, time, timezone

from contracts_py.decision import DecisionBrief, Goal, Intervention
from contracts_py.engine import Impact, SimulationResult, ValueBreakdown
from contracts_py.enums import ClaimStatus, Direction, Future, ImpactCategory, ImpactLevel, Origin, Polarity
from contracts_py.twin import OrganizationSettings, Twin

from .interventions import AppliedScenario, apply_interventions
from .propagation import DELAYED_AFTER_DAYS, impact_id, impact_ledger, propagate
from .risk import risk_score

DAYS_PER_MONTH = 30
QUICK_ASSUMPTION = ("Quick mode: midpoint edge strengths; hard constraints, pressures, and business loss are "
                    "evaluated by simulate")


def _savings_impacts(applied: AppliedScenario, interventions: list[Intervention], *, decision_id: str,
                     scenario_id: str) -> list[Impact]:
    ents = {e.id: e for e in applied.twin.entities}
    impacts = []
    for i in interventions:
        saved = applied.savings_by_intervention.get(i.id, 0)
        if saved <= 0:
            continue
        target = ents[i.target_entity_id]
        impacts.append(Impact(
            impact_id=impact_id(i.id, "savings"), decision_id=decision_id, scenario_id=scenario_id,
            source_entity=target.id, source_kind="intervention", source_ref=i.id, affected_entity=target.id,
            affected_department=target.department_id,
            level=ImpactLevel.delayed if i.start_day > DELAYED_AFTER_DAYS else ImpactLevel.direct,
            category=ImpactCategory.financial, polarity=Polarity.benefit, direction=Direction.decrease,
            metric="annual_cost_usd", magnitude=float(saved), unit="usd", value_usd=saved, severity=1,
            first_effect_day=i.start_day, peak_effect_day=i.start_day, confidence=1.0,
            dependency_path=[target.id], evidence_refs=list(target.evidence_refs), origin=Origin.engine,
            status=ClaimStatus.computed,
        ))
    return impacts


def _monthly_net(gross: int, net: int, start_day: int, horizon_days: int) -> list[int]:
    """Cumulative net per month: one-off costs land in the start month, savings accrue after it."""
    months = max(1, horizon_days // DAYS_PER_MONTH)
    costs = gross - net
    accrual_days = max(1, months * DAYS_PER_MONTH - start_day)
    series = []
    for m in range(1, months):
        elapsed = min(1.0, max(0, m * DAYS_PER_MONTH - start_day) / accrual_days)
        series.append(round(gross * elapsed) - (costs if m * DAYS_PER_MONTH > start_day else 0))
    return [*series, net]


def _goal_met(goal: Goal, value: ValueBreakdown) -> bool | None:
    if goal.metric == "annual_savings_usd":
        actual = value.gross_savings_usd if goal.basis == "gross" else value.net_value_usd
    elif goal.metric == "net_value_usd":
        actual = value.net_value_usd
    else:
        return None
    return actual >= goal.target if goal.direction == "at_least" else actual <= goal.target


def quick_impact(twin: Twin, interventions: list[Intervention], *, brief: DecisionBrief | None = None,
                 settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> SimulationResult:
    """Point-estimate impact of ``interventions`` on ``twin``; the baseline twin is never changed.

    Without a brief (schema G3) the result is ``act_now`` with no constraint results,
    ``goal_met = False`` and ``feasible = True``.
    """
    settings = settings or OrganizationSettings()
    horizon = brief.horizon_days if brief else settings.default_horizon_days
    decision_id = brief.decision_id if brief else "dec_adhoc"
    scenario_id = f"scn_{run_id}_{Future.act_now.value}_none"
    constraints = brief.constraints if brief else []

    applied = apply_interventions(twin, interventions, horizon_days=horizon)
    losses = propagate(applied.twin, applied.losses, settings=settings)
    gains = propagate(applied.twin, applied.gains, settings=settings, coverage_share=False)
    impacts = [
        *_savings_impacts(applied, interventions, decision_id=decision_id, scenario_id=scenario_id),
        *impact_ledger(applied.twin, losses, decision_id=decision_id, scenario_id=scenario_id,
                       polarity=Polarity.harm, constraints=constraints, horizon_days=horizon),
        *impact_ledger(applied.twin, gains, decision_id=decision_id, scenario_id=scenario_id,
                       polarity=Polarity.benefit, constraints=constraints, horizon_days=horizon),
    ]

    gross = applied.gross_savings_usd
    net = gross - applied.transition_cost_usd - applied.added_cost_usd - applied.rebound_cost_usd
    start_day = min((i.start_day for i in interventions), default=0)
    value = ValueBreakdown(
        gross_savings_usd=gross, transition_cost_usd=applied.transition_cost_usd,
        added_cost_usd=applied.added_cost_usd, rebound_cost_usd=applied.rebound_cost_usd,
        expected_business_loss_usd=0, pressure_cost_usd=0, avoided_failure_cost_usd=0, net_value_usd=net,
        monthly_net_usd=_monthly_net(gross, net, start_day, horizon),
    )

    assumptions = [QUICK_ASSUMPTION, *applied.assumptions]
    goal_met = False
    if brief is not None:
        met = _goal_met(brief.goal, value)
        if met is None:
            assumptions.append(f"goal metric {brief.goal.metric} is not priced in quick mode")
        goal_met = bool(met)
    if not losses.converged or not gains.converged:
        assumptions.append("propagation hit the iteration cap before converging")

    digest = hashlib.sha256(json.dumps(sorted(i.id for i in interventions)).encode()).hexdigest()[:12]
    departments = sorted({i.affected_department for i in impacts if i.affected_department})
    return SimulationResult(
        result_id=f"res_{run_id}_quick_{digest}", run_id=run_id, scenario_id=scenario_id, future=Future.act_now,
        mode="quick", intervention_ids=[i.id for i in interventions], value=value, goal_met=goal_met,
        impacts=impacts,
        risk=risk_score(applied.twin, impacts, value, goal_missed=brief is not None and not goal_met,
                        settings=settings),
        affected_department_ids=departments, feasible=True, assumptions=assumptions,
        # Stamped from the twin's as-of date so the same inputs give byte-identical output.
        computed_at=datetime.combine(twin.version.as_of_date, time(), tzinfo=timezone.utc),
    )
