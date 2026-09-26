from fastapi.testclient import TestClient

from canary_api.app import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_company_fixture_has_seven_vendors() -> None:
    response = client.get("/company")
    assert response.status_code == 200
    vendors = [
        entity
        for entity in response.json()["entities"]
        if entity["kind"] == "vendor"
    ]
    assert len(vendors) == 7


def test_vendor_scenario_returns_traceable_impacts() -> None:
    response = client.post(
        "/scenarios/simulate",
        json={
            "title": "Consolidate redundant providers",
            "objective": "Save at least $2B without losing compliance coverage",
            "remove_entity_ids": ["vendor_beacon", "vendor_echo"],
            "savings_target": 2_000_000_000,
            "constraints": {"compliance_coverage": 1.0},
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["gross_savings"] == 2_200_000_000
    assert result["impacts"]
    assert all(impact["path"] for impact in result["impacts"])


def test_critical_vendor_is_rejected() -> None:
    response = client.post(
        "/scenarios/simulate",
        json={
            "title": "Remove compliance provider",
            "objective": "Reduce vendor costs",
            "remove_entity_ids": ["vendor_diligence"],
            "savings_target": 500_000_000,
            "constraints": {"compliance_coverage": 1.0},
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "infeasible"
    assert any("critical resource" in violation for violation in result["violations"])

