"""One test per validate_twin rule (schema v2.2.0 section 12, rules 1-4 and 16-19).

Each test starts from ``BASE_TWIN`` (a minimal, hand-verified-clean twin) and mutates a
deep copy to introduce exactly one violation, then asserts validate_twin reports an issue
with that rule number and severity. ``test_baseline_twin_is_clean`` pins down that the
fixture itself has zero issues, so a rule test failing to see an issue means the mutation
didn't trigger the check, not that the baseline was already dirty.
"""

from __future__ import annotations

import copy
from typing import Any

from company_twin.models import Twin
from company_twin.validate import validate_twin

BASE_TWIN: dict[str, Any] = {
    "schema_version": "2.1.1",
    "version": {
        "twin_version": "tv_test",
        "settings_version": 1,
        "prompt_version": "p1",
        "model_id": "m1",
        "engine_version": "e1",
        "created_at": "2026-09-26T00:00:00Z",
        "as_of_date": "2026-09-26",
    },
    "organization": {
        "id": "org_test",
        "legal_name": "Test Co",
        "display_name": "Test Co",
        "sector": "technology_saas",
        "business_model": "b2b",
        "size_band": "smb",
        "headquarters_country": "US",
        "annual_revenue_usd": 1000000,
        "total_annual_budget_usd": 3000000,
        "total_headcount_fte": 21,
        "fiscal_year_start_month": 1,
        "regulatory_frameworks": ["SOC2"],
        "description": "test org",
    },
    "department_profiles": [
        {
            "department_id": "dept_a",
            "mission": "m",
            "staffing": {
                "sanctioned_fte": 1, "actual_fte": 1, "contractors_fte": 0,
                "open_positions": 0, "attrition_rate_annual": 0.1,
                "avg_time_to_hire_days": 30, "utilisation": 0.5,
            },
            "budget": {"annual_budget_usd": 1000000, "spent_ytd_usd": 0, "fixed_cost_pct": 0.1},
            "strengths": [{"id": "str_a", "name": "s", "category": "capability", "level": 3,
                           "concentration": 0.2}],
            "maturity_level": 3,
        },
        {
            "department_id": "dept_b",
            "mission": "m",
            "staffing": {
                "sanctioned_fte": 20, "actual_fte": 20, "contractors_fte": 0,
                "open_positions": 0, "attrition_rate_annual": 0.1,
                "avg_time_to_hire_days": 30, "utilisation": 0.5,
            },
            "budget": {"annual_budget_usd": 2000000, "spent_ytd_usd": 0, "fixed_cost_pct": 0.1},
            "strengths": [{"id": "str_b", "name": "s", "category": "capability", "level": 3,
                           "concentration": 0.2}],
            "maturity_level": 3,
        },
    ],
    "entities": [
        {"id": "dept_a", "type": "department", "name": "A", "annual_cost_usd": 1000000, "capacity_fte": 1},
        {"id": "dept_b", "type": "department", "name": "B", "annual_cost_usd": 2000000, "capacity_fte": 20},
        {"id": "role_a", "type": "role", "name": "Role A", "department_id": "dept_a",
         "annual_cost_usd": 100000, "capacity_fte": 1},
        {"id": "pt_a", "type": "person_token", "name": "PT A", "department_id": "dept_a",
         "role_id": "role_a", "sensitivity": "hr"},
        {"id": "wf_a", "type": "workflow", "name": "WF A", "department_id": "dept_a",
         "criticality": "high", "min_qualified_owners": 1, "failure_cost_per_day_usd": 1000,
         "documented_pct": 0.5},
        {"id": "sys_b", "type": "system", "name": "Sys B", "department_id": "dept_b",
         "annual_cost_usd": 500000, "failure_cost_per_day_usd": 2000},
        {"id": "ctl_a", "type": "control", "name": "Ctl A", "department_id": "dept_a",
         "mandatory": True, "framework": "SOC2"},
    ],
    "edges": [
        {"id": "e_wf_sys", "source": "wf_a", "target": "sys_b", "relation": "DEPENDS_ON",
         "criticality": "high", "evidence_refs": ["ev_1"], "strength": 0.5,
         "substitutability": 0.5, "lag_days": 0, "confidence": 0.9},
        {"id": "e_owns", "source": "role_a", "target": "wf_a", "relation": "OWNS",
         "criticality": "medium", "strength": 0.5, "substitutability": 0.5,
         "lag_days": 0, "confidence": 0.9},
        {"id": "ch_a_b", "source": "dept_a", "target": "dept_b", "relation": "FLOWS_TO",
         "channel_kind": "budget", "criticality": "medium", "strength": 0.5,
         "substitutability": 0.5, "lag_days": 0, "confidence": 0.9},
    ],
    "pressures": [],
    "documents": [
        {"id": "doc_a", "title": "Doc A", "doc_type": "runbook", "department_id": "dept_a",
         "owner_role_id": "role_a", "uri": "artifacts/doc_a.md", "mime_type": "text/markdown",
         "status": "current", "covers_entity_ids": ["wf_a"], "summary": "s",
         "uploaded_at": "2026-09-26T00:00:00Z"},
    ],
    "evidence": [
        {"id": "ev_1", "source_type": "workflow_map", "document_id": "doc_a", "snippet": "snip"},
    ],
}


