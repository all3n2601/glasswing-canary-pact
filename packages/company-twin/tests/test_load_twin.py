"""load_twin (plan B-01) and the B-03 evidence/confidence acceptance check.

Covers: load_twin with and without a snippets file, documented_pct derivation and its
disagreement warning, invalid references failing with readable validate_twin errors, and
every critical edge on the real fixture carrying evidence and a confidence score.
"""

from __future__ import annotations

import json

from company_twin.loader import default_fixture_path, load_twin
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
