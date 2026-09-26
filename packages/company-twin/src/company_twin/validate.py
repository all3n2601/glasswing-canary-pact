"""Validation for the company twin (Person 1: "validated company graph").

The contract models (contracts_py.twin) enforce per-entity and structural rules on load.
This module adds the cross-entity and graph acceptance checks from schema v2.1 section 12
and the team work-division, returning the agreed boundary type:
``list[contracts_py.twin.ValidationIssue]`` (empty = valid).

Run:  python -m company_twin.validate
"""

from __future__ import annotations

import networkx as nx
from contracts_py.twin import ValidationIssue

from .graph import build_graph
from .loader import load_company_twin
from .models import EntityType, Relation, Twin


def validate_twin(twin: Twin) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    def err(rule: str, message: str, ids: list[str] | None = None) -> None:
        issues.append(ValidationIssue(rule=rule, severity="error", message=message, ids=ids or []))

    def warn(rule: str, message: str, ids: list[str] | None = None) -> None:
        issues.append(ValidationIssue(rule=rule, severity="warning", message=message, ids=ids or []))

    ents = {e.id: e for e in twin.entities}
    depts = {e.id for e in twin.entities if e.type == EntityType.department}
    roles = {e.id for e in twin.entities if e.type == EntityType.role}
    person_tokens = {e.id for e in twin.entities if e.type == EntityType.person_token}
    org = twin.organization

    # rule 16: organization totals equal the sums
    dept_budget = sum(e.annual_cost_usd or 0 for e in twin.entities if e.type == EntityType.department)
    if org.total_annual_budget_usd != dept_budget:
        err("org_budget_total", f"total_annual_budget_usd {org.total_annual_budget_usd} != sum dept budgets {dept_budget}")
    fte = sum(p.staffing.actual_fte + p.staffing.contractors_fte for p in twin.department_profiles)
    if org.total_headcount_fte != fte:
        err("org_headcount_total", f"total_headcount_fte {org.total_headcount_fte} != sum profile FTE {fte}")
    for fw in org.regulatory_frameworks:
        if not any(e.framework == fw for e in twin.entities if e.type == EntityType.control):
            err("framework_without_control", f"regulatory framework {fw} has no control entity")

    # rule 17: department profiles consistent with their entities
    for p in twin.department_profiles:
        de = ents.get(p.department_id)
        if de is None:
            err("profile_orphan", "profile points to missing department", [p.department_id])
            continue
        if p.budget.annual_budget_usd != de.annual_cost_usd:
            err("profile_budget_mismatch", "profile budget != entity annual_cost_usd", [p.department_id])
        if p.staffing.actual_fte + p.staffing.contractors_fte != de.capacity_fte:
            err("profile_fte_mismatch", "actual+contractor FTE != entity capacity_fte", [p.department_id])
        for s in p.strengths:
            for sid in s.supports_entity_ids:
                if sid not in ents:
                    err("strength_bad_support", f"strength {s.id} supports unknown entity", [sid])
            for kr in s.key_role_ids:
                if kr not in roles:
                    err("strength_bad_role", f"strength {s.id} key_role_id is not a role", [kr])
                if kr in person_tokens:
                    err("strength_person_token", f"strength {s.id} key_role_ids must not contain a person token", [kr])

    # rule 19: documents
    for d in twin.documents:
        for cid in d.covers_entity_ids:
            if cid not in ents:
                err("doc_bad_cover", f"document {d.id} covers unknown entity", [cid])
        if d.owner_role_id is not None and d.owner_role_id not in roles:
            err("doc_bad_owner", f"document {d.id} owner_role_id is not a role", [d.owner_role_id])

    # FLOWS_TO channels connect departments (or kpi_company)
    domain_nodes = depts | {"kpi_company"}
    for e in twin.edges:
        if e.relation == Relation.FLOWS_TO and (e.source not in domain_nodes or e.target not in domain_nodes):
            err("channel_not_domain", f"FLOWS_TO edge {e.id} must connect departments/kpi_company", [e.id])

    # every entity department_id resolves to a department
    for e in twin.entities:
        if e.department_id is not None and e.department_id not in depts:
            err("bad_department_id", f"{e.id} department_id is not a department", [e.id])

    # acceptance: every critical workflow has an owner OR is a flagged knowledge risk
    owned = {e.target for e in twin.edges if e.relation == Relation.OWNS}
    for e in twin.entities:
        if e.type == EntityType.workflow and e.criticality.value in ("high", "critical"):
            flagged = (e.min_qualified_owners or 0) >= 1 and e.documented_pct is not None
            if e.id not in owned and not flagged:
                warn("critical_wf_no_owner", f"critical workflow {e.id} has no owner and is not flagged", [e.id])

    # graph reachability: the decision targets have a downstream blast radius
    g = build_graph(twin)
    for target in ("dept_operations", "vendor_auditlog", "proj_warehouse_migration", "dept_engineering"):
        if target in g and not nx.descendants(g, target):
            warn("no_downstream", f"decision target {target} has no downstream reachable nodes", [target])

    return issues


def main() -> int:
    twin = load_company_twin()
    issues = validate_twin(twin)
    errors = [i for i in issues if i.severity == "error"]
    print(f"Twin: {twin.organization.display_name}  (schema {twin.schema_version})")
    print(f"entities={len(twin.entities)} edges={len(twin.edges)} issues={len(issues)} errors={len(errors)}")
    for i in issues:
        print(f"  {i.severity.upper()} [{i.rule}] {i.message} {i.ids or ''}")
    print("RESULT:", "VALID" if not errors else "INVALID")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
