"""load_twin (plan B-01) and the B-03 evidence/confidence acceptance check.

Covers: load_twin with and without a snippets file, documented_pct derivation and its
disagreement warning, invalid references failing with readable validate_twin errors, and
every critical edge on the real fixture carrying evidence and a confidence score, and the
mitigation catalog loader (plan E-07) checking kinds, unique ids and twin references.
"""

from __future__ import annotations

import json

import pytest

from company_twin.loader import (
    default_fixture_path,
    default_mitigation_catalog_path,
    load_mitigation_catalog,
    load_twin,
)
from company_twin.validate import validate_twin


def test_load_twin_without_snippets_matches_the_fixture():
    twin = load_twin(default_fixture_path())
    assert twin.organization.id == "org_northstar"
    assert twin.entities and twin.edges


def test_load_twin_overlays_snippets_by_evidence_id(tmp_path):
    twin_without = load_twin(default_fixture_path())
    some_evidence_id = twin_without.evidence[0].id
    original_snippet = twin_without.evidence[0].snippet

    snippets_path = tmp_path / "snippets.json"
    snippets_path.write_text(json.dumps({some_evidence_id: "OVERLAID SNIPPET TEXT"}))

    twin_with = load_twin(default_fixture_path(), snippets_path)
    overlaid = next(v for v in twin_with.evidence if v.id == some_evidence_id)
    assert overlaid.snippet == "OVERLAID SNIPPET TEXT"
    assert overlaid.snippet != original_snippet

    # every other evidence record is untouched
    untouched_before = {v.id: v.snippet for v in twin_without.evidence if v.id != some_evidence_id}
    untouched_after = {v.id: v.snippet for v in twin_with.evidence if v.id != some_evidence_id}
    assert untouched_before == untouched_after


def test_load_twin_overlay_ignores_unknown_evidence_ids(tmp_path):
    snippets_path = tmp_path / "snippets.json"
    snippets_path.write_text(json.dumps({"ev_does_not_exist": "text"}))

    # must not raise
    twin = load_twin(default_fixture_path(), snippets_path)
    assert not any(v.id == "ev_does_not_exist" for v in twin.evidence)


def test_load_twin_overlay_warns_but_does_not_truncate_oversized_snippets(tmp_path, caplog):
    import logging

    twin_without = load_twin(default_fixture_path())
    some_evidence_id = twin_without.evidence[0].id
    oversized = "x" * 301

    snippets_path = tmp_path / "snippets.json"
    snippets_path.write_text(json.dumps({some_evidence_id: oversized}))

    with caplog.at_level(logging.WARNING, logger="company_twin.loader"):
        twin_with = load_twin(default_fixture_path(), snippets_path)

    overlaid = next(v for v in twin_with.evidence if v.id == some_evidence_id)
    assert overlaid.snippet == oversized  # applied in full, not truncated
    assert any(some_evidence_id in r.message for r in caplog.records)


def test_load_twin_derives_documented_pct_and_warns_on_disagreement(caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="company_twin.loader"):
        twin = load_twin(default_fixture_path())

    # wf_billing_recon's only covering document is an *outdated* runbook, so the
    # derived value (0.0) disagrees with the fixture's hand-set 0.35 (the
    # deliberately under-documented billing-exception story, brief section 4.4).
    billing_recon = next(e for e in twin.entities if e.id == "wf_billing_recon")
    assert billing_recon.documented_pct == 0.35  # fixture value kept, not overwritten
    assert any("wf_billing_recon" in r.message for r in caplog.records)


def test_invalid_references_fail_with_readable_errors():
    twin = load_twin(default_fixture_path())
    twin.edges[0].target = "entity_that_does_not_exist"

    issues = validate_twin(twin)
    errors = [i for i in issues if i.severity == "error"]
    assert errors
    bad_ref_errors = [i for i in errors if "entity_that_does_not_exist" in i.message]
    assert bad_ref_errors
    # readable: names the edge and the missing id, not just "invalid"
    assert all(i.ids for i in bad_ref_errors)


def test_every_critical_edge_has_evidence_and_confidence():
    twin = load_twin(default_fixture_path())
    for e in twin.edges:
        if e.criticality.value in ("high", "critical"):
            assert e.evidence_refs, e.id
            assert 0.0 <= e.confidence <= 1.0, e.id


def test_fixture_passes_validate_twin_with_zero_errors():
    twin = load_twin(default_fixture_path())
    issues = validate_twin(twin)
    errors = [i for i in issues if i.severity == "error"]
    assert not errors, errors


# ---- build_twin: in-memory input (plan B-01, B-04), e.g. a twin loaded from the database ----

def _fixture_data() -> dict:
    return json.loads(default_fixture_path().read_text())


def test_build_twin_from_a_mapping_matches_load_twin_and_validates():
    from company_twin import build_twin

    built = build_twin(_fixture_data())
    assert built.model_dump_json() == load_twin(default_fixture_path()).model_dump_json()
    assert [i for i in validate_twin(built) if i.severity == "error"] == []


def test_build_twin_does_not_mutate_its_input_and_is_idempotent():
    from company_twin import build_twin

    source = load_twin(default_fixture_path())
    before = source.model_dump_json()
    once = build_twin(source)
    assert source.model_dump_json() == before
    # A twin built before it was persisted builds to the same twin after it is loaded again.
    assert build_twin(json.loads(once.model_dump_json())).model_dump_json() == once.model_dump_json()


