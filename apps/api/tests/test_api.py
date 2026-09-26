from fastapi.testclient import TestClient

from canary_api.app import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_company_fixture_exposes_current_vendors() -> None:
    response = client.get("/scenarios/company")
    assert response.status_code == 200
    vendors = [
        entity
        for entity in response.json()["entities"]
        if entity["type"] == "vendor"
    ]
    assert len(vendors) == 6


def test_vendor_scenario_returns_traceable_impacts() -> None:
    response = client.post(
        "/scenarios/simulate",
        json={
            "title": "Consolidate redundant providers",
            "objective": "Save at least $2B without losing compliance coverage",
            "remove_entity_ids": ["vendor_cloud", "vendor_enrichiq"],
            "savings_target": 500_000,
            "constraints": {"compliance_coverage": 1.0},
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["gross_savings"] == 660_000
    assert result["impacts"]
    assert all(impact["path"] for impact in result["impacts"])

    assessments_response = client.get(
        f"/scenarios/{result['scenario_id']}/assessments"
    )
    assert assessments_response.status_code == 200
    assessments = assessments_response.json()
    assert set(assessments) == {
        "dept_ai_data",
        "dept_compliance",
        "dept_engineering",
        "dept_finance",
        "dept_operations",
    }
    assert all("act_now_view" in assessment for assessment in assessments.values())


def test_critical_vendor_is_rejected() -> None:
    response = client.post(
        "/scenarios/simulate",
        json={
            "title": "Remove compliance provider",
            "objective": "Reduce vendor costs",
            "remove_entity_ids": ["vendor_auditlog"],
            "savings_target": 200_000,
            "constraints": {"compliance_coverage": 1.0},
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "infeasible"
    assert any("critical resource" in violation for violation in result["violations"])
