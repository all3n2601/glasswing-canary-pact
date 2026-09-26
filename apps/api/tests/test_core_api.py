import hashlib
import time

import pytest
from pydantic import TypeAdapter

from contracts_py.api import DecisionCreated, HealthResponse, ReplayInfo, ReplayStarted
from contracts_py.engine import FutureComparison, PortfolioComparison, SimulationResult
from contracts_py.enums import RunStatus
from contracts_py.events import RunState
from contracts_py.package import DecisionPackage, HumanDecision
from contracts_py.twin import (
    DepartmentDetail,
    DepartmentProfile,
    Document,
    DomainGraph,
    Organization,
    OrganizationSettings,
    Pressure,
    Twin,
)

from canary_api import runtime


def validate(model, response):
    assert response.status_code == 200, response.text
    return TypeAdapter(model).validate_python(response.json())


def wait_for_status(client, run_id: str, status: RunStatus, timeout: float = 5.0) -> RunState:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = validate(RunState, client.get(f"/runs/{run_id}"))
        if state.status is status:
            return state
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} never reached {status}")


@pytest.mark.parametrize(
    ("path", "model"),
    [
        ("/health", HealthResponse),
        ("/company", Twin),
        ("/company/graph", DomainGraph),
        ("/company/graph?level=domain", DomainGraph),
        ("/company/pressures", list[Pressure]),
        ("/organization", Organization),
        ("/organization/settings", OrganizationSettings),
        ("/departments", list[DepartmentProfile]),
        ("/departments/dept_operations", DepartmentDetail),
        ("/documents", list[Document]),
        ("/documents?department_id=dept_operations&doc_type=runbook&status=outdated", list[Document]),
        ("/documents/doc_runbook_billing_recon", Document),
        ("/replays", list[ReplayInfo]),
    ],
)
def test_get_endpoints_match_contracts(client, path, model) -> None:
    validate(model, client.get(path))


def test_stub_twin_shape(client) -> None:
    twin = validate(Twin, client.get("/company"))
    departments = [e for e in twin.entities if e.type == "department"]
    assert len(departments) == 9
    assert len(twin.department_profiles) == 9
    assert {p.id for p in twin.pressures} == {"pr_cloud_growth", "pr_auditlog_renewal", "pr_billing_recon_hazard"}
    assert len(twin.documents) == 2


def test_settings_are_contract_defaults(client) -> None:
    settings = validate(OrganizationSettings, client.get("/organization/settings"))
    defaults = OrganizationSettings(organization_id="org_novacorp")
    assert settings.model_dump(exclude={"updated_at"}) == defaults.model_dump(exclude={"updated_at"})


def test_missing_ids_are_404(client) -> None:
    assert client.get("/departments/dept_nope").status_code == 404
    assert client.get("/departments/vendor_auditlog").status_code == 404
    assert client.get("/documents/doc_nope").status_code == 404
    assert client.get("/runs/run_nope").status_code == 404
    assert client.post("/replays/nope/play").status_code == 404
    assert client.post("/replays/sample_run/play?speed=3").status_code == 422


def test_simulate_endpoints_match_contracts(client, brief_json) -> None:
    validate(SimulationResult, client.post("/simulate/quick", json={"brief": brief_json}))
    validate(SimulationResult, client.post("/simulate/quick", json={"brief": brief_json, "intervention_ids": ["i_eng"]}))
    validate(FutureComparison, client.post("/simulate/futures", json={"brief": brief_json}))
    validate(PortfolioComparison, client.post("/simulate/optimize", json={"brief": brief_json}))
    assert client.post("/simulate/quick", json={"brief": brief_json, "intervention_ids": ["i_nope"]}).status_code == 422


def test_decision_run_reaches_approval_and_records_decision(client, brief_json) -> None:
    run_id = validate(DecisionCreated, client.post("/decisions", json=brief_json)).run_id
    state = wait_for_status(client, run_id, RunStatus.awaiting_approval)
    assert state.package_id

    response = client.get(f"/runs/{run_id}/package")
    package = validate(DecisionPackage, response)
    assert package.futures.rows and package.blast_radius_act_now and package.blast_radius_inaction
    served_hash = hashlib.sha256(response.content).hexdigest()

    wrong = client.post(f"/runs/{run_id}/decision",
                        json={"decision": "approve", "decided_by": "demo_user", "package_hash": "0" * 64})
    assert wrong.status_code == 409

    decision = validate(HumanDecision, client.post(
        f"/runs/{run_id}/decision",
        json={"decision": "approve", "decided_by": "demo_user", "package_hash": served_hash},
    ))
    assert decision.package_hash == served_hash
    assert validate(RunState, client.get(f"/runs/{run_id}")).status is RunStatus.completed


def test_decision_brief_gets_settings_defaults(client, brief_json) -> None:
    for key in ("horizon_days", "futures", "delay_days", "seed", "mc_samples"):
        brief_json.pop(key)
    run_id = validate(DecisionCreated, client.post("/decisions", json=brief_json)).run_id
    wait_for_status(client, run_id, RunStatus.awaiting_approval)
    brief = runtime.bus.runs[run_id].events[0].payload
    settings = OrganizationSettings()
    assert brief.horizon_days == settings.default_horizon_days
    assert brief.futures == settings.default_futures
    assert brief.delay_days == settings.default_delay_days
    assert brief.seed == settings.default_seed
    assert brief.mc_samples == settings.mc_samples


def test_invalid_brief_is_rejected(client, brief_json) -> None:
    brief_json["candidate_interventions"][0]["target_entity_id"] = "ctl_soc2_audit_logging"
    assert client.post("/decisions", json=brief_json).status_code == 422


def test_package_before_ready_is_409(client) -> None:
    runtime.bus.create_run("run_empty", "dec_cut_2m", "stub-twin-1")
    assert client.get("/runs/run_empty/package").status_code == 409
    assert client.post("/runs/run_empty/decision",
                       json={"decision": "approve", "decided_by": "x", "package_hash": "0" * 64}).status_code == 409


def test_replay_play_creates_new_run(client) -> None:
    started = validate(ReplayStarted, client.post("/replays/sample_run/play?speed=4"))
    assert started.speed == 4
    state = wait_for_status(client, started.run_id, RunStatus.awaiting_approval)
    assert state.run_id == started.run_id
    assert all(s.startswith(f"scn_{started.run_id}_") for s in state.scenario_ids)
    package = validate(DecisionPackage, client.get(f"/runs/{started.run_id}/package"))
    assert package.run_id == started.run_id
