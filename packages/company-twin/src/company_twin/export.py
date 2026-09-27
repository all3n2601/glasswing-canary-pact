"""Derived exports for the company twin (Person 1 required outputs).

All four are computed deterministically from the single source of truth
(data/synthetic_company.json); none is hand-maintained.

    python -m company_twin.export        # writes the four json files into data/

* knowledge_map.json  : knowledge -> holder roles -> workflow, with bus factor / stranded risk
* graph_snapshot.json : nodes + edges for the frontend graph view (person tokens mapped to roles)
* vendor_report.json  : per-vendor cost, consumers, substitutability, coverage, replacement
* organization_profile.json : the OrganizationProfileView of the fixture under default settings, so
  the company's size, budget and departments cannot drift from the twin

Person tokens (pt_) never appear in these outputs; holders are reported as roles so the
frontend and any downstream prompt only ever show role-level information.

Reporting heuristics below classify rows in the derived reports. They are NOT authoritative
risk thresholds (those live in the engine / settings); the twin data stays judgement-free.
"""

from __future__ import annotations

import json
from datetime import datetime, time, timezone
from pathlib import Path

import networkx as nx
from contracts_py.api import OrganizationDepartmentSummary, OrganizationProfileView
from contracts_py.twin import OrganizationSettings

from .graph import affected_departments, build_graph
from .loader import default_fixture_path, load_company_twin
from .models import EntityType, Relation, Twin, entity_map

SPOF_MAX_HOLDERS = 2
SPOF_MAX_DOCUMENTED = 0.5
VENDOR_REPLACEABLE_MIN_SUB = 0.5
VENDOR_IRREPLACEABLE_MAX_SUB = 0.2


def _role_of(twin: Twin) -> dict[str, str]:
    """person_token id -> its role_id (for de-identifying outputs)."""
    return {e.id: (e.role_id or e.id) for e in twin.entities if e.type == EntityType.person_token}


def knowledge_map(twin: Twin) -> dict:
    ents = entity_map(twin)
    role_of = _role_of(twin)
    knows: dict[str, list[str]] = {}
    for e in twin.edges:
        if e.relation == Relation.KNOWS:
            knows.setdefault(e.target, []).append(e.source)  # knowledge -> [person tokens]
    supports_wf: dict[str, list[str]] = {}
    for e in twin.edges:
        if e.relation == Relation.SUPPORTS and ents.get(e.target) and ents[e.target].type == EntityType.workflow:
            supports_wf.setdefault(e.source, []).append(e.target)  # knowledge -> [workflows]
    rows = []
    for k in twin.entities:
        if k.type != EntityType.knowledge_asset:
            continue
        holders = knows.get(k.id, [])                       # person tokens, kept internal
        holder_roles = sorted({role_of.get(pt, pt) for pt in holders})
        rows.append({
            "knowledge_id": k.id,
            "name": k.name,
            "department_id": k.department_id,
            "documented_pct": k.documented_pct,
            "holder_roles": holder_roles,                   # roles, never pt_ ids
            "bus_factor": len(holders) if holders else None,
            "enables_workflows": supports_wf.get(k.id, []),
            "single_point_of_failure": bool(holders)
            and len(holders) <= SPOF_MAX_HOLDERS
            and (k.documented_pct or 0) < SPOF_MAX_DOCUMENTED,
        })
    owners: dict[str, list[str]] = {}
    for e in twin.edges:
        if e.relation == Relation.OWNS:
            owners.setdefault(e.target, []).append(e.source)
    workflows = []
    for w in twin.entities:
        if w.type != EntityType.workflow:
            continue
        o = owners.get(w.id, [])
        owner_roles = sorted({role_of.get(pt, pt) for pt in o})
        has_named_owners = len(o) > 0
        workflows.append({
            "workflow_id": w.id, "name": w.name, "criticality": w.criticality.value,
            "min_qualified_owners": w.min_qualified_owners, "owner_roles": owner_roles,
            "documented_pct": w.documented_pct,
            "ownership_modeled": has_named_owners,   # false = owned at role/dept level, not a SPOF
            "stranded_if_owners_removed": has_named_owners and len(o) <= (w.min_qualified_owners or 0),
        })
    return {"knowledge_assets": rows, "workflows": workflows}


