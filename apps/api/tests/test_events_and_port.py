import json
import os
import subprocess
import sys
import types
import time

import pytest

from canary_api import engine_port, runtime, storage
from canary_api.paths import REPLAYS_DIR
from canary_api.storage import FileStorage
from canary_api.stubs.run import sample_run
from canary_api.stubs.twin import stub_twin
from contracts_py.events import Event, EventLog, EventType
from contracts_py.package import DecisionPackage


def test_sample_run_file_is_a_valid_event_log() -> None:
    raw = json.loads((REPLAYS_DIR / "sample_run.json").read_text())
    log = EventLog.model_validate(raw)
    sequences = [e.sequence for e in log.root]
    assert sequences == sorted(set(sequences))
    assert log.model_dump(mode="json") == sample_run().model_dump(mode="json")

    types = [e.type for e in log.root]
    assert types[0] is EventType.run_created
    assert types.count(EventType.blast_radius_ready) == 2
    for kind in (EventType.simulation_completed, EventType.futures_compared, EventType.portfolio_ranked,
                 EventType.package_ready):
        assert kind in types
    completed = [e.payload.agent_id for e in log.root if e.type is EventType.agent_completed]
    assert len(set(completed)) == 5
    assert all(e.payload.status == "replayed" for e in log.root if e.type is EventType.agent_completed)
    statuses = {e.payload.to_status for e in log.root if e.type is EventType.phase_changed}
    assert statuses == {
        "validating", "building_futures", "optimizing", "running_agents", "propagating", "challenging",
        "comparing_futures", "generating_package", "awaiting_approval",
    }
    assert not [s for s in json.dumps(raw).split('"') if s.startswith("pt_")]


def test_websocket_mid_run_receives_every_sequence_once_in_order(client, monkeypatch) -> None:
    monkeypatch.setenv("CANARY_REPLAY_STEP_SECONDS", "0.03")
    total = len(sample_run().root)
    run_id = client.post("/replays/sample_run/play").json()["run_id"]

    deadline = time.monotonic() + 5
    while client.get(f"/runs/{run_id}").json()["last_sequence"] < 5:
        assert time.monotonic() < deadline
        time.sleep(0.01)

    received = []
    with client.websocket_connect(f"/runs/{run_id}/events") as ws:
        connected_at = client.get(f"/runs/{run_id}").json()["last_sequence"]
        while len(received) < total:
            received.append(Event.model_validate_json(ws.receive_text()))
    assert connected_at < total
    assert [e.sequence for e in received] == list(range(1, total + 1))
    assert {e.run_id for e in received} == {run_id}


def test_stream_drops_live_events_already_sent_as_history() -> None:
    import asyncio

    async def scenario() -> list[int]:
        bus = runtime.bus
        bus.create_run("run_dedupe", "dec_vendor_reduction", "stub-northstar-1")
        events = sample_run().root
        for event in events[:3]:
            bus.publish("run_dedupe", event.type, event.payload.model_dump(mode="json"), actor=event.actor)
        stream = bus.stream("run_dedupe")
        seen = [(await anext(stream)).sequence]
        # A live copy of an event already sent as history must be skipped.
        queue = next(iter(bus.runs["run_dedupe"].subscribers))
        queue.put_nowait(bus.runs["run_dedupe"].events[1])
        for event in events[3:5]:
            bus.publish("run_dedupe", event.type, event.payload.model_dump(mode="json"), actor=event.actor)
        for _ in range(4):
            seen.append((await anext(stream)).sequence)
        await stream.aclose()
        return seen

    assert asyncio.run(scenario()) == [1, 2, 3, 4, 5]


def test_events_are_persisted_as_jsonl(client) -> None:
    run_id = client.post("/replays/sample_run/play?speed=4").json()["run_id"]
    deadline = time.monotonic() + 5
    while client.get(f"/runs/{run_id}").json()["status"] != "awaiting_approval":
        assert time.monotonic() < deadline
        time.sleep(0.02)
    lines = (runtime.bus.root / run_id / "events.jsonl").read_text().splitlines()
    EventLog.model_validate([json.loads(line) for line in lines])
    assert len(lines) == len(sample_run().root)
    assert json.loads((runtime.bus.root / run_id / "state.json").read_text())["status"] == "awaiting_approval"


