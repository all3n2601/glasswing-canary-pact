"""Intervention operators (plan C-01; schema v2.2.0 section 6.4).

Each ``ActionType`` becomes a graph edit on a scenario clone of the twin, plus the direct
effects the propagation starts from and the money lines it moves. Agents and the UI never edit
edges; they only pick interventions. The baseline twin is never mutated (plan B-04).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contracts_py.decision import Intervention
from contracts_py.enums import ActionType, EntityType, InterventionKind, Relation
from contracts_py.twin import Entity, Twin

from company_twin import clone, entity_map

DAYS_PER_YEAR = 365
PERSON_TOKEN_RELATIONS = {Relation.OWNS, Relation.KNOWS, Relation.BACKS_UP}


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
    added_cost_usd: int = 0
    rebound_cost_usd: int = 0
    savings_by_intervention: dict[str, int] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)


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
        s.gross_savings_usd += moved
        s.savings_by_intervention[i.id] = moved
        for entity in affected:
            _seed(s.losses, entity.id, share, i.start_day, i.id)
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


def apply_interventions(twin: Twin, interventions: list[Intervention], *, horizon_days: int = DAYS_PER_YEAR,
                        ) -> AppliedScenario:
    """Apply ``interventions`` to a fresh clone of ``twin`` and return the clone with its direct effects.

    Mitigations (``kind == mitigation``) are re-simulated by ``mitigate`` (plan E-07) and are rejected here.
    """
    scenario = AppliedScenario(twin=clone(twin))
    ents = entity_map(scenario.twin)
    for i in interventions:
        if i.kind is InterventionKind.mitigation:
            raise ValueError(f"{i.id}: mitigation {i.type} is applied by mitigate (plan E-07), not as an action")
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
    return scenario
