import networkx as nx

from .models import CompanyTwin


def build_graph(twin: CompanyTwin) -> nx.DiGraph:
    graph = nx.DiGraph(company_id=twin.id, version=twin.version)
    for entity in twin.entities:
        graph.add_node(entity.id, **entity.model_dump())
    for dependency in twin.dependencies:
        if dependency.source not in graph or dependency.target not in graph:
            raise ValueError(
                f"Dependency references an unknown entity: "
                f"{dependency.source} -> {dependency.target}"
            )
        graph.add_edge(
            dependency.source,
            dependency.target,
            **dependency.model_dump(exclude={"source", "target"}),
        )
    return graph


def downstream_paths(graph: nx.DiGraph, entity_id: str) -> dict[str, list[str]]:
    if entity_id not in graph:
        raise KeyError(f"Unknown entity: {entity_id}")
    return {
        target: nx.shortest_path(graph, entity_id, target)
        for target in nx.descendants(graph, entity_id)
    }

