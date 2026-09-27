"""Intervention operators (plan C-01; schema v2.2.0 section 6.4).

Each ``ActionType`` becomes a graph edit on a scenario clone of the twin, plus the direct
effects the propagation starts from and the money lines it moves. Agents and the UI never edit
edges; they only pick interventions. The baseline twin is never mutated (plan B-04).

Department profiles shape capacity cuts (schema v2.2.0 section 5.11, CORE):

- a department-level ``reduce_capacity`` saves at most ``budget * (1 - fixed_cost_pct)``;
- the capacity a cut removes is ``cut_pct * max(1, utilisation)`` of the cut department (or the
  cut role's department), so cutting an overstretched team hurts more than proportionally.

Mitigations (``kind == mitigation``, plan E-07, sections 4.2, 11.8) are graph edits too. Every action
is applied first, then every mitigation in order, so a mitigation edits the post-action graph; each
one's ``one_time_cost_usd`` is transition cost like an action's. A role "has no capacity left" when
its ``capacity_fte`` is 0 (``remove_roles`` or a full cut); a person token counts for its role (A5).

- ``reassign_owner`` (workflow target, ``new_owner_id`` a role with capacity): train a backup owner.
  Every OWNS or BACKS_UP edge into the workflow from a role with no capacity left, and every KNOWS
  edge from such a role into a knowledge asset that SUPPORTS the workflow, is handed to the new
  owner. The propagation graph holds one edge per entity pair, so the handed-over edges (and any
  the new owner already had into the same entity) merge into one new-owner edge that keeps the
  strongest one's strength, substitutability, lag, criticality and confidence and the union of their
  evidence: OWNS into the workflow, KNOWS into each knowledge asset. The removed roles' loss stops
  flowing through the handed-over edges. With no ownership edge to hand over, the new owner gets an
  OWNS edge of ``params["strength"]`` (default 0.5), substitutability 0.2 and confidence 0.7.
- ``document_runbook`` (workflow or knowledge asset target): raises ``documented_pct`` (and a
  workflow's ``exception_documented_pct``) to at least ``params["documented_pct"]`` (default 0.8);
  a workflow's supporting knowledge-asset edges get at least that substitutability, since
  documented knowledge can be picked up by others.
- ``add_replacement_feed`` (dataset target, ``params["replacement_vendor_id"]`` a vendor the plan
  does not remove): a PROVIDES edge from the replacement vendor with ``params["strength"]`` or the
  strongest current provider's strength, and that provider's substitutability, lag, criticality
  and confidence. ``one_time_cost_usd`` is the migration.

Engine-made edges carry no ``extraction_method`` (the contract's methods describe evidence
extraction) and IDs ``e_{intervention_id}_{n}``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contracts_py.decision import Intervention
from contracts_py.enums import ActionType, EntityType, InterventionKind, MitigationType, Relation
from contracts_py.twin import Edge, Entity, Twin

from company_twin import entity_map

DAYS_PER_YEAR = 365
PERSON_TOKEN_RELATIONS = {Relation.OWNS, Relation.KNOWS, Relation.BACKS_UP}
OWNER_RELATIONS = {Relation.OWNS, Relation.BACKS_UP}
DEFAULT_DOCUMENTED_PCT = 0.8
DEFAULT_NEW_OWNER_STRENGTH = 0.5
NEW_OWNER_SUBSTITUTABILITY = 0.2
# A trained backup owner is planned, not observed, so its new edge is held with moderate confidence.
NEW_OWNER_CONFIDENCE = 0.7


@dataclass(frozen=True)
class Seed:
    """A direct change at an intervention target: ``magnitude`` in [0, 1] from ``start_day``."""

    magnitude: float
    start_day: int
    source_ref: str


@dataclass
class AppliedScenario:
    twin: Twin
    losses: dict[str, Seed] = field(default_factory=dict)
    gains: dict[str, Seed] = field(default_factory=dict)
    gross_savings_usd: int = 0
    transition_cost_usd: int = 0
    # Termination (vendor exit and project cancellation fees) and vendor migration, the parts of
    # transition_cost_usd reported on their own (ValueBreakdown.termination_cost_usd, migration_cost_usd).
    termination_cost_usd: int = 0
    migration_cost_usd: int = 0
    added_cost_usd: int = 0
    rebound_cost_usd: int = 0
    savings_by_intervention: dict[str, int] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)


def scenario_copy(twin: Twin) -> Twin:
    """A scenario clone: fresh entity objects and a fresh edge list over the shared, unmutated rest.

    Operators only reassign scalar entity fields and replace ``twin.edges``, so copying the
    entities shallowly isolates the baseline at a fraction of a deep copy's cost (128 portfolios
    are evaluated per optimize call).
    """
    return twin.model_copy(update={"entities": [e.model_copy() for e in twin.entities], "edges": list(twin.edges)})


def _require(entity: Entity, types: set[EntityType], intervention: Intervention) -> None:
    if entity.type not in types:
        allowed = ", ".join(sorted(t.value for t in types))
        raise ValueError(f"{intervention.id}: {intervention.type} needs a {allowed} target, "
                         f"got {entity.type.value} {entity.id}")


def _seed(bucket: dict[str, Seed], entity_id: str, magnitude: float, start_day: int, source_ref: str) -> None:
    """Two changes to one entity combine like independent losses (noisy-OR)."""
    current = bucket.get(entity_id)
    if current is None:
        bucket[entity_id] = Seed(min(1.0, magnitude), start_day, source_ref)
        return
    combined = 1 - (1 - current.magnitude) * (1 - magnitude)
    keep = current if current.magnitude >= magnitude else Seed(magnitude, start_day, source_ref)
    bucket[entity_id] = Seed(min(1.0, combined), min(current.start_day, start_day), keep.source_ref)


def _scale_roles(roles: list[Entity], factor: float) -> None:
    for role in roles:
        if role.capacity_fte is not None:
            role.capacity_fte = role.capacity_fte * factor
        if role.annual_cost_usd is not None:
            role.annual_cost_usd = round(role.annual_cost_usd * factor)


def _roles_in_scope(twin: Twin, target: Entity) -> list[Entity]:
    if target.type is EntityType.department:
        return [e for e in twin.entities if e.type is EntityType.role and e.department_id == target.id]
    return [target] if target.type is EntityType.role else []


def _remove_vendor(s: AppliedScenario, i: Intervention, target: Entity) -> None:
    _require(target, {EntityType.vendor}, i)
    saved = target.annual_cost_usd or 0
    s.gross_savings_usd += saved
    s.savings_by_intervention[i.id] = saved
    s.termination_cost_usd += target.one_time_exit_cost_usd or 0
    s.migration_cost_usd += target.migration_cost_usd or 0
    s.transition_cost_usd += (target.one_time_exit_cost_usd or 0) + (target.migration_cost_usd or 0)
    target.annual_cost_usd = 0
    _seed(s.losses, target.id, 1.0, i.start_day, i.id)


def _change_capacity(s: AppliedScenario, i: Intervention, target: Entity, sign: int) -> None:
    share = (i.amount_pct or 0) / 100
    roles = _roles_in_scope(s.twin, target)
    # A department cut applies the same percentage to every role in it (schema A5).
    affected = roles if target.type is EntityType.department else [target]
    cost = sum(e.annual_cost_usd or 0 for e in affected)
    moved = round(cost * share)
    _scale_roles(roles, 1 + sign * share)
    if target.type is not EntityType.role and target.type is not EntityType.department and target.annual_cost_usd:
        target.annual_cost_usd = round(target.annual_cost_usd * (1 + sign * share))
    if sign < 0:
        profiles = {p.department_id: p for p in s.twin.department_profiles}
        department_id = target.id if target.type is EntityType.department else target.department_id
        profile = profiles.get(department_id or "")
        if profile is not None and target.type is EntityType.department:
            cap = round(profile.budget.annual_budget_usd * (1 - profile.budget.fixed_cost_pct))
            if moved > cap:
                s.assumptions.append(f"{i.id}: savings capped at ${cap:,} by {department_id} fixed_cost_pct "
                                     f"{profile.budget.fixed_cost_pct}")
                moved = cap
        utilisation = max(1.0, profile.staffing.utilisation) if profile is not None else 1.0
        s.gross_savings_usd += moved
        s.savings_by_intervention[i.id] = moved
        for entity in affected:
            _seed(s.losses, entity.id, min(1.0, share * utilisation), i.start_day, i.id)
    else:
        s.added_cost_usd += moved
        for entity in affected:
            _seed(s.gains, entity.id, share, i.start_day, i.id)


def _remove_roles(s: AppliedScenario, i: Intervention, target: Entity) -> None:
    _require(target, {EntityType.role}, i)
    saved = target.annual_cost_usd or 0
    s.gross_savings_usd += saved
    s.savings_by_intervention[i.id] = saved
    target.capacity_fte = 0.0
    target.annual_cost_usd = 0
    tokens = {e.id for e in s.twin.entities if e.type is EntityType.person_token and e.role_id == target.id}
    s.twin.edges = [e for e in s.twin.edges if not (e.source in tokens and e.relation in PERSON_TOKEN_RELATIONS)]
    for token in s.twin.entities:
        if token.id in tokens:
            token.capacity_fte = 0.0
    _seed(s.losses, target.id, 1.0, i.start_day, i.id)


def _retired_run_cost(s: AppliedScenario, project: Entity, days: int) -> int:
    ents = entity_map(s.twin)
    annual = sum(ents[r].annual_cost_usd or 0 for r in project.retires_entity_ids if r in ents)
    return round(annual * days / DAYS_PER_YEAR)


def _stop_project(s: AppliedScenario, i: Intervention, target: Entity, horizon_days: int) -> None:
    _require(target, {EntityType.project}, i)
    saved = target.remaining_cost_usd or 0
    s.gross_savings_usd += saved
    s.savings_by_intervention[i.id] = saved
    s.transition_cost_usd += target.one_time_exit_cost_usd or 0
    s.termination_cost_usd += target.one_time_exit_cost_usd or 0
    # What the project would have retired keeps running to the horizon (rebound).
    retire_day = target.expected_completion_day if target.expected_completion_day is not None else horizon_days
    s.rebound_cost_usd += _retired_run_cost(s, target, max(0, horizon_days - max(retire_day, i.start_day)))
    target.remaining_cost_usd = 0
    _seed(s.losses, target.id, 1.0, i.start_day, i.id)


def _start_or_invest(s: AppliedScenario, i: Intervention, target: Entity) -> None:
    if i.type is ActionType.start_project:
        _require(target, {EntityType.project}, i)
    s.added_cost_usd += i.amount_usd or 0
    lag = (target.expected_completion_day or 0) if i.type is ActionType.start_project else 0
    if i.amount_pct is not None:
        gain = i.amount_pct / 100
    elif i.type is ActionType.start_project:
        gain = 1.0
    else:
        gain = 0.0
        s.assumptions.append(f"{i.id}: no amount_pct given, so the investment adds cost but no modelled capacity")
    if gain > 0:
        _seed(s.gains, target.id, gain, i.start_day + lag, i.id)


def _delay_project(s: AppliedScenario, i: Intervention, target: Entity) -> None:
    _require(target, {EntityType.project}, i)
    days = i.duration_days or 0
    # The retirement it would deliver slips by the delay, so the retired entities run longer.
    s.rebound_cost_usd += _retired_run_cost(s, target, days)
    if target.expected_completion_day is not None:
        target.expected_completion_day += days


def role_of(entity: Entity | None) -> str | None:
    """The role an OWNS, KNOWS or BACKS_UP edge counts for: a role itself, or a person token's role (A5)."""
    if entity is None:
        return None
    if entity.type is EntityType.role:
        return entity.id
    if entity.type is EntityType.person_token:
        return entity.role_id
    return None


