"""Document staleness (schema v2.2.0 section 5.12 / 7.13).

A non-``current`` document (outdated, archived, or still a draft) is stale by
definition. A ``current`` document goes stale once ``as_of_date - last_reviewed``
exceeds its own ``review_cycle_days``, or ``settings.doc_staleness_days`` when it has
none. ``as_of_date`` is always the twin's simulated "today" (``VersionInfo.as_of_date``),
never the wall clock, so replays stay deterministic.
"""

from __future__ import annotations

from datetime import date

from .models import Document, OrganizationSettings

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