def test_package_guard_rejects_person_tokens(client, monkeypatch) -> None:
    package = next(e.payload for e in sample_run().root if e.type is EventType.package_ready)
    leaked = package.model_dump(mode="json")
    leaked["open_questions"].append("Ask pt_07 about reconciliation")
    with pytest.raises(ValueError, match="person tokens"):
        DecisionPackage.model_validate(leaked)

    run_id = client.post("/replays/sample_run/play?speed=4").json()["run_id"]
    deadline = time.monotonic() + 5
    while client.get(f"/runs/{run_id}").json()["status"] != "awaiting_approval":
        assert time.monotonic() < deadline
        time.sleep(0.02)
    monkeypatch.setattr(engine_port, "to_role_level", lambda obj, twin: {**obj.model_dump(mode="json"),
                                                                          "open_questions": ["Ask pt_07"]})
    response = client.get(f"/runs/{run_id}/package")
    assert response.status_code == 422
    assert "person tokens" in response.json()["detail"]


def test_real_engine_missing_function_gives_clear_error(client, monkeypatch, tmp_path) -> None:
    # Stand-in modules without the functions, so this keeps testing the error path however far the
    # real twin and engine packages have got.
    monkeypatch.setitem(sys.modules, "simulation_engine", types.ModuleType("simulation_engine"))
    monkeypatch.setitem(sys.modules, "company_twin", types.ModuleType("company_twin"))
    monkeypatch.setenv("ENGINE_IMPL", "real")
    with pytest.raises(engine_port.EngineNotReady, match=r"simulation_engine\.quick_impact"):
        engine_port.quick_impact(stub_twin(), [])
    with pytest.raises(engine_port.EngineNotReady, match=r"company_twin\.load_twin"):
        engine_port.load_twin(REPLAYS_DIR)
    # With no stored twin to fall back on, the seed load fails and the API answers 503.
    monkeypatch.setattr(storage, "_current", FileStorage(tmp_path))
    monkeypatch.setattr(runtime, "_twin", None)
    response = client.get("/company")
    assert response.status_code == 503
    assert "seed loading failed" in response.json()["detail"]


def test_runtime_defaults_to_the_real_engine_and_twin(client, monkeypatch) -> None:
    monkeypatch.delenv("ENGINE_IMPL", raising=False)
    monkeypatch.delenv("TWIN_IMPL", raising=False)
    assert (engine_port.engine_impl(), engine_port.twin_impl()) == ("real", "real")
    assert client.get("/company").json()["organization"]["id"] == "org_northstar"


def test_real_engine_does_not_crash_at_import() -> None:
    env = {**os.environ, "ENGINE_IMPL": "real"}
    result = subprocess.run([sys.executable, "-c", "import canary_api.app"], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_replay_rewrites_only_run_id_fields() -> None:
    import asyncio

    from canary_api import runs

    events = sample_run().root
    package_event = next(e for e in events if e.type is EventType.package_ready)
    note = f"Recorded as {package_event.run_id}; check run_sample before approving."
    package = package_event.payload.model_copy(update={"open_questions": [note]})
    edited = [e.model_copy(update={"payload": package}) if e is package_event else e for e in events]

    runtime.bus.create_run("run_rewrite", "dec_vendor_reduction", "stub-northstar-1")
    asyncio.run(runs.play("run_rewrite", edited, 0))

    replayed = runtime.bus.runs["run_rewrite"]
    assert replayed.state.status == "awaiting_approval"
    assert replayed.package is not None
    assert replayed.package.run_id == "run_rewrite"
    assert replayed.package.futures.run_id == "run_rewrite"
    assert replayed.package.portfolios.naive.result.run_id == "run_rewrite"
    assert replayed.package.open_questions == [note]
    assert replayed.package.package_id == package.package_id
    assert runs.rewrite_run_ids({"a": [{"run_id": "run_old", "text": "run_old"}]}, "run_new") == {
        "a": [{"run_id": "run_new", "text": "run_old"}]
    }


def test_stub_clone_with_edges_keeps_extraction_method() -> None:
    from canary_api.stubs import engine as stub_engine

    twin = stub_twin()
    agent_edge = twin.edges[0].model_copy(update={"id": "e_agent_probe", "extraction_method": "agent"})
    cloned = stub_engine.clone_with_edges(twin, [agent_edge])
    assert next(e for e in cloned.edges if e.id == "e_agent_probe").extraction_method == "agent"
    assert "e_agent_probe" not in {e.id for e in twin.edges}


def test_real_clone_with_edges_keeps_extraction_method() -> None:
    twin = runtime.twin()
    agent_edge = twin.edges[0].model_copy(update={"id": "e_agent_probe", "extraction_method": "agent"})
    cloned = engine_port.clone_with_edges(twin, [agent_edge])
    assert next(e for e in cloned.edges if e.id == "e_agent_probe").extraction_method == "agent"
    assert "e_agent_probe" not in {e.id for e in twin.edges}
