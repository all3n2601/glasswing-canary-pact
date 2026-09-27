import json

import pytest

from canary_api import engine_port, runtime, storage
from canary_api.paths import DATA_DIR
from canary_api.storage import FileStorage
from contracts_py.twin import Twin

FIXTURE = DATA_DIR / "synthetic_company.json"
SNIPPETS = json.loads((DATA_DIR / "artifacts" / "snippets.json").read_text())


def raw_twin() -> Twin:
    # Parsed straight from JSON: none of the loader's derived fields are filled in.
    twin = Twin.model_validate(json.loads(FIXTURE.read_text()))
    for profile in twin.department_profiles:
        profile.owned_entity_ids, profile.document_ids, profile.critical_workflow_ids = [], [], []
    return twin


@pytest.fixture
def empty_store(tmp_path, monkeypatch):
    backend = FileStorage(tmp_path)
    monkeypatch.setattr(storage, "_current", backend)
    monkeypatch.setattr(runtime, "_twin", None)
    return backend


def test_stored_twin_without_derived_fields_comes_back_with_them(empty_store, monkeypatch) -> None:
    stored = raw_twin()
    assert all(not p.owned_entity_ids for p in stored.department_profiles)
    empty_store.save_twin(stored, active=True)
    calls = []
    real_build = engine_port.build_twin
    monkeypatch.setattr(engine_port, "build_twin", lambda data, snippets=None: calls.append(snippets) or real_build(data))

    twin = runtime.twin()
    assert calls == [None], "snippets must not be overlaid again on load"
    assert all(p.owned_entity_ids for p in twin.department_profiles)
    assert twin.department_profiles == real_build(stored).department_profiles
    by_id = {e.id: e.snippet for e in twin.evidence}
    assert by_id == {e.id: e.snippet for e in stored.evidence}


def test_seeding_overlays_snippets_once(empty_store) -> None:
    twin = runtime.twin()
    stored = empty_store.load_active_twin()
    assert stored is not None
    for evidence in stored.evidence:
        assert evidence.snippet == SNIPPETS[evidence.id]
    assert {e.id: e.snippet for e in twin.evidence} == {e.id: e.snippet for e in stored.evidence}


def test_every_twin_evidence_record_has_a_short_snippet() -> None:
    evidence = json.loads(FIXTURE.read_text())["evidence"]
    missing = [e["id"] for e in evidence if e["id"] not in SNIPPETS]
    assert missing == []
    too_long = {k: len(v) for k, v in SNIPPETS.items() if len(v) > 300}
    assert too_long == {}
    assert not [k for k, v in SNIPPETS.items() if "PLACEHOLDER" in v or "\u2014" in v]
