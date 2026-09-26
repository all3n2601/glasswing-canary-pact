"""Person 1 acceptance tests - every requirement, and a few beyond.

Covers the work-division Person-1 acceptance checks, merged-schema v2 section 12,
the Northstar plan story (vendor consolidation and workforce knowledge loss, plan
Milestone A), the planted vendor-reconciliation dependency, the frozen ID registry,
and the derived exports. Runs under the repo toolchain:  uv run pytest
"""

from __future__ import annotations

import json
import re

import networkx as nx

from company_twin.export import graph_snapshot, knowledge_map, vendor_report
from company_twin.graph import affected_departments, build_graph
from company_twin.loader import default_fixture_path, load_company_twin
from company_twin.models import EntityType, Relation, entity_map
from company_twin.validate import validate_twin

TWIN = load_company_twin()
G = build_graph(TWIN)
IDS = {e.id for e in TWIN.entities}
DATA_DIR = default_fixture_path().parent


# ---- work-division section 4 acceptance ------------------------------------
def test_every_edge_has_valid_endpoints():
    for e in TWIN.edges:
        assert e.source in IDS and e.target in IDS, e.id


def test_every_vendor_has_cost_consumers_and_replacement_info():
    rep = {v["vendor_id"]: v for v in vendor_report(TWIN)["vendors"]}
    vendors = [e for e in TWIN.entities if e.type == EntityType.vendor]
    assert vendors
    for v in vendors:
        r = rep[v.id]
        assert v.annual_cost_usd and v.annual_cost_usd > 0
        assert r["consumers"]
        assert "min_substitutability" in r and "replaceable" in r
        assert r["coverage"] >= 1


def test_every_critical_workflow_has_owner_or_is_flagged_knowledge_risk():
    owned = {e.target for e in TWIN.edges if e.relation == Relation.OWNS}
    for w in TWIN.entities:
        if w.type == EntityType.workflow and w.criticality.value in ("high", "critical"):
            flagged = (w.min_qualified_owners or 0) >= 1 and w.documented_pct is not None
            assert w.id in owned or flagged, w.id


def test_removing_a_node_finds_downstream_departments_and_kpis():
    depts = affected_departments(G, "sys_audit_service")
    assert "dept_compliance" in depts
    assert nx.has_path(G, "sys_audit_service", "kpi_soc2_coverage")


def test_fixture_validates_without_manual_correction():
    issues = validate_twin(TWIN)
    errors = [i for i in issues if i.severity == "error"]
    assert not errors, errors


# ---- schema v2 structural / cross-field ------------------------------------
def test_money_is_integer_usd():
    for e in TWIN.entities:
        for field in ("annual_cost_usd", "one_time_exit_cost_usd", "arr_usd", "failure_cost_per_day_usd"):
            val = getattr(e, field, None)
            if val is not None:
                assert isinstance(val, int), (e.id, field)


def test_org_totals_reconcile():
    dept_budget = sum(e.annual_cost_usd or 0 for e in TWIN.entities if e.type == EntityType.department)
    assert TWIN.organization.total_annual_budget_usd == dept_budget == 40_000_000_000
    fte = sum(p.staffing.actual_fte + p.staffing.contractors_fte for p in TWIN.department_profiles)
    assert TWIN.organization.total_headcount_fte == fte == 60_000


def test_person_tokens_are_anonymised_and_not_in_strengths():
    tokens = {e.id for e in TWIN.entities if e.type == EntityType.person_token}
    for t in tokens:
        assert t.startswith("pt_")
    for p in TWIN.department_profiles:
        for s in p.strengths:
            assert not (set(s.key_role_ids) & tokens), s.id


# ---- "skills at every level" -----------------------------------------------
def test_every_department_has_roles_strengths_knowledge_and_a_document():
    from collections import defaultdict
    roles: dict = defaultdict(int)
    know: dict = defaultdict(int)
    docs: dict = defaultdict(int)
    for e in TWIN.entities:
        if e.type == EntityType.role:
            roles[e.department_id] += 1
        if e.type == EntityType.knowledge_asset:
            know[e.department_id] += 1
    for d in TWIN.documents:
        if d.status == "current" and d.department_id:
            docs[d.department_id] += 1
    prof = {p.department_id: p for p in TWIN.department_profiles}
    for de in [e for e in TWIN.entities if e.type == EntityType.department]:
        assert roles[de.id] >= 2, f"{de.id} roles"
        assert know[de.id] >= 1, f"{de.id} knowledge"
        assert len(prof[de.id].strengths) >= 2, f"{de.id} strengths"
        assert docs[de.id] >= 1, f"{de.id} current document"


