import networkx as nx

from .models import Twin


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
