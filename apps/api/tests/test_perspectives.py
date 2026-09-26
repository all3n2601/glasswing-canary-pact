import json
import re
import time

from api_auth_helpers import auth_headers

from agent_orchestration.router import route_agents
from canary_api import runtime
from canary_api.events import EventBus
from canary_api.paths import REPLAYS_DIR
from canary_api.stubs import engine as stub_engine
from canary_api.stubs.twin import sample_brief
from contracts_py.agents import AgentAssessment, AgentOutput, CallMetrics, FutureView
from contracts_py.events import EventType
from contracts_py.twin import OrganizationSettings

PERSON_TOKEN = re.compile(r"\bpt_[a-z0-9_]+")
PERSPECTIVE_EVENTS = (EventType.agent_completed, EventType.challenge_raised)


def wait_for(client, run_id: str, status: str) -> None:
    deadline = time.monotonic() + 10
    while client.get(f"/runs/{run_id}").json()["status"] != status:
        assert time.monotonic() < deadline, f"{run_id} never reached {status}"
        time.sleep(0.02)


def perspectives(client, run_id: str) -> list[AgentAssessment]:
    response = client.get(f"/runs/{run_id}/perspectives")
    assert response.status_code == 200, response.text
    assert not PERSON_TOKEN.search(response.text)
    return [AgentAssessment.model_validate(item) for item in response.json()]


def expected_order(run_id: str) -> list[str]:
    events = sorted(runtime.bus.runs[run_id].events, key=lambda e: e.sequence)
    return list(dict.fromkeys(e.payload.assessment_id for e in events if e.type in PERSPECTIVE_EVENTS))


def test_mock_run_returns_every_routed_agent_and_the_challenger_in_order(client) -> None:
    brief = sample_brief()
    run_id = client.post("/decisions?llm_mode=mock", headers=auth_headers(client),
                         json=brief.model_dump(mode="json")).json()["run_id"]
    wait_for(client, run_id, "awaiting_approval")
    items = perspectives(client, run_id)

    routed = route_agents(brief, twin=runtime.twin(), engine=stub_engine,
                          settings=OrganizationSettings(llm_mode="mock"))
    agent_ids = [a.agent_id for a in items]
    assert len(items) == len(routed) + 1
    assert sorted(agent_ids[:-1]) == sorted(routed) and agent_ids[-1] == "challenger"
    assert [a.pass_type for a in items] == ["first_pass"] * len(routed) + ["challenge"]
    assert [a.assessment_id for a in items] == expected_order(run_id)
    assert all(a.run_id == run_id for a in items)
    challenger_events = [e for e in runtime.bus.runs[run_id].events
                         if e.type in PERSPECTIVE_EVENTS and e.payload.agent_id == "challenger"]
    assert len(challenger_events) >= 1 and agent_ids.count("challenger") == 1


def test_replay_returns_the_sample_run_assessments(client) -> None:
    run_id = client.post("/replays/sample_run/play?speed=4").json()["run_id"]
    wait_for(client, run_id, "awaiting_approval")
    items = perspectives(client, run_id)
    recorded = [e["payload"] for e in json.loads((REPLAYS_DIR / "sample_run.json").read_text())
                if e["type"] in ("agent_completed", "challenge_raised")]
    assert len(recorded) == 5
    assert [a.agent_id for a in items] == [r["agent_id"] for r in recorded]
    assert [a.assessment_id for a in items] == [r["assessment_id"] for r in recorded]
    assert all(a.run_id == run_id for a in items)


def test_unknown_or_invalid_run_is_404(client) -> None:
    assert client.get("/runs/run_does_not_exist/perspectives").status_code == 404
    assert client.get("/runs/not_a_run/perspectives").status_code == 404


def test_perspectives_survive_an_app_restart(client, monkeypatch) -> None:
    run_id = client.post("/replays/sample_run/play?speed=4").json()["run_id"]
    wait_for(client, run_id, "awaiting_approval")
    before = client.get(f"/runs/{run_id}/perspectives").json()
    runtime.bus.flush()
    # A fresh bus has no runs in memory, so the endpoint must read the run back from storage.
    monkeypatch.setattr(runtime, "bus", EventBus())
    assert run_id not in runtime.bus.runs
    assert client.get(f"/runs/{run_id}/perspectives").json() == before


def test_person_tokens_are_withheld(client) -> None:
    runtime.bus.create_run("run_leaky", "dec_vendor_reduction", "stub-northstar-1")
    leaky = AgentAssessment(
        assessment_id="asm_run_leaky_ops", run_id="run_leaky", agent_id="operations", pass_type="first_pass",
        status="ok",
        output=AgentOutput(act_now_view=FutureView(summary="Ask pt_07 about billing."),
                           inaction_view=FutureView(summary="No change."), confidence=0.5),
        metrics=CallMetrics(model_id="mock", prompt_version="p", prompt_hash="h", latency_ms=0, input_tokens=0,
                            output_tokens=0),
        created_at="2026-09-26T17:00:00Z",
    )
    runtime.bus.publish("run_leaky", EventType.agent_completed, leaky, actor="operations")
    response = client.get("/runs/run_leaky/perspectives")
    assert response.status_code == 500
    assert not PERSON_TOKEN.search(response.text)