# ---- the plan story: vendor consolidation (A-03) + workforce knowledge loss (A-04) ----
def _reaches(a, b):
    return nx.has_path(G, a, b)


def test_vendor_costs_total_exactly_8b():
    vendor_total = sum(e.annual_cost_usd or 0 for e in TWIN.entities if e.type == EntityType.vendor)
    assert vendor_total == 8_000_000_000
    vendors = {e.id for e in TWIN.entities if e.type == EntityType.vendor}
    assert vendors == {
        "vendor_apex", "vendor_beacon", "vendor_cinder", "vendor_delta",
        "vendor_echo", "vendor_flux", "vendor_granite",
    }


def test_only_the_eight_workforce_roles_own_or_back_up_the_two_stranded_workflows():
    workforce_roles = {
        "role_close_accountant", "role_gl_accountant", "role_reporting_analyst",
        "role_data_platform_lead", "role_billing_ops_lead", "role_billing_specialist",
        "role_revenue_accountant", "role_ar_specialist",
    }
    strand_targets = {"wf_financial_close", "wf_billing_recon"}
    owners = {e.source for e in TWIN.edges
              if e.relation in (Relation.OWNS, Relation.BACKS_UP) and e.target in strand_targets}
    assert owners
    assert owners <= workforce_roles
    # the outside backups (W-4, W-5) must not own/back these workflows on the base twin
    assert "role_controller" not in owners and "role_finance_analyst" not in owners


def test_planted_edge_is_absent_and_its_evidence_names_both_endpoints():
    planted_source, planted_target = "ds_account_intel", "wf_vendor_reconciliation"
    assert not any(e.source == planted_source and e.target == planted_target for e in TWIN.edges)
    manifest = json.loads((DATA_DIR / "planted_items.json").read_text())
    assert manifest["planted_edge"]["source"] == planted_source
    assert manifest["planted_edge"]["target"] == planted_target
    ents = entity_map(TWIN)
    ev = next(v for v in TWIN.evidence if v.id == "ev_echo_account_intel_feed")
    assert ents[planted_source].name in ev.snippet
    assert ents[planted_target].name in ev.snippet
    assert manifest["planted_edge"]["evidence_refs"] == ["ev_echo_account_intel_feed"]


def test_delta_sole_provider_identity_apex_sole_provider_corporate_linkage():
    providers_identity = {e.source for e in TWIN.edges
                          if e.relation == Relation.PROVIDES and e.target == "ds_identity_verification"}
    providers_linkage = {e.source for e in TWIN.edges
                         if e.relation == Relation.PROVIDES and e.target == "ds_corporate_linkage"}
    assert providers_identity == {"vendor_delta"}
    assert providers_linkage == {"vendor_apex"}
    assert entity_map(TWIN)["ds_identity_verification"].criticality.value == "critical"
    assert entity_map(TWIN)["ds_corporate_linkage"].criticality.value == "critical"


# ---- derived exports well-formed -------------------------------------------
def test_exports_are_wellformed():
    km = knowledge_map(TWIN)
    assert any(k["single_point_of_failure"] for k in km["knowledge_assets"])
    assert any(w["stranded_if_owners_removed"] for w in km["workflows"])
    gs = graph_snapshot(TWIN)
    non_tokens = [e for e in TWIN.entities if e.type != EntityType.person_token]
    assert len(gs["nodes"]) == len(non_tokens)          # person tokens mapped to roles
    assert 0 < len(gs["edges"]) <= len(TWIN.edges)      # remapped, self-loops/dupes dropped
    # no person tokens leak to the frontend
    node_ids = {n["id"] for n in gs["nodes"]}
    assert not any(n.startswith("pt_") for n in node_ids)
    for e in gs["edges"]:
        assert not e["source"].startswith("pt_") and not e["target"].startswith("pt_")
    vr = vendor_report(TWIN)
    delta = next(v for v in vr["vendors"] if v["vendor_id"] == "vendor_delta")
    assert delta["irreplaceable_flag"] is True


