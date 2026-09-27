"""quick_impact (schema v2.2.0 section 7.13, G3) on the full fixture, including the < 100 ms budget."""

from __future__ import annotations

import json
import time

from contracts_py.decision import DecisionBrief
from contracts_py.engine import SimulationResult
from contracts_py.enums import Future
from contracts_py.twin import OrganizationSettings

from company_twin import load_twin
from company_twin.loader import default_fixture_path
from simulation_engine import check_result, quick_impact
from simulation_engine.simulate import bounded_id

TWIN = load_twin(default_fixture_path())
DATA = default_fixture_path().parent
VENDOR = DecisionBrief.model_validate(json.loads((DATA / "vendor_scenario.json").read_text()))
WORKFORCE = DecisionBrief.model_validate(json.loads((DATA / "workforce_scenario.json").read_text()))


def picks(brief: DecisionBrief, *ids: str):
    by_id = {i.id: i for i in brief.candidate_interventions}
    return [by_id[i] for i in ids]


def test_without_a_brief_follows_g3():
    result = quick_impact(TWIN, picks(VENDOR, "remove_delta"))
    assert result.future is Future.act_now
    assert result.constraint_results == []
    assert result.goal_met is False
    assert result.feasible is True
    assert result.mode == "quick"


def test_every_output_passes_check_result():
    plans = [[i.id] for i in VENDOR.candidate_interventions] + [["remove_beacon", "remove_echo"], []]
    for ids in plans:
        for brief in (VENDOR, None):
            result = quick_impact(TWIN, picks(VENDOR, *ids), brief=brief)
            assert check_result(result, TWIN) == [], ids
    workforce = quick_impact(TWIN, WORKFORCE.candidate_interventions, brief=WORKFORCE)
    assert check_result(workforce, TWIN) == []
    assert workforce.goal_met


def test_beacon_and_echo_save_exactly_2_3b_gross_and_meet_the_goal():
    result = quick_impact(TWIN, picks(VENDOR, "remove_beacon", "remove_echo"), brief=VENDOR)
    assert result.value.gross_savings_usd == 2_300_000_000
    assert result.goal_met
    assert result.value.net_value_usd < result.value.gross_savings_usd


def test_removing_delta_harms_the_kyc_control_and_names_the_constraint():
    result = quick_impact(TWIN, picks(VENDOR, "remove_delta"), brief=VENDOR)
    kyc = next(i for i in result.impacts if i.affected_entity == "ctl_kyc_screening")
    assert kyc.source_ref == "remove_delta"
    assert kyc.dependency_path[0] == "vendor_delta"
    assert "c_compliance" in kyc.constraint_refs
    assert kyc.severity >= 4
    assert "dept_compliance" in result.affected_department_ids
    assert result.risk.components.compliance_control == OrganizationSettings().risk_weights.compliance_control


def test_same_inputs_give_byte_identical_output_and_leave_the_baseline_alone():
    before = TWIN.model_dump_json()
    first = quick_impact(TWIN, picks(VENDOR, "remove_beacon", "remove_echo"), brief=VENDOR, run_id="run_same")
    second = quick_impact(TWIN, picks(VENDOR, "remove_beacon", "remove_echo"), brief=VENDOR, run_id="run_same")
    assert first.model_dump_json() == second.model_dump_json()
    assert TWIN.model_dump_json() == before


def test_quick_impact_runs_under_100_ms_on_the_full_fixture():
    interventions = picks(VENDOR, "remove_beacon", "remove_echo")
    quick_impact(TWIN, interventions, brief=VENDOR)
    started = time.perf_counter()
    quick_impact(TWIN, interventions, brief=VENDOR)
    assert time.perf_counter() - started < 0.1


def test_a_70_character_run_id_gives_contract_valid_ids_that_match_the_act_now_scenario():
    run_id = "run_" + "r" * 66
    result = quick_impact(TWIN, picks(VENDOR, "remove_beacon", "remove_echo"), brief=VENDOR, run_id=run_id)
    assert len(run_id) == 70 and len(result.scenario_id) <= 80 and len(result.result_id) <= 80
    assert result.result_id.startswith("res_") and result.result_id != f"res_{run_id}_quick"
    assert SimulationResult.model_validate(result.model_dump()) == result
    # scenario_for's body with no plan; the Scenario contract itself only lets inaction go without a plan.
    assert result.scenario_id == bounded_id("scn_", f"{run_id}_{Future.act_now.value}_none")
    assert result.scenario_id == "scn_ef26eae24f33aed85f5faf55"
