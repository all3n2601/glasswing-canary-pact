import time

from api_auth_helpers import auth_headers
from real_data import sample_brief, workforce_brief

from canary_api import runs, runtime
from contracts_py.events import EventType
from contracts_py.twin import OrganizationSettings


def wait_for(client, run_id: str, status: str) -> None:
    deadline = time.monotonic() + 30
    while client.get(f"/runs/{run_id}").json()["status"] != status:
        state = runtime.bus.runs[run_id].state.status
        assert state != "failed", runtime.bus.runs[run_id].events[-1].payload
        assert time.monotonic() < deadline, f"{run_id} never reached {status}"
        time.sleep(0.05)


def run(client, brief, mode: str | None) -> tuple[str, list, dict]:
    query = f"?llm_mode={mode}" if mode else ""
    response = client.post(f"/decisions{query}", headers=auth_headers(client), json=brief.model_dump(mode="json"))
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    wait_for(client, run_id, "awaiting_approval")
    assessments = {}
    for event in runtime.bus.runs[run_id].events:
        if event.type in (EventType.agent_completed, EventType.challenge_raised):
            assessments.setdefault(event.payload.assessment_id, event.payload)
    return run_id, list(assessments.values()), client.get(f"/runs/{run_id}/package").json()


def test_replay_falls_back_per_decision(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CANARY_LLM_CACHE_DIR", str(tmp_path / "cache"))
    vendor, workforce = sample_brief(), workforce_brief()
    # A live run records answers for the vendor decision only.
    _, live, _ = run(client, vendor, "live")
    assert live and all(a.status == "ok" for a in live)
    assert any((tmp_path / "cache").rglob("*.json"))

    _, other, package = run(client, workforce, "replay")
    assert other and all(a.status == "ok" and a.metrics.model_id == "mock" for a in other)
    assert package["assumptions"].count(runs.MOCK_FALLBACK_ASSUMPTION) == 1

    _, same, package = run(client, vendor, "replay")
    assert same and {a.status for a in same} <= {"replayed", "fallback_cached"} and "replayed" in {a.status for a in same}
    assert all(a.metrics.model_id != "mock" for a in same)
    assert runs.MOCK_FALLBACK_ASSUMPTION not in package["assumptions"]


def test_default_mode_follows_allow_live(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CANARY_LLM_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("CANARY_ALLOW_LIVE", "true")
    assert runs.default_llm_mode() == "live"
    assert runs.resolve_llm_settings(OrganizationSettings(), None, "dec_any")[0].llm_mode == "live"
    _, live, _ = run(client, sample_brief(), None)
    assert live and all(a.status == "ok" and a.metrics.model_id == "test-live" for a in live)

    monkeypatch.setenv("CANARY_ALLOW_LIVE", "false")
    assert runs.default_llm_mode() == "replay"
    _, replay, package = run(client, workforce_brief(), None)
    assert all(a.metrics.model_id == "mock" for a in replay)
    assert runs.MOCK_FALLBACK_ASSUMPTION in package["assumptions"]
    forced = client.post("/decisions?llm_mode=live", headers=auth_headers(client),
                         json=sample_brief().model_dump(mode="json"))
    assert forced.status_code == 403
