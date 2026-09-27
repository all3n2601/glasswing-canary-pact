"""Workforce knowledge risk (plan C-07, sections 4.2, 11.6, 19.3; schema v2.2.0 sections 5.11, 7.2, 7.15, rule 11).

Everything is role-level: a person token's OWNS, KNOWS, or BACKS_UP edge counts for its role, so
no output names or ranks a person token (plan A5).

**Workflows.** A workflow's qualified owners are the roles with an OWNS or BACKS_UP edge into it
and capacity left. It is stranded when fewer than its minimum remain (rule 11, as ``contracts_py``
enforces). A workflow that had owners has a minimum of at least 1, so losing all qualified owners
strands it even with no configured ``min_qualified_owners`` (plan 11.6). For each reported
workflow ``WorkflowCoverage`` carries the plan 11.6 inputs:

- capable owners (``owners_before`` / ``owners_after``) and independent backups (``backup_count_after``);
- recent execution coverage: the summed strength of the OWNS edges still held (in ``reasons``);
- ``owner_capacity_fte_before`` / ``_after``: owner ``capacity_fte * edge strength``;
- documentation (``documented_pct``) and, reported separately, exception-path documentation
  (``exception_documented_pct``) and automation (``automation_pct``);
- recovery knowledge: supporting knowledge assets that are lost (in ``reasons``);
- ``training_days_required`` (the longest ``time_to_train_days`` of a lost owner) and
  ``replacement_cost_usd`` (their summed ``replacement_cost_usd``), against the workflow's
  criticality and ``max_downtime_days`` (in ``reasons``).

**Knowledge.** A knowledge asset's holders are the roles with a KNOWS edge into it and capacity
left. It is lost when no holder capacity remains and it is less than half documented (schema
7.15). A lost asset adds one ``ownership`` impact to every workflow it SUPPORTS; that impact is not
priced (the propagated capacity loss already is).

Only workflows whose owners or supporting-knowledge holders changed, and knowledge assets whose
holders changed, are reported.

A stranded workflow that is itself documented (``company_twin.documented_workflow_ids``) in a
department whose ``documentation_coverage`` is at least ``DOCUMENTED_DOWNGRADE_AT`` has its harm
severity lowered one level: someone can pick it up from the documents (schema 5.11, CORE).
"""

from __future__ import annotations

from dataclasses import dataclass

from contracts_py.decision import Constraint
from contracts_py.engine import Impact, KnowledgeCoverage, WorkflowCoverage
from contracts_py.enums import (
    ClaimStatus,
    Direction,
    EntityType,
    ImpactCategory,
    ImpactLevel,
    Origin,
    Polarity,
    Relation,
)
from contracts_py.twin import Twin

from company_twin import documented_workflow_ids

from .interventions import Seed, role_of
from .propagation import DELAYED_AFTER_DAYS, constraint_refs, impact_id, severity

OWNER_RELATIONS = {Relation.OWNS, Relation.BACKS_UP}
DOCUMENTED_DOWNGRADE_AT = 0.8
LOST_BELOW_DOCUMENTED = 0.5


@dataclass(frozen=True)
class Holding:
    """One role's hold on a workflow or knowledge asset."""

    relation: Relation
    strength: float
    capacity_fte: float


def _holdings(twin: Twin, relations: set[Relation]) -> dict[str, dict[str, Holding]]:
    """Target ID -> role ID -> strongest holding, for roles with capacity left."""
    ents = {e.id: e for e in twin.entities}
    out: dict[str, dict[str, Holding]] = {}
    for edge in twin.edges:
        if edge.relation not in relations:
            continue
        role_id = role_of(ents.get(edge.source))
        role = ents.get(role_id or "")
        if role is None or (role.capacity_fte is not None and role.capacity_fte <= 0):
            continue
        current = out.setdefault(edge.target, {}).get(role.id)
        # OWNS outranks BACKS_UP; a stronger edge of the same relation wins.
        rank = (edge.relation is Relation.OWNS, edge.strength)
        if current is None or rank > (current.relation is Relation.OWNS, current.strength):
            # A role with no capacity_fte on record counts as one FTE.
            capacity = role.capacity_fte if role.capacity_fte is not None else 1.0
            out[edge.target][role.id] = Holding(edge.relation, edge.strength, capacity)
    return out


def _supports(twin: Twin) -> dict[str, list[str]]:
    """Workflow ID -> the knowledge assets that SUPPORT it."""
    ents = {e.id: e for e in twin.entities}
    out: dict[str, list[str]] = {}
    for edge in twin.edges:
        source, target = ents.get(edge.source), ents.get(edge.target)
        if (edge.relation is Relation.SUPPORTS and source is not None and target is not None
                and source.type is EntityType.knowledge_asset and target.type is EntityType.workflow):
            out.setdefault(target.id, []).append(source.id)
    return {k: sorted(v) for k, v in out.items()}


