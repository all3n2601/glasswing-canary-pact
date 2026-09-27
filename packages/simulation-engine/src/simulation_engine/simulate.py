"""One future of one plan (plan sections 11.1-11.2; schema v2.2.0 sections 6.6, 7.6, 7.13, A12).

``simulate`` runs a ``Scenario`` of a ``DecisionBrief`` on a fresh clone of the twin; the plan's
interventions are looked up in the brief's ``candidate_interventions``:

- inaction: no interventions; every active pressure runs from its start day.
- act_now and alternative: the plan's interventions at their ``start_day``.
- delay: the plan's interventions ``delay_days`` later, so every neutralisation also starts after
  the delay. Recurring savings accrue at the act-now daily rate from the delayed start, so
  ``gross_savings_usd`` is what the delayed plan realises inside the horizon; the goal and the
  constraints are still judged on the plan's annual run rate.

Every future prices the brief's active pressures in expected-value form (``pressures.py``) as
``pressure_cost_usd``, reports them in ``pressures_triggered``, and adds one ``pressure`` impact
per costed pressure. Inaction is feasible unless it fails a hard constraint; missing the goal is
the decision's reason to act, not a rejection of doing nothing.

Mode ``quick`` reports point values with null percentiles. Mode ``full`` falls back to expected
value until Monte Carlo lands (plan E-03): the same numbers, ``p10 = p50 = p90 = net_value_usd``,
the brief's seed, and assumptions saying so.
"""

from __future__ import annotations

import hashlib

from contracts_py.decision import CandidatePlan, DecisionBrief, Intervention, Scenario
from contracts_py.engine import SimulationResult, ValueBreakdown
from contracts_py.enums import Future, Polarity
from contracts_py.twin import OrganizationSettings, Twin

from .constraints import rejection_reasons
from .pressures import Harm, active_pressures, price_pressures
from .quick import QUICK_ASSUMPTION, evaluate
from .value import accrual_days, monthly_net

MAX_ID_LENGTH = 80
MODES = ("quick", "full")
FUTURES_ASSUMPTION = ("Midpoint edge strengths and point values; baseline pressures are priced in expected-value "
                      "form (hazards as probability x cost per event x months, ranges at their point values)")
EXPECTED_VALUE_ASSUMPTIONS = [
    "Full mode falls back to expected value until Monte Carlo lands (plan E-03); the seed is recorded for replay",
    "Values are expected values, not simulated ranges: p10 = p50 = p90 = net_value_usd in this mode",
    "p_better_than_inaction is a yes/no comparison of expected values in this mode (1.0 or 0.0), not a probability",
]


def bounded_id(prefix: str, body: str) -> str:
    """``prefix + body``, hashed down when it would exceed the contract's 80-character ID limit."""
    candidate = prefix + body
    if len(candidate) <= MAX_ID_LENGTH:
        return candidate
    return prefix + hashlib.sha256(body.encode()).hexdigest()[:24]


def plan_interventions(brief: DecisionBrief, plan: CandidatePlan) -> list[Intervention]:
    by_id = {i.id: i for i in brief.candidate_interventions}
    unknown = [i for i in plan.intervention_ids if i not in by_id]
    if unknown:
        raise ValueError(f"plan {plan.plan_id} references interventions missing from the brief: {unknown}")
    return [by_id[i] for i in plan.intervention_ids]


def _interventions(brief: DecisionBrief, scenario: Scenario, plan: CandidatePlan | None) -> list[Intervention]:
    if scenario.future is Future.inaction:
        if plan is not None or scenario.plan_id is not None:
            raise ValueError(f"the inaction scenario {scenario.scenario_id} takes no plan")
        return []
    if plan is None:
        raise ValueError(f"the {scenario.future.value} future needs a plan")
    if scenario.plan_id != plan.plan_id:
        raise ValueError(f"scenario {scenario.scenario_id} is for plan {scenario.plan_id}, not {plan.plan_id}")
    interventions = plan_interventions(brief, plan)
    if scenario.future is Future.delay:
        delay = delay_days(brief, scenario)
        interventions = [i.model_copy(update={"start_day": i.start_day + delay}) for i in interventions]
    return interventions


def delay_days(brief: DecisionBrief, scenario: Scenario) -> int:
    """The scenario's delay, or the brief's when the scenario leaves it at 0."""
    return scenario.delay_days or brief.delay_days


