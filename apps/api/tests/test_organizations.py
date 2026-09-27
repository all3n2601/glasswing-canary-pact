"""Account organization isolation across company context and historical runs."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from canary_api import auth, runtime, storage
from canary_api.app import app
from canary_api.events import EventBus
from company_twin import load_company_twin
from contracts_py.api import SignupRequest, UserRole


def exercise_organizations(backend, monkeypatch):
    monkeypatch.setattr(storage, "_current", backend)
    monkeypatch.setattr(runtime, "_twin", None)
    monkeypatch.setattr(runtime, "bus", EventBus())
    first = load_company_twin()
    backend.save_twin(first)
    store = auth.UserStore(backend)
    original = store.create(SignupRequest(email="original@example.com", password="original-password", display_name="Original"), role=UserRole.approver)
    second = first.model_copy(deep=True)
    second.organization.id = "org_second"
    second.organization.display_name = "Second organization"
    second.version.twin_version = "twin_second_v1"
    if second.organization_settings:
        second.organization_settings.organization_id = "org_second"
    backend.save_twin(second)
    other = store.create(SignupRequest(email="second@example.com", password="second-password", display_name="Second"), role=UserRole.approver, organization_id="org_second")
    assert backend.load_active_twin().organization.id == first.organization.id
    assert backend.user_organization(original.user_id) == first.organization.id
    assert backend.user_organization(other.user_id) == "org_second"
    runtime.bus.create_run("run_first_org", "decision_first", first.version.twin_version)
    runtime.bus.flush()
    with TestClient(app) as client:
        def login(email, password):
            response = client.post("/auth/login", json={"email": email, "password": password})
            assert response.status_code == 200
            return {"Authorization": "Bearer " + response.json()["access_token"]}
        headers = login(original.email, "original-password")
        other_headers = login(other.email, "second-password")
        for path in ["/company", "/organization/profile", "/departments", "/documents", "/runs/run_first_org"]:
            assert client.get(path).status_code == 401
            assert client.get(path, headers={"Authorization": "Bearer invalid"}).status_code == 401
        def read(index):
            selected = headers if index % 2 == 0 else other_headers
            expected = first.organization.id if index % 2 == 0 else second.organization.id
            response = client.get("/company", headers=selected)
            assert response.status_code == 200
            assert response.json()["organization"]["id"] == expected
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(read, range(12)))
        for path in ["/organization", "/organization/profile", "/departments", f"/departments/{first.department_profiles[0].department_id}", "/documents", "/company/graph"]:
            assert client.get(path, headers=other_headers).status_code == 200
        for suffix in ["", "/perspectives", "/package", "/office-profile", "/office-graph", "/event-log", "/office-evidence/ev_any", "/office-departments/dept_engineering"]:
            assert client.get("/runs/run_first_org" + suffix, headers=other_headers).status_code == 404
        assert client.get("/runs/run_first_org", headers=headers).status_code == 200
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/runs/run_first_org/events", headers=other_headers):
                pass
        assert exc.value.code == 4404
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/runs/run_first_org/events"):
                pass
        assert exc.value.code == 4401
        # A baseline edit stays in the logged-in organization, including after reload.
        profile = client.get("/organization/profile", headers=other_headers).json()
        profile["organization"]["description"] = "Updated second organization"
        response = client.post("/organization/profile", headers=other_headers, json={
            "expected_twin_version": second.version.twin_version,
            "organization": profile["organization"], "departments": [],
            "settings": profile["settings"],
        })
        assert response.status_code == 200, response.text
        assert backend.load_active_twin("org_second").organization.description == "Updated second organization"
        assert backend.load_active_twin().organization.description == first.organization.description
        assert client.post("/auth/logout", headers=other_headers).status_code == 204
        assert client.get("/company", headers=other_headers).status_code == 401


def test_file_organizations(tmp_path, monkeypatch):
    exercise_organizations(storage.FileStorage(tmp_path), monkeypatch)
    restarted = storage.FileStorage(tmp_path)
    assert set(restarted.organization_ids()) == {"org_northstar", "org_second"}
    assert restarted.user_organization(restarted.user_by_email("second@example.com").user.user_id) == "org_second"
    assert restarted.load_active_twin("org_second").organization.description == "Updated second organization"