# ---- derived DepartmentProfile fields (computed in the loader) --------------
def test_department_profile_derived_fields_are_populated():
    ents = entity_map(TWIN)
    for p in TWIN.department_profiles:
        did = p.department_id
        # owned = every entity with this department_id
        assert set(p.owned_entity_ids) == {e.id for e in TWIN.entities if e.department_id == did}
        # critical workflows subset of owned, all high/critical workflows
        for wid in p.critical_workflow_ids:
            assert ents[wid].type == EntityType.workflow
            assert ents[wid].criticality.value in ("high", "critical")
        assert set(p.kpi_ids) == {e.id for e in TWIN.entities
                                  if e.department_id == did and e.type == EntityType.kpi}
        assert 0.0 <= p.documentation_coverage <= 1.0


# ---- project entity fields the engine needs --------------------------------
def test_projects_have_remaining_cost_and_expected_completion():
    projects = [e for e in TWIN.entities if e.type == EntityType.project]
    assert projects
    for pr in projects:
        assert pr.remaining_cost_usd is not None and pr.remaining_cost_usd >= 0
        assert pr.expected_completion_day is not None and pr.expected_completion_day > 0
    mig = entity_map(TWIN)["proj_billing_modernization"]
    assert mig.remaining_cost_usd == round(mig.annual_cost_usd * (1 - mig.completion_pct))


def test_version_has_as_of_date():
    assert str(TWIN.version.as_of_date) == "2026-09-26"  # contracts_py coerces to date


# ---- documentation coverage (task item 3): every critical workflow has current runbook/sop
# coverage, except the two deliberate story gaps -----------------------------
def test_every_critical_workflow_has_current_runbook_or_sop_except_the_story_gaps():
    # wf_billing_recon: its only covering document (doc_billing_recon_runbook) is deliberately
    # outdated (W-3). kn_warehouse_lineage, the other story gap, is a knowledge asset behind
    # wf_financial_close, not a workflow-level doc gap, so wf_financial_close itself (documented
    # via doc_sop_financial_close) is not exempted here.
    story_gap_workflows = {"wf_billing_recon"}
    current_doc_types_by_entity: dict[str, set[str]] = {}
    for d in TWIN.documents:
        if d.status.value == "current":
            for cid in d.covers_entity_ids:
                current_doc_types_by_entity.setdefault(cid, set()).add(d.doc_type.value)

    critical_workflows = [
        e for e in TWIN.entities
        if e.type == EntityType.workflow and e.criticality.value in ("high", "critical")
    ]
    assert critical_workflows
    for w in critical_workflows:
        if w.id in story_gap_workflows:
            continue
        covering = current_doc_types_by_entity.get(w.id, set())
        assert covering & {"runbook", "sop"}, f"{w.id} has no current runbook or sop"


# ---- A-01: frozen ID registry -----------------------------------------------
ID_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")


def _registry_ids(registry: dict, group: str) -> set[str]:
    return {it["id"] for it in registry.get(group, []) if isinstance(it, dict) and "id" in it}


def test_id_registry_covers_every_fixture_id_and_matches_the_schema_regex():
    registry = json.loads((DATA_DIR / "id_registry.json").read_text())
    for group, items in registry.items():
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, dict) and "id" in it:
                assert ID_REGEX.match(it["id"]) and len(it["id"]) <= 80, (group, it["id"])

    fixture_entity_ids = {e.id for e in TWIN.entities if e.type != EntityType.person_token}
    registry_entity_ids: set[str] = set()
    for group in ("departments", "kpis", "customer_segments", "controls", "roles", "systems",
                  "vendors", "datasets", "workflows", "knowledge", "projects"):
        registry_entity_ids |= _registry_ids(registry, group)
    assert fixture_entity_ids <= registry_entity_ids, fixture_entity_ids - registry_entity_ids

    assert {d.id for d in TWIN.documents} == _registry_ids(registry, "documents")
    assert {v.id for v in TWIN.evidence} == _registry_ids(registry, "evidence")
    assert {p.id for p in TWIN.pressures} == _registry_ids(registry, "pressures")
    channel_ids = {e.id for e in TWIN.edges if e.relation == Relation.FLOWS_TO}
    assert channel_ids == _registry_ids(registry, "channels")

    vendor_brief = json.loads((DATA_DIR / "vendor_scenario.json").read_text())
    workforce_brief = json.loads((DATA_DIR / "workforce_scenario.json").read_text())
    brief_intervention_ids = {i["id"] for i in vendor_brief["candidate_interventions"]} | {
        i["id"] for i in workforce_brief["candidate_interventions"]
    }
    assert brief_intervention_ids == _registry_ids(registry, "interventions")