def graph_snapshot(twin: Twin) -> dict:
    """Frontend graph. Person tokens are mapped to their role so only roles are shown."""
    role_of = _role_of(twin)

    def mapid(x: str) -> str:
        return role_of.get(x, x)

    nodes = [
        {"id": e.id, "type": e.type.value, "name": e.name,
         "department_id": e.department_id, "criticality": e.criticality.value}
        for e in twin.entities
        if e.type != EntityType.person_token  # roles already exist as nodes
    ]
    seen: set[tuple[str, str, str]] = set()
    edges = []
    for e in twin.edges:
        s, t = mapid(e.source), mapid(e.target)
        if s == t:
            continue  # self-loop created by folding a token into its role
        key = (s, t, e.relation.value)
        if key in seen:
            continue
        seen.add(key)
        edges.append({"id": e.id, "source": s, "target": t, "relation": e.relation.value,
                      "label": e.label, "strength": e.strength, "criticality": e.criticality.value})
    return {"company": twin.organization.display_name, "twin_version": twin.version.twin_version,
            "nodes": nodes, "edges": edges}


def vendor_report(twin: Twin) -> dict:
    """Vendor coverage / consumers / replacement, derived from the edge graph.

    Satisfies 'every vendor has cost, coverage, consumers, replacement' without adding
    non-schema fields to the vendor entity.
    """
    g = build_graph(twin)
    subs: dict[str, list[str]] = {}
    for e in twin.edges:
        if e.relation == Relation.SUBSTITUTES_FOR:
            subs.setdefault(e.target, []).append(e.source)
    rows = []
    for v in twin.entities:
        if v.type != EntityType.vendor:
            continue
        out_edges = [e for e in twin.edges if e.source == v.id]
        consumers = [e.target for e in out_edges]
        min_sub = min((e.substitutability for e in out_edges), default=1.0)
        rows.append({
            "vendor_id": v.id, "name": v.name,
            "annual_cost_usd": v.annual_cost_usd,
            "one_time_exit_cost_usd": v.one_time_exit_cost_usd,
            "consumers": consumers,
            "consuming_departments": sorted(affected_departments(g, v.id)),
            "coverage": len(nx.descendants(g, v.id)),
            "min_substitutability": round(min_sub, 3),
            "replaceable": min_sub >= VENDOR_REPLACEABLE_MIN_SUB,
            "irreplaceable_flag": min_sub < VENDOR_IRREPLACEABLE_MAX_SUB,
            "replacement_candidates": subs.get(v.id, []),
        })
    rows.sort(key=lambda r: r["annual_cost_usd"], reverse=True)
    return {"vendors": rows}


def organization_profile(twin: Twin, settings: OrganizationSettings | None = None) -> dict:
    """The organization profile view: the twin's organization and a summary row per department profile.

    Default settings are stamped from the twin's as-of date so the export is byte-identical on every run.
    """
    settings = settings or OrganizationSettings(
        updated_at=datetime.combine(twin.version.as_of_date, time(), tzinfo=timezone.utc))
    names = {e.id: e.name for e in twin.entities if e.type == EntityType.department}
    view = OrganizationProfileView(
        organization=twin.organization,
        departments=[
            OrganizationDepartmentSummary(
                department_id=p.department_id, name=names[p.department_id], mission=p.mission,
                actual_fte=p.staffing.actual_fte, annual_budget_usd=p.budget.annual_budget_usd,
                utilisation=p.staffing.utilisation, maturity_level=p.maturity_level,
                enabled=p.agent_id is None or p.agent_id in settings.enabled_agent_ids,
            )
            for p in twin.department_profiles
        ],
        settings=settings,
    )
    return view.model_dump(mode="json")


def main() -> int:
    twin = load_company_twin()
    out_dir = default_fixture_path().parent
    artifacts = {
        "knowledge_map.json": knowledge_map(twin),
        "graph_snapshot.json": graph_snapshot(twin),
        "vendor_report.json": vendor_report(twin),
        "organization_profile.json": organization_profile(twin),
    }
    for name, data in artifacts.items():
        (out_dir / name).write_text(json.dumps(data, indent=2) + "\n")
        print(f"wrote {out_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
