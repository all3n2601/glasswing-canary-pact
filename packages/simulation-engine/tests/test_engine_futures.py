"""Pressures, the three futures, and compare_futures (plan E-01, E-02, section 11.2; schema 5.5, 6.6, 7.7, A12;
stories V-1, V-9; rule 13)."""

from __future__ import annotations

import json

import pytest
from contracts_py.decision import CandidatePlan, DecisionBrief
from contracts_py.enums import Future, PressureKind
from contracts_py.twin import Pressure

from company_twin import entity_map, load_twin
from company_twin.loader import default_fixture_path
from simulation_engine import blast_radius, check_result, compare_futures, optimize, simulate
from simulation_engine.blast import money
from simulation_engine.futures import scenario_for
from simulation_engine.pressures import Harm, active_pressures, price_pressures
from simulation_engine.simulate import EXPECTED_VALUE_ASSUMPTIONS

TWIN = load_twin(default_fixture_path())
DATA = default_fixture_path().parent
VENDOR = DecisionBrief.model_validate(json.loads((DATA / "vendor_scenario.json").read_text()))
WORKFORCE = DecisionBrief.model_validate(json.loads((DATA / "workforce_scenario.json").read_text()))
ENTS = entity_map(TWIN)
PRESSURES = {p.id: p for p in TWIN.pressures}
RUN = "run_fut"


def plan_of(brief: DecisionBrief, plan_id: str, *intervention_ids: str) -> CandidatePlan:
    ids = list(intervention_ids) or [i.id for i in brief.candidate_interventions]
    return CandidatePlan(plan_id=plan_id, label="Recommended plan", intervention_ids=ids, source="optimizer")


BEACON_ECHO = plan_of(VENDOR, "plan_beacon_echo", "remove_beacon", "remove_echo")
EIGHT_ROLES = plan_of(WORKFORCE, "plan_remove_eight_roles")


def run(future: Future, brief: DecisionBrief = VENDOR, plan: CandidatePlan = BEACON_ECHO, mode: str = "full"):
    scenario = scenario_for(TWIN, brief, RUN, future, plan)
    return simulate(TWIN, brief, scenario, None if future is Future.inaction else plan, mode)


def trigger(result, pressure_id):
    return next(t for t in result.pressures_triggered if t.pressure_id == pressure_id)


@pytest.fixture(scope="module")
def vendor_futures():
    return compare_futures(TWIN, VENDOR, BEACON_ECHO, run_id=RUN)


# Pressures (schema 5.5)


def price(pressure: Pressure, interventions=(), harms=None):
    return price_pressures(TWIN, [pressure], list(interventions), harms=harms or {}, horizon_days=365,
                           decision_id="dec_test", scenario_id="scn_test", scale_usd=2_000_000_000)


def test_renewal_step_is_priced_from_the_renewal_day():
    apex = PRESSURES["pr_apex_renewal"]
    priced = price(apex)
    assert priced.total_usd == round(ENTS["vendor_apex"].annual_cost_usd * 0.08 * (365 - 60) / 365)
    assert priced.triggers[0].expected_events == 1 and not priced.triggers[0].neutralised
    assert priced.monthly_usd[1] == 0 < priced.monthly_usd[2] and priced.monthly_usd[-1] == priced.total_usd


def test_cost_growth_compounds_monthly():
    flux = PRESSURES["pr_flux_usage_growth"]
    base = ENTS["vendor_flux"].annual_cost_usd
    days = [30] * 11 + [35]
    expected = sum(base * d / 365 * ((1 + flux.rate) ** (k + 1) - 1) for k, d in enumerate(days))
    assert price(flux).total_usd == round(expected)


def test_hazard_probability_rises_with_capacity_loss_from_the_day_it_starts():
    hazard = PRESSURES["pr_billing_recon_hazard"]
    calm = price(hazard)
    assert calm.total_usd == round(hazard.monthly_probability * 365 / 30 * hazard.cost_per_event_usd)
    stressed = price(hazard, harms={"wf_billing_recon": Harm(0.5, 30)})
    boosted = hazard.monthly_probability * (1 + hazard.capacity_sensitivity * 0.5)
    events = (hazard.monthly_probability * 30 + boosted * 335) / 30
    assert stressed.triggers[0].expected_events == pytest.approx(events, abs=1e-6)
    assert stressed.total_usd == round(events * hazard.cost_per_event_usd)
    assert hazard.capacity_sensitivity > 0


