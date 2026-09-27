import asyncio
import hashlib
import inspect
import json
import os
import re
import threading
import time

import pytest
from api_auth_helpers import auth_headers
from real_data import workforce_brief

from agent_orchestration.ports import EnginePort
from agent_orchestration.llm import sciforium_call
from canary_api import engine_port, runs, runtime, storage
from canary_api.storage import FileStorage
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
        runtime.bus.create_run("run_threads", "dec_vendor_reduction", "stub-northstar-1")
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


def test_orchestrated_decision_uses_explicit_test_provider_to_reach_approval(client, brief_json) -> None:
    run_id = client.post("/decisions", headers=auth_headers(client), json=brief_json).json()["run_id"]
    wait_for(client, run_id, "awaiting_approval")
    events = runtime.bus.runs[run_id].events
    assert events[0].type is EventType.run_created
    assert not [e for e in events if e.type is EventType.settings_updated]
    assessments = [e.payload for e in events if e.type is EventType.agent_completed]
    assert assessments and all(a.status == "ok" and a.metrics.model_id == "test-provider" for a in assessments)
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


@pytest.mark.live_agents
def test_runtime_builds_only_the_real_provider_client() -> None:
    llm = runtime.build_llm(OrganizationSettings(llm_mode="live"))
    assert llm.live_call is sciforium_call
    intake = runtime.build_intake(OrganizationSettings(llm_mode="live"))
    assert intake.live_call is sciforium_call
    with pytest.raises(ValueError, match="require llm_mode='live'"):
        runtime.build_llm(OrganizationSettings().model_copy(update={"llm_mode": "mock"}))
    with pytest.raises(ValueError, match="requires llm_mode='live'"):
        runtime.build_intake(OrganizationSettings().model_copy(update={"llm_mode": "mock"}))


LIVE_TEST_ENABLED = os.environ.get("CANARY_RUN_LIVE_TESTS", "").strip().lower() == "true"


@pytest.mark.live_agents
@pytest.mark.skipif(not LIVE_TEST_ENABLED, reason="set CANARY_RUN_LIVE_TESTS=true to make paid provider calls")
def test_live_provider_decision_reaches_approval_without_agent_substitutes(client, brief_json) -> None:
    response = client.post("/decisions", headers=auth_headers(client), json=brief_json)
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    wait_for(client, run_id, "awaiting_approval", timeout=180.0)

    events = runtime.bus.runs[run_id].events
    assessments = [event.payload for event in events if event.type is EventType.agent_completed]
    failures = [event.payload for event in events if event.type is EventType.agent_failed]
    assert assessments
    assert failures == []
    assert all(assessment.status == "ok" for assessment in assessments)
    assert all(assessment.metrics.model_id != "test-provider" for assessment in assessments)
    assert sum(assessment.metrics.input_tokens for assessment in assessments) > 0
    assert sum(assessment.metrics.output_tokens for assessment in assessments) > 0

    package_response = client.get(f"/runs/{run_id}/package")
    package = DecisionPackage.model_validate(package_response.json())
    assert package.run_id == run_id
    decision = client.post(f"/runs/{run_id}/decision", headers=auth_headers(client), json={
        "decision": "approve",
        "decided_by": "live_test",
        "package_hash": hashlib.sha256(package_response.content).hexdigest(),
    })
    assert decision.status_code == 200, decision.text
    assert client.get(f"/runs/{run_id}").json()["status"] == "completed"


@pytest.mark.live_agents
@pytest.mark.skipif(not LIVE_TEST_ENABLED, reason="set CANARY_RUN_LIVE_TESTS=true to make paid provider calls")
def test_live_free_text_is_structured_then_runs_only_live_agents(client) -> None:
    prompt = (
        "Remove BeaconIQ and EchoMarket to cut at least $2 billion in annual external-data spend while preserving "
        "compliance and critical data coverage."
    )
    response = client.post("/decisions/draft", headers=auth_headers(client), json={"prompt": prompt})
    assert response.status_code == 200, response.text
    draft = response.json()
    brief = draft["brief"]
    assert brief["decision_type"] == "vendor_consolidation"
    assert brief["goal"] == {
        "metric": "annual_savings_usd",
        "target": 2_000_000_000,
        "unit": "usd",
        "basis": "gross",
        "direction": "at_least",
    }
    assert {(item["type"], item["target_entity_id"]) for item in brief["candidate_interventions"]} == {
        ("remove_vendor", "vendor_beacon"),
        ("remove_vendor", "vendor_echo"),
    }
    assert {constraint["metric"] for constraint in brief["constraints"]} >= {
        "compliance_controls_broken",
        "critical_coverage_pct",
    }

    created = client.post("/decisions", headers=auth_headers(client), json=brief)
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]
    wait_for(client, run_id, "awaiting_approval", timeout=180.0)
    events = runtime.bus.runs[run_id].events
    assessments = [event.payload for event in events if event.type is EventType.agent_completed]
    assert assessments and all(assessment.status == "ok" for assessment in assessments)
    assert not [event for event in events if event.type is EventType.agent_failed]
    assert all(assessment.metrics.model_id != "test-provider" for assessment in assessments)

    package_response = client.get(f"/runs/{run_id}/package")
    assert package_response.status_code == 200, package_response.text
    package = DecisionPackage.model_validate(package_response.json())
    assert package.brief.goal.metric == "annual_savings_usd"
    assert package.brief.goal.target == 2_000_000_000
    decision = client.post(f"/runs/{run_id}/decision", headers=auth_headers(client), json={
        "decision": "approve",
        "decided_by": "live_free_text_test",
        "package_hash": hashlib.sha256(package_response.content).hexdigest(),
    })
    assert decision.status_code == 200, decision.text
    assert client.get(f"/runs/{run_id}").json()["status"] == "completed"