def _no_capacity(ents: dict[str, Entity], source_id: str) -> bool:
    role = ents.get(role_of(ents.get(source_id)) or "")
    return role is not None and role.capacity_fte is not None and role.capacity_fte <= 0


def _edge_id(i: Intervention, n: int) -> str:
    from .simulate import bounded_id  # simulate imports this module (through quick), so import on use

    return bounded_id("e_", f"{i.id}_{n}")


def _hand_over(s: AppliedScenario, i: Intervention, edges: list[Edge], new_owner: str, target: str,
               relation: Relation, n: int) -> None:
    """Merge ``edges`` and the new owner's own edges into ``target`` into one ``relation`` edge from the new owner."""
    own = [e for e in s.twin.edges
           if e.source == new_owner and e.target == target and e.relation in PERSON_TOKEN_RELATIONS]
    merged = [*edges, *own]
    gone = {e.id for e in merged}
    strongest = max(merged, key=lambda e: (e.strength, e.id))
    s.twin.edges = [e for e in s.twin.edges if e.id not in gone]
    s.twin.edges.append(strongest.model_copy(update={
        "id": _edge_id(i, n), "source": new_owner, "relation": relation, "extraction_method": None,
        "evidence_refs": list(dict.fromkeys(ref for e in merged for ref in e.evidence_refs)),
    }))