def test_neutralised_by_stops_a_pressure_on_the_neutraliser_start_day():
    echo = PRESSURES["pr_echo_renewal"]
    removal = next(i for i in VENDOR.candidate_interventions if i.id == "remove_echo")
    early = price(echo, [removal])
    assert early.total_usd == 0 and early.triggers[0].neutralised and early.impacts == []
    late = price(echo, [removal.model_copy(update={"start_day": 150})])
    assert late.total_usd == round(ENTS["vendor_echo"].annual_cost_usd * 0.12 * 30 / 365)
    assert late.triggers[0].neutralised
    other = next(i for i in VENDOR.candidate_interventions if i.id == "remove_apex")
    assert not price(echo, [other]).triggers[0].neutralised


def test_deadline_is_charged_once_and_unpriced_kinds_say_so():
    deadline = Pressure(id="pr_test_deadline", kind=PressureKind.deadline, name="Filing deadline",
                        target_entity_id="ctl_sox_reconciliation", start_day=200, consequence_cost_usd=5_000_000,
                        description="test")
    assert price(deadline).total_usd == 5_000_000 and price(deadline).triggers[0].expected_events == 1
    drift = Pressure(id="pr_test_drift", kind=PressureKind.kpi_drift, name="Margin drift", rate=-0.01,
                     target_entity_id="kpi_gross_margin", description="test")
    priced = price(drift)
    assert priced.total_usd == 0 and any("no dollar cost" in a for a in priced.assumptions)


def test_the_brief_selects_the_active_pressures():
    assert [p.id for p in active_pressures(TWIN, VENDOR.active_pressure_ids)] == sorted(VENDOR.active_pressure_ids)
    assert len(active_pressures(TWIN, None)) == len(TWIN.pressures)
    with pytest.raises(ValueError):
        active_pressures(TWIN, ["pr_missing"])


def test_every_future_prices_every_active_pressure():
    for future in (Future.inaction, Future.act_now, Future.delay):
        result = run(future)
        assert sorted(t.pressure_id for t in result.pressures_triggered) == sorted(VENDOR.active_pressure_ids)
        assert result.value.pressure_cost_usd == sum(t.expected_cost_usd for t in result.pressures_triggered)
        costed = [i for i in result.impacts if i.source_kind == "pressure"]
        assert {i.source_ref for i in costed} == {t.pressure_id for t in result.pressures_triggered
                                                  if t.expected_cost_usd > 0}


# The three futures (schema 6.6)


def test_v1_inaction_loses_money_and_pressure_is_its_largest_line():
    result = run(Future.inaction)
    v = result.value
    assert result.future is Future.inaction and result.plan_id is None and result.intervention_ids == []
    assert v.net_value_usd < 0 and v.net_value_usd == -v.pressure_cost_usd
    lines = [v.gross_savings_usd, v.transition_cost_usd, v.added_cost_usd, v.rebound_cost_usd,
             v.expected_business_loss_usd, v.avoided_failure_cost_usd]
    assert all(v.pressure_cost_usd > line for line in lines)
    assert not any(t.neutralised for t in result.pressures_triggered)
    # Missing the goal is the reason to act, not a rejection of doing nothing.
    assert not result.goal_met and result.feasible and result.rejection_reasons == []
    assert check_result(result, TWIN) == []


def test_act_now_neutralises_the_echo_renewal_and_keeps_the_others():
    result = run(Future.act_now)
    assert trigger(result, "pr_echo_renewal").neutralised and trigger(result, "pr_echo_renewal").expected_cost_usd == 0
    assert trigger(result, "pr_apex_renewal").expected_cost_usd > 0
    assert result.value.gross_savings_usd == 2_300_000_000
    assert result.feasible and result.goal_met


def test_delay_shifts_the_plan_and_neutralisation_starts_after_the_delay():
    now, later = run(Future.act_now), run(Future.delay)
    assert later.future is Future.delay and later.plan_id == "plan_beacon_echo"
    savings = [i for i in later.impacts if i.metric == "annual_cost_usd"]
    assert {i.first_effect_day for i in savings} == {30 + VENDOR.delay_days}
    # Savings accrue at the act-now daily rate from day 120, so 90 of the 330 accrual days are lost.
    assert later.value.gross_savings_usd == round(2_300_000_000 * (360 - 120) / (360 - 30))
    assert later.goal_met and later.feasible  # judged on the annual run rate
    assert any(a.startswith("Delay future") for a in later.assumptions)

    longer = VENDOR.model_copy(update={"delay_days": 120})
    waited = simulate(TWIN, longer, scenario_for(TWIN, longer, RUN, Future.delay, BEACON_ECHO), BEACON_ECHO, "full")
    assert trigger(waited, "pr_echo_renewal").expected_cost_usd == round(1_100_000_000 * 0.12 * 30 / 365)
    assert trigger(now, "pr_echo_renewal").expected_cost_usd == 0


