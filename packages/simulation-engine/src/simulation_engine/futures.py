"""Take it, leave it, or wait: the futures comparison (plan section 11.2; schema v2.2.0 section 7.7, rule 13, A12).

``compare_futures`` simulates every future the brief requests (inaction always) for one plan,
plus one ``alternative`` row per alternative plan, and compares each against inaction. It runs in
expected-value mode (A12) until Monte Carlo lands (plan E-03):

- ``net_value_p50_usd`` is the expected net value, and ``delta_vs_inaction_p10 = p50 = p90`` is
  the expected difference from inaction;
- ``p_better_than_inaction`` is 1.0 when that delta is positive, else 0.0 (inaction: 0.0): a yes/no
  comparison, not a probability;
- ``breakeven_day`` is the end of the first month whose cumulative net value exceeds inaction's;
- ``cost_of_delay_usd`` (delay row only) is act-now net value minus delay net value;
- ``monthly_delta_usd`` is the cumulative difference from inaction per month;
- ``best_row_index`` is the feasible row with the largest delta, ties to lower risk, then order;
- the headline follows the A12 template: "Acting now is worth $X more than doing nothing;
  waiting N days costs $Y.", then says the values are point estimates and p_better is yes/no;
- every row label ends in "(point estimate)", and each row's result carries the same assumptions.

Scenario IDs are ``scn_{run_id}_{future}_{plan_id or none}``, the IDs the orchestrator gives the
same futures, so each row's ``result_id`` matches the orchestrator's simulated result.
"""

from __future__ import annotations

from datetime import datetime, time, timezone

from contracts_py.decision import CandidatePlan, DecisionBrief, Scenario
from contracts_py.engine import FutureComparison, FutureRow, SimulationResult
from contracts_py.enums import Future
from contracts_py.twin import OrganizationSettings, Twin

from .blast import money
from .simulate import POINT_ESTIMATE, bounded_id, simulate
from .value import DAYS_PER_MONTH

COMPARED_MODE = "full"
# Expected-value mode labels every row and the headline: no simulated ranges exist yet (plan E-03).
ROW_LABEL_SUFFIX = f" ({POINT_ESTIMATE})"
HEADLINE_NOTE = (f" Values are {POINT_ESTIMATE}s, not simulated ranges; p_better_than_inaction is a yes/no "
                 "comparison, not a probability.")


def scenario_for(twin: Twin, brief: DecisionBrief, run_id: str, future: Future,
                 plan: CandidatePlan | None) -> Scenario:
    plan_id = None if future is Future.inaction or plan is None else plan.plan_id
    return Scenario(
        scenario_id=bounded_id("scn_", f"{run_id}_{future.value}_{plan_id or 'none'}"), run_id=run_id, future=future,
        plan_id=plan_id, delay_days=brief.delay_days if future is Future.delay else 0,
        baseline_twin_version=twin.version.twin_version,
        created_at=datetime.combine(twin.version.as_of_date, time(), tzinfo=timezone.utc),
    )


def _breakeven_day(result: SimulationResult, inaction: SimulationResult, horizon_days: int) -> int | None:
    months = len(result.value.monthly_net_usd)
    for m, (net, reference) in enumerate(zip(result.value.monthly_net_usd, inaction.value.monthly_net_usd)):
        if net > reference:
            return horizon_days if m == months - 1 else (m + 1) * DAYS_PER_MONTH
    return None


def _row(result: SimulationResult, inaction: SimulationResult, label: str, horizon_days: int,
         cost_of_delay: int | None = None) -> FutureRow:
    reference = result.future is Future.inaction
    delta = 0 if reference else result.value.net_value_usd - inaction.value.net_value_usd
    return FutureRow(
        future=result.future, plan_id=result.plan_id, result_id=result.result_id, label=label + ROW_LABEL_SUFFIX,
        net_value_p50_usd=result.value.net_value_usd, delta_vs_inaction_p10_usd=delta,
        delta_vs_inaction_p50_usd=delta, delta_vs_inaction_p90_usd=delta,
        p_better_than_inaction=1.0 if delta > 0 else 0.0,
        breakeven_day=None if reference else _breakeven_day(result, inaction, horizon_days),
        cost_of_delay_usd=cost_of_delay, feasible=result.feasible, risk_score=result.risk.score,
        monthly_delta_usd=[0] * len(result.value.monthly_net_usd) if reference else
        [n - r for n, r in zip(result.value.monthly_net_usd, inaction.value.monthly_net_usd)],
    )


def _headline(act_now: SimulationResult, inaction: SimulationResult, delay: SimulationResult | None,
              delay_days: int) -> str:
    delta = act_now.value.net_value_usd - inaction.value.net_value_usd
    text = f"Acting now is worth {money(abs(delta))} {'more' if delta >= 0 else 'less'} than doing nothing"
    if delay is not None:
        cost = act_now.value.net_value_usd - delay.value.net_value_usd
        text += f"; waiting {delay_days} days {'costs' if cost >= 0 else 'saves'} {money(abs(cost))}"
    text += "."
    if not act_now.feasible:
        text += f" As planned it is infeasible ({len(act_now.rejection_reasons)} failed checks)."
    return text + HEADLINE_NOTE


def compare_futures(twin: Twin, brief: DecisionBrief, plan: CandidatePlan, *,
                    alternatives: list[CandidatePlan] | None = None, settings: OrganizationSettings | None = None,
                    run_id: str = "run_adhoc") -> FutureComparison:
    """Every requested future of ``plan`` (and each alternative plan) against inaction, in expected-value mode."""
    settings = settings or OrganizationSettings()

    def run(future: Future, chosen: CandidatePlan | None) -> SimulationResult:
        scenario = scenario_for(twin, brief, run_id, future, chosen)
        return simulate(twin, brief, scenario, None if future is Future.inaction else chosen, COMPARED_MODE,
                        settings=settings)

    requested = list(dict.fromkeys(f for f in brief.futures if f is not Future.alternative))
    inaction = run(Future.inaction, None)
    act_now = run(Future.act_now, plan)
    delay = run(Future.delay, plan) if Future.delay in requested else None
    horizon = brief.horizon_days

    rows: list[FutureRow] = []
    for future in requested:
        if future is Future.inaction:
            rows.append(_row(inaction, inaction, "Do nothing", horizon))
        elif future is Future.act_now:
            rows.append(_row(act_now, inaction, f"{plan.label}, now", horizon))
        elif future is Future.delay and delay is not None:
            rows.append(_row(delay, inaction, f"{plan.label}, in {brief.delay_days} days", horizon,
                             cost_of_delay=act_now.value.net_value_usd - delay.value.net_value_usd))
    seen = {plan.plan_id}
    for alternative in alternatives or []:
        if alternative.plan_id in seen:
            continue
        seen.add(alternative.plan_id)
        rows.append(_row(run(Future.alternative, alternative), inaction, f"Alternative: {alternative.label}", horizon))

    feasible = [n for n, row in enumerate(rows) if row.feasible]
    best = min(feasible, key=lambda n: (-rows[n].delta_vs_inaction_p50_usd, rows[n].risk_score, n), default=None)
    return FutureComparison(
        comparison_id=bounded_id("cmp_", f"{run_id}_{plan.plan_id}"), decision_id=brief.decision_id, run_id=run_id,
        reference_result_id=inaction.result_id, rows=rows, best_row_index=best,
        headline=_headline(act_now, inaction, delay, brief.delay_days),
    )
