"""Vendor portfolio optimizer (plan sections 4.1, 11.5; schema v2.2.0 section 7.8).

Every subset of the brief's candidate interventions (7 vendor removals: 128 portfolios) is
evaluated in quick mode with its goal and hard constraints:

- naive: greedy by gross savings, adding the largest saver until the goal is met (R5);
- recommended: the best feasible portfolio by net value, ties broken by lower risk, then plan ID;
- alternatives: the feasible portfolio with the lowest gross cost (gross savings minus net
  value: every cost line together), the feasible portfolio with the lowest risk, then every
  rejected portfolio with its failed checks in ``rejection_reasons``.

Feasible portfolios are ranked 1..n in recommendation order; rejected ones have no rank. Portfolios
are ranked on their own quick economics, without baseline pressures; ``simulate`` and
``compare_futures`` add the pressures for the chosen plan's futures.

Only the vendor scenario is searched. Any other brief evaluates one plan of all its candidate
interventions (schema X5; the workforce subset search is not approved for v1): it is the naive
plan, and the recommended one only when it is feasible (``recommended`` is the best *feasible*
portfolio), with ``evaluated_count`` 1.
"""

from __future__ import annotations

from itertools import combinations

from contracts_py.decision import DecisionBrief, Intervention
from contracts_py.engine import Portfolio, PortfolioComparison, SimulationResult
from contracts_py.enums import ActionType, DecisionType, Future
from contracts_py.twin import OrganizationSettings, Twin

from .quick import evaluate
from .simulate import bounded_id

NAIVE_PLAN_ID = "plan_naive"
COUNT_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
               "twelve")


def plan_id_for(interventions: list[Intervention]) -> str:
    if not interventions:
        return "plan_none"
    return bounded_id("plan_", "_".join(i.id.removeprefix("remove_") for i in interventions))


def _run(twin: Twin, brief: DecisionBrief, plan_id: str, interventions: list[Intervention],
         settings: OrganizationSettings, run_id: str) -> SimulationResult:
    scenario_id = bounded_id("scn_", f"{run_id}_{Future.act_now.value}_{plan_id}")
    return evaluate(twin, interventions, brief=brief, settings=settings, run_id=run_id, scenario_id=scenario_id,
                    plan_id=plan_id, result_id=bounded_id("res_", scenario_id.removeprefix("scn_")))


def single_plan_id(interventions: list[Intervention]) -> str:
    """``plan_remove_eight_roles`` for eight role removals; ``plan_all_candidates`` otherwise."""
    count = len(interventions)
    if 0 < count < len(COUNT_WORDS) and all(i.type is ActionType.remove_roles for i in interventions):
        return f"plan_remove_{COUNT_WORDS[count]}_roles"
    return "plan_all_candidates"


def _single_plan(twin: Twin, brief: DecisionBrief, settings: OrganizationSettings, run_id: str,
                 ) -> PortfolioComparison:
    plan_id = single_plan_id(brief.candidate_interventions)
    result = _run(twin, brief, plan_id, list(brief.candidate_interventions), settings, run_id)
    portfolio = Portfolio(plan_id=plan_id, intervention_ids=result.intervention_ids,
                          rank=1 if result.feasible else None, result=result)
    return PortfolioComparison(evaluated_count=1, naive=portfolio,
                               recommended=portfolio if result.feasible else None, alternatives=[])


def _order(result: SimulationResult) -> tuple[int, float, str]:
    return -result.value.net_value_usd, result.risk.score, result.plan_id or ""


def _naive(brief: DecisionBrief, results: dict[frozenset[str], SimulationResult]) -> list[Intervention]:
    """Largest gross saver first until the goal is met (all of them if it never is)."""
    single = {i.id: results[frozenset({i.id})].value.gross_savings_usd for i in brief.candidate_interventions}
    greedy = sorted(brief.candidate_interventions, key=lambda i: (-single[i.id], i.id))
    chosen: list[Intervention] = []
    for intervention in greedy:
        chosen.append(intervention)
        if results[frozenset(i.id for i in chosen)].goal_met:
            break
    order = {i.id: n for n, i in enumerate(brief.candidate_interventions)}
    return sorted(chosen, key=lambda i: order[i.id])


def optimize(twin: Twin, brief: DecisionBrief, *, settings: OrganizationSettings | None = None,
             run_id: str = "run_adhoc") -> PortfolioComparison:
    """Evaluate every portfolio of ``brief``'s candidate interventions and pick naive and recommended."""
    settings = settings or OrganizationSettings()
    if brief.decision_type is not DecisionType.vendor_consolidation:
        return _single_plan(twin, brief, settings, run_id)
    candidates = brief.candidate_interventions
    results: dict[frozenset[str], SimulationResult] = {}
    for size in range(len(candidates) + 1):
        for subset in combinations(candidates, size):
            chosen = list(subset)
            results[frozenset(i.id for i in chosen)] = _run(twin, brief, plan_id_for(chosen), chosen, settings, run_id)

    feasible = sorted((r for r in results.values() if r.feasible), key=_order)
    rank = {r.plan_id: n for n, r in enumerate(feasible, start=1)}

    def portfolio(result: SimulationResult) -> Portfolio:
        return Portfolio(plan_id=result.plan_id or "", intervention_ids=result.intervention_ids,
                         rank=rank.get(result.plan_id), result=result)

    naive_interventions = _naive(brief, results)
    naive_key = frozenset(i.id for i in naive_interventions)
    naive_result = _run(twin, brief, NAIVE_PLAN_ID, naive_interventions, settings, run_id)
    naive = Portfolio(plan_id=NAIVE_PLAN_ID, intervention_ids=naive_result.intervention_ids,
                      rank=rank.get(results[naive_key].plan_id), result=naive_result)

    recommended = portfolio(feasible[0]) if feasible else None
    shown = {results[naive_key].plan_id, *([recommended.plan_id] if recommended else [])}
    alternatives: list[Portfolio] = []
    if feasible:
        cheapest = min(feasible, key=lambda r: (r.value.gross_savings_usd - r.value.net_value_usd, *_order(r)))
        safest = min(feasible, key=lambda r: (r.risk.score, *_order(r)))
        for pick in (cheapest, safest):
            if pick.plan_id not in shown:
                shown.add(pick.plan_id)
                alternatives.append(portfolio(pick))
    rejected = sorted((r for r in results.values() if not r.feasible and r.plan_id not in shown),
                      key=lambda r: (-r.value.gross_savings_usd, r.plan_id or ""))
    alternatives += [portfolio(r) for r in rejected]
    return PortfolioComparison(evaluated_count=len(results), naive=naive, recommended=recommended,
                               alternatives=alternatives)
