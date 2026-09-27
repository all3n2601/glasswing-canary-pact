"""One future of one plan (plan sections 11.1-11.2; schema v2.2.0 sections 6.6, 7.6, 7.13).

``simulate`` runs a ``Scenario`` of a ``DecisionBrief``: the plan's interventions are looked up in
the brief's ``candidate_interventions`` and evaluated on a fresh clone of the twin.
"""

from __future__ import annotations

import hashlib

from contracts_py.decision import CandidatePlan, DecisionBrief, Intervention, Scenario
from contracts_py.engine import SimulationResult
from contracts_py.enums import Future
from contracts_py.twin import OrganizationSettings, Twin

from .quick import evaluate

MAX_ID_LENGTH = 80


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


def simulate(twin: Twin, brief: DecisionBrief, scenario: Scenario, plan: CandidatePlan | None, mode: str, *,
             settings: OrganizationSettings | None = None) -> SimulationResult:
    """Simulate ``scenario`` for ``plan`` under ``brief``; the baseline twin is never changed.

    Implemented: the act-now future in quick mode. Inaction and delay arrive with
    ``compare_futures`` (plan E-02) and full mode with the Monte Carlo pass (plan E-03).
    """
    if mode != "quick":
        raise NotImplementedError(f"simulate mode {mode!r} is not implemented yet; only 'quick' is (plan E-03)")
    if scenario.future is not Future.act_now:
        raise NotImplementedError(f"simulate future {scenario.future.value!r} is not implemented yet; only "
                                  "'act_now' is (plan E-02)")
    if plan is None:
        raise ValueError("the act_now future needs a plan")
    if scenario.plan_id != plan.plan_id:
        raise ValueError(f"scenario {scenario.scenario_id} is for plan {scenario.plan_id}, not {plan.plan_id}")
    return evaluate(twin, plan_interventions(brief, plan), brief=brief, settings=settings or OrganizationSettings(),
                    run_id=scenario.run_id, scenario_id=scenario.scenario_id, plan_id=plan.plan_id,
                    result_id=bounded_id("res_", scenario.scenario_id.removeprefix("scn_")))