def test_full_mode_falls_back_to_expected_value_with_equal_percentiles():
    for future in (Future.inaction, Future.act_now, Future.delay):
        full, quick = run(future, mode="full"), run(future, mode="quick")
        v = full.value
        assert full.mode == "full" and full.seed == VENDOR.seed
        assert v.p10_net_value_usd == v.p50_net_value_usd == v.p90_net_value_usd == v.net_value_usd
        assert all(a in full.assumptions for a in EXPECTED_VALUE_ASSUMPTIONS)
        assert quick.mode == "quick" and quick.seed is None
        assert (quick.value.p10_net_value_usd, quick.value.p50_net_value_usd, quick.value.p90_net_value_usd) == \
            (None, None, None)
        assert not set(EXPECTED_VALUE_ASSUMPTIONS) & set(quick.assumptions)
        assert quick.value.net_value_usd == v.net_value_usd
        assert check_result(full, TWIN) == [] and check_result(quick, TWIN) == []


# compare_futures (schema 7.7, A12)


def test_rule_13_one_row_per_requested_future_with_matching_ids(vendor_futures):
    rows = vendor_futures.rows
    assert [r.future for r in rows] == list(VENDOR.futures)
    for row in rows:
        plan_id = None if row.future is Future.inaction else "plan_beacon_echo"
        assert row.plan_id == plan_id
        assert row.result_id == f"res_{RUN}_{row.future.value}_{plan_id or 'none'}"
    inaction = next(r for r in rows if r.future is Future.inaction)
    assert vendor_futures.reference_result_id == inaction.result_id
    assert (inaction.delta_vs_inaction_p10_usd, inaction.delta_vs_inaction_p50_usd,
            inaction.delta_vs_inaction_p90_usd, inaction.p_better_than_inaction) == (0, 0, 0, 0.0)
    assert inaction.breakeven_day is None and inaction.monthly_delta_usd == [0] * 12
    assert vendor_futures.comparison_id == f"cmp_{RUN}_plan_beacon_echo"
    assert check_result(vendor_futures, TWIN) == []


def test_expected_value_rows_have_equal_deltas_and_a_yes_no_comparison(vendor_futures):
    results = {f: run(f) for f in (Future.inaction, Future.act_now, Future.delay)}
    base = results[Future.inaction].value.net_value_usd
    for row in vendor_futures.rows:
        result = results[row.future]
        delta = result.value.net_value_usd - base
        assert row.net_value_p50_usd == result.value.net_value_usd
        assert row.delta_vs_inaction_p10_usd == row.delta_vs_inaction_p50_usd == row.delta_vs_inaction_p90_usd == delta
        assert row.p_better_than_inaction == (1.0 if delta > 0 else 0.0)
        assert len(row.monthly_delta_usd) == 12 and row.monthly_delta_usd[-1] == delta
        assert row.feasible == result.feasible and row.risk_score == result.risk.score


def test_v9_waiting_costs_money_and_breakeven_comes_later(vendor_futures):
    rows = {r.future: r for r in vendor_futures.rows}
    now, later = rows[Future.act_now], rows[Future.delay]
    assert later.cost_of_delay_usd == now.net_value_p50_usd - later.net_value_p50_usd
    assert later.cost_of_delay_usd > 0
    assert now.cost_of_delay_usd is None and rows[Future.inaction].cost_of_delay_usd is None
    assert now.breakeven_day is not None and later.breakeven_day is not None
    assert now.breakeven_day < later.breakeven_day
    first = next(m for m, d in enumerate(now.monthly_delta_usd) if d > 0)
    assert now.breakeven_day == (first + 1) * 30


def test_best_row_and_the_a12_headline(vendor_futures):
    rows = vendor_futures.rows
    assert rows[vendor_futures.best_row_index].future is Future.act_now
    now = next(r for r in rows if r.future is Future.act_now)
    delay = next(r for r in rows if r.future is Future.delay)
    assert vendor_futures.headline == (f"Acting now is worth {money(now.delta_vs_inaction_p50_usd)} more than doing "
                                       f"nothing; waiting 90 days costs {money(delay.cost_of_delay_usd)}.")


def test_alternative_plans_get_one_row_each():
    alternative = plan_of(VENDOR, "plan_beacon_flux", "remove_beacon", "remove_flux")
    comparison = compare_futures(TWIN, VENDOR, BEACON_ECHO, alternatives=[alternative, alternative, BEACON_ECHO],
                                 run_id=RUN)
    extra = [r for r in comparison.rows if r.future is Future.alternative]
    assert [r.plan_id for r in extra] == ["plan_beacon_flux"]
    assert extra[0].result_id == f"res_{RUN}_alternative_plan_beacon_flux"
    assert check_result(comparison, TWIN) == []


