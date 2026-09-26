"""Validation for the company twin (Person 1: "validated company graph").

The Pydantic models (models.py) already enforce per-entity and structural rules on load.
This module adds the *cross-entity* and *graph* acceptance checks from the merged schema v2
(section 12) and the team work-division, and produces a human-readable report.

Run:  python -m company_twin.validate            # validates the default fixture
      validate_twin(twin) -> ValidationReport     # importable
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from .graph import build_graph
from .loader import load_company_twin
from .models import EntityType, Relation, Twin


@dataclass
class ValidationReport:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def err(self, msg: str) -> None:
        self.errors.append(msg)
        self.ok = False

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_twin(twin: Twin) -> ValidationReport:
    r = ValidationReport()
    ents = {e.id: e for e in twin.entities}
    depts = {e.id for e in twin.entities if e.type == EntityType.DEPARTMENT}
    roles = {e.id for e in twin.entities if e.type == EntityType.ROLE}
    person_tokens = {e.id for e in twin.entities if e.type == EntityType.PERSON_TOKEN}
    org = twin.organization

    # --- rule 16: organization totals equal the sums ---
    dept_budget = sum(e.annual_cost_usd or 0 for e in twin.entities if e.type == EntityType.DEPARTMENT)
    if org.total_annual_budget_usd != dept_budget:
        r.err(f"org.total_annual_budget_usd ({org.total_annual_budget_usd:,}) != sum dept budgets ({dept_budget:,})")
    fte = sum(p.staffing.actual_fte + p.staffing.contractors_fte for p in twin.department_profiles)
    if org.total_headcount_fte != fte:
        r.err(f"org.total_headcount_fte ({org.total_headcount_fte}) != sum profile FTE ({fte})")
    for fw in org.regulatory_frameworks:
        if not any(e.framework == fw for e in twin.entities if e.type == EntityType.CONTROL):
            r.err(f"regulatory framework {fw} has no control entity")

    # --- rule 17: department profiles consistent with their entities ---
    for p in twin.department_profiles:
        de = ents.get(p.department_id)
        if de is None:
            r.err(f"profile {p.department_id} points to a missing department")
            continue
        if p.budget.annual_budget_usd != de.annual_cost_usd:
            r.err(f"{p.department_id}: profile budget != entity annual_cost_usd")
        if p.staffing.actual_fte + p.staffing.contractors_fte != de.capacity_fte:
            r.err(f"{p.department_id}: actual+contractor FTE != entity capacity_fte")
        # rule 18: strengths
        for s in p.strengths:
            for sid in s.supports_entity_ids:
                if sid not in ents:
                    r.err(f"strength {s.id} supports unknown entity {sid}")
            for kr in s.key_role_ids:
                if kr not in roles:
                    r.err(f"strength {s.id} key_role_id {kr} is not a role")
                if kr in person_tokens:
                    r.err(f"strength {s.id} key_role_ids must not contain a person token")

    # --- rule 19: documents ---
    for d in twin.documents:
        for cid in d.covers_entity_ids:
            if cid not in ents:
                r.err(f"document {d.id} covers unknown entity {cid}")
        if d.owner_role_id is not None and d.owner_role_id not in roles:
            r.err(f"document {d.id} owner_role_id {d.owner_role_id} is not a role")

    # --- FLOWS_TO channels connect departments (or kpi_company) ---
    domain_nodes = depts | {"kpi_company"}
    for e in twin.edges:
        if e.relation == Relation.FLOWS_TO:
            if e.source not in domain_nodes or e.target not in domain_nodes:
                r.err(f"FLOWS_TO edge {e.id} must connect departments/kpi_company")

    # --- every entity's department_id resolves to a department ---
    for e in twin.entities:
        if e.department_id is not None and e.department_id not in depts:
            r.err(f"{e.id} department_id {e.department_id} is not a department")

    # --- acceptance: every critical workflow has an owner OR is a flagged knowledge risk ---
    owned = {e.target for e in twin.edges if e.relation == Relation.OWNS}
    for e in twin.entities:
        if e.type == EntityType.WORKFLOW and e.criticality.value in ("high", "critical"):
            flagged_risk = (e.min_qualified_owners or 0) >= 1 and (e.documented_pct is not None)
            if e.id not in owned and not flagged_risk:
                r.warn(f"critical workflow {e.id} has no OWNS edge and is not flagged as a knowledge risk")

    # --- graph reachability acceptance: removing a node finds downstream depts/workflows/KPIs ---
    g = build_graph(twin)
    # sample the four decision targets
    for target in ("dept_operations", "vendor_auditlog", "proj_warehouse_migration", "dept_engineering"):
        if target in g:
            desc = nx.descendants(g, target)
            if not desc:
                r.warn(f"decision target {target} has no downstream reachable nodes")

    r.stats = {
        "entities": len(twin.entities),
        "edges": len(twin.edges),
        "pressures": len(twin.pressures),
        "documents": len(twin.documents),
        "evidence": len(twin.evidence),
        "department_profiles": len(twin.department_profiles),
        "roles": len(roles),
        "person_tokens": len(person_tokens),
        "flows_to_channels": sum(1 for e in twin.edges if e.relation == Relation.FLOWS_TO),
    }
    return r


def main() -> int:
    twin = load_company_twin()
    report = validate_twin(twin)
    print(f"Twin: {twin.organization.display_name}  (schema {twin.schema_version})")
    print("stats:", report.stats)
    for w in report.warnings:
        print("  WARN:", w)
    for e in report.errors:
        print("  ERROR:", e)
    print("RESULT:", "VALID ✅" if report.ok else "INVALID ❌")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
