"""Dependency propagation and the impact ledger (plan C-03, section 11.3; schema v2.2.0 sections 5.4, 5.9, 7.1).

A direct change at an intervention target travels along outgoing edges. Each edge transfers
``strength * (1 - substitutability)`` of its source's change, and independent upstream changes
merge with noisy-OR::

    loss(target) = 1 - (1 - seed(target)) * product(1 - loss(source) * transfer(edge))

A dataset is special: removing one of its providers harms it only by the share of coverage no
remaining provider supplies. With provider coverage ``s`` and substitutability ``u``::

    coverage = 1 - product(1 - s * (1 - loss(provider) * (1 - u)))
    loss(dataset) = 1 - coverage_after / coverage_before

Only entities within ``settings.propagation_max_hops`` of a change can be affected, a change
below ``settings.min_impact_threshold`` neither propagates nor is reported, and loops (the
department channels in schema 5.9) are iterated to a fixed point. Each affected entity keeps its
strongest explanatory path, from which its timing, confidence, and evidence come.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache

import networkx as nx
from contracts_py.decision import Constraint
from contracts_py.engine import Impact
from contracts_py.enums import (
    ClaimStatus,
    Criticality,
    Direction,
    EntityType,
    ImpactCategory,
    ImpactLevel,
    Origin,
    Polarity,
    Relation,
)
from contracts_py.twin import Entity, OrganizationSettings, Twin

from .interventions import Seed

MAX_ITERATIONS = 10
CONVERGENCE_TOLERANCE = 0.001
DELAYED_AFTER_DAYS = 90
MAX_ID_LENGTH = 80  # contracts_py.common.ID

CATEGORY_OF: dict[EntityType, ImpactCategory] = {
    EntityType.person_token: ImpactCategory.ownership,
    EntityType.role: ImpactCategory.ownership,
    EntityType.knowledge_asset: ImpactCategory.ownership,
    EntityType.system: ImpactCategory.technical,
    EntityType.vendor: ImpactCategory.technical,
    EntityType.dataset: ImpactCategory.technical,
    EntityType.workflow: ImpactCategory.operational,
    EntityType.project: ImpactCategory.operational,
    EntityType.kpi: ImpactCategory.business,
    EntityType.customer_segment: ImpactCategory.business,
    EntityType.control: ImpactCategory.compliance,
    EntityType.department: ImpactCategory.operational,
}

CRITICALITY_WEIGHT = {Criticality.low: 0.25, Criticality.medium: 0.5, Criticality.high: 0.75, Criticality.critical: 1.0}


@dataclass(frozen=True)
class Effect:
    entity_id: str
    magnitude: float
    source_ref: str
    dependency_path: list[str]
    edge_path: list[str]
    first_effect_day: int
    peak_effect_day: int
    confidence: float
    evidence_refs: list[str]
    feedback: bool

    @property
    def hops(self) -> int:
        return len(self.edge_path)


@dataclass(frozen=True)
class Propagation:
    effects: dict[str, Effect]
    iterations: int
    converged: bool


NodeKey = tuple[str, EntityType, tuple[str, ...]]
EdgeKey = tuple[str, str, str, Relation, float, float, int, float, tuple[str, ...]]


def _graph(twin: Twin) -> nx.DiGraph:
    """The dependency graph propagation walks, shared by scenario clones with the same structure.

    Propagation reads only each node's type and evidence and each edge's transfer, timing and
    evidence fields, so the graph is keyed on those values: the 128 portfolios of one optimize
    call differ only in their seeds and reuse one graph instead of rebuilding it every time.
    """
    nodes = tuple((e.id, e.type, tuple(e.evidence_refs)) for e in twin.entities)
    edges = tuple((e.source, e.target, e.id, e.relation, e.strength, e.substitutability, e.lag_days, e.confidence,
                   tuple(e.evidence_refs)) for e in twin.edges)
    return _cached_graph(nodes, edges)


@lru_cache(maxsize=32)
def _cached_graph(nodes: tuple[NodeKey, ...], edges: tuple[EdgeKey, ...]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for entity_id, entity_type, evidence_refs in nodes:
        graph.add_node(entity_id, type=entity_type, evidence_refs=evidence_refs)
    for source, target, edge_id, relation, strength, substitutability, lag_days, confidence, evidence_refs in edges:
        if source not in graph or target not in graph:
            raise ValueError(f"Edge references an unknown entity: {source} -> {target}")
        graph.add_edge(source, target, id=edge_id, relation=relation, strength=strength,
                       substitutability=substitutability, lag_days=lag_days, confidence=confidence,
                       evidence_refs=evidence_refs)
    return graph


def _transfer(data: dict) -> float:
    return data["strength"] * (1 - data["substitutability"])


def _in_scope(graph: nx.DiGraph, seeds: dict[str, Seed], max_hops: int) -> set[str]:
    scope: set[str] = set()
    for entity_id in seeds:
        scope |= set(nx.single_source_shortest_path_length(graph, entity_id, cutoff=max_hops))
    return scope


def _provider_loss(graph: nx.DiGraph, node: str, loss: dict[str, float], threshold: float) -> float:
    before = after = 1.0
    for source, _, data in graph.in_edges(node, data=True):
        if data["relation"] is not Relation.PROVIDES:
            continue
        s, u = data["strength"], data["substitutability"]
        lost = loss.get(source, 0.0)
        lost = lost if lost >= threshold else 0.0
        before *= 1 - s
        after *= 1 - s * (1 - lost * (1 - u))
    covered_before = 1 - before
    return 0.0 if covered_before <= 0 else max(0.0, 1 - (1 - after) / covered_before)


def _is_dataset(graph: nx.DiGraph, node: str) -> bool:
    return graph.nodes[node]["type"] is EntityType.dataset


def _fixed_point(graph: nx.DiGraph, seeds: dict[str, Seed], scope: list[str], threshold: float,
                 coverage_share: bool) -> tuple[dict[str, float], int, bool]:
    loss = {n: seeds[n].magnitude if n in seeds else 0.0 for n in scope}
    for iteration in range(1, MAX_ITERATIONS + 1):
        new: dict[str, float] = {}
        for node in scope:
            keep = 1 - (seeds[node].magnitude if node in seeds else 0.0)
            shared = coverage_share and _is_dataset(graph, node)
            if shared:
                keep *= 1 - _provider_loss(graph, node, loss, threshold)
            for source, _, data in graph.in_edges(node, data=True):
                if shared and data["relation"] is Relation.PROVIDES:
                    continue
                upstream = loss.get(source, 0.0)
                if upstream >= threshold:
                    keep *= 1 - upstream * _transfer(data)
            new[node] = min(1.0, max(0.0, 1 - keep))
        change = max((abs(new[n] - loss[n]) for n in scope), default=0.0)
        loss = new
        if change < CONVERGENCE_TOLERANCE:
            return loss, iteration, True
    return loss, MAX_ITERATIONS, False


def _strongest_paths(graph: nx.DiGraph, seeds: dict[str, Seed], scope: set[str], max_hops: int,
                     ) -> dict[str, tuple[float, list[str], list[str]]]:
    """Best (score, entity path, edge path) per node with at most ``max_hops`` edges, from any seed."""
    best = {n: (seed.magnitude, [n], []) for n, seed in sorted(seeds.items())}
    edges = sorted(((u, v, d) for u, v, d in graph.edges(data=True) if u in scope and v in scope),
                   key=lambda e: e[2]["id"])
    for _ in range(max_hops):
        updated = dict(best)
        for u, v, data in edges:
            if u not in best or v in seeds:
                continue
            score, path, edge_path = best[u]
            if v in path:
                continue
            candidate = score * _transfer(data)
            if candidate > updated.get(v, (0.0,))[0]:
                updated[v] = (candidate, [*path, v], [*edge_path, data["id"]])
        if updated == best:
            break
        best = updated
    return best


def propagate(twin: Twin, seeds: dict[str, Seed], *, settings: OrganizationSettings | None = None,
              coverage_share: bool = True) -> Propagation:
    """Propagate direct changes ``seeds`` through ``twin`` (a scenario clone) to a fixed point."""
    settings = settings or OrganizationSettings()
    threshold, max_hops = settings.min_impact_threshold, settings.propagation_max_hops
    graph = _graph(twin)
    unknown = sorted(set(seeds) - set(graph))
    if unknown:
        raise KeyError(f"seeds reference unknown entities: {unknown}")
    scope = _in_scope(graph, seeds, max_hops)
    loss, iterations, converged = _fixed_point(graph, seeds, sorted(scope), threshold, coverage_share)
    paths = _strongest_paths(graph, seeds, scope, max_hops)

    affected = {n for n, value in loss.items() if value >= threshold and n in paths}
    first_day: dict[str, int] = {}
    for node in affected:
        _, path, edge_path = paths[node]
        lag = sum(graph.edges[path[i], path[i + 1]]["lag_days"] for i in range(len(edge_path)))
        first_day[node] = seeds[path[0]].start_day + lag

    effects: dict[str, Effect] = {}
    for node in sorted(affected):
        _, path, edge_path = paths[node]
        data = [graph.edges[path[i], path[i + 1]] for i in range(len(edge_path))]
        contributing = [(u, d) for u, _, d in graph.in_edges(node, data=True) if u in affected]
        peak = max([first_day[node], *(first_day[u] + d["lag_days"] for u, d in contributing)])
        feedback = node not in seeds and any(
            node in paths[u][1] and loss[u] * _transfer(d) >= threshold for u, d in contributing
        )
        confidence = 1.0
        evidence: list[str] = []
        for d in data:
            confidence *= d["confidence"]
            evidence += [ref for ref in d["evidence_refs"] if ref not in evidence]
        if not data:
            evidence = list(graph.nodes[node]["evidence_refs"])
        effects[node] = Effect(
            entity_id=node, magnitude=round(loss[node], 6), source_ref=seeds[path[0]].source_ref,
            dependency_path=path, edge_path=edge_path, first_effect_day=first_day[node], peak_effect_day=peak,
            confidence=round(confidence, 6), evidence_refs=evidence, feedback=feedback,
        )
    return Propagation(effects=effects, iterations=iterations, converged=converged)


def impact_level(effect: Effect) -> ImpactLevel:
    if effect.feedback:
        return ImpactLevel.feedback
    if effect.first_effect_day > DELAYED_AFTER_DAYS:
        return ImpactLevel.delayed
    if effect.hops == 0:
        return ImpactLevel.direct
    return ImpactLevel.dependent if effect.hops == 1 else ImpactLevel.second_order


def severity(entity: Entity, magnitude: float) -> int:
    """1-5 from how much of the entity is lost and how critical it is."""
    return max(1, min(5, 1 + round(4 * magnitude * CRITICALITY_WEIGHT[entity.criticality])))


def constraint_refs(entity: Entity, constraints: list[Constraint]) -> list[str]:
    """Constraints a harm to ``entity`` pushes on, by the metric each constraint measures."""
    refs = []
    for c in constraints:
        match c.metric:
            case "compliance_controls_broken":
                hit = entity.type is EntityType.control and bool(entity.mandatory)
            case "revenue_impact_pct":
                hit = entity.id == c.scope_entity_id if c.scope_entity_id else entity.type is EntityType.kpi
            case "customer_impact_pct":
                hit = entity.type is EntityType.customer_segment or bool(entity.customer_facing)
            case "stranded_workflows":
                hit = entity.type is EntityType.workflow
            case "critical_systems_degraded":
                hit = entity.type is EntityType.system and entity.criticality is Criticality.critical
            case "max_capacity_loss_pct":
                hit = entity.type in (EntityType.role, EntityType.department)
            case "critical_coverage_pct":
                hit = entity.type is EntityType.dataset and entity.criticality is Criticality.critical
            case _:
                hit = False
        if hit:
            refs.append(c.id)
    return refs


def bounded_id(prefix: str, body: str) -> str:
    """``prefix + body``, or ``prefix`` plus a hash of ``body`` when that would pass the contract's 80-character limit.

    Every engine-created ID goes through here; agent_orchestration keeps an identical copy (pinned by tests), so the
    engine and the orchestrator name a scenario alike.
    """
    candidate = prefix + body
    if len(candidate) <= MAX_ID_LENGTH:
        return candidate
    return prefix + hashlib.sha256(body.encode()).hexdigest()[:24]


def impact_id(*parts: str) -> str:
    return bounded_id("imp_", "_".join(parts))


def impact_ledger(twin: Twin, propagation: Propagation, *, decision_id: str, scenario_id: str, polarity: Polarity,
                  constraints: list[Constraint], horizon_days: int) -> list[Impact]:
    """One engine ``Impact`` per affected entity whose first effect lands inside the horizon."""
    ents = {e.id: e for e in twin.entities}
    harm = polarity is Polarity.harm
    impacts = []
    for effect in propagation.effects.values():
        if effect.first_effect_day > horizon_days:
            continue
        entity = ents[effect.entity_id]
        department = entity.id if entity.type is EntityType.department else entity.department_id
        impacts.append(Impact(
            impact_id=impact_id(effect.entity_id, "loss" if harm else "gain"),
            decision_id=decision_id, scenario_id=scenario_id,
            source_entity=effect.dependency_path[0], source_kind="intervention", source_ref=effect.source_ref,
            affected_entity=effect.entity_id, affected_department=department, level=impact_level(effect),
            category=CATEGORY_OF[entity.type], polarity=polarity,
            direction=Direction.decrease if harm else Direction.increase,
            metric="capacity_loss" if harm else "capacity_gain", magnitude=effect.magnitude, unit="ratio",
            severity=severity(entity, effect.magnitude) if harm else 1,
            first_effect_day=effect.first_effect_day, peak_effect_day=effect.peak_effect_day,
            confidence=effect.confidence, dependency_path=effect.dependency_path, edge_path=effect.edge_path,
            evidence_refs=effect.evidence_refs, constraint_refs=constraint_refs(entity, constraints) if harm else [],
            origin=Origin.engine, status=ClaimStatus.computed,
        ))
    return impacts