def _twin(mutate=None) -> Twin:
    data = copy.deepcopy(BASE_TWIN)
    if mutate is not None:
        mutate(data)
    return Twin.model_validate(data)


def _issues_for_rule(twin: Twin, rule: int) -> list:
    return [i for i in validate_twin(twin) if i.rule == rule]


def test_baseline_twin_is_clean():
    assert validate_twin(_twin()) == []


def test_rule_01_edge_endpoint_missing():
    def mutate(data):
        data["edges"][0]["target"] = "sys_missing"

    issues = _issues_for_rule(_twin(mutate), 1)
    assert any(i.severity == "error" and "sys_missing" in i.message for i in issues)


def test_rule_01_evidence_ref_unresolved():
    def mutate(data):
        data["entities"][4]["evidence_refs"] = ["ev_missing"]

    issues = _issues_for_rule(_twin(mutate), 1)
    assert any(i.severity == "error" and "ev_missing" in i.message for i in issues)


def test_rule_01_required_field_missing_per_type():
    def mutate(data):
        del data["entities"][5]["failure_cost_per_day_usd"]  # sys_b is a system

    issues = _issues_for_rule(_twin(mutate), 1)
    assert any(i.severity == "error" and "sys_b" in i.message for i in issues)


def test_rule_02_high_edges_need_evidence():
    def mutate(data):
        data["edges"][0]["evidence_refs"] = []

    issues = _issues_for_rule(_twin(mutate), 2)
    assert any(i.severity == "error" and "e_wf_sys" in i.message for i in issues)


def test_rule_02_flows_to_needs_channel_kind():
    def mutate(data):
        data["edges"][2]["channel_kind"] = None

    issues = _issues_for_rule(_twin(mutate), 2)
    assert any(i.severity == "error" and "ch_a_b" in i.message for i in issues)


def test_rule_03_cross_department_edge_needs_channel():
    def mutate(data):
        data["edges"].pop()  # drop ch_a_b, leaving e_wf_sys crossing dept_a -> dept_b unmatched

    issues = _issues_for_rule(_twin(mutate), 3)
    assert any(i.severity == "warning" and "e_wf_sys" in i.message for i in issues)


def test_rule_04_person_token_prefix():
    def mutate(data):
        data["entities"][3]["id"] = "person_a"
        data["entities"][3]["role_id"] = "role_a"
        # keep every other reference to pt_a consistent by not referencing it elsewhere

    issues = _issues_for_rule(_twin(mutate), 4)
    assert any(i.severity == "error" and "pt_" in i.message for i in issues)


