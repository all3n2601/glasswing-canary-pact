"""Quick-mode evaluation (plan section 11.1; schema v2.2.0 sections 7.6, 7.13).

``evaluate`` is the one deterministic midpoint pass behind ``quick_impact`` (the agents' tool),
``simulate(mode="quick")`` and the optimizer: it applies the interventions to a scenario clone,
propagates their losses and gains, prices every value line, reports the workflow coverage that
changed, checks the brief's goal and hard constraints, and scores the risk. It targets < 100 ms
on the full fixture.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, time, timezone

from contracts_py.decision import DecisionBrief, Intervention
from contracts_py.engine import Impact, SimulationResult
from contracts_py.enums import ClaimStatus, Direction, Future, ImpactCategory, ImpactLevel, Origin, Polarity
from contracts_py.twin import OrganizationSettings, Twin

from .constraints import ScenarioMetrics, evaluate_constraints, goal_met, rejection_reasons
from .interventions import AppliedScenario, apply_interventions
from .knowledge import downgrade_documented, workflow_coverage
from .propagation import DELAYED_AFTER_DAYS, Propagation, impact_id, impact_ledger, propagate
from .risk import risk_score
from .value import price_harms, value_breakdown

QUICK_ASSUMPTION = ("Quick mode: midpoint edge strengths; every value is a point estimate; baseline pressures are "
                    "priced by simulate")


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


def _priced(impacts: list[Impact], by_impact: dict[str, int]) -> list[Impact]:
    return [i.model_copy(update={"value_usd": by_impact[i.impact_id]}) if i.impact_id in by_impact else i
            for i in impacts]


def evaluate(twin: Twin, interventions: list[Intervention], *, brief: DecisionBrief | None,
             settings: OrganizationSettings, run_id: str, scenario_id: str, result_id: str,
             plan_id: str | None = None, future: Future = Future.act_now) -> SimulationResult:
    """One quick evaluation of ``interventions`` on a clone of ``twin``, without baseline pressures."""
    horizon = brief.horizon_days if brief else settings.default_horizon_days
    decision_id = brief.decision_id if brief else "dec_adhoc"
    constraints = brief.constraints if brief else []

    applied = apply_interventions(twin, interventions, horizon_days=horizon)
    losses = propagate(applied.twin, applied.losses, settings=settings)
    gains = (propagate(applied.twin, applied.gains, settings=settings, coverage_share=False) if applied.gains
             else Propagation(effects={}, iterations=0, converged=True))
    coverage = workflow_coverage(twin, applied.twin)
    harms = impact_ledger(applied.twin, losses, decision_id=decision_id, scenario_id=scenario_id,
                          polarity=Polarity.harm, constraints=constraints, horizon_days=horizon)
    harms = downgrade_documented(harms, coverage, applied.twin)
    priced = price_harms(applied.twin, harms, horizon)
    impacts = [
        *_savings_impacts(applied, interventions, decision_id=decision_id, scenario_id=scenario_id),
        *_priced(harms, {**priced.displaced_by_impact, **priced.loss_by_impact}),
        *impact_ledger(applied.twin, gains, decision_id=decision_id, scenario_id=scenario_id,
                       polarity=Polarity.benefit, constraints=constraints, horizon_days=horizon),
    ]
    start_day = min((i.start_day for i in interventions), default=0)
    value = value_breakdown(applied, priced, start_day=start_day, horizon_days=horizon)
    metrics = ScenarioMetrics(applied.twin, impacts, value, coverage)

    assumptions = [QUICK_ASSUMPTION, *applied.assumptions]
    if applied.termination_cost_usd or applied.migration_cost_usd:
        assumptions.append(f"transition_cost_usd includes ${applied.termination_cost_usd:,} termination and "
                           f"${applied.migration_cost_usd:,} migration")
    if priced.displaced_work_usd:
        assumptions.append(f"added_cost_usd includes ${priced.displaced_work_usd:,} displaced work: harmed workflows "
                           "and systems priced at loss x failure_cost_per_day_usd until the horizon")
    if not losses.converged or not gains.converged:
        assumptions.append("propagation hit the iteration cap before converging")

    met, results, reasons, feasible = False, [], [], True
    if brief is not None:
        computed = goal_met(brief.goal, value)
        if computed is None:
            assumptions.append(f"goal metric {brief.goal.metric} is not computed in quick mode")
        met = bool(computed)
        results = evaluate_constraints(constraints, metrics)
        reasons = rejection_reasons(brief, value, met, results)
        feasible = not reasons

    departments = sorted({i.affected_department for i in impacts if i.affected_department})
    return SimulationResult(
        result_id=result_id, run_id=run_id, scenario_id=scenario_id, future=future, plan_id=plan_id,
        mode="quick", intervention_ids=[i.id for i in interventions], value=value, goal_met=met,
        constraint_results=results, impacts=impacts, workflow_coverage=coverage,
        risk=risk_score(metrics, impacts, goal_missed=brief is not None and not met, constraints=constraints,
                        settings=settings),
        affected_department_ids=departments, feasible=feasible, rejection_reasons=reasons, assumptions=assumptions,
        # Stamped from the twin's as-of date so the same inputs give byte-identical output.
        computed_at=datetime.combine(twin.version.as_of_date, time(), tzinfo=timezone.utc),
    )


def quick_impact(twin: Twin, interventions: list[Intervention], *, brief: DecisionBrief | None = None,
                 settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> SimulationResult:
    """Point-estimate impact of ``interventions`` on ``twin``; the baseline twin is never changed.

    With a brief the goal and every constraint are evaluated and ``feasible`` follows them.
    Without one (schema G3) the result is ``act_now`` with no constraint results,
    ``goal_met = False`` and ``feasible = True``.
    """
    digest = hashlib.sha256(json.dumps(sorted(i.id for i in interventions)).encode()).hexdigest()[:12]
    return evaluate(twin, interventions, brief=brief, settings=settings or OrganizationSettings(), run_id=run_id,
                    scenario_id=f"scn_{run_id}_{Future.act_now.value}_none", result_id=f"res_{run_id}_quick_{digest}")
