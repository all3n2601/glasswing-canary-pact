import hashlib
import time

import pytest
from api_auth_helpers import auth_headers
from pydantic import TypeAdapter

from contracts_py.api import DecisionCreated, DecisionDraft, HealthResponse, OrganizationProfileView, ReplayInfo, ReplayStarted
from contracts_py.engine import FutureComparison, PortfolioComparison, SimulationResult
from contracts_py.enums import RunStatus
from contracts_py.events import EventType, PhaseChanged, RunState
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
        ("/organization/profile", OrganizationProfileView),
        ("/departments", list[DepartmentProfile]),
        ("/departments/dept_operations", DepartmentDetail),
        ("/documents", list[Document]),
        ("/documents?department_id=dept_operations&doc_type=runbook&status=outdated", list[Document]),
        ("/documents/doc_billing_recon_runbook", Document),
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
    assert twin.organization.id == "org_northstar"
    assert {p.id for p in twin.pressures} == {
        "pr_apex_renewal", "pr_echo_renewal", "pr_flux_usage_growth", "pr_vendor_recon_hazard",
        "pr_billing_recon_hazard", "pr_lineage_holder_attrition", "pr_contractor_cost_growth",
    }
    vendors = {e.id: e.annual_cost_usd for e in twin.entities if e.type == "vendor"}
    assert len(vendors) == 7 and sum(vendors.values()) == 8_000_000_000
    assert len([e for e in twin.edges if e.id.startswith("ch_")]) == 25
    assert {e.document_id for e in twin.evidence} <= {d.id for d in twin.documents}
    assert all(e.type != "person_token" for e in twin.entities)


def test_settings_are_contract_defaults(client) -> None:
    settings = validate(OrganizationSettings, client.get("/organization/settings"))
    defaults = OrganizationSettings(organization_id="org_northstar")
    assert settings.model_dump(exclude={"updated_at"}) == defaults.model_dump(exclude={"updated_at"})


def test_missing_ids_are_404(client) -> None:
    assert client.get("/departments/dept_nope").status_code == 404
    assert client.get("/departments/vendor_apex").status_code == 404
    assert client.get("/documents/doc_nope").status_code == 404
    assert client.get("/runs/run_nope").status_code == 404
    assert client.post("/replays/nope/play").status_code == 404
    assert client.post("/replays/sample_run/play?speed=3").status_code == 422


def test_simulate_endpoints_match_contracts(client, brief_json) -> None:
    validate(SimulationResult, client.post("/simulate/quick", json={"brief": brief_json}))
    validate(SimulationResult, client.post("/simulate/quick", json={"brief": brief_json, "intervention_ids": ["remove_beacon"]}))
    validate(FutureComparison, client.post("/simulate/futures", json={"brief": brief_json}))
    validate(PortfolioComparison, client.post("/simulate/optimize", json={"brief": brief_json}))
    assert client.post("/simulate/quick", json={"brief": brief_json, "intervention_ids": ["i_nope"]}).status_code == 422


def test_decision_run_reaches_approval_and_records_decision(client, brief_json) -> None:
    run_id = validate(DecisionCreated, client.post("/decisions", headers=auth_headers(client), json=brief_json)).run_id
    state = wait_for_status(client, run_id, RunStatus.awaiting_approval)
    assert state.package_id

    response = client.get(f"/runs/{run_id}/package")
    package = validate(DecisionPackage, response)
    assert package.futures.rows and package.blast_radius_act_now and package.blast_radius_inaction
    served_hash = hashlib.sha256(response.content).hexdigest()

    wrong = client.post(f"/runs/{run_id}/decision", headers=auth_headers(client),
                        json={"decision": "approve", "decided_by": "demo_user", "package_hash": "0" * 64})
    assert wrong.status_code == 409

    decision = validate(HumanDecision, client.post(
        f"/runs/{run_id}/decision", headers=auth_headers(client),
        json={"decision": "approve", "decided_by": "demo_user", "package_hash": served_hash},
    ))
    assert decision.package_hash == served_hash
    assert validate(RunState, client.get(f"/runs/{run_id}")).status is RunStatus.completed


def test_prompt_decision_drafts_and_runs_every_department(client) -> None:
    headers = auth_headers(client)
    draft = validate(DecisionDraft, client.post(
        "/decisions/draft",
        headers=headers,
        json={"prompt": "Should we outsource customer support next quarter while protecting retention?"},
    ))
    assert draft.brief.decision_id.startswith("dec_prompt_")
    assert len(draft.assessing_department_ids) == 9
    assert all(i.params.get("prompt_generated") is True for i in draft.brief.candidate_interventions)

    run_id = validate(DecisionCreated, client.post(
        "/decisions?llm_mode=mock", headers=headers, json=draft.brief.model_dump(mode="json")
    )).run_id
    state = wait_for_status(client, run_id, RunStatus.awaiting_approval)
    assert len(state.assessment_ids) >= 11
    package = validate(DecisionPackage, client.get(f"/runs/{run_id}/package"))
    assert len(package.department_impacts) == 9
    assert package.recommendation is None
    assert any("unquantified" in assumption.lower() for assumption in package.assumptions)


def test_decision_brief_gets_settings_defaults(client, brief_json) -> None:
    for key in ("horizon_days", "futures", "delay_days", "seed", "mc_samples"):
        brief_json.pop(key)
    run_id = validate(DecisionCreated, client.post("/decisions", headers=auth_headers(client), json=brief_json)).run_id
    wait_for_status(client, run_id, RunStatus.awaiting_approval)
    brief = runtime.bus.runs[run_id].events[0].payload
    settings = OrganizationSettings()
    assert brief.horizon_days == settings.default_horizon_days
    assert brief.futures == settings.default_futures
    assert brief.delay_days == settings.default_delay_days
    assert brief.seed == settings.default_seed
    assert brief.mc_samples == settings.mc_samples