def test_rule_04_person_token_sensitivity():
    def mutate(data):
        data["entities"][3]["sensitivity"] = "general"

    issues = _issues_for_rule(_twin(mutate), 4)
    assert any(i.severity == "error" and "hr" in i.message for i in issues)


def test_rule_16_organization_budget_total():
    def mutate(data):
        data["organization"]["total_annual_budget_usd"] = 1

    issues = _issues_for_rule(_twin(mutate), 16)
    assert any(i.severity == "error" for i in issues)


def test_rule_16_framework_without_control():
    def mutate(data):
        data["organization"]["regulatory_frameworks"] = ["SOC2", "GDPR"]

    issues = _issues_for_rule(_twin(mutate), 16)
    assert any(i.severity == "error" and "GDPR" in i.message for i in issues)


def test_rule_17_profile_budget_mismatch():
    def mutate(data):
        data["department_profiles"][0]["budget"]["annual_budget_usd"] = 1

    issues = _issues_for_rule(_twin(mutate), 17)
    assert any(i.severity == "error" and "dept_a" in i.ids for i in issues)


def test_rule_17_missing_profile():
    def mutate(data):
        data["department_profiles"].pop()

    issues = _issues_for_rule(_twin(mutate), 17)
    assert any(i.severity == "error" and "dept_b" in i.message for i in issues)


def test_rule_17_over_sanctioned_staffing_is_a_warning():
    def mutate(data):
        data["department_profiles"][0]["staffing"]["sanctioned_fte"] = 0
        data["department_profiles"][0]["staffing"]["open_positions"] = 0
        # actual_fte (1) > sanctioned_fte (0) + open_positions (0)

    issues = _issues_for_rule(_twin(mutate), 17)
    assert any(i.severity == "warning" and "dept_a" in i.ids for i in issues)
    assert not any(i.severity == "error" and "sanctioned" in i.message for i in issues)


def test_rule_18_strength_level_needs_evidence():
    def mutate(data):
        data["department_profiles"][0]["strengths"][0]["level"] = 4

    issues = _issues_for_rule(_twin(mutate), 18)
    assert any(i.severity == "error" and "str_a" in i.message for i in issues)


def test_rule_18_strength_key_role_must_not_be_person_token():
    def mutate(data):
        # key_role_ids is role_-prefixed at the model level, so the planted person
        # token needs a role_-shaped id to reach this twin-level check at all.
        data["entities"].append({"id": "role_masquerade", "type": "person_token", "name": "Masquerade",
                                  "department_id": "dept_a", "role_id": "role_a", "sensitivity": "hr"})
        data["department_profiles"][0]["strengths"][0]["key_role_ids"] = ["role_masquerade"]

    issues = _issues_for_rule(_twin(mutate), 18)
    assert any(i.severity == "error" and "role_masquerade" in i.message for i in issues)


def test_rule_19_document_covers_unknown_entity():
    def mutate(data):
        data["documents"][0]["covers_entity_ids"] = ["wf_missing"]

    issues = _issues_for_rule(_twin(mutate), 19)
    assert any(i.severity == "error" and "wf_missing" in i.message for i in issues)


def test_rule_19_non_synthetic_document_needs_checksum():
    def mutate(data):
        data["documents"][0]["synthetic"] = False

    issues = _issues_for_rule(_twin(mutate), 19)
    assert any(i.severity == "error" and "doc_a" in i.message for i in issues)


def test_rule_19_document_owner_must_be_a_role():
    def mutate(data):
        # role_-prefixed (so contracts_py's own RoleID pattern still accepts it)
        # but no such role entity exists in the twin.
        data["documents"][0]["owner_role_id"] = "role_ghost"

    issues = _issues_for_rule(_twin(mutate), 19)
    assert any(i.severity == "error" and "role_ghost" in i.message for i in issues)