def _reassign_owner(s: AppliedScenario, i: Intervention, target: Entity) -> None:
    _require(target, {EntityType.workflow}, i)
    ents = entity_map(s.twin)
    owner = ents.get(i.new_owner_id or "")
    if owner is None or owner.type is not EntityType.role:
        raise ValueError(f"{i.id}: reassign_owner needs new_owner_id to be a role in the twin, got {i.new_owner_id}")
    if owner.capacity_fte is not None and owner.capacity_fte <= 0:
        raise ValueError(f"{i.id}: new owner {owner.id} has no capacity left in this scenario")
    handed = [e for e in s.twin.edges
              if e.target == target.id and e.relation in OWNER_RELATIONS and _no_capacity(ents, e.source)]
    n = 1
    if handed:
        _hand_over(s, i, handed, owner.id, target.id, Relation.OWNS, n)
        n += 1
    supporting = sorted(e.source for e in s.twin.edges if e.target == target.id and e.relation is Relation.SUPPORTS
                        and ents[e.source].type is EntityType.knowledge_asset)
    transferred = []
    for knowledge_id in supporting:
        knows = [e for e in s.twin.edges
                 if e.target == knowledge_id and e.relation is Relation.KNOWS and _no_capacity(ents, e.source)]
        if knows:
            _hand_over(s, i, knows, owner.id, knowledge_id, Relation.KNOWS, n)
            n += 1
            transferred.append(knowledge_id)
    owns_already = any(e.source == owner.id and e.target == target.id and e.relation in OWNER_RELATIONS
                       for e in s.twin.edges)
    strength = float(i.params.get("strength", DEFAULT_NEW_OWNER_STRENGTH))
    if not handed and not owns_already:
        s.twin.edges.append(Edge(
            id=_edge_id(i, n), source=owner.id, target=target.id, relation=Relation.OWNS, strength=strength,
            substitutability=NEW_OWNER_SUBSTITUTABILITY, lag_days=0, criticality=target.criticality,
            confidence=NEW_OWNER_CONFIDENCE,
        ))
    sources = sorted({role_of(ents.get(e.source)) or e.source for e in handed})
    if handed:
        what = f"takes over {target.id} from {', '.join(sources)}"
    elif owns_already:
        what = f"already owns {target.id}, so no ownership edge is added"
    else:
        what = (f"gets an OWNS edge into {target.id} of strength {strength:g}, substitutability "
                f"{NEW_OWNER_SUBSTITUTABILITY:g} and confidence {NEW_OWNER_CONFIDENCE:g}")
    s.assumptions.append(f"{i.id}: reassign_owner trains {owner.id} as a backup owner, who {what}"
                         + (f"; knowledge transferred: {', '.join(transferred)}" if transferred else "")
                         + "; engine-made edges carry no extraction_method")


