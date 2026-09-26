"""Twin cloning and versioning (plan B-04; schema v2.2.0 section 7.13).

Every scenario is an isolated deep copy of the baseline (master plan section 6.4): the
baseline twin must stay byte-equivalent no matter what a scenario clone does to it.
"""

from __future__ import annotations

import hashlib
from typing import NamedTuple

from .models import Criticality, Edge, Relation, Twin, entity_map


def clone(twin: Twin) -> Twin:
    """Deep copy ``twin``. Mutating the result never touches the baseline."""
    return twin.model_copy(deep=True)


class AgentEdgeDefaults(NamedTuple):
    strength: float
    strength_range: tuple[float, float]
    substitutability: float


# Default strength/strength_range/substitutability per relation type for an edge built
# from an agent-validated dependency claim (schema v2.2.0 section 8.5: "any number ...
# never taken from the agent"). An agent never supplies these numbers itself, so this
# starts each relation from a shaped prior instead of one flat 0.5/0.5 placeholder; the
# engine still re-tunes both as more evidence resolves.
AGENT_EDGE_DEFAULTS: dict[Relation, AgentEdgeDefaults] = {
    # Structural/control relations: once established, hard to substitute.
    Relation.OWNS: AgentEdgeDefaults(0.7, (0.55, 0.85), 0.3),
    Relation.CONTROLS: AgentEdgeDefaults(0.7, (0.55, 0.85), 0.3),
    Relation.RUNS: AgentEdgeDefaults(0.7, (0.55, 0.85), 0.3),
    Relation.MAINTAINS: AgentEdgeDefaults(0.7, (0.55, 0.85), 0.3),
    Relation.DEPENDS_ON: AgentEdgeDefaults(0.7, (0.55, 0.85), 0.3),
    # Flow/exchange relations: moderate strength, moderate substitutability.
    Relation.FLOWS_TO: AgentEdgeDefaults(0.6, (0.45, 0.75), 0.4),
    Relation.PROVIDES: AgentEdgeDefaults(0.6, (0.45, 0.75), 0.4),
    Relation.CONSUMES: AgentEdgeDefaults(0.6, (0.45, 0.75), 0.4),
    Relation.CONTRIBUTES_TO: AgentEdgeDefaults(0.6, (0.45, 0.75), 0.4),
    Relation.FUNDS: AgentEdgeDefaults(0.6, (0.45, 0.75), 0.4),
    # Support/knowledge relations: softer, easier to work around.
    Relation.KNOWS: AgentEdgeDefaults(0.5, (0.35, 0.65), 0.5),
    Relation.SUPPORTS: AgentEdgeDefaults(0.5, (0.35, 0.65), 0.5),
    Relation.BACKS_UP: AgentEdgeDefaults(0.5, (0.35, 0.65), 0.5),
    # Named substitution relation: by definition highly substitutable.
    Relation.SUBSTITUTES_FOR: AgentEdgeDefaults(0.5, (0.35, 0.65), 0.9),
}


def _default_agent_edge_id(source: str, target: str, relation: Relation) -> str:
    edge_id = f"e_{source}_{relation.value.lower()}_{target}"
    if len(edge_id) > 80:
        edge_id = "e_agent_" + hashlib.sha256(edge_id.encode()).hexdigest()[:16]
    return edge_id


def edge_from_agent_dependency(
    source: str,
    target: str,
    relation: Relation,
    evidence_refs: list[str],
    confidence: float,
    *,
    edge_id: str | None = None,
    label: str | None = None,
) -> Edge:
    """Build an ``Edge`` from an agent-validated dependency claim (schema section 8.5).

    Uses ``AGENT_EDGE_DEFAULTS`` for strength/strength_range/substitutability instead of
    a flat placeholder. ``criticality`` defaults to medium and ``lag_days`` to 0, matching
    prior agent-merge behavior; the engine re-tunes these as more evidence resolves.
    """
    defaults = AGENT_EDGE_DEFAULTS[relation]
    return Edge(
        id=edge_id or _default_agent_edge_id(source, target, relation),
        source=source,
        target=target,
        relation=relation,
        label=label,
        strength=defaults.strength,
        strength_range=defaults.strength_range,
        substitutability=defaults.substitutability,
        lag_days=0,
        criticality=Criticality.medium,
        confidence=confidence,
        evidence_refs=list(evidence_refs),
        extraction_method="agent",
    )


def _apply_agent_defaults(edge: Edge) -> Edge:
    defaults = AGENT_EDGE_DEFAULTS[edge.relation]
    return edge.model_copy(
        update={
            "strength": defaults.strength,
            "strength_range": defaults.strength_range,
            "substitutability": defaults.substitutability,
        }
    )


def clone_with_edges(twin: Twin, edges: list[Edge], *, agent_proposed: bool = False) -> Twin:
    """Deep copy ``twin`` with ``edges`` appended to the clone's edge list.

    Used to validate a proposed or planted dependency (schema section 7.13): the extra
    edges live only on the clone, so the baseline's ``edges[]`` is unaffected. Every
    edge's strength/strength_range/substitutability is replaced with its
    ``AGENT_EDGE_DEFAULTS`` before it is appended when either ``agent_proposed`` is True
    or the edge already self-identifies as agent-sourced (``extraction_method ==
    "agent"``), so agent edges get relation-specific defaults even when a caller (the
    orchestrator, engine_port) builds the edge itself and never passes the flag.
    """
    scenario = clone(twin)
    prepared = [
        _apply_agent_defaults(e) if agent_proposed or e.extraction_method == "agent" else e
        for e in edges
    ]
    scenario.edges = [*scenario.edges, *(e.model_copy(deep=True) for e in prepared)]
    return scenario


def widen_uncertainty(twin: Twin, department_ids: list[str], delta: float = 0.1) -> Twin:
    """Widen the ``strength_range`` of edges a department owns by ``±delta`` (schema
    v2.2.0 section 8.6): an unavailable agent's department still widens the uncertainty
    band of the edges it is the source of, so missing input visibly increases uncertainty.
    """
    scenario = clone(twin)
    owning_depts = set(department_ids)
    ents = entity_map(scenario)
    for edge in scenario.edges:
        source = ents.get(edge.source)
        if source is None or source.department_id not in owning_depts:
            continue
        low, high = edge.strength_range
        edge.strength_range = (max(0.0, low - delta), min(1.0, high + delta))
    return scenario
