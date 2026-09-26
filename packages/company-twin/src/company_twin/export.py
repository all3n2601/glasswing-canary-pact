"""Derived exports for the company twin (Person 1 required outputs).

All three are computed deterministically from the single source of truth
(``data/synthetic_company.json``); none is hand-maintained.

    python -m company_twin.export        # writes the three json files into data/

* knowledge_map.json  — person_token -> knowledge -> workflow, with bus factor / stranded risk
* graph_snapshot.json — nodes + edges for the frontend graph view
* vendor_report.json  — per-vendor cost, consumers, substitutability, coverage, replacement
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from .graph import affected_departments, build_graph
from .loader import default_fixture_path, load_company_twin
from .models import EntityType, Relation, Twin, entity_map


def knowledge_map(twin: Twin) -> dict:
    ents = entity_map(twin)
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
        holders = knows.get(k.id, [])
        rows.append({
            "knowledge_id": k.id,
            "name": k.name,
            "department_id": k.department_id,
            "documented_pct": k.documented_pct,
            "holders": holders,
            "bus_factor": len(holders) if holders else None,
            "enables_workflows": supports_wf.get(k.id, []),
            "single_point_of_failure": bool(holders) and len(holders) <= 2 and (k.documented_pct or 0) < 0.5,
        })
    # workflow ownership / stranding view
    owners: dict[str, list[str]] = {}
    for e in twin.edges:
        if e.relation == Relation.OWNS:
            owners.setdefault(e.target, []).append(e.source)
    workflows = []
    for w in twin.entities:
        if w.type != EntityType.workflow:
            continue
        o = owners.get(w.id, [])
        has_named_owners = len(o) > 0
        workflows.append({
            "workflow_id": w.id, "name": w.name, "criticality": w.criticality.value,
            "min_qualified_owners": w.min_qualified_owners, "owners": o,
            "documented_pct": w.documented_pct,
            "ownership_modeled": has_named_owners,   # false = owned at role/dept level, not a SPOF
            # a stranding risk only where we have modeled owners at/below the threshold
            "stranded_if_owners_removed": has_named_owners and len(o) <= (w.min_qualified_owners or 0),
        })
    return {"knowledge_assets": rows, "workflows": workflows}


def graph_snapshot(twin: Twin) -> dict:
    return {
        "company": twin.organization.display_name,
        "twin_version": twin.version.twin_version,
        "nodes": [
            {"id": e.id, "type": e.type.value, "name": e.name,
             "department_id": e.department_id, "criticality": e.criticality.value}
            for e in twin.entities
        ],
        "edges": [
            {"id": e.id, "source": e.source, "target": e.target, "relation": e.relation.value,
             "label": e.label, "strength": e.strength, "criticality": e.criticality.value}
            for e in twin.edges
        ],
    }


def vendor_report(twin: Twin) -> dict:
    """Vendor coverage / consumers / replacement — derived from the edge graph.

    Satisfies the acceptance check 'every vendor has cost, coverage, consumers, replacement'
    without adding non-schema fields to the vendor entity.
    """
    g = build_graph(twin)
    ents = entity_map(twin)
    subs = {  # possible replacements declared via SUBSTITUTES_FOR
    }
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
        depts = sorted(affected_departments(g, v.id))
        rows.append({
            "vendor_id": v.id, "name": v.name,
            "annual_cost_usd": v.annual_cost_usd,
            "one_time_exit_cost_usd": v.one_time_exit_cost_usd,
            "consumers": consumers,
            "consuming_departments": depts,
            "coverage": len(nx.descendants(g, v.id)),          # downstream footprint
            "min_substitutability": round(min_sub, 3),
            "replaceable": min_sub >= 0.5,
            "irreplaceable_flag": min_sub < 0.2,               # cutting this breaks something
            "replacement_candidates": subs.get(v.id, []),
        })
    rows.sort(key=lambda r: r["annual_cost_usd"], reverse=True)
    return {"vendors": rows}


def main() -> int:
    twin = load_company_twin()
    out_dir = default_fixture_path().parent
    artifacts = {
        "knowledge_map.json": knowledge_map(twin),
        "graph_snapshot.json": graph_snapshot(twin),
        "vendor_report.json": vendor_report(twin),
    }
    for name, data in artifacts.items():
        (out_dir / name).write_text(json.dumps(data, indent=2) + "\n")
        print(f"wrote {out_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