def test_invalid_brief_is_rejected(client, brief_json) -> None:
    brief_json["protected_entity_ids"] = [brief_json["candidate_interventions"][0]["target_entity_id"]]
    assert client.post("/decisions", headers=auth_headers(client), json=brief_json).status_code == 422


def test_package_before_ready_is_409(client) -> None:
    runtime.bus.create_run("run_empty", "dec_vendor_reduction", "stub-northstar-1")
    assert client.get("/runs/run_empty/package").status_code == 409
    assert client.post("/runs/run_empty/decision", headers=auth_headers(client),
                       json={"decision": "approve", "decided_by": "x", "package_hash": "0" * 64}).status_code == 409


def test_replay_play_creates_new_run(client) -> None:
    started = validate(ReplayStarted, client.post("/replays/sample_run/play?speed=4"))
    assert started.speed == 4
    state = wait_for_status(client, started.run_id, RunStatus.awaiting_approval)
    assert state.run_id == started.run_id
    assert state.scenario_ids
    package = validate(DecisionPackage, client.get(f"/runs/{started.run_id}/package"))
    assert package.run_id == started.run_id


def test_organization_profile_lists_all_departments(client) -> None:
    profile = validate(OrganizationProfileView, client.get("/organization/profile"))
    twin = validate(Twin, client.get("/company"))
    assert [d.department_id for d in profile.departments] == [p.department_id for p in twin.department_profiles]
    assert len(profile.departments) == 9
    operations = next(d for d in profile.departments if d.department_id == "dept_operations")
    assert (operations.name, operations.actual_fte, operations.annual_budget_usd, operations.utilisation) == (
        "Operations", 5_200, 6_000_000_000, 1.12
    )
    assert all(d.enabled for d in profile.departments)
    assert profile.settings.organization_id == twin.organization.id


def test_profile_marks_departments_without_enabled_agent(client, monkeypatch) -> None:
    settings = runtime.settings().model_copy(update={"enabled_agent_ids": ["finance", "compliance", "challenger"]})
    monkeypatch.setattr(runtime, "settings", lambda: settings)
    profile = validate(OrganizationProfileView, client.get("/organization/profile"))
    enabled = {d.department_id for d in profile.departments if d.enabled}
    assert enabled == {"dept_finance", "dept_compliance"}


def awaiting_run(client, brief_json) -> tuple[str, str]:
    run_id = validate(DecisionCreated, client.post("/decisions", headers=auth_headers(client), json=brief_json)).run_id
    wait_for_status(client, run_id, RunStatus.awaiting_approval)
    response = client.get(f"/runs/{run_id}/package")
    assert response.status_code == 200
    return run_id, hashlib.sha256(response.content).hexdigest()


def decide(client, run_id: str, decision: str, package_hash: str):
    return client.post(f"/runs/{run_id}/decision", headers=auth_headers(client),
                       json={"decision": decision, "decided_by": "demo_user", "package_hash": package_hash})


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_approve_and_reject_complete_the_run(client, brief_json, decision) -> None:
    run_id, package_hash = awaiting_run(client, brief_json)
    assert validate(HumanDecision, decide(client, run_id, decision, package_hash)).decision == decision
    assert validate(RunState, client.get(f"/runs/{run_id}")).status is RunStatus.completed
    assert decide(client, run_id, "approve", package_hash).status_code == 409


def test_request_scenario_keeps_the_run_awaiting_approval(client, brief_json) -> None:
    run_id, package_hash = awaiting_run(client, brief_json)
    assert validate(HumanDecision, decide(client, run_id, "request_scenario", package_hash)).decision == "request_scenario"
    assert validate(RunState, client.get(f"/runs/{run_id}")).status is RunStatus.awaiting_approval
    recorded = [e for e in runtime.bus.runs[run_id].events if e.type == "human_decision_recorded"]
    assert [e.payload.decision for e in recorded] == ["request_scenario"]
    assert decide(client, run_id, "approve", package_hash).status_code == 200


def test_decision_is_409_unless_awaiting_approval(client, brief_json) -> None:
    run_id, package_hash = awaiting_run(client, brief_json)
    runtime.bus.publish(run_id, EventType.phase_changed,
                        PhaseChanged(from_status=RunStatus.awaiting_approval, to_status=RunStatus.failed), actor="test")
    assert decide(client, run_id, "approve", package_hash).status_code == 409


@pytest.mark.parametrize("run_id", ["..", "run_..", "run_../x", "RUN_1", "run_", "x"])
def test_bad_run_ids_are_404_before_disk(client, run_id, monkeypatch) -> None:
    def no_disk(*args, **kwargs):
        raise AssertionError("disk touched")

    monkeypatch.setattr(runtime.bus, "_load", no_disk)
    assert runtime.bus.get(run_id) is None
    for path in (f"/runs/{run_id}", f"/runs/{run_id}/package"):
        assert client.get(path).status_code == 404
    assert decide(client, run_id, "approve", "0" * 64).status_code == 404
    with pytest.raises(ValueError):
        runtime.bus.create_run(run_id, "dec_vendor_reduction", "stub-northstar-1")


def test_bad_run_id_websocket_is_refused(client) -> None:
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect("/runs/run_../events"):
            pass
    assert closed.value.code == 4404
