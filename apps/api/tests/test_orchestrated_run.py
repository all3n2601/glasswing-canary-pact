import asyncio
import hashlib
import inspect
import json
import re
import threading
import time

import pytest
from api_auth_helpers import auth_headers

import company_twin
from agent_orchestration.ports import EnginePort
from canary_api import engine_port, runs, runtime
from canary_api.paths import DATA_DIR
from contracts_py.enums import RunStatus
from contracts_py.events import AgentStarted, Event, EventLog, EventType
from contracts_py.package import DecisionPackage
from contracts_py.twin import OrganizationSettings


def wait_for(client, run_id: str, status: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get(f"/runs/{run_id}").json()
        if state["status"] == status:
            return state
        assert state["status"] != "failed", runtime.bus.runs[run_id].events[-1].payload
        time.sleep(0.02)
    raise AssertionError(f"{run_id} never reached {status}")


def protocol_methods() -> dict[str, inspect.Signature]:
    return {
        name: inspect.signature(member)
        for name, member in vars(EnginePort).items()
        if inspect.isfunction(member) and not name.startswith("_")
    }


def test_engine_port_satisfies_engine_protocol_structurally() -> None:
    methods = protocol_methods()
    assert methods
    for name, expected in methods.items():
        actual = getattr(engine_port, name, None)
        assert callable(actual), f"engine_port.{name} is missing"
        wanted = [(p.name, p.kind) for p in expected.parameters.values() if p.name != "self"]
        got = [(p.name, p.kind) for p in inspect.signature(actual).parameters.values()]
        assert got == wanted, f"engine_port.{name} parameters {got} do not match {wanted}"


def test_thread_emitter_publishes_on_the_loop_in_order(monkeypatch) -> None:
    publish_threads: set[int] = set()
    real_publish = runtime.bus.publish

    def tracking_publish(*args, **kwargs):
        publish_threads.add(threading.get_ident())
        return real_publish(*args, **kwargs)

    monkeypatch.setattr(runtime.bus, "publish", tracking_publish)

    async def scenario() -> int:
        runtime.bus.create_run("run_threads", "dec_cut_2m", "stub-twin-1")
        emit = runs.ThreadEmitter("run_threads", asyncio.get_running_loop(), runtime.twin())

        def worker(n: int) -> None:
            for i in range(25):
                emit(EventType.agent_started, AgentStarted(agent_id=f"agent_{n}_{i}"), actor=f"thread_{n}")

        await asyncio.gather(*(asyncio.to_thread(worker, n) for n in range(4)))
        await asyncio.sleep(0.05)
        return threading.get_ident()

    loop_thread = asyncio.run(scenario())
    events = runtime.bus.runs["run_threads"].events
    assert [e.sequence for e in events] == list(range(1, 101))
    assert publish_threads == {loop_thread}
    for n in range(4):
        mine = [e.payload.agent_id for e in events if e.actor == f"thread_{n}"]
        assert mine == [f"agent_{n}_{i}" for i in range(25)]


def test_mock_decision_runs_real_orchestrator_to_approval(client, brief_json) -> None:
    run_id = client.post("/decisions?llm_mode=mock", headers=auth_headers(client), json=brief_json).json()["run_id"]
    wait_for(client, run_id, "awaiting_approval")
    events = runtime.bus.runs[run_id].events
    assert events[0].type is EventType.run_created
    assert not [e for e in events if e.type is EventType.settings_updated]
    assert runs.MOCK_FALLBACK_ASSUMPTION not in client.get(f"/runs/{run_id}/package").json()["assumptions"]
    assessments = [e.payload for e in events if e.type is EventType.agent_completed]
    assert assessments and all(a.status == "ok" and a.metrics.model_id == "mock" for a in assessments)
    EventLog.model_validate([e.model_dump(mode="json") for e in events])

    response = client.get(f"/runs/{run_id}/package")
    assert response.status_code == 200
    package = DecisionPackage.model_validate(response.json())
    assert package.run_id == run_id

    with client.websocket_connect(f"/runs/{run_id}/events") as ws:
        received = [Event.model_validate_json(ws.receive_text()) for _ in events]
    assert [e.sequence for e in received] == list(range(1, len(events) + 1))

    decision = client.post(f"/runs/{run_id}/decision", headers=auth_headers(client), json={
        "decision": "approve", "decided_by": "demo_user",
        "package_hash": hashlib.sha256(response.content).hexdigest(),
    })
    assert decision.status_code == 200
    assert client.get(f"/runs/{run_id}").json()["status"] == "completed"


def test_websocket_mid_orchestrated_run_gets_every_sequence_once(client, brief_json) -> None:
    run_id = client.post("/decisions?llm_mode=mock", headers=auth_headers(client), json=brief_json).json()["run_id"]
    with client.websocket_connect(f"/runs/{run_id}/events") as ws:
        received: list[Event] = []
        while not received or not (received[-1].type is EventType.phase_changed
                                   and received[-1].payload.to_status is RunStatus.awaiting_approval):
            received.append(Event.model_validate_json(ws.receive_text()))
    assert [e.sequence for e in received] == list(range(1, len(received) + 1))


def test_empty_replay_cache_falls_back_to_mock_with_a_package_assumption(client, brief_json) -> None:
    assert runtime.cache_is_empty(runtime.llm_cache_dir())
    run_id = client.post("/decisions", headers=auth_headers(client), json=brief_json).json()["run_id"]
    wait_for(client, run_id, "awaiting_approval")
    events = runtime.bus.runs[run_id].events
    assert events[0].type is EventType.run_created
    assert not [e for e in events if e.type is EventType.settings_updated]
    package = client.get(f"/runs/{run_id}/package").json()
    assert package["assumptions"].count(runs.MOCK_FALLBACK_ASSUMPTION) == 1
    assessments = [e.payload for e in events if e.type is EventType.agent_completed]
    assert assessments and not [a for a in assessments if a.status in ("unavailable", "fallback_cached")]


def test_replay_with_cached_answers_stays_in_replay(monkeypatch, tmp_path) -> None:
    (tmp_path / "finance").mkdir()
    (tmp_path / "finance" / "abc.json").write_text(json.dumps({"agent_id": "finance"}))
    monkeypatch.setenv("CANARY_LLM_CACHE_DIR", str(tmp_path))
    resolved, fell_back = runs.resolve_llm_settings(OrganizationSettings(), None)
    assert (resolved.llm_mode, fell_back) == ("replay", False)
    assert runtime.build_llm(resolved).cache_dir == tmp_path
    live, fell_back = runs.resolve_llm_settings(OrganizationSettings(), "live")
    assert (live.llm_mode, fell_back) == ("live", False)


def test_bad_llm_mode_is_rejected(client, brief_json) -> None:
    assert client.post("/decisions?llm_mode=chatty", headers=auth_headers(client), json=brief_json).status_code == 422


def test_real_mode_loads_synthetic_company_with_optional_snippets(monkeypatch) -> None:
    calls = []
    stub = runtime.twin()
    monkeypatch.setattr(company_twin, "load_twin", lambda path, snippets=None: calls.append((path, snippets)) or stub,
                        raising=False)
    monkeypatch.setenv("ENGINE_IMPL", "real")
    monkeypatch.setitem(runtime._twins, "real", None)
    runtime._twins.pop("real")
    assert runtime.twin() is stub
    snippets = DATA_DIR / "artifacts" / "snippets.json"
    assert calls == [(DATA_DIR / "synthetic_company.json", snippets if snippets.is_file() else None)]


PERSON_TOKEN = re.compile(r"\bpt_[a-z0-9_]+")


def test_failed_publish_marks_the_run_failed() -> None:
    runtime.bus.create_run("run_publish_fails", "dec_cut_2m", "stub-twin-1")
    twin = runtime.twin()
    runs._publish("run_publish_fails", EventType.agent_started, AgentStarted(agent_id="finance"), "finance", None,
                  None, twin, [])
    # A payload of the wrong model for its event type cannot be published.
    runs._publish("run_publish_fails", EventType.simulation_completed, AgentStarted(agent_id="finance"), "engine",
                  None, None, twin, [])
    runs._publish("run_publish_fails", EventType.agent_started, AgentStarted(agent_id="ops"), "ops", None, None,
                  twin, [])
    events = runtime.bus.runs["run_publish_fails"].events
    assert [e.type for e in events] == [EventType.agent_started, EventType.phase_changed, EventType.run_failed]
    assert events[1].payload.to_status is RunStatus.failed
    assert "simulation_completed" in events[2].payload.reason
    assert runtime.bus.runs["run_publish_fails"].state.status is RunStatus.failed


def leak_person_tokens(monkeypatch) -> None:
    from canary_api.stubs import engine as stub_engine

    original = stub_engine.simulate

    def simulate(*args, **kwargs):
        result = original(*args, **kwargs)
        impacts = [i.model_copy(update={"affected_entity": "pt_07", "assumptions": ["owned by pt_07"]})
                   for i in result.impacts]
        return result.model_copy(update={"impacts": impacts, "assumptions": [*result.assumptions, "pt_07 leaves"]})

    monkeypatch.setattr(stub_engine, "simulate", simulate)


def all_event_text(run_id: str) -> str:
    return "\n".join(e.model_dump_json() for e in runtime.bus.runs[run_id].events)


def test_to_role_level_keeps_person_tokens_out_of_events(client, brief_json, monkeypatch) -> None:
    from canary_api.stubs import engine as stub_engine

    leak_person_tokens(monkeypatch)
    calls: list[str] = []

    def to_role_level(obj, twin):
        calls.append(type(obj).__name__)
        text = obj.model_dump_json() if hasattr(obj, "model_dump_json") else json.dumps(obj)
        return json.loads(PERSON_TOKEN.sub("role_billing_ops_lead", text))

    monkeypatch.setattr(stub_engine, "to_role_level", to_role_level)
    run_id = client.post("/decisions?llm_mode=mock", headers=auth_headers(client), json=brief_json).json()["run_id"]
    wait_for(client, run_id, "awaiting_approval")
    assert "SimulationResult" in calls
    assert not PERSON_TOKEN.search(all_event_text(run_id))


def test_person_tokens_left_by_the_engine_fail_the_run_without_leaking(client, brief_json, monkeypatch) -> None:
    leak_person_tokens(monkeypatch)
    run_id = client.post("/decisions?llm_mode=mock", headers=auth_headers(client), json=brief_json).json()["run_id"]
    wait_for(client, run_id, "failed")
    events = runtime.bus.runs[run_id].events
    failures = [e.payload.reason for e in events if e.type is EventType.run_failed]
    assert len(failures) == 1 and "person tokens" in failures[0]
    assert not PERSON_TOKEN.search(all_event_text(run_id))


def test_live_mode_needs_explicit_opt_in(client, brief_json, monkeypatch) -> None:
    monkeypatch.delenv("CANARY_ALLOW_LIVE", raising=False)
    denied = client.post("/decisions?llm_mode=live", headers=auth_headers(client), json=brief_json)
    assert denied.status_code == 403
    assert "CANARY_ALLOW_LIVE" in denied.json()["detail"]
    monkeypatch.setenv("CANARY_ALLOW_LIVE", "true")
    assert runs.live_allowed()
    monkeypatch.setenv("CANARY_ALLOW_LIVE", "yes")
    assert not runs.live_allowed()
