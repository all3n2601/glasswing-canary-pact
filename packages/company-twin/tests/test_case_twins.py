import json
from pathlib import Path

from company_twin import build_twin, load_mitigation_catalog
from company_twin.loader import default_mitigation_catalog_path
from contracts_py.decision import DecisionBrief

CASE = Path(__file__).resolve().parents[3] / "data" / "cases" / "tsb-2018"


def test_tsb_case_twin_builds_and_its_files_agree():
    twin = build_twin(json.loads((CASE / "twin.json").read_text()))
    ids = {e.id for e in twin.entities}
    brief = DecisionBrief.model_validate(json.loads((CASE / "brief_naive.json").read_text()))
    assert {i.target_entity_id for i in brief.candidate_interventions} <= ids
    assert load_mitigation_catalog(CASE / "mitigations.json", twin)
    planted = json.loads((CASE / "planted_items.json").read_text())
    edge = planted["planted_edge"]
    assert edge["id"] not in {e.id for e in twin.edges}
    assert {edge["source"], edge["target"]} <= ids
    assert set(edge["evidence_refs"]) <= {ev.id for ev in twin.evidence}


def test_mitigation_catalog_path_can_point_at_a_case(monkeypatch):
    monkeypatch.setenv("CANARY_MITIGATION_CATALOG_PATH", str(CASE / "mitigations.json"))
    assert default_mitigation_catalog_path() == CASE / "mitigations.json"
    monkeypatch.delenv("CANARY_MITIGATION_CATALOG_PATH")
    assert default_mitigation_catalog_path().name == "mitigations.json"
    assert default_mitigation_catalog_path().parent.name == "data"
