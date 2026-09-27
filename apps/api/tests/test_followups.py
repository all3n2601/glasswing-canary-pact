import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path

import pytest
from api_auth_helpers import auth_headers
from real_data import sample_brief
from fastapi.testclient import TestClient

from canary_api import auth, runs, runtime, storage
from canary_api.storage import FileStorage
from contracts_py.api import HealthResponse, HumanDecisionRequest
from contracts_py.enums import Future, RunStatus
from contracts_py.events import AgentStarted, EventType, RunFailed

STORY_VALUES = json.loads((Path(runs.__file__).parent / "stubs" / "story_values.json").read_text())


def test_decided_by_is_optional() -> None:
    request = HumanDecisionRequest(decision="approve", package_hash="0" * 64)
    assert request.decided_by is None


def test_health_reports_file_backend_and_no_failures(client, monkeypatch) -> None:
    monkeypatch.setattr(storage.writer, "failures", 0)
    health = HealthResponse.model_validate(client.get("/health").json())
    assert (health.status, health.storage, health.storage_write_failures) == ("ok", "file", 0)


def test_health_is_degraded_after_a_failed_write(client, monkeypatch) -> None:
    monkeypatch.setattr(storage.writer, "failures", 0)

    def broken() -> None:
        raise OSError("disk full")

    storage.writer.submit(broken)
    storage.writer.flush()
    health = HealthResponse.model_validate(client.get("/health").json())
    assert (health.status, health.storage_write_failures) == ("degraded", 1)


def test_health_names_postgres_when_it_is_the_backend(client, monkeypatch) -> None:
    class FakePostgres(storage.PostgresStorage):
        def __init__(self) -> None:
            pass

    monkeypatch.setattr(storage, "_current", FakePostgres())
    assert client.get("/health").json()["storage"] == "postgres"


def test_warning_when_no_approver_exists(tmp_path, monkeypatch, caplog) -> None:
    monkeypatch.setattr(storage, "_current", FileStorage(tmp_path))
    monkeypatch.delenv("CANARY_DEMO_APPROVER_EMAIL", raising=False)
    monkeypatch.delenv("CANARY_DEMO_APPROVER_PASSWORD", raising=False)
    with caplog.at_level(logging.WARNING, logger="canary_api.auth"):
        assert auth.warn_if_no_approver() is True
    assert "CANARY_DEMO_APPROVER_EMAIL" in caplog.text and "CANARY_DEMO_APPROVER_PASSWORD" in caplog.text


def test_startup_emits_the_no_approver_warning(tmp_path, monkeypatch, caplog) -> None:
    from canary_api.app import app

    monkeypatch.setattr(storage, "_current", FileStorage(tmp_path))
    monkeypatch.delenv("CANARY_DEMO_APPROVER_EMAIL", raising=False)
    with caplog.at_level(logging.WARNING, logger="canary_api.auth"), TestClient(app):
        pass
    assert "No approver account exists" in caplog.text


def test_no_warning_once_an_approver_exists(tmp_path, monkeypatch, caplog) -> None:
    monkeypatch.setattr(storage, "_current", FileStorage(tmp_path))
    monkeypatch.setenv("CANARY_DEMO_APPROVER_EMAIL", "approver@example.com")
    monkeypatch.setenv("CANARY_DEMO_APPROVER_PASSWORD", "demo password 1")
    auth.seed_demo_approver()
    with caplog.at_level(logging.WARNING, logger="canary_api.auth"):
        assert auth.warn_if_no_approver() is False
    assert "No approver account exists" not in caplog.text


@pytest.mark.parametrize("decision_id", sorted(STORY_VALUES))
def test_stored_future_rows_match_the_stored_results(decision_id) -> None:
    results = STORY_VALUES[decision_id]["results"]
    net = {key: r["value"]["net_value_usd"] for key, r in results.items()}
    monthly = {key: r["value"]["monthly_net_usd"] for key, r in results.items()}
    rows = {row["future"]: row for row in STORY_VALUES[decision_id]["rows"]}
    for future in ("act_now", "inaction", "delay"):
        row = rows[future]
        delta = net[future] - net["inaction"]
        assert row["net_value_p50_usd"] == net[future]
        assert row["delta_vs_inaction_p10_usd"] == row["delta_vs_inaction_p50_usd"] == row["delta_vs_inaction_p90_usd"] == delta
        assert row["monthly_delta_usd"] == [a - b for a, b in zip(monthly[future], monthly["inaction"])]
        assert row["p_better_than_inaction"] == (1.0 if delta > 0 else 0.0)
        assert row["risk_score"] == results[future]["risk"]["score"]
        assert row["cost_of_delay_usd"] == (
            (net["act_now"] - net["inaction"]) - (net["delay"] - net["inaction"]) if future == "delay" else None
        )


