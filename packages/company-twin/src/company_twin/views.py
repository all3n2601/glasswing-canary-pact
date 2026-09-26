"""Permission-filtered and aggregated read models over the twin (plan B-05; schema
v2.2.0 sections 5.7, 5.8, 7.13).
"""

from __future__ import annotations

import re
from typing import Any, TypeVar

from pydantic import BaseModel

from .models import (
    AgentView,
    DepartmentDetail,
    DepartmentSummary,
    DomainGraph,
    EntityType,
    Relation,
    Sensitivity,
    Twin,
    entity_map,
)

T = TypeVar("T")


def build_agent_view(
    twin: Twin,
    *,
    agent_id: str,
    department_id: str | None,
    visible_entity_types: list[EntityType],
    visible_sensitivity: list[Sensitivity],
) -> AgentView:
    """Filter ``twin`` down to what one agent may see (schema section 5.7). Entities are
    filtered by type and sensitivity; edges, pressures and evidence only survive when
    every entity/document they touch is itself visible, so a redacted entity never leaks
    through a relationship. This is also why a planted edge withheld from ``twin.edges``
    (schema section 7.13) can never appear here: the filter only ever narrows that list.
    """
    allowed_types = set(visible_entity_types)
    allowed_sensitivity = set(visible_sensitivity)

    visible_entities = [e for e in twin.entities if e.type in allowed_types and e.sensitivity in allowed_sensitivity]
    visible_ids = {e.id for e in visible_entities}

    visible_edges = [e for e in twin.edges if e.source in visible_ids and e.target in visible_ids]
    visible_pressures = [p for p in twin.pressures if p.target_entity_id in visible_ids]

    visible_documents = [d for d in twin.documents if d.sensitivity in allowed_sensitivity]
    visible_document_ids = {d.id for d in visible_documents}
    visible_evidence = [v for v in twin.evidence if v.document_id in visible_document_ids]

    own_profile = next((p for p in twin.department_profiles if p.department_id == department_id), None)
    other_summaries = [
        DepartmentSummary(
            department_id=p.department_id,
            mission=p.mission,
            strength_names=[s.name for s in p.strengths],
            staffing=p.staffing,
        )
        for p in twin.department_profiles
        if p.department_id != department_id
    ]

    return AgentView(
        agent_id=agent_id,
        twin_version=twin.version.twin_version,
        organization=twin.organization,
        department_profile=own_profile,
        other_department_summaries=other_summaries,
        entities=visible_entities,
        edges=visible_edges,
        pressures=visible_pressures,
        documents=visible_documents,
        evidence=visible_evidence,
        redacted_entity_count=len(twin.entities) - len(visible_entities),
    )


def to_role_level(obj: T, twin: Twin) -> T:
    """Replace every ``pt_`` person-token ID in ``obj`` with its ``role_id`` (plan A5;
    schema section 7.13). Walks any pydantic model, list, tuple or dict, however deeply
    nested, so no output layer needs to remember to de-identify person tokens itself.
    """
    pt_to_role = {
        e.id: e.role_id for e in twin.entities if e.type == EntityType.person_token and e.role_id is not None
    }
    return _replace_ids(obj, pt_to_role)


_PT_TOKEN = re.compile(r"pt_[a-z0-9_]+")


def _replace_ids(value: Any, pt_to_role: dict[str, str]) -> Any:
    if isinstance(value, str):
        if value in pt_to_role:
            return pt_to_role[value]
        if "pt_" not in value:
            return value
        # a pt_ id embedded in free text (e.g. "ask pt_07"), not the whole string
        return _PT_TOKEN.sub(lambda m: pt_to_role.get(m.group(0), m.group(0)), value)
    if isinstance(value, BaseModel):
        updates = {name: _replace_ids(getattr(value, name), pt_to_role) for name in type(value).model_fields}
        return value.model_copy(update=updates)
    if isinstance(value, list):
        return [_replace_ids(v, pt_to_role) for v in value]
    if isinstance(value, tuple):
        return tuple(_replace_ids(v, pt_to_role) for v in value)
    if isinstance(value, dict):
        return {_replace_ids(k, pt_to_role): _replace_ids(v, pt_to_role) for k, v in value.items()}
    return value


def aggregate_domain_graph(twin: Twin) -> DomainGraph:
    """The department-map level for the overview chart (schema section 5.8): the 9
    departments and ``kpi_company`` as nodes, the 25 FLOWS_TO channels as edges. These
    channels are stored directly on the twin rather than computed, so this only selects
    them; it does not re-aggregate entity-level edges.
    """
    nodes = [e for e in twin.entities if e.type == EntityType.department or e.id == "kpi_company"]
    edges = [e for e in twin.edges if e.relation == Relation.FLOWS_TO]
    return DomainGraph(nodes=nodes, edges=edges)


def department_detail(twin: Twin, department_id: str) -> DepartmentDetail:
    ents = entity_map(twin)
    entity = ents[department_id]
    profile = next((p for p in twin.department_profiles if p.department_id == department_id), None)
    if profile is None:
        raise ValueError(f"No department profile for {department_id}")

    return DepartmentDetail(
        entity=entity,
        profile=profile,
        owned_entities=[e for e in twin.entities if e.department_id == department_id],
        documents=[d for d in twin.documents if d.department_id == department_id],
        channels_in=[e for e in twin.edges if e.relation == Relation.FLOWS_TO and e.target == department_id],
        channels_out=[e for e in twin.edges if e.relation == Relation.FLOWS_TO and e.source == department_id],
    )
