from datetime import datetime, timezone

import importlib

import pytest
from contracts_py.decision import CandidatePlan
from contracts_py.enums import Future

from agent_orchestration.orchestrator import MAX_ID_LENGTH, _Run, bounded_id

# The package re-exports a function named simulate, so the module is fetched by name.
engine_ids = importlib.import_module("simulation_engine.simulate")
NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("body", ["run_abc_act_now_plan_beacon_echo", "run_" + "x" * 30 + "_act_now_plan_" + "y" * 60])
def test_bounded_id_matches_the_engine(body) -> None:
    ours = bounded_id("scn_", body)
    assert ours == engine_ids.bounded_id("scn_", body)
    assert len(ours) <= MAX_ID_LENGTH


def test_long_plan_id_gives_a_capped_deterministic_scenario_id(brief, twin, settings) -> None:
    run = _Run(brief, twin, engine=None, settings=settings, llm=None, emit=lambda *a, **k: None,  # type: ignore[arg-type]
               run_id="run_0123456789ab", clock=lambda: NOW)
    plan_id = "plan_" + "_".join(f"remove_vendor_number_{n}" for n in range(6))
    plan = CandidatePlan(plan_id=plan_id[:80], label="long", intervention_ids=[], source="enumerated")
    scenario = run.scenario(Future.act_now, plan)
    body = f"run_0123456789ab_act_now_{plan.plan_id}"
    assert len("scn_" + body) > MAX_ID_LENGTH
    assert len(scenario.scenario_id) <= MAX_ID_LENGTH
    assert scenario.scenario_id == engine_ids.bounded_id("scn_", body)
    assert run.scenario(Future.act_now, plan).scenario_id == scenario.scenario_id

    short = CandidatePlan(plan_id="plan_beacon_echo", label="short", intervention_ids=[], source="optimizer")
    assert run.scenario(Future.delay, short).scenario_id == "scn_run_0123456789ab_delay_plan_beacon_echo"