def test_no_feasible_row_but_inaction_makes_doing_nothing_the_best_row():
    comparison = compare_futures(TWIN, WORKFORCE, EIGHT_ROLES, run_id=RUN)
    assert [r.future for r in comparison.rows] == list(WORKFORCE.futures)
    best = comparison.rows[comparison.best_row_index]
    assert best.future is Future.inaction
    assert "infeasible" in comparison.headline
    assert check_result(comparison, TWIN) == []


def test_same_inputs_give_byte_identical_futures_and_leave_the_baseline_alone(vendor_futures):
    before = TWIN.model_dump_json()
    assert compare_futures(TWIN, VENDOR, BEACON_ECHO, run_id=RUN).model_dump_json() == vendor_futures.model_dump_json()
    assert run(Future.delay).model_dump_json() == run(Future.delay).model_dump_json()
    assert TWIN.model_dump_json() == before


# Blast radius of doing nothing (schema 7.10)


def test_inaction_blast_radius_is_rooted_at_do_nothing_with_a_pressure_ring():
    result = run(Future.inaction)
    blast = blast_radius(result, TWIN)
    root = next(n for n in blast.nodes if n.node_id == blast.root_node_id)
    assert root.kind == "decision" and root.headline == "Do nothing"
    ring = {e.target for e in blast.edges if e.source == root.node_id}
    pressures = {n.node_id for n in blast.nodes if n.kind == "pressure"}
    assert ring == pressures == {t.pressure_id for t in result.pressures_triggered if t.expected_cost_usd > 0}
    assert all(e.label == "Pressure" for e in blast.edges if e.source == root.node_id or e.source in pressures)
    assert {e.target for e in blast.edges if e.source in pressures} == {PRESSURES[p].target_entity_id
                                                                         for p in pressures}
    assert blast.future is Future.inaction and blast.plan_id is None
    assert check_result(blast, TWIN) == []


# Both briefs, as the orchestrator calls the engine


@pytest.mark.parametrize("brief", [VENDOR, WORKFORCE], ids=lambda b: b.decision_id)
def test_orchestrator_call_sequence_runs_end_to_end(brief):
    """optimize, simulate(..., "full") for inaction, act_now and delay, compare_futures, and both blast radii."""
    run_id = "run_orch"
    portfolio = optimize(TWIN, brief, run_id=run_id)
    assert check_result(portfolio, TWIN) == []
    chosen = portfolio.recommended or portfolio.naive
    plan = CandidatePlan(plan_id=chosen.plan_id, label="Chosen plan", intervention_ids=chosen.intervention_ids,
                         source="optimizer")
    results = {}
    for future in (Future.inaction, Future.act_now, Future.delay):
        scenario = scenario_for(TWIN, brief, run_id, future, plan)
        results[future] = simulate(TWIN, brief, scenario, plan if scenario.plan_id else None, "full")
        assert check_result(results[future], TWIN) == []
    comparison = compare_futures(TWIN, brief, plan, alternatives=[], run_id=run_id)
    assert check_result(comparison, TWIN) == []
    assert {r.result_id for r in comparison.rows} == {r.result_id for r in results.values()}
    for row in comparison.rows:
        assert row.net_value_p50_usd == results[row.future].value.net_value_usd
    for future in (Future.act_now, Future.inaction):
        assert check_result(blast_radius(results[future], TWIN), TWIN) == []


def test_cost_split_fields_break_down_transition_and_added_cost_without_changing_net():
    ents = ENTS
    for future in (Future.act_now, Future.delay):
        v = run(future).value
        assert v.termination_cost_usd == ents["vendor_beacon"].one_time_exit_cost_usd + \
            ents["vendor_echo"].one_time_exit_cost_usd
        assert v.migration_cost_usd == ents["vendor_beacon"].migration_cost_usd + ents["vendor_echo"].migration_cost_usd
        # The plan has no other one-off costs or investments, so the split is exact here.
        assert v.termination_cost_usd + v.migration_cost_usd == v.transition_cost_usd
        assert v.displaced_work_cost_usd == v.added_cost_usd > 0
    inaction = run(Future.inaction).value
    assert (inaction.termination_cost_usd, inaction.migration_cost_usd, inaction.displaced_work_cost_usd) == (0, 0, 0)
    optimized = optimize(TWIN, VENDOR, run_id=RUN).recommended.result.value
    assert optimized.termination_cost_usd + optimized.migration_cost_usd == optimized.transition_cost_usd