def _fte(holdings: dict[str, Holding]) -> float:
    return round(sum(h.capacity_fte * h.strength for h in holdings.values()), 6)


def knowledge_coverage(baseline: Twin, scenario: Twin) -> list[KnowledgeCoverage]:
    """Coverage of every knowledge asset whose holders differ between ``baseline`` and ``scenario``."""
    before, after = _holdings(baseline, {Relation.KNOWS}), _holdings(scenario, {Relation.KNOWS})
    dependents: dict[str, list[str]] = {}
    for workflow_id, knowledge_ids in _supports(scenario).items():
        for knowledge_id in knowledge_ids:
            dependents.setdefault(knowledge_id, []).append(workflow_id)
    ents = {e.id: e for e in scenario.entities}
    rows = []
    for kn in sorted((e for e in scenario.entities if e.type is EntityType.knowledge_asset), key=lambda e: e.id):
        held_before, held_after = before.get(kn.id, {}), after.get(kn.id, {})
        if held_before.keys() == held_after.keys():
            continue
        documented = kn.documented_pct or 0.0
        capacity_after = round(sum(h.capacity_fte for h in held_after.values()), 6)
        lost = capacity_after == 0 and documented < LOST_BELOW_DOCUMENTED
        gone = sorted(set(held_before) - set(held_after))
        workflows = sorted(dependents.get(kn.id, []))
        reasons = [f"lost holders {', '.join(gone)}"] if gone else []
        reasons.append(f"{len(held_after)} holders left with {capacity_after:g} FTE; {documented:.0%} documented")
        if lost:
            reasons.append(f"lost: no holder capacity left and less than {LOST_BELOW_DOCUMENTED:.0%} documented")
        for workflow_id in workflows:
            exception = ents[workflow_id].exception_documented_pct
            if exception is not None and exception < documented:
                reasons.append(f"{workflow_id}: its exception path is only {exception:.0%} documented, "
                               f"below the {documented:.0%} ordinary documentation")
        rows.append(KnowledgeCoverage(
            knowledge_id=kn.id, holders_before=sorted(held_before), holders_after=sorted(held_after),
            holder_capacity_fte_before=round(sum(h.capacity_fte for h in held_before.values()), 6),
            holder_capacity_fte_after=capacity_after, documented_pct=documented, lost=lost,
            dependent_workflow_ids=workflows, reasons=reasons,
        ))
    return rows


def workflow_coverage(baseline: Twin, scenario: Twin,
                      knowledge: list[KnowledgeCoverage] | None = None) -> list[WorkflowCoverage]:
    """Coverage of every workflow whose owners, or supporting knowledge holders, changed."""
    before, after = _holdings(baseline, OWNER_RELATIONS), _holdings(scenario, OWNER_RELATIONS)
    knowledge = knowledge if knowledge is not None else knowledge_coverage(baseline, scenario)
    changed_knowledge = {k.knowledge_id: k for k in knowledge}
    supports = _supports(scenario)
    roles = {e.id: e for e in baseline.entities if e.type is EntityType.role}
    rows = []
    for wf in sorted((e for e in scenario.entities if e.type is EntityType.workflow), key=lambda e: e.id):
        owners_before, owners_after = before.get(wf.id, {}), after.get(wf.id, {})
        touched = [k for k in supports.get(wf.id, []) if k in changed_knowledge]
        if owners_before.keys() == owners_after.keys() and not touched:
            continue
        minimum = max(wf.min_qualified_owners or 0, 1 if owners_before else 0)
        gone = sorted(set(owners_before) - set(owners_after))
        stranded = len(owners_after) < minimum
        reasons = [f"lost qualified owners {', '.join(gone)}"] if gone else []
        if stranded:
            reasons.append(f"{len(owners_after)} qualified owners left for a minimum of {minimum}")
        backups = sum(1 for h in owners_after.values() if h.relation is Relation.BACKS_UP)
        execution = [sum(h.strength for h in o.values() if h.relation is Relation.OWNS)
                     for o in (owners_before, owners_after)]
        reasons.append(f"{backups} independent backups left; recent execution coverage {min(1.0, execution[0]):.0%} "
                       f"-> {min(1.0, execution[1]):.0%}")
        documented = wf.documented_pct or 0.0
        exception = wf.exception_documented_pct
        reasons.append(f"{documented:.0%} documented" + (f"; exception path {exception:.0%} documented"
                                                        if exception is not None else "")
                       + (f"; {wf.automation_pct:.0%} automated" if wf.automation_pct is not None else ""))
        lost_knowledge = [k for k in touched if changed_knowledge[k].lost]
        if lost_knowledge:
            reasons.append(f"recovery knowledge lost: {', '.join(lost_knowledge)}")
        training = max((roles[r].time_to_train_days for r in gone if roles[r].time_to_train_days is not None),
                       default=None)
        replacement = sum(roles[r].replacement_cost_usd or 0 for r in gone) if gone else None
        if training is not None:
            downtime = f" against a maximum downtime of {wf.max_downtime_days} days" if wf.max_downtime_days else ""
            reasons.append(f"{wf.criticality.value} workflow: a replacement owner takes {training} days to "
                           f"train{downtime}")
        rows.append(WorkflowCoverage(
            workflow_id=wf.id, criticality=wf.criticality, owners_before=sorted(owners_before),
            owners_after=sorted(owners_after), min_qualified_owners=minimum, backup_count_after=backups,
            documented_pct=documented, stranded=stranded, reasons=reasons,
            owner_capacity_fte_before=_fte(owners_before), owner_capacity_fte_after=_fte(owners_after),
            exception_documented_pct=exception, automation_pct=wf.automation_pct,
            training_days_required=training, replacement_cost_usd=replacement,
        ))
    return rows


