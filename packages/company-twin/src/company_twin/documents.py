"""Document staleness and workflow documentation (schema v2.2.0 sections 5.11, 5.12, 7.13).

A non-``current`` document (outdated, archived, or still a draft) is stale by
definition. A ``current`` document goes stale once ``as_of_date - last_reviewed``
exceeds its own ``review_cycle_days``, or ``settings.doc_staleness_days`` when it has
none. ``as_of_date`` is always the twin's simulated "today" (``VersionInfo.as_of_date``),
never the wall clock, so replays stay deterministic.
"""

from __future__ import annotations

from datetime import date

from .models import Document, EntityType, OrganizationSettings, Relation, Twin

# The doc types that document a workflow (OrganizationSettings.required_doc_types_per_workflow's default).
WORKFLOW_DOC_TYPES = frozenset({"runbook", "sop"})
# A supporting knowledge asset counts as written down at this share (the KnowledgeCoverage "lost" threshold).
KNOWLEDGE_DOCUMENTED_AT = 0.5

_DEFAULT_DOC_STALENESS_DAYS: int = OrganizationSettings.model_fields["doc_staleness_days"].default


def document_is_stale(
    doc: Document,
    *,
    as_of_date: date,
    settings: OrganizationSettings | None = None,
) -> bool:
    if doc.status.value != "current":
        return True
    if doc.last_reviewed is None:
        return False
    threshold = doc.review_cycle_days
    if threshold is None:
        threshold = settings.doc_staleness_days if settings is not None else _DEFAULT_DOC_STALENESS_DAYS
    return (as_of_date - doc.last_reviewed).days > threshold


def documented_workflow_ids(twin: Twin, settings: OrganizationSettings | None = None) -> set[str]:
    """Workflows someone could run from the documents alone (schema 5.11 ``documentation_coverage``).

    A workflow is documented when a current, non-stale runbook or SOP covers it **and** every
    knowledge asset that SUPPORTS it is at least ``KNOWLEDGE_DOCUMENTED_AT`` documented. An
    outdated runbook, an incident report, or an SOP that defers to an undocumented knowledge
    holder does not count.
    """
    as_of = twin.version.as_of_date
    covered: set[str] = set()
    for doc in twin.documents:
        if doc.doc_type.value in WORKFLOW_DOC_TYPES and not document_is_stale(doc, as_of_date=as_of,
                                                                               settings=settings):
            covered.update(doc.covers_entity_ids)
    ents = {e.id: e for e in twin.entities}
    undocumented_knowledge_behind: set[str] = set()
    for edge in twin.edges:
        source = ents.get(edge.source)
        if (edge.relation is Relation.SUPPORTS and source is not None and source.type is EntityType.knowledge_asset
                and (source.documented_pct or 0.0) < KNOWLEDGE_DOCUMENTED_AT):
            undocumented_knowledge_behind.add(edge.target)
    return {e.id for e in twin.entities if e.type is EntityType.workflow and e.id in covered
            and e.id not in undocumented_knowledge_behind}
