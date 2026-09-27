"""Workflow ownership coverage (plan section 11.6; schema v2.2.0 sections 5.11, 7.2, rule 11).

A workflow's qualified owners are the roles with an OWNS or BACKS_UP edge into it and capacity
left. It is stranded when fewer than ``min_qualified_owners`` remain (rule 11, as
``contracts_py`` enforces). Only workflows whose owners changed are reported.

A stranded workflow that is itself documented (``company_twin.documented_workflow_ids``: a
current runbook or SOP, with its supporting knowledge written down) in a department whose
``documentation_coverage`` is at least ``DOCUMENTED_DOWNGRADE_AT`` has its harm severity lowered
one level: someone can pick it up from the documents (schema 5.11, CORE).
"""

from __future__ import annotations

from contracts_py.engine import Impact, WorkflowCoverage
from contracts_py.enums import EntityType, Polarity, Relation
from contracts_py.twin import Twin

from company_twin import documented_workflow_ids

OWNER_RELATIONS = {Relation.OWNS, Relation.BACKS_UP}
DOCUMENTED_DOWNGRADE_AT = 0.8


def _owners(twin: Twin) -> dict[str, dict[str, Relation]]:
    ents = {e.id: e for e in twin.entities}
    owners: dict[str, dict[str, Relation]] = {}
    for edge in twin.edges:
        role = ents.get(edge.source)
        if edge.relation in OWNER_RELATIONS and role is not None and role.type is EntityType.role:
            if role.capacity_fte is None or role.capacity_fte > 0:
                owners.setdefault(edge.target, {})[role.id] = edge.relation
    return owners


def workflow_coverage(baseline: Twin, scenario: Twin) -> list[WorkflowCoverage]:
    """Coverage of every workflow whose qualified owners differ between ``baseline`` and ``scenario``."""
    before, after = _owners(baseline), _owners(scenario)
    rows = []
    for wf in sorted((e for e in scenario.entities if e.type is EntityType.workflow), key=lambda e: e.id):
        owners_before, owners_after = before.get(wf.id, {}), after.get(wf.id, {})
        if owners_before.keys() == owners_after.keys():
            continue
        minimum = wf.min_qualified_owners or 0
        lost = sorted(set(owners_before) - set(owners_after))
        stranded = len(owners_after) < minimum
        reasons = [f"lost qualified owners {', '.join(lost)}"] if lost else []
        if stranded:
            reasons.append(f"{len(owners_after)} qualified owners left for a minimum of {minimum}")
        rows.append(WorkflowCoverage(
            workflow_id=wf.id, criticality=wf.criticality, owners_before=sorted(owners_before),
            owners_after=sorted(owners_after), min_qualified_owners=minimum,
            backup_count_after=sum(1 for r in owners_after.values() if r is Relation.BACKS_UP),
            documented_pct=wf.documented_pct or 0.0, stranded=stranded, reasons=reasons,
            exception_documented_pct=wf.exception_documented_pct, automation_pct=wf.automation_pct,
        ))
    return rows


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
