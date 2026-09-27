"""Blast radius: the drawable graph of one simulation result (plan section 13.4; schema v2.2.0 section 7.10, rule 14).

- The root is a ``decision`` node for the plan (``plan_id``, or the scenario when there is none);
  the inaction root is labelled "Do nothing".
- Every baseline pressure with an expected cost is a ``pressure`` node on the root's first ring
  ("Pressure" edges), feeding the entity it acts on.
- Every affected entity is one node: ``department`` for a department entity, ``entity`` otherwise.
  Its headline, level, severity, and money come from its impacts (harm first, then benefit).
- Each impact adds one edge from the nearest node on its dependency path (the root for the
  intervention target) to its affected entity, labelled by the impact:
  a harm naming a failed hard constraint is a "Critical constraint"; harm to a KPI or customer
  segment is a "Revenue effect"; otherwise "Direct impact" for direct impacts, "Indirect impact"
  for dependent ones, and "Second-order risk" for second-order, delayed, or feedback ones.
- KPI and customer-segment nodes feed the ``outcome`` node, which carries the net value.
- Departments are summarised by their harm (or, with none, their benefit) impacts.

Every edge references existing nodes (rule 14).
"""

from __future__ import annotations

from contracts_py.engine import (
    BlastEdge,
    BlastNode,
    BlastRadius,
    CompanyOutcome,
    DepartmentImpactSummary,
    Impact,
    SimulationResult,
)
from contracts_py.enums import EntityType, ImpactLevel, Polarity
from contracts_py.twin import Twin

OUTCOME_NODE_ID = "outcome_company"
REVENUE_TYPES = {EntityType.kpi, EntityType.customer_segment}
LEVEL_LABEL = {ImpactLevel.direct: "Direct impact", ImpactLevel.dependent: "Indirect impact"}


def money(usd: int) -> str:
    sign, usd = ("-" if usd < 0 else ""), abs(usd)
    for scale, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if usd >= scale:
            return f"{sign}${f'{usd / scale:,.2f}'.rstrip('0').rstrip('.')}{suffix}"
    return f"{sign}${usd:,}"


def _impact_headline(impact: Impact, name: str) -> str:
    if impact.source_kind == "pressure":
        return f"{name}: {money(impact.value_usd or 0)} expected pressure cost"
    if impact.unit == "usd":
        return f"{name}: {money(impact.value_usd or 0)} a year saved"
    verb = "loses" if impact.polarity is Polarity.harm else "gains"
    cost = f" ({money(impact.value_usd)})" if impact.value_usd else ""
    return f"{name} {verb} {impact.magnitude:.0%} of capacity{cost}"


