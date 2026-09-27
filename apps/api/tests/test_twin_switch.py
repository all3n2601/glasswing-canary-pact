import json

from canary_api import engine_port, paths, runtime
from contracts_py.decision import DecisionBrief


def test_versioned_briefs_match_the_canonical_data_files() -> None:
    for filename in ("vendor_scenario.json", "workforce_scenario.json"):
        brief = DecisionBrief.model_validate_json((paths.DATA_DIR / filename).read_text())
        assert brief.decision_id in {"dec_vendor_reduction", "dec_workforce_knowledge"}


def test_vendor_brief_ids_exist_in_the_real_twin() -> None:
    raw = json.loads((paths.DATA_DIR / "vendor_scenario.json").read_text())
    brief = DecisionBrief.model_validate(raw)
    twin = runtime.twin()
    entity_ids = {entity.id for entity in twin.entities}
    pressure_ids = {pressure.id for pressure in twin.pressures}
    assert {item.target_entity_id for item in brief.candidate_interventions} <= entity_ids
    assert set(brief.active_pressure_ids or []) <= pressure_ids


def test_runtime_uses_only_the_real_engine_and_twin(client) -> None:
    assert engine_port.engine_impl() == "real"
    assert engine_port.twin_impl() == "real"
    body = client.get("/health").json()
    assert (body["engine_impl"], body["twin_impl"]) == ("real", "real")
    assert client.get("/company").json()["organization"]["id"] == "org_northstar"