def _document_runbook(s: AppliedScenario, i: Intervention, target: Entity) -> None:
    _require(target, {EntityType.workflow, EntityType.knowledge_asset}, i)
    level = float(i.params.get("documented_pct", DEFAULT_DOCUMENTED_PCT))
    target.documented_pct = max(target.documented_pct or 0.0, level)
    detail = ""
    if target.type is EntityType.workflow:
        target.exception_documented_pct = max(target.exception_documented_pct or 0.0, level)
        ents = entity_map(s.twin)
        s.twin.edges = [
            e.model_copy(update={"substitutability": max(e.substitutability, level)})
            if (e.target == target.id and e.relation is Relation.SUPPORTS
                and ents[e.source].type is EntityType.knowledge_asset) else e
            for e in s.twin.edges
        ]
        detail = ", exception path included, and its supporting knowledge edges are at least that substitutable"
    s.assumptions.append(f"{i.id}: document_runbook documents {target.id} to at least {level:.0%}{detail}"
                         + ("" if "documented_pct" in i.params else " (the default level)"))


def _add_replacement_feed(s: AppliedScenario, i: Intervention, target: Entity) -> None:
    _require(target, {EntityType.dataset}, i)
    ents = entity_map(s.twin)
    vendor_id = i.params.get("replacement_vendor_id")
    vendor = ents.get(vendor_id) if isinstance(vendor_id, str) else None
    if vendor is None or vendor.type is not EntityType.vendor:
        raise ValueError(f"{i.id}: add_replacement_feed needs params.replacement_vendor_id to be a vendor in the "
                         f"twin, got {vendor_id}")
    if vendor.id in s.losses:
        raise ValueError(f"{i.id}: replacement vendor {vendor.id} is itself removed or cut by the plan")
    providers = [e for e in s.twin.edges if e.target == target.id and e.relation is Relation.PROVIDES]
    if any(e.source == vendor.id for e in providers):
        raise ValueError(f"{i.id}: {vendor.id} already provides {target.id}")
    if not providers:
        raise ValueError(f"{i.id}: {target.id} has no provider to replace")
    template = max(providers, key=lambda e: (e.strength, e.id))
    strength = float(i.params.get("strength") or template.strength)
    s.twin.edges.append(Edge(
        id=_edge_id(i, 1), source=vendor.id, target=target.id, relation=Relation.PROVIDES, strength=strength,
        substitutability=template.substitutability, lag_days=template.lag_days, criticality=template.criticality,
        confidence=template.confidence,
    ))
    s.migration_cost_usd += i.one_time_cost_usd
    s.assumptions.append(f"{i.id}: add_replacement_feed has {vendor.id} provide {target.id} at strength {strength:g} "
                         f"with {template.source}'s substitutability {template.substitutability:g}; the "
                         f"${i.one_time_cost_usd:,} one-time cost is the migration; the planned feed has no evidence "
                         "yet and, as an engine-made edge, no extraction_method")