def test_stub_results_serve_the_stored_rows() -> None:
    from canary_api.stubs import results

    for decision_id in STORY_VALUES:
        served = results.future_comparison("run_x", decision_id)
        stored = STORY_VALUES[decision_id]["rows"]
        for row, expected in zip(served.rows, stored):
            dumped = row.model_dump(mode="json")
            assert {k: dumped[k] for k in expected} == expected
            assert row.result_id == results.result_id("run_x", Future(row.future), row.plan_id)


def test_emits_after_run_failure_are_dropped() -> None:
    async def scenario() -> list[EventType]:
        runtime.bus.create_run("run_cancel", "dec_vendor_reduction", "stub-northstar-1")
        emit = runs.ThreadEmitter("run_cancel", asyncio.get_running_loop(), runtime.twin())
        assert emit.cancelled() is False
        emit(EventType.agent_started, AgentStarted(agent_id="finance"), actor="finance")
        await asyncio.sleep(0.01)
        runs.fail_run("run_cancel", "engine exploded")
        assert emit.cancelled() is True
        await asyncio.to_thread(emit, EventType.agent_started, AgentStarted(agent_id="sales"), actor="sales")
        emit(EventType.run_failed, RunFailed(reason="second failure"), actor="orchestrator")
        await asyncio.sleep(0.05)
        return [e.type for e in runtime.bus.runs["run_cancel"].events]

    types = asyncio.run(scenario())
    assert types == [EventType.agent_started, EventType.phase_changed, EventType.run_failed]
    assert runtime.bus.runs["run_cancel"].state.status is RunStatus.failed


def run_with_fake_orchestrator(monkeypatch, fake) -> str:
    monkeypatch.setattr(runs, "run_decision", fake)
    run_id = "run_fake_" + hashlib.sha256(fake.__name__.encode()).hexdigest()[:8]
    twin = runtime.twin()
    runtime.bus.create_run(run_id, "dec_vendor_reduction", twin.version.twin_version)
    asyncio.run(runs.orchestrate(run_id, sample_brief(), twin, runtime.settings(), "mock"))
    return run_id


def test_should_stop_is_passed_when_run_decision_accepts_it(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def accepts(brief, *, engine, settings, llm, emit, run_id, twin, should_stop):
        seen["before"] = should_stop()
        runs.fail_run(run_id, "stopped for the test")
        seen["after"] = should_stop()

    run_with_fake_orchestrator(monkeypatch, accepts)
    assert seen == {"before": False, "after": True}


def test_should_stop_is_not_passed_to_an_older_run_decision(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def older(brief, *, engine, settings, llm, emit, run_id, twin):
        seen["called"] = True

    run_id = run_with_fake_orchestrator(monkeypatch, older)
    assert seen == {"called": True}
    assert runtime.bus.runs[run_id].state.status is not RunStatus.failed


def test_decision_without_decided_by_is_accepted(client) -> None:
    headers = auth_headers(client)
    run_id = client.post("/decisions", headers=headers,
                         json=sample_brief().model_dump(mode="json")).json()["run_id"]
    deadline = time.monotonic() + 10
    while client.get(f"/runs/{run_id}").json()["status"] != "awaiting_approval":
        assert time.monotonic() < deadline
        time.sleep(0.02)
    package = client.get(f"/runs/{run_id}/package")
    response = client.post(f"/runs/{run_id}/decision", headers=headers,
                           json={"decision": "approve", "package_hash": hashlib.sha256(package.content).hexdigest()})
    assert response.status_code == 200 and response.json()["decided_by"]