def test_build_twin_derives_every_profile_field_from_the_twin_itself():
    from company_twin import build_twin

    data = _fixture_data()
    for profile in data["department_profiles"]:
        for field in ("owned_entity_ids", "critical_workflow_ids", "kpi_ids", "document_ids"):
            profile[field] = []
        profile["documentation_coverage"] = 0.0
    built = build_twin(data)
    reference = load_twin(default_fixture_path())
    assert [p.model_dump() for p in built.department_profiles] == [p.model_dump() for p in reference.department_profiles]
    assert all(p.owned_entity_ids for p in built.department_profiles)


def test_build_twin_overlays_snippets_before_persistence():
    from company_twin import build_twin

    evidence_id = _fixture_data()["evidence"][0]["id"]
    built = build_twin(_fixture_data(), {evidence_id: "FINAL WORDING", "ev_not_in_twin": "ignored"})
    assert next(e for e in built.evidence if e.id == evidence_id).snippet == "FINAL WORDING"
    assert build_twin(_fixture_data(), None).model_dump_json() == build_twin(_fixture_data()).model_dump_json()


def test_build_twin_raises_readable_errors_for_an_invalid_twin():
    import pytest
    from company_twin import TwinValidationError, build_twin

    data = _fixture_data()
    data["edges"][0]["target"] = "ent_missing"
    with pytest.raises(TwinValidationError) as raised:
        build_twin(data)
    assert raised.value.issues and all(i.severity == "error" for i in raised.value.issues)
    assert "ent_missing" in str(raised.value)


def test_story_gaps_lower_documentation_coverage_of_the_owning_departments():
    from company_twin import documented_workflow_ids, entity_map

    twin = load_twin(default_fixture_path())
    ents = entity_map(twin)
    coverage = {p.department_id: p.documentation_coverage for p in twin.department_profiles}
    documented = documented_workflow_ids(twin)
    # wf_billing_recon's only runbook is outdated; wf_financial_close's SOP defers to kn_warehouse_lineage,
    # which is 20% documented and covered by no runbook or SOP.
    assert "wf_billing_recon" not in documented and "wf_financial_close" not in documented
    assert all(d.status.value != "current" for d in twin.documents
               if d.doc_type.value in ("runbook", "sop") and "wf_billing_recon" in d.covers_entity_ids)
    assert not any("kn_warehouse_lineage" in d.covers_entity_ids for d in twin.documents
                   if d.doc_type.value in ("runbook", "sop"))
    for workflow in ("wf_billing_recon", "wf_financial_close"):
        assert coverage[ents[workflow].department_id] < 1.0
    assert "wf_invoicing" in documented  # a current SOP with no undocumented knowledge behind it counts


CATALOG = [
    {"id": "mit_close_backup", "kind": "mitigation", "type": "reassign_owner", "target_entity_id": "wf_financial_close",
     "new_owner_id": "role_controller", "duration_days": 20, "one_time_cost_usd": 15000, "rationale": "Train a backup"},
    {"id": "mit_lineage_runbook", "kind": "mitigation", "type": "document_runbook",
     "target_entity_id": "kn_warehouse_lineage", "one_time_cost_usd": 8000, "params": {"documented_pct": 0.8},
     "rationale": "Write down the lineage"},
    {"id": "mit_account_feed", "kind": "mitigation", "type": "add_replacement_feed",
     "target_entity_id": "ds_account_intel", "one_time_cost_usd": 250000,
     "params": {"replacement_vendor_id": "vendor_apex"}, "rationale": "Move the feed to Apex"},
]


def _write_catalog(tmp_path, entries) -> str:
    path = tmp_path / "mitigations.json"
    path.write_text(json.dumps(entries))
    return str(path)


def test_mitigation_catalog_loads_and_checks_references_against_the_twin(tmp_path):
    twin = load_twin(default_fixture_path())
    catalog = load_mitigation_catalog(_write_catalog(tmp_path, CATALOG), twin)
    assert [m.id for m in catalog] == ["mit_close_backup", "mit_lineage_runbook", "mit_account_feed"]
    assert catalog[0].new_owner_id == "role_controller" and catalog[2].one_time_cost_usd == 250000
    assert load_mitigation_catalog(_write_catalog(tmp_path, CATALOG)) == catalog
    assert default_mitigation_catalog_path() == default_fixture_path().parent / "mitigations.json"


@pytest.mark.parametrize(("change", "message"), [
    ({"kind": "action", "type": "remove_roles"}, "must be mitigations"),
    ({"target_entity_id": "wf_missing"}, "target_entity_id 'wf_missing' is not in the twin"),
    ({"new_owner_id": "role_missing"}, "new_owner_id 'role_missing' is not in the twin"),
    ({"target_entity_id": "kn_warehouse_lineage"}, "is a knowledge_asset, expected workflow"),
    ({"new_owner_id": "role_controller", "target_entity_id": "wf_billing_recon", "id": "mit_account_feed"},
     "must be unique"),
])
def test_mitigation_catalog_rejects_bad_entries(tmp_path, change, message):
    twin = load_twin(default_fixture_path())
    entries = [{**CATALOG[0], **change}, *CATALOG[1:]]
    with pytest.raises(ValueError, match=message):
        load_mitigation_catalog(_write_catalog(tmp_path, entries), twin)


def test_mitigation_catalog_checks_the_replacement_vendor_type(tmp_path):
    twin = load_twin(default_fixture_path())
    entries = [*CATALOG[:2], {**CATALOG[2], "params": {"replacement_vendor_id": "role_controller"}}]
    with pytest.raises(ValueError, match="replacement_vendor_id role_controller is a role, expected vendor"):
        load_mitigation_catalog(_write_catalog(tmp_path, entries), twin)
    with pytest.raises(ValueError, match="JSON array"):
        load_mitigation_catalog(_write_catalog(tmp_path, {"mitigations": CATALOG}), twin)