def apply_interventions(twin: Twin, interventions: list[Intervention], *, horizon_days: int = DAYS_PER_YEAR,
                        ) -> AppliedScenario:
    """Apply ``interventions`` to a fresh clone of ``twin`` and return the clone with its direct effects.

    Every action is applied first, in order, then every mitigation, in order, on the post-action graph.
    """
    scenario = AppliedScenario(twin=scenario_copy(twin))
    ents = entity_map(scenario.twin)
    ordered = ([i for i in interventions if i.kind is InterventionKind.action]
               + [i for i in interventions if i.kind is InterventionKind.mitigation])
    for i in ordered:
        target = ents.get(i.target_entity_id)
        if target is None:
            raise ValueError(f"{i.id}: unknown target entity {i.target_entity_id}")
        scenario.transition_cost_usd += i.one_time_cost_usd
        match i.type:
            case ActionType.assess_change:
                scenario.assumptions.append(f"{i.id}: assess_change makes no graph edit")
            case ActionType.remove_vendor:
                _remove_vendor(scenario, i, target)
            case ActionType.reduce_capacity:
                _change_capacity(scenario, i, target, -1)
            case ActionType.add_capacity:
                _change_capacity(scenario, i, target, +1)
            case ActionType.remove_roles:
                _remove_roles(scenario, i, target)
            case ActionType.stop_project:
                _stop_project(scenario, i, target, horizon_days)
            case ActionType.start_project | ActionType.invest:
                _start_or_invest(scenario, i, target)
            case ActionType.delay_project:
                _delay_project(scenario, i, target)
            case MitigationType.reassign_owner:
                _reassign_owner(scenario, i, target)
            case MitigationType.document_runbook:
                _document_runbook(scenario, i, target)
            case MitigationType.add_replacement_feed:
                _add_replacement_feed(scenario, i, target)
            case _:
                raise ValueError(f"{i.id}: {i.type} is not modelled yet")
    return scenario
