def test_vendor_scenario_returns_traceable_impacts(client) -> None:
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

    scenario_id = result["scenario_id"]
    assert client.get(f"/scenarios/{scenario_id}/results").json() == result
    assert client.get(f"/scenarios/{scenario_id}/report").json()["scenario_id"] == scenario_id


def test_critical_vendor_is_rejected(client) -> None:
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


def test_unknown_scenario_is_404(client) -> None:
    assert client.get("/scenarios/missing/results").status_code == 404
