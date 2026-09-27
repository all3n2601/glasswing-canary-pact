"""The missing-fact selector and vendor history retention (plan sections 11.10, 19.5; E-06, V-11)."""

from __future__ import annotations

import json
import re
import time

import pytest
from contracts_py.decision import CandidatePlan, Constraint, DecisionBrief, Goal, Intervention
from contracts_py.engine import MissingQuestion
from contracts_py.enums import ActionType, Criticality, EntityType, Future, InterventionKind, Relation
from contracts_py.twin import Edge, Entity

from company_twin import load_twin
from company_twin.loader import default_fixture_path
from simulation_engine import compare_futures, missing_questions, optimize, simulate
from simulation_engine import questions as selector
from simulation_engine.futures import scenario_for
from simulation_engine.questions import COST_OF_ANSWER_USD, NO_CHANGE, scored_questions
from simulation_engine.simulate import bounded_id

TWIN = load_twin(default_fixture_path())
DATA = default_fixture_path().parent
VENDOR = DecisionBrief.model_validate(json.loads((DATA / "vendor_scenario.json").read_text()))
PLANTED = json.loads((DATA / "planted_items.json").read_text())["planted_unknown"]
BEACON_ECHO = CandidatePlan(plan_id="plan_beacon_echo", label="Recommended plan (remove_beacon, remove_echo)",
                            intervention_ids=["remove_beacon", "remove_echo"], source="optimizer")
ID = re.compile(r"^[a-z][a-z0-9_]*$")
REAL_BRIEF_BUDGET_S = 10


def with_history(twin, vendor_id: str, retains: bool | None):
    return twin.model_copy(update={"entities": [
        e.model_copy(update={"retains_history_after_termination": retains}) if e.id == vendor_id else e
        for e in twin.entities]})


# A toy portfolio: vendor_a ($100M, $10M exit) shares ds_shared with a vendor that stays, and nearly all of its
# coverage is substitutable; vendor_c ($70M) alone provides ds_solo, which nothing downstream reads. The optimizer
# presents plan A + C (net $160M, recommended), plan A (naive, $90M) and plan C (cheapest, $70M).


def vendor(vendor_id: str, cost: int, retains: bool | None, exit_cost: int = 0) -> Entity:
    return Entity(id=vendor_id, type=EntityType.vendor, name=vendor_id.replace("_", " ").title(),
                  annual_cost_usd=cost, one_time_exit_cost_usd=exit_cost, migration_cost_usd=0,
                  retains_history_after_termination=retains)


def edge(source: str, target: str, relation: Relation, strength: float, substitutability: float) -> Edge:
    return Edge(id=f"e_{source}_{target}", source=source, target=target, relation=relation, strength=strength,
                substitutability=substitutability, lag_days=0, criticality=Criticality.high, confidence=0.9)


TOY = TWIN.model_copy(update={
    "entities": [vendor("vendor_a", 100_000_000, None, 10_000_000), vendor("vendor_keep", 50_000_000, True),
                 vendor("vendor_c", 70_000_000, True),
                 *(Entity(id=d, type=EntityType.dataset, name=d) for d in ("ds_shared", "ds_solo")),
                 Entity(id="kpi_sales", type=EntityType.kpi, name="Sales")],
    "edges": [edge("vendor_a", "ds_shared", Relation.PROVIDES, 0.9, 0.9),
              edge("vendor_keep", "ds_shared", Relation.PROVIDES, 0.8, 0.5),
              edge("vendor_c", "ds_solo", Relation.PROVIDES, 1.0, 0.0),
              edge("ds_shared", "kpi_sales", Relation.CONSUMES, 1.0, 0.0)],
    "pressures": [], "department_profiles": [],
})
TOY_BRIEF = VENDOR.model_copy(update={
    "candidate_interventions": [
        Intervention(id=f"remove_{v}", kind=InterventionKind.action, type=ActionType.remove_vendor,
                     target_entity_id=f"vendor_{v}", start_day=30, rationale="toy") for v in ("a", "c")],
    "constraints": [Constraint(id="c_sales", metric="revenue_impact_pct", operator="<=", threshold=5, unit="percent",
                               hard=True, scope_entity_id="kpi_sales", description="Sales fall at most 5%")],
    "goal": Goal(metric="annual_savings_usd", target=50_000_000), "active_pressure_ids": [],
})
TOY_PLAN = CandidatePlan(plan_id="plan_a_c", label="Remove A and C", intervention_ids=["remove_a", "remove_c"],
                         source="optimizer")


def winner(twin, brief, plan):
    """The compared winner against every portfolio the optimizer presents on the base toy twin."""
    portfolios = optimize(TOY, brief)
    alternatives = [CandidatePlan(plan_id=p.plan_id, label=p.plan_id, intervention_ids=p.intervention_ids,
                                  source="enumerated")
                    for p in [portfolios.naive, portfolios.recommended, *portfolios.alternatives]]
    comparison = compare_futures(twin, brief, plan, alternatives=alternatives)
    return comparison.rows[comparison.best_row_index]


@pytest.fixture(scope="module")
def toy_scored():
    return scored_questions(TOY, TOY_BRIEF, TOY_PLAN)