def knowledge_impacts(baseline: Twin, knowledge: list[KnowledgeCoverage], losses: dict[str, Seed], *,
                      decision_id: str, scenario_id: str, constraints: list[Constraint]) -> list[Impact]:
    """One ``ownership`` harm on every workflow a lost knowledge asset supports (schema 7.15)."""
    ents = {e.id: e for e in baseline.entities}
    edges = {(e.source, e.target, e.relation): e for e in baseline.edges}
    impacts = []
    for row in knowledge:
        if not row.lost:
            continue
        kn = ents[row.knowledge_id]
        gone = [losses[r] for r in row.holders_before if r in losses]
        day = max((s.start_day for s in gone), default=0)
        source_ref = max(gone, key=lambda s: (s.start_day, s.source_ref)).source_ref if gone else kn.id
        for workflow_id in row.dependent_workflow_ids:
            wf = ents[workflow_id]
            edge = edges[(kn.id, wf.id, Relation.SUPPORTS)]
            magnitude = round(1 - row.documented_pct, 6)
            impacts.append(Impact(
                impact_id=impact_id(workflow_id, "knowledge", kn.id), decision_id=decision_id,
                scenario_id=scenario_id, source_entity=kn.id, source_kind="intervention", source_ref=source_ref,
                affected_entity=wf.id, affected_department=wf.department_id,
                level=ImpactLevel.delayed if day > DELAYED_AFTER_DAYS else ImpactLevel.dependent,
                category=ImpactCategory.ownership, polarity=Polarity.harm, direction=Direction.decrease,
                metric="knowledge_lost", magnitude=magnitude, unit="ratio", severity=severity(wf, magnitude),
                first_effect_day=day, peak_effect_day=day, confidence=edge.confidence,
                dependency_path=[kn.id, wf.id], edge_path=[edge.id],
                evidence_refs=list(dict.fromkeys([*edge.evidence_refs, *kn.evidence_refs])),
                assumptions=[f"{kn.id} is lost: no holder capacity left and {row.documented_pct:.0%} documented"],
                constraint_refs=constraint_refs(wf, constraints), origin=Origin.engine, status=ClaimStatus.computed,
            ))
    return impacts


def downgrade_documented(impacts: list[Impact], coverage: list[WorkflowCoverage], twin: Twin) -> list[Impact]:
    """Lower by one the severity of harm to documented stranded workflows in well-documented departments."""
    ents = {e.id: e for e in twin.entities}
    documented = {p.department_id: p.documentation_coverage for p in twin.department_profiles}
    stranded = {c.workflow_id for c in coverage if c.stranded} & documented_workflow_ids(twin)
    out = []
    for impact in impacts:
        department = ents[impact.affected_entity].department_id
        if (impact.polarity is Polarity.harm and impact.affected_entity in stranded and impact.severity > 1
                and documented.get(department or "", 0.0) >= DOCUMENTED_DOWNGRADE_AT):
            impact = impact.model_copy(update={
                "severity": impact.severity - 1,
                "assumptions": [*impact.assumptions, f"severity lowered one level: {department} documentation "
                                                     f"coverage is at least {DOCUMENTED_DOWNGRADE_AT}"],
            })
        out.append(impact)
    return out
