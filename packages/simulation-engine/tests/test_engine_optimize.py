"""Vendor portfolio optimizer (plan C-06, sections 4.1, 11.5, 19.2; stories V-2 to V-7)."""

from __future__ import annotations

import json
import time

import pytest
from contracts_py.decision import DecisionBrief
from contracts_py.enums import EntityType

from company_twin import entity_map, load_twin
from company_twin.loader import default_fixture_path
from simulation_engine import check_result, optimize, quick_impact
from simulation_engine.constraints import BROKEN_LOSS

TWIN = load_twin(default_fixture_path())
DATA = default_fixture_path().parent
VENDOR = DecisionBrief.model_validate(json.loads((DATA / "vendor_scenario.json").read_text()))
WORKFORCE = DecisionBrief.model_validate(json.loads((DATA / "workforce_scenario.json").read_text()))


@pytest.fixture(scope="module")
def comparison():
    return optimize(TWIN, VENDOR, run_id="run_opt")


def every_portfolio(comparison):
    return [comparison.naive, *([comparison.recommended] if comparison.recommended else []), *comparison.alternatives]


def constraint(result, constraint_id):
    return next(c for c in result.constraint_results if c.constraint_id == constraint_id)


def picks(*names):
    by_id = {i.id: i for i in VENDOR.candidate_interventions}
    return [by_id[f"remove_{n}"] for n in names]


def test_v2_vendor_costs_total_8b_and_all_128_portfolios_are_evaluated(comparison):
    vendors = [e for e in TWIN.entities if e.type is EntityType.vendor]
    assert sum(v.annual_cost_usd for v in vendors) == 8_000_000_000
    assert comparison.evaluated_count == 128


def test_v3_naive_is_greedy_apex_plus_cinder_and_is_infeasible(comparison):
    naive = comparison.naive
    assert naive.plan_id == "plan_naive"
    assert naive.intervention_ids == ["remove_apex", "remove_cinder"]
    assert naive.rank is None and not naive.result.feasible
    coverage = constraint(naive.result, "c_coverage")
    assert not coverage.passed and coverage.value < 100
    assert "ds_corporate_linkage" in coverage.explanation
    assert any(r.startswith("c_coverage") for r in naive.result.rejection_reasons)


def test_v4_recommended_is_beacon_plus_echo_ranked_first_with_every_line_separate(comparison):
    best = comparison.recommended
    assert best is not None and best.plan_id == "plan_beacon_echo" and best.rank == 1
    result = best.result
    assert result.feasible and result.goal_met and all(c.passed for c in result.constraint_results if c.hard)
    v = result.value
    assert v.gross_savings_usd == 2_300_000_000
    assert v.transition_cost_usd == 220_000_000
    assert "$90,000,000 vendor termination and $130,000,000 migration" in " ".join(result.assumptions)
    assert 100_000_000 <= v.added_cost_usd <= 140_000_000
    assert v.expected_business_loss_usd == 0
    assert 1_900_000_000 <= v.net_value_usd <= 2_000_000_000
    assert v.net_value_usd == (v.gross_savings_usd - v.transition_cost_usd - v.added_cost_usd - v.rebound_cost_usd
                               - v.expected_business_loss_usd - v.pressure_cost_usd + v.avoided_failure_cost_usd)
    feasible = [p for p in every_portfolio(comparison) if p.result.feasible]
    assert all(p.result.value.net_value_usd <= v.net_value_usd for p in feasible)


def test_v5_removing_delta_alone_breaks_kyc_compliance():
    result = quick_impact(TWIN, picks("delta"), brief=VENDOR)
    compliance = constraint(result, "c_compliance")
    assert not compliance.passed and compliance.value == 1
    assert "ctl_kyc_screening" in compliance.explanation
    assert not result.feasible


def test_v6_every_plan_saving_under_2b_is_rejected_with_a_reason(comparison):
    small = [p for p in every_portfolio(comparison) if p.result.value.gross_savings_usd < 2_000_000_000]
    assert small
    for p in small:
        assert not p.result.feasible and p.rank is None
        assert p.result.rejection_reasons[0].startswith("goal:")


def _intent_providers_left(result):
    losses = {i.affected_entity: i.magnitude for i in result.impacts if i.polarity.value == "harm"}
    providers = [e.source for e in TWIN.edges if e.target == "ds_intent_signals" and e.relation.value == "PROVIDES"]
    return [p for p in providers if losses.get(p, 0.0) < BROKEN_LOSS]


def test_v7_two_individually_safe_removals_are_unsafe_together():
    for alone in ("cinder", "echo"):
        result = quick_impact(TWIN, picks(alone), brief=VENDOR)
        assert _intent_providers_left(result)
        assert constraint(result, "c_sales").passed
    both = quick_impact(TWIN, picks("cinder", "echo"), brief=VENDOR)
    assert _intent_providers_left(both) == []
    assert not constraint(both, "c_sales").passed and not both.feasible


def test_alternatives_hold_lowest_cost_lowest_risk_and_every_rejected_plan(comparison):
    candidates = VENDOR.candidate_interventions
    subsets = [[c for n, c in enumerate(candidates) if mask >> n & 1] for mask in range(2 ** len(candidates))]
    independent = [quick_impact(TWIN, s, brief=VENDOR) for s in subsets]
    feasible = [r for r in independent if r.feasible]
    infeasible = {frozenset(r.intervention_ids) for r in independent if not r.feasible}

    ranked = [p for p in comparison.alternatives if p.rank is not None]
    rejected = [p for p in comparison.alternatives if p.rank is None]
    assert all(p.result.feasible for p in ranked)
    assert all(not p.result.feasible and p.result.rejection_reasons for p in rejected)
    assert {frozenset(p.intervention_ids) for p in rejected} | {frozenset(comparison.naive.intervention_ids)} == infeasible
    shown = [comparison.recommended, *ranked]
    lowest_cost = min(r.value.gross_savings_usd - r.value.net_value_usd for r in feasible)
    assert lowest_cost in {p.result.value.gross_savings_usd - p.result.value.net_value_usd for p in shown}
    assert min(r.risk.score for r in feasible) in {p.result.risk.score for p in shown}


def test_every_output_passes_check_result(comparison):
    assert check_result(comparison, TWIN) == []


def test_same_input_gives_the_same_ranking_and_leaves_the_baseline_alone(comparison):
    before = TWIN.model_dump_json()
    again = optimize(TWIN, VENDOR, run_id="run_opt")
    assert again.model_dump_json() == comparison.model_dump_json()
    assert TWIN.model_dump_json() == before


def test_128_portfolios_run_in_under_5_seconds():
    started = time.perf_counter()
    optimize(TWIN, VENDOR)
    assert time.perf_counter() - started < 5


def test_non_vendor_briefs_evaluate_the_single_proposed_plan():
    comparison = optimize(TWIN, WORKFORCE)
    assert comparison.evaluated_count == 1
    assert comparison.naive.intervention_ids == [item.id for item in WORKFORCE.candidate_interventions]
    assert not comparison.naive.result.feasible
    assert comparison.recommended is None


def test_vendor_entities_carry_the_exit_and_migration_costs_the_engine_charges():
    ents = entity_map(TWIN)
    result = quick_impact(TWIN, picks("beacon", "echo"), brief=VENDOR)
    expected = sum((ents[v].one_time_exit_cost_usd or 0) + (ents[v].migration_cost_usd or 0)
                   for v in ("vendor_beacon", "vendor_echo"))
    assert result.value.transition_cost_usd == expected