def simulate(twin: Twin, brief: DecisionBrief, scenario: Scenario, plan: CandidatePlan | None, mode: str, *,
             settings: OrganizationSettings | None = None) -> SimulationResult:
    """Simulate ``scenario`` for ``plan`` under ``brief``; the baseline twin is never changed."""
    if mode not in MODES:
        raise ValueError(f"simulate mode must be one of {MODES}, got {mode!r}")
    if scenario.future is Future.alternative and plan is None:
        raise ValueError("the alternative future needs a plan")
    settings = settings or OrganizationSettings()
    interventions = _interventions(brief, scenario, plan)
    base = evaluate(twin, interventions, brief=brief, settings=settings, run_id=scenario.run_id,
                    scenario_id=scenario.scenario_id, plan_id=scenario.plan_id, future=scenario.future,
                    result_id=bounded_id("res_", scenario.scenario_id.removeprefix("scn_")))
    horizon = brief.horizon_days
    assumptions = [FUTURES_ASSUMPTION, *(a for a in base.assumptions if a != QUICK_ASSUMPTION)]

    v = base.value
    gross = v.gross_savings_usd
    start_day = min((i.start_day for i in interventions), default=0)
    if scenario.future is Future.delay and gross:
        planned = min(i.start_day for i in plan_interventions(brief, plan))  # type: ignore[arg-type]
        full = accrual_days(planned, horizon)
        gross = round(v.gross_savings_usd * accrual_days(start_day, horizon) / full) if full else 0
        assumptions.append(f"Delay future: interventions start {delay_days(brief, scenario)} days later and every "
                           f"neutralisation starts after the delay; gross_savings_usd is the ${gross:,} realised after "
                           f"day {start_day} of the ${v.gross_savings_usd:,} annual run rate, which the goal and "
                           "constraints are judged on")

    harms = {i.affected_entity: Harm(i.magnitude, i.first_effect_day) for i in base.impacts
             if i.polarity is Polarity.harm and i.unit == "ratio"}
    priced = price_pressures(twin, active_pressures(twin, brief.active_pressure_ids), interventions, harms=harms,
                             horizon_days=horizon, decision_id=brief.decision_id, scenario_id=scenario.scenario_id,
                             scale_usd=brief.goal.target)
    assumptions += priced.assumptions

    recurring = gross - v.added_cost_usd - v.rebound_cost_usd - v.expected_business_loss_usd
    before_pressure = monthly_net(recurring, v.transition_cost_usd, start_day, horizon)
    net = recurring - v.transition_cost_usd - priced.total_usd + v.avoided_failure_cost_usd
    percentile = net if mode == "full" else None
    value = ValueBreakdown(
        gross_savings_usd=gross, transition_cost_usd=v.transition_cost_usd, added_cost_usd=v.added_cost_usd,
        rebound_cost_usd=v.rebound_cost_usd, expected_business_loss_usd=v.expected_business_loss_usd,
        pressure_cost_usd=priced.total_usd, avoided_failure_cost_usd=v.avoided_failure_cost_usd, net_value_usd=net,
        monthly_net_usd=[n - p for n, p in zip(before_pressure, priced.monthly_usd)],
        p10_net_value_usd=percentile, p50_net_value_usd=percentile, p90_net_value_usd=percentile,
        termination_cost_usd=v.termination_cost_usd, migration_cost_usd=v.migration_cost_usd,
        displaced_work_cost_usd=v.displaced_work_cost_usd,
    )
    if mode == "full":
        assumptions += EXPECTED_VALUE_ASSUMPTIONS

    feasible, reasons = base.feasible, base.rejection_reasons
    if scenario.future is Future.inaction:
        reasons = rejection_reasons(brief, value, True, base.constraint_results)
        feasible = not reasons
    impacts = [*base.impacts, *priced.impacts]
    return base.model_copy(update={
        "mode": mode, "seed": brief.seed if mode == "full" else None, "value": value, "impacts": impacts,
        "pressures_triggered": priced.triggers, "feasible": feasible, "rejection_reasons": reasons,
        "affected_department_ids": sorted({i.affected_department for i in impacts if i.affected_department}),
        "assumptions": assumptions,
    })
