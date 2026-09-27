import logging

import pytest
from canary_api.engine_port import EngineNotReady
from canary_api.stubs import results
from contracts_py.enums import ActionType

from agent_orchestration import AgentLLM, run_decision
from agent_orchestration.orchestrator import simulation_mode
from orchestration_helpers import NOW, Recorder, SpyEngine


def run(brief, twin, settings, engine):
    return run_decision(brief, engine=engine, settings=settings, llm=AgentLLM(settings), emit=Recorder(),
                        run_id="run_test", twin=twin, clock=lambda: NOW)


def test_package_vendor_overlaps_come_from_the_removed_vendors(brief, twin, settings) -> None:
    engine = SpyEngine()
    package = run(brief, twin, settings, engine)
    removed = [i.target_entity_id for i in brief.candidate_interventions if i.type is ActionType.remove_vendor]
    calls = [args for name, args in engine.calls if name == "vendor_overlap"]
    assert len(calls) == 1 and calls[0][1] == removed
    assert package.vendor_overlaps == results.vendor_overlaps(brief.decision_id) != []


def test_no_vendor_actions_means_no_overlap_call(people_brief, twin, settings) -> None:
    engine = SpyEngine()
    package = run(people_brief, twin, settings, engine)
    assert package.vendor_overlaps == [] and "vendor_overlap" not in engine.names()


class OverlapRaises(SpyEngine):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    def vendor_overlap(self, twin, vendor_ids):
        raise self.error


@pytest.mark.parametrize("error", [
    ValueError("vendor_apex is not a vendor in the twin"),
    EngineNotReady("ENGINE_IMPL=real but simulation_engine.vendor_overlap does not exist yet"),
])
def test_engine_overlap_error_is_reported_not_fatal(brief, twin, settings, error, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="agent_orchestration.orchestrator"):
        package = run(brief, twin, settings, OverlapRaises(error))
    assert package.vendor_overlaps == []
    assert f"Engine vendor_overlap: {error}" in package.assumptions
    assert type(error).__name__ in caplog.text


@pytest.mark.parametrize(("value", "expected"), [(None, "full"), ("quick", "quick"), ("full", "full")])
def test_sim_mode_env_reaches_simulate(brief, twin, settings, monkeypatch, value, expected) -> None:
    if value is None:
        monkeypatch.delenv("CANARY_SIM_MODE", raising=False)
    else:
        monkeypatch.setenv("CANARY_SIM_MODE", value)
    engine = SpyEngine()
    run(brief, twin, settings, engine)
    modes = {args[4] for name, args in engine.calls if name == "simulate"}
    assert modes == {expected}


def test_invalid_sim_mode_raises(monkeypatch) -> None:
    monkeypatch.setenv("CANARY_SIM_MODE", "turbo")
    with pytest.raises(ValueError, match="CANARY_SIM_MODE must be one of full, quick"):
        simulation_mode()