def blast_radius(result: SimulationResult, twin: Twin) -> BlastRadius:
    """Nodes, edges, department summaries, and outcome of ``result`` in the UI's shape."""
    ents = {e.id: e for e in twin.entities}
    failed = {c.constraint_id for c in result.constraint_results if c.hard and not c.passed}
    root = result.plan_id or result.scenario_id
    root_headline = (f"{len(result.intervention_ids)} interventions: {', '.join(result.intervention_ids)}"
                     if result.intervention_ids else "Do nothing")

    by_entity: dict[str, list[Impact]] = {}
    for impact in result.impacts:
        by_entity.setdefault(impact.affected_entity, []).append(impact)

    nodes = [BlastNode(node_id=root, kind="decision", headline=root_headline)]
    pressure_impacts = sorted((i for i in result.impacts if i.source_kind == "pressure"), key=lambda i: i.source_ref)
    for impact in pressure_impacts:
        nodes.append(BlastNode(
            node_id=impact.source_ref, kind="pressure", pressure_id=impact.source_ref,
            headline=f"Pressure on {ents[impact.affected_entity].name}: {money(impact.value_usd or 0)} expected cost",
            level=impact.level, category=impact.category, polarity=impact.polarity, severity=impact.severity,
            value_usd=impact.value_usd, first_effect_day=impact.first_effect_day, impact_ids=[impact.impact_id],
        ))
    for entity_id in sorted(by_entity):
        entity = ents[entity_id]
        impacts = sorted(by_entity[entity_id], key=lambda i: (i.polarity is not Polarity.harm, -i.severity))
        lead = impacts[0]
        values = [i.value_usd for i in impacts if i.value_usd is not None]
        nodes.append(BlastNode(
            node_id=entity_id, kind="department" if entity.type is EntityType.department else "entity",
            department_id=entity.id if entity.type is EntityType.department else entity.department_id,
            entity_id=entity_id, headline="; ".join(_impact_headline(i, entity.name) for i in impacts),
            level=lead.level, category=lead.category, polarity=lead.polarity, severity=lead.severity,
            value_usd=sum(values) if values else None, first_effect_day=min(i.first_effect_day for i in impacts),
            impact_ids=[i.impact_id for i in impacts],
        ))

    edges: dict[tuple[str, str], BlastEdge] = {}
    for impact in pressure_impacts:
        edges[(root, impact.source_ref)] = BlastEdge(source=root, target=impact.source_ref, label="Pressure",
                                                     level=impact.level, critical_constraint=False)
        edges[(impact.source_ref, impact.affected_entity)] = BlastEdge(
            source=impact.source_ref, target=impact.affected_entity, label="Pressure", level=impact.level,
            critical_constraint=False)
    for impact in result.impacts:
        if impact.source_kind == "pressure":
            continue
        path = impact.dependency_path or [impact.affected_entity]
        parents = [n for n in path[:-1] if n in by_entity]
        source = parents[-1] if parents else root
        if source == impact.affected_entity:
            source = root
        target_type = ents[impact.affected_entity].type
        critical = impact.polarity is Polarity.harm and bool(failed & set(impact.constraint_refs))
        if critical:
            label = "Critical constraint"
        elif impact.polarity is Polarity.harm and target_type in REVENUE_TYPES:
            label = "Revenue effect"
        else:
            label = LEVEL_LABEL.get(impact.level, "Second-order risk")
        key = (source, impact.affected_entity)
        if key not in edges or critical:
            edges[key] = BlastEdge(source=source, target=impact.affected_entity, label=label, level=impact.level,
                                   critical_constraint=critical)

    nodes.append(BlastNode(node_id=OUTCOME_NODE_ID, kind="outcome", headline=f"Net value {money(result.value.net_value_usd)}",
                           value_usd=result.value.net_value_usd))
    for entity_id in sorted(by_entity):
        if ents[entity_id].type in REVENUE_TYPES:
            edges[(entity_id, OUTCOME_NODE_ID)] = BlastEdge(source=entity_id, target=OUTCOME_NODE_ID,
                                                            label="Revenue effect", critical_constraint=False)

    departments = []
    by_department: dict[str, list[Impact]] = {}
    for impact in result.impacts:
        if impact.affected_department:
            by_department.setdefault(impact.affected_department, []).append(impact)
    for department_id in sorted(by_department):
        impacts = by_department[department_id]
        harms = [i for i in impacts if i.polarity is Polarity.harm]
        shown = harms or impacts
        worst = max(shown, key=lambda i: (i.severity, i.magnitude if i.unit != "usd" else 0.0, i.impact_id))
        departments.append(DepartmentImpactSummary(
            department_id=department_id, polarity=Polarity.harm if harms else Polarity.benefit,
            severity=worst.severity, impact_ids=[i.impact_id for i in impacts],
            headline=(f"{ents[department_id].name}: {len(harms)} harmed, {len(impacts) - len(harms)} improved; "
                      f"most severe: {_impact_headline(worst, ents[worst.affected_entity].name)}"),
        ))

    verdict = "feasible" if result.feasible else f"infeasible ({len(result.rejection_reasons)} failed checks)"
    return BlastRadius(
        run_id=result.run_id, scenario_id=result.scenario_id, future=result.future, plan_id=result.plan_id,
        root_node_id=root, nodes=nodes, edges=list(edges.values()), departments=departments,
        outcome=CompanyOutcome(net_value_usd=result.value.net_value_usd, risk_level=result.risk.level,
                               headline=(f"Net value {money(result.value.net_value_usd)}, risk "
                                         f"{result.risk.level.value} ({result.risk.score:.1f}), {verdict}")),
    )