def test_websocket_mid_orchestrated_run_gets_every_sequence_once(client, brief_json) -> None:
    run_id = client.post("/decisions", headers=auth_headers(client), json=brief_json).json()["run_id"]
    with client.websocket_connect(f"/runs/{run_id}/events") as ws:
        received: list[Event] = []
        while not received or not (received[-1].type is EventType.phase_changed
                                   and received[-1].payload.to_status is RunStatus.awaiting_approval):
            received.append(Event.model_validate_json(ws.receive_text()))
    assert [e.sequence for e in received] == list(range(1, len(received) + 1))


def test_bad_llm_mode_is_rejected(client, brief_json) -> None:
    assert client.post("/decisions?llm_mode=chatty", headers=auth_headers(client), json=brief_json).status_code == 422
    assert client.post("/decisions?llm_mode=mock", headers=auth_headers(client), json=brief_json).status_code == 422


def test_runtime_seeds_then_loads_the_versioned_company_twin_from_storage(monkeypatch, tmp_path) -> None:
    backend = FileStorage(tmp_path)
    monkeypatch.setattr(storage, "_current", backend)
    monkeypatch.setattr(runtime, "_twin", None)
    loaded = runtime.twin()
    assert loaded.organization.id == "org_northstar"
    assert backend.load_active_twin() == loaded
    assert runtime.twin() is loaded


PERSON_TOKEN = re.compile(r"\bpt_[a-z0-9_]+")


def test_failed_publish_marks_the_run_failed() -> None:
    runtime.bus.create_run("run_publish_fails", "dec_vendor_reduction", "stub-northstar-1")
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


def leak_person_tokens(monkeypatch, token: str = "pt_07") -> None:
    original = engine_port.simulate

    def simulate(*args, **kwargs):
        result = original(*args, **kwargs)
        impacts = [i.model_copy(update={"affected_entity": token, "assumptions": [f"owned by {token}"]})
                   for i in result.impacts]
        return result.model_copy(update={"impacts": impacts, "assumptions": [*result.assumptions, f"{token} leaves"]})

    monkeypatch.setattr(engine_port, "simulate", simulate)


def all_event_text(run_id: str) -> str:
    return "\n".join(e.model_dump_json() for e in runtime.bus.runs[run_id].events)


def test_to_role_level_keeps_person_tokens_out_of_events(client, brief_json, monkeypatch) -> None:
    leak_person_tokens(monkeypatch, "pt_billing_01")
    calls: list[str] = []

    def to_role_level(obj, twin):
        calls.append(type(obj).__name__)
        text = obj.model_dump_json() if hasattr(obj, "model_dump_json") else json.dumps(obj)
        return json.loads(PERSON_TOKEN.sub("role_billing_ops_lead", text))

    monkeypatch.setattr(engine_port, "to_role_level", to_role_level)
    run_id = client.post("/decisions", headers=auth_headers(client), json=brief_json).json()["run_id"]
    wait_for(client, run_id, "awaiting_approval")
    assert "SimulationResult" in calls
    assert not PERSON_TOKEN.search(all_event_text(run_id))


def test_person_tokens_left_by_the_engine_fail_the_run_without_leaking(client, brief_json, monkeypatch) -> None:
    leak_person_tokens(monkeypatch, "pt_unknown_07")
    run_id = client.post("/decisions", headers=auth_headers(client), json=brief_json).json()["run_id"]
    wait_for(client, run_id, "failed")
    events = runtime.bus.runs[run_id].events
    failures = [e.payload.reason for e in events if e.type is EventType.run_failed]
    assert len(failures) == 1 and "person tokens" in failures[0]
    assert not PERSON_TOKEN.search(all_event_text(run_id))


def test_live_mode_needs_explicit_opt_in(client, brief_json, monkeypatch) -> None:
    monkeypatch.delenv("CANARY_ALLOW_LIVE", raising=False)
    denied = client.post("/decisions?llm_mode=live", headers=auth_headers(client), json=brief_json)
    assert denied.status_code == 503
    assert "CANARY_ALLOW_LIVE" in denied.json()["detail"]
    monkeypatch.setenv("CANARY_ALLOW_LIVE", "true")
    assert runs.live_allowed()
    monkeypatch.setenv("CANARY_ALLOW_LIVE", "yes")
    assert not runs.live_allowed()


def test_live_workforce_decision_routes_people_knowledge_and_detects_real_concentration(client) -> None:
    body = workforce_brief().model_dump(mode="json")
    run_id = client.post("/decisions", headers=auth_headers(client), json=body).json()["run_id"]
    wait_for(client, run_id, "awaiting_approval")
    events = runtime.bus.runs[run_id].events
    assert "people_knowledge" in [e.payload.agent_id for e in events if e.type is EventType.agent_started]
    assessments = {e.payload.agent_id: e.payload for e in events if e.type is EventType.agent_completed}
    assert assessments["people_knowledge"].status == "ok"

    response = client.get(f"/runs/{run_id}/package")
    assert response.status_code == 200
    package = DecisionPackage.model_validate(response.json())
    assert package.decision_id == "dec_workforce_knowledge"
    assert not PERSON_TOKEN.search(response.text) and not PERSON_TOKEN.search(all_event_text(run_id))
    naive = package.portfolios.naive.result
    assert not naive.feasible
    assert {w.workflow_id for w in naive.workflow_coverage if w.stranded} == {
        "wf_billing_recon", "wf_financial_close"
    }
    assert package.portfolios.recommended is None
