from canary_api import runtime, storage
from contracts_py.api import DepartmentSave, RunEventPage
from contracts_py.events import EventType, AgentStarted
from api_auth_helpers import auth_headers


def test_department_save_and_historical_profile(client):
    baseline=runtime.twin()
    run_id="run_office_history"
    runtime.bus.create_run(run_id,"dec_office",baseline.version.twin_version)
    headers=auth_headers(client)
    payload=dict(expected_twin_version=baseline.version.twin_version,department=dict(department_id="dept_office_test",name="Research",mission="Explore ideas",actual_fte=3,annual_budget_usd=300000,assumption="Declared staffing and budget; capability still needs evidence."))
    DepartmentSave.model_validate(payload)
    try:
        assert client.post("/departments/save",json=payload).status_code==401
        response=client.post("/departments/save",json=payload,headers=headers)
        assert response.status_code==200,response.text
        assert any(d["department_id"]=="dept_office_test" for d in response.json()["departments"])
        assert storage.current().load_active_twin().version.twin_version==response.json()["twin_version"]
        assert client.post("/departments/save",json=payload,headers=headers).status_code==409
        history=client.get(f"/runs/{run_id}/office-profile",headers=headers)
        assert history.status_code==200
        assert history.json()["twin_version"]==baseline.version.twin_version
        assert not any(d["department_id"]=="dept_office_test" for d in history.json()["departments"])
    finally:
        runtime.activate_twin(baseline)


def test_event_history_auth_cursor_and_pagination(client):
    run_id="run_office_events"
    runtime.bus.create_run(run_id,"dec_office",runtime.twin().version.twin_version)
    for agent in ["finance","operations","engineering"]:
        runtime.bus.publish(run_id,EventType.agent_started,AgentStarted(agent_id=agent),actor=agent)
    assert client.get(f"/runs/{run_id}/event-log").status_code==401
    headers=auth_headers(client)
    first=client.get(f"/runs/{run_id}/event-log?limit=2",headers=headers)
    page=RunEventPage.model_validate(first.json())
    assert page.next_sequence==2 and page.has_more and len(page.events)==2
    last=client.get(f"/runs/{run_id}/event-log?after_sequence=2",headers=headers).json()
    assert [e["sequence"] for e in last["events"]]==[3]
    assert not last["has_more"]
    assert client.get(f"/runs/{run_id}/event-log?limit=999",headers=headers).status_code==422


def test_full_agent_review_of_created_department(client):
    from test_orchestrated_run import wait_for
    brief=dict(decision_id="dec_office_create",decision_type="restructure",title="Create research",statement="Test a new research department",goal=dict(metric="net_value_usd",target=-500000),created_by="test_user",candidate_interventions=[dict(id="change_research",kind="action",type="assess_change",target_entity_id="dept_new_research",rationale="Proposed addition")],organization_changes=[dict(intervention_id="change_research",operation="create",department_id="dept_new_research",new_department=dict(department_id="dept_new_research",name="Research",mission="Explore capabilities",actual_fte=4,annual_budget_usd=400000,assumption="Research capability remains unverified until workflows and evidence are supplied."))])
    response=client.post("/decisions",json=brief,headers=auth_headers(client))
    assert response.status_code==200,response.text
    run_id=response.json()["run_id"]
    wait_for(client,run_id,"awaiting_approval")
    page=client.get(f"/runs/{run_id}/event-log?limit=250",headers=auth_headers(client))
    assert page.status_code==200,page.text
    assert any(e["type"]=="agent_completed" for e in page.json()["events"])
    assert page.json()["terminal"]


def test_settings_save_survives_runtime_reload(client):
    baseline=runtime.twin()
    try:
        profile=client.get("/organization/profile").json()
        profile["settings"]["default_horizon_days"]=180
        payload=dict(expected_twin_version=profile["twin_version"],organization=profile["organization"],departments=[],settings=profile["settings"])
        response=client.post("/organization/profile",json=payload,headers=auth_headers(client))
        assert response.status_code==200,response.text
        runtime._twin=None
        assert runtime.settings().default_horizon_days==180
        assert client.post("/organization/profile",json=payload,headers=auth_headers(client)).status_code==409
    finally:
        runtime.activate_twin(baseline)


def test_office_preview_matches_engine_and_frozen_graph(client):
    from real_data import sample_brief
    baseline = runtime.twin()
    payload = dict(brief=sample_brief().model_dump(mode="json"), expected_twin_version=baseline.version.twin_version)
    headers = auth_headers(client)
    assert client.post("/simulate/office-preview", json=payload).status_code == 401
    preview = client.post("/simulate/office-preview", json=payload, headers=headers)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["result"]["scenario_id"] == body["blast_radius"]["scenario_id"]
    assert body["baseline_twin_version"] == baseline.version.twin_version
    assert body["result"]["department_states"]
    payload["expected_twin_version"] = "stale_version"
    assert client.post("/simulate/office-preview", json=payload, headers=headers).status_code == 409


def test_run_evidence_uses_saved_snapshot(client):
    baseline = runtime.twin()
    run_id = "run_office_evidence"
    runtime.bus.create_run(run_id,"dec_office",baseline.version.twin_version)
    evidence = baseline.evidence[0]
    headers = auth_headers(client)
    url = f"/runs/{run_id}/office-evidence/{evidence.id}"
    assert client.get(url).status_code == 401
    response = client.get(url,headers=headers)
    assert response.status_code == 200
    assert response.json()["snippet"] == evidence.snippet
    assert client.get(f"/runs/{run_id}/office-evidence/ev_unknown",headers=headers).status_code == 404
