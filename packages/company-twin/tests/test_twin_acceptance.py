"""Person 1 acceptance tests — every requirement, and a few beyond.

Covers the work-division Person-1 acceptance checks, merged-schema v2 section 12,
the four planted decision traps, the planted challenger dependency, and the derived
exports. Runs under the repo toolchain:  uv run pytest
"""

from __future__ import annotations

import json

import networkx as nx

from company_twin.export import graph_snapshot, knowledge_map, vendor_report
from company_twin.graph import affected_departments, build_graph
from company_twin.loader import default_fixture_path, load_company_twin
from company_twin.models import EntityType, Relation
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
    vendors = [e for e in TWIN.entities if e.type == EntityType.VENDOR]
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
        if w.type == EntityType.WORKFLOW and w.criticality.value in ("high", "critical"):
            flagged = (w.min_qualified_owners or 0) >= 1 and w.documented_pct is not None
            assert w.id in owned or flagged, w.id


def test_removing_a_node_finds_downstream_departments_and_kpis():
    depts = affected_departments(G, "vendor_auditlog")
    assert "dept_compliance" in depts
    assert nx.has_path(G, "vendor_auditlog", "kpi_soc2_coverage")


def test_fixture_validates_without_manual_correction():
    report = validate_twin(TWIN)
    assert report.ok, report.errors


# ---- schema v2 structural / cross-field ------------------------------------
def test_money_is_integer_usd():
    for e in TWIN.entities:
        for field in ("annual_cost_usd", "one_time_exit_cost_usd", "arr_usd", "failure_cost_per_day_usd"):
            val = getattr(e, field, None)
            if val is not None:
                assert isinstance(val, int), (e.id, field)


def test_org_totals_reconcile():
    dept_budget = sum(e.annual_cost_usd or 0 for e in TWIN.entities if e.type == EntityType.DEPARTMENT)
    assert TWIN.organization.total_annual_budget_usd == dept_budget == 8_000_000
    fte = sum(p.staffing.actual_fte + p.staffing.contractors_fte for p in TWIN.department_profiles)
    assert TWIN.organization.total_headcount_fte == fte == 420


def test_person_tokens_are_anonymised_and_not_in_strengths():
    tokens = {e.id for e in TWIN.entities if e.type == EntityType.PERSON_TOKEN}
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
        if e.type == EntityType.ROLE:
            roles[e.department_id] += 1
        if e.type == EntityType.KNOWLEDGE_ASSET:
            know[e.department_id] += 1
    for d in TWIN.documents:
        if d.status == "current" and d.department_id:
            docs[d.department_id] += 1
    prof = {p.department_id: p for p in TWIN.department_profiles}
    for de in [e for e in TWIN.entities if e.type == EntityType.DEPARTMENT]:
        assert roles[de.id] >= 2, f"{de.id} roles"
        assert know[de.id] >= 1, f"{de.id} knowledge"
        assert len(prof[de.id].strengths) >= 2, f"{de.id} strengths"
        assert docs[de.id] >= 1, f"{de.id} current document"


# ---- the four planted decision traps + planted challenger find --------------
def _reaches(a, b):
    return nx.has_path(G, a, b)


def test_trap_1_platform_ops_billing_stranding():
    assert _reaches("pt_billing_01", "kn_billing_exception")
    assert _reaches("wf_billing_recon", "wf_invoicing")
    wf = TWIN.entity_map()["wf_billing_recon"]
    owners = [e.source for e in TWIN.edges if e.target == "wf_billing_recon" and e.relation == Relation.OWNS]
    assert len(owners) == wf.min_qualified_owners == 2 and wf.documented_pct < 0.5


def test_trap_2_cancel_auditlog_breaks_soc2():
    assert _reaches("vendor_auditlog", "ds_audit_log")
    assert _reaches("vendor_auditlog", "kpi_soc2_coverage")  # full chain through the control
    assert TWIN.entity_map()["ctl_soc2_audit_logging"].mandatory is True


def test_trap_3_stop_migration_carry_cost():
    proj = TWIN.entity_map()["proj_warehouse_migration"]
    assert proj.retires_entity_ids == ["sys_warehouse_legacy"]
    assert TWIN.entity_map()["sys_warehouse_legacy"].annual_cost_usd == 400_000


def test_trap_4_reduce_engineering_hits_uptime():
    assert _reaches("sys_core_api", "kpi_uptime_sla")


def test_planted_challenger_dependency_identity_access():
    manifest = json.loads((DATA_DIR / "planted_items.json").read_text())
    chain = manifest["missed_dependency"]["chain"]
    for a, b in zip(chain, chain[1:]):
        assert _reaches(a, b), (a, b)
    ev_ids = {v.id for v in TWIN.evidence}
    assert set(manifest["missed_dependency"]["evidence_refs"]) <= ev_ids


# ---- derived exports well-formed -------------------------------------------
def test_exports_are_wellformed():
    km = knowledge_map(TWIN)
    assert any(k["single_point_of_failure"] for k in km["knowledge_assets"])
    assert any(w["stranded_if_owners_removed"] for w in km["workflows"])
    gs = graph_snapshot(TWIN)
    assert len(gs["nodes"]) == len(TWIN.entities) and len(gs["edges"]) == len(TWIN.edges)
    vr = vendor_report(TWIN)
    auditlog = next(v for v in vr["vendors"] if v["vendor_id"] == "vendor_auditlog")
    assert auditlog["irreplaceable_flag"] is True