def test_a_null_history_fact_whose_false_answer_flips_the_winner_ranks_first(toy_scored):
    assert winner(TOY, TOY_BRIEF, TOY_PLAN).plan_id == "plan_a_c"
    assert winner(with_history(TOY, "vendor_a", False), TOY_BRIEF, TOY_PLAN).plan_id == "plan_c"
    first, *rest = toy_scored
    q = first.question
    assert q.uncertain_input == "vendor_a.retains_history_after_termination"
    assert q.question_id == "q_vendor_a_retains_history_after_termination"
    assert (q.answer_type, q.options) == ("boolean", ["true", "false"])
    assert "assumes Vendor A retains history" in q.current_assumption
    assert q.changes_recommendation_if == ("false: the winner becomes Alternative: Alternative plan (remove_c) "
                                           "(point estimate)")
    # Under False, plan A + C (net $160M) and plan A lose sales above 5% and plan C (net $70M) wins.
    assert first.probability == 0.5 and q.value_gap_usd == 160_000_000 - 70_000_000
    assert rest and all(r.probability == 0 and r.question.changes_recommendation_if == NO_CHANGE for r in rest)
    assert all(r.score < first.score for r in rest)


def test_the_score_is_probability_times_gap_minus_cost_and_orders_the_questions(toy_scored):
    for s in toy_scored:
        assert s.score == s.probability * s.question.value_gap_usd - s.cost_usd
    assert toy_scored[0].cost_usd == COST_OF_ANSWER_USD["vendor_fact"]
    edge_question = next(s for s in toy_scored if s.question.uncertain_input.endswith(".strength"))
    assert edge_question.cost_usd == COST_OF_ANSWER_USD["edge_strength"]
    # No answer changes the winner, so its gap is the winner's margin over the runner-up (naive plan A, $90M).
    assert edge_question.question.value_gap_usd == 160_000_000 - 90_000_000
    assert [s.score for s in toy_scored] == sorted((s.score for s in toy_scored), reverse=True)


def test_question_ids_are_valid_bounded_and_the_ranking_is_deterministic(toy_scored):
    assert [q.question for q in toy_scored] == missing_questions(TOY, TOY_BRIEF, TOY_PLAN)
    for s in toy_scored:
        MissingQuestion.model_validate(s.question.model_dump())
        assert ID.match(s.question.question_id) and len(s.question.question_id) <= 80
    long = bounded_id("q_", "vendor_" + "x" * 80 + "_retains_history_after_termination")
    assert ID.match(long) and len(long) <= 80


def test_skipping_rejected_plans_that_cannot_recover_gives_the_same_ranking(toy_scored, monkeypatch):
    monkeypatch.setattr(selector, "_can_recover", lambda *_: True)
    assert scored_questions(TOY, TOY_BRIEF, TOY_PLAN) == toy_scored


def test_a_known_history_fact_is_not_asked_about():
    known = with_history(TOY, "vendor_a", True)
    assert all("retains_history" not in q.uncertain_input for q in missing_questions(known, TOY_BRIEF, TOY_PLAN))


# History retention in remove_vendor (plan E-06)


def act_now(twin, brief=VENDOR, plan=BEACON_ECHO):
    return simulate(twin, brief, scenario_for(twin, brief, "run_q", Future.act_now, plan), plan, "full")


def test_history_retained_and_unknown_give_identical_results():
    assert PLANTED["entity_id"] == "vendor_echo" and PLANTED["intended_value"] is None
    unknown = act_now(TWIN)
    assert act_now(with_history(TWIN, "vendor_echo", True)).model_dump_json() == unknown.model_dump_json()
    toy = act_now(TOY, TOY_BRIEF, TOY_PLAN)
    assert act_now(with_history(TOY, "vendor_a", True), TOY_BRIEF, TOY_PLAN).model_dump_json() == toy.model_dump_json()


def test_history_lost_after_termination_is_strictly_worse():
    kept, lost = act_now(TWIN), act_now(with_history(TWIN, "vendor_echo", False))
    assert lost.value.net_value_usd < kept.value.net_value_usd
    assert lost.value.gross_savings_usd == kept.value.gross_savings_usd
    harm = {i.affected_entity: i.magnitude for i in kept.impacts if i.polarity.value == "harm" and i.unit == "ratio"}
    worse = {i.affected_entity: i.magnitude for i in lost.impacts if i.polarity.value == "harm" and i.unit == "ratio"}
    assert all(worse[e] >= m for e, m in harm.items())
    assert worse["ds_account_intel"] > harm["ds_account_intel"]
    assert "vendor_echo keeps no history after termination" in " ".join(lost.assumptions)


# The real vendor brief (plan E-06 acceptance: the planted sensitive unknown ranks first)


@pytest.fixture(scope="module")
def vendor_scored():
    started = time.perf_counter()
    scored = scored_questions(TWIN, VENDOR, BEACON_ECHO, run_id="run_q")
    return scored, time.perf_counter() - started


def test_real_brief_questions_are_valid_and_within_the_time_budget(vendor_scored):
    scored, elapsed = vendor_scored
    assert elapsed < REAL_BRIEF_BUDGET_S
    assert scored and len({s.question.question_id for s in scored}) == len(scored)
    for s in scored:
        MissingQuestion.model_validate(s.question.model_dump())
        assert ID.match(s.question.question_id)


def test_the_planted_unknown_ranks_first_and_its_false_answer_changes_the_winner(vendor_scored):
    scored, _ = vendor_scored
    first = scored[0].question
    assert first.uncertain_input == f"{PLANTED['entity_id']}.{PLANTED['field']}"
    assert scored[0].probability == 0.5 and scored[0].score > scored[1].score
    assert first.changes_recommendation_if == ("false: the winner becomes Alternative: Alternative plan "
                                               "(remove_beacon, remove_flux) (point estimate)")
    lost = act_now(with_history(TWIN, "vendor_echo", False))
    sales = next(c for c in lost.constraint_results if c.constraint_id == "c_sales")
    assert not sales.passed and not lost.feasible
