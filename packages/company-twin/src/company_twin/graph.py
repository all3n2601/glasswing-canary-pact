from typing import Literal

import networkx as nx

from .models import Edge, Twin


def build_graph(twin: Twin) -> nx.DiGraph:
    graph = nx.DiGraph(company_id=twin.organization.id, version=twin.version.twin_version)
    for entity in twin.entities:
        graph.add_node(entity.id, **entity.model_dump())
    for e in twin.edges:
        if e.source not in graph or e.target not in graph:
            raise ValueError(f"Edge references an unknown entity: {e.source} -> {e.target}")
        graph.add_edge(e.source, e.target, **e.model_dump(exclude={"source", "target"}))
    return graph


def downstream_paths(graph: nx.DiGraph, entity_id: str) -> dict[str, list[str]]:
    if entity_id not in graph:
        raise KeyError(f"Unknown entity: {entity_id}")
    return {
        target: nx.shortest_path(graph, entity_id, target)
        for target in nx.descendants(graph, entity_id)
    }


def upstream_paths(graph: nx.DiGraph, entity_id: str) -> dict[str, list[str]]:
    """What this entity depends on (ancestors), with the shortest explaining path."""
    if entity_id not in graph:
        raise KeyError(f"Unknown entity: {entity_id}")
    return {
        source: nx.shortest_path(graph, source, entity_id)
        for source in nx.ancestors(graph, entity_id)
    }


def blast_set(graph: nx.DiGraph, entity_id: str, max_depth: int = 4) -> dict[str, list[str]]:
    """Downstream nodes reachable within ``max_depth`` hops, grouped by entity type.

    Answers the Person-1 acceptance check: removing a node finds all downstream
    departments, workflows and KPIs it affects.
    """
    if entity_id not in graph:
        raise KeyError(f"Unknown entity: {entity_id}")
    reachable = nx.single_source_shortest_path_length(graph, entity_id, cutoff=max_depth)
    out: dict[str, list[str]] = {}
    for node, depth in reachable.items():
        if node == entity_id:
            continue
        kind = graph.nodes[node].get("type", "unknown")
        out.setdefault(kind, []).append(node)
    return out


def list_dependencies(
    twin: Twin,
    entity_id: str,
    direction: Literal["in", "out", "both"],
    max_depth: int = 1,
) -> list[Edge]:
    """Edges within ``max_depth`` hops of ``entity_id`` (plan B-02; schema v2.2.0
    section 7.13). ``direction`` follows edges forward ("out", what it depends
    on downstream), backward ("in", what depends on it), or both.
    """
    graph = build_graph(twin)
    if entity_id not in graph:
        raise KeyError(f"Unknown entity: {entity_id}")

    reachable: set[str] = set()
    if direction in ("out", "both"):
        reachable |= set(nx.single_source_shortest_path_length(graph, entity_id, cutoff=max_depth))
    if direction in ("in", "both"):
        reverse = graph.reverse(copy=False)
        reachable |= set(nx.single_source_shortest_path_length(reverse, entity_id, cutoff=max_depth))

    return [e for e in twin.edges if e.source in reachable and e.target in reachable]


def affected_departments(graph: nx.DiGraph, entity_id: str, max_depth: int = 4) -> set[str]:
    """Departments touched downstream of a change (via each node's department_id)."""
    reachable = nx.single_source_shortest_path_length(graph, entity_id, cutoff=max_depth)
    depts: set[str] = set()
    for node in reachable:
        if node == entity_id:
            continue
        dep = graph.nodes[node].get("department_id")
        if dep:
            depts.add(dep)
        if graph.nodes[node].get("type") == "department":
            depts.add(node)
    return depts


def reachable_departments(twin: Twin, source_entity_ids: list[str], max_hops: int = 4) -> list[str]:
    """Departments reachable within ``max_hops`` of any of ``source_entity_ids`` (schema
    v2.2.0 section 7.13). Used by agent routing: a department is in scope when it owns a
    source entity outright (0 hops) or is touched downstream of one (plan section 8.1).
    """
    graph = build_graph(twin)
    depts: set[str] = set()
    for entity_id in source_entity_ids:
        if entity_id not in graph:
            raise KeyError(f"Unknown entity: {entity_id}")
        own_dept = graph.nodes[entity_id].get("department_id")
        if own_dept:
            depts.add(own_dept)
        if graph.nodes[entity_id].get("type") == "department":
            depts.add(entity_id)
        depts |= affected_departments(graph, entity_id, max_depth=max_hops)
    return sorted(depts)
