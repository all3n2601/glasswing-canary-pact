import re

from canary_api.stubs import engine, results
from canary_api.stubs.twin import sample_brief, stub_twin, workforce_brief
from contracts_py.decision import CandidatePlan
from contracts_py.enums import Future

PERSON_TOKEN = re.compile(r"\bpt_[a-z0-9_]+")


def test_vendor_story_constants() -> None:
    decision = sample_brief().decision_id
    act = results.act_now_result("run_x", decision)
    assert decision == "dec_vendor_reduction"
    assert (act.plan_id, act.intervention_ids, act.value.gross_savings_usd, act.feasible) == (
        "plan_beacon_echo", ["remove_beacon", "remove_echo"], 2_300_000_000, True)
    naive = results.naive_result("run_x", decision)
    assert (naive.plan_id, naive.intervention_ids, naive.feasible) == ("plan_naive", ["remove_apex", "remove_cinder"], False)
    assert "ds_corporate_linkage" in naive.rejection_reasons[0]
    inaction = results.inaction_result("run_x", decision)
    assert inaction.value.gross_savings_usd == 0 and inaction.value.pressure_cost_usd > 0
    rows = {row.future: row for row in results.future_comparison("run_x", decision).rows}
    assert rows[Future.delay].cost_of_delay_usd and rows[Future.delay].cost_of_delay_usd > 0
    assert rows[Future.act_now].delta_vs_inaction_p50_usd > rows[Future.delay].delta_vs_inaction_p50_usd


def test_workforce_story_strands_two_workflows_before_mitigation() -> None:
    brief = workforce_brief()
    assert brief.decision_id == "dec_workforce_knowledge" and len(brief.candidate_interventions) == 8
    naive = results.naive_result("run_x", brief.decision_id)
    assert naive.plan_id == "plan_remove_eight_roles" and not naive.feasible
    assert {w.workflow_id for w in naive.workflow_coverage if w.stranded} == {"wf_financial_close", "wf_billing_recon"}
    mitigated = results.act_now_result("run_x", brief.decision_id)
    assert mitigated.plan_id == "plan_remove_eight_roles_mitigated" and mitigated.feasible
    assert not [w for w in mitigated.workflow_coverage if w.stranded]
    plan = CandidatePlan(plan_id="plan_remove_eight_roles", label="x", intervention_ids=[], source="naive")
    scenario = results.scenario("run_x", Future.act_now, plan.plan_id)
    assert engine.simulate(stub_twin(), brief, scenario, plan, "full").plan_id == "plan_remove_eight_roles"


def test_briefs_only_reference_twin_ids() -> None:
    twin = stub_twin()
    entities, pressures = {e.id for e in twin.entities}, {p.id for p in twin.pressures}
    for brief in (sample_brief(), workforce_brief()):
        assert {i.target_entity_id for i in brief.candidate_interventions} <= entities
        assert set(brief.active_pressure_ids or []) <= pressures
    assert not PERSON_TOKEN.search(stub_twin().model_dump_json())


HEADLINE = re.compile(r"worth \$(?P<act>[\d.]+)(?P<act_unit>[MB]) more than doing nothing; "
                      r"waiting (?P<days>\d+) days costs \$(?P<delay>[\d.]+)(?P<delay_unit>[MB])\.$")
SCALE = {"M": 1_000_000, "B": 1_000_000_000}


def stated(amount: str, unit: str) -> tuple[float, float]:
    decimals = len(amount.partition(".")[2])
    return float(amount) * SCALE[unit], 0.5 * 10 ** -decimals * SCALE[unit]


def test_headlines_state_the_row_values() -> None:
    for brief in (sample_brief(), workforce_brief()):
        comparison = results.future_comparison("run_x", brief.decision_id)
        match = HEADLINE.search(comparison.headline)
        assert match, comparison.headline
        rows = {row.future: row for row in comparison.rows}
        act, act_tolerance = stated(match["act"], match["act_unit"])
        delay, delay_tolerance = stated(match["delay"], match["delay_unit"])
        assert abs(act - rows[Future.act_now].delta_vs_inaction_p50_usd) <= act_tolerance
        assert rows[Future.delay].cost_of_delay_usd is not None
        assert abs(delay - rows[Future.delay].cost_of_delay_usd) <= delay_tolerance
        assert int(match["days"]) == brief.delay_days
