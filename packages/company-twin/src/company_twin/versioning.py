"""Twin cloning and versioning (plan B-04; schema v2.2.0 section 7.13).

Every scenario is an isolated deep copy of the baseline (master plan section 6.4): the
baseline twin must stay byte-equivalent no matter what a scenario clone does to it.
"""

from __future__ import annotations

from .models import Edge, Twin, entity_map


def clone(twin: Twin) -> Twin:
    """Deep copy ``twin``. Mutating the result never touches the baseline."""
    return twin.model_copy(deep=True)


def clone_with_edges(twin: Twin, edges: list[Edge]) -> Twin:
    """Deep copy ``twin`` with ``edges`` appended to the clone's edge list.

    Used to validate a proposed or planted dependency (schema section 7.13): the extra
    edges live only on the clone, so the baseline's ``edges[]`` is unaffected.
    """
    scenario = clone(twin)
    scenario.edges = [*scenario.edges, *(e.model_copy(deep=True) for e in edges)]
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
