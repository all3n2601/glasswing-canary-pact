import json
import logging
import os
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from contracts_py.decision import Intervention
from contracts_py.enums import InterventionKind, MitigationType
from contracts_py.twin import ValidationIssue

from .documents import documented_workflow_ids
from .models import CompanyTwin, EntityType, Twin, entity_map
from .validate import validate_twin

log = logging.getLogger(__name__)

# schema v2.2.0 section 5.12: the doc types a workflow needs to be "documented"
# (matches OrganizationSettings.required_doc_types_per_workflow's default).
REQUIRED_DOC_TYPES_PER_WORKFLOW = ("runbook", "sop")
DOCUMENTED_PCT_DISAGREEMENT_TOLERANCE = 0.05
MAX_OVERLAY_SNIPPET_LENGTH = 300


# The entity types a catalogued mitigation may target; other mitigation types only need an existing target.
MITIGATION_TARGET_TYPES = {
    MitigationType.reassign_owner: {EntityType.workflow},
    MitigationType.document_runbook: {EntityType.workflow, EntityType.knowledge_asset},
    MitigationType.add_replacement_feed: {EntityType.dataset},
}


def default_fixture_path() -> Path:
    return Path(__file__).resolve().parents[4] / "data" / "synthetic_company.json"


def default_mitigation_catalog_path() -> Path:
    """``CANARY_MITIGATION_CATALOG_PATH`` when set (a case twin's own catalog), else ``data/mitigations.json``."""
    override = os.environ.get("CANARY_MITIGATION_CATALOG_PATH")
    return Path(override) if override else default_fixture_path().parent / "mitigations.json"


class TwinValidationError(ValueError):
    """``build_twin`` found error-severity ``validate_twin`` issues; ``issues`` lists them."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        shown = "; ".join(f"rule {i.rule}: {i.message}" for i in issues[:5])
        more = f" (and {len(issues) - 5} more)" if len(issues) > 5 else ""
        super().__init__(f"twin failed validation with {len(issues)} errors: {shown}{more}")


def _populate_derived_profile_fields(twin: Twin) -> None:
    """Compute the derived DepartmentProfile fields from the graph rather than
    hand-setting them in the fixture (schema v2.1 §5.11). Mutates in place.

    ``documentation_coverage`` is the share of the department's high and critical
    workflows that ``documented_workflow_ids`` counts as documented."""
    documented = documented_workflow_ids(twin)

    for p in twin.department_profiles:
        did = p.department_id
        owned = [e for e in twin.entities if e.department_id == did]
        p.owned_entity_ids = [e.id for e in owned]
        crit_wf = [
            e.id for e in owned
            if e.type == EntityType.workflow and e.criticality.value in ("high", "critical")
        ]
        p.critical_workflow_ids = crit_wf
        p.kpi_ids = [e.id for e in owned if e.type == EntityType.kpi]
        p.document_ids = [d.id for d in twin.documents if d.department_id == did]
        if crit_wf:
            covered = sum(1 for w in crit_wf if w in documented)
            p.documentation_coverage = round(covered / len(crit_wf), 3)
        else:
            p.documentation_coverage = 1.0  # nothing critical to document


def _derive_documented_pct(twin: Twin) -> None:
    """Derive each workflow's documented_pct from current, covering documents
    (schema v2.2.0 section 5.12): the share of {runbook, sop} present as a
    *current* document covering it. A hand-set fixture value is kept as-is
    (e.g. a stale runbook deliberately keeps a workflow's coverage low for the
    knowledge-loss story); we only warn when it disagrees with the derived
    value. Mutates in place."""
    covers: dict[str, set[str]] = {}
    for d in twin.documents:
        if d.status.value != "current":
            continue
        for entity_id in d.covers_entity_ids:
            covers.setdefault(entity_id, set()).add(d.doc_type.value)

    for e in twin.entities:
        if e.type != EntityType.workflow:
            continue
        matched = covers.get(e.id, set()) & set(REQUIRED_DOC_TYPES_PER_WORKFLOW)
        derived = round(len(matched) / len(REQUIRED_DOC_TYPES_PER_WORKFLOW), 3)
        if e.documented_pct is None:
            e.documented_pct = derived
        elif abs(e.documented_pct - derived) > DOCUMENTED_PCT_DISAGREEMENT_TOLERANCE:
            log.warning(
                "documented_pct disagreement for %s: fixture=%s derived=%s (kept fixture value)",
                e.id, e.documented_pct, derived,
            )


def _overlay_snippets(twin: Twin, snippets: Mapping[str, str]) -> None:
    """Overlay final snippet wording (ev_ id -> text) onto matching Evidence records
    (schema v2.2.0 section 5.12: text never changes a number).

    An overlaid snippet longer than ``MAX_OVERLAY_SNIPPET_LENGTH`` is applied as-is
    (never truncated silently) but logs a ``ValidationIssue``-shaped warning, since a
    snippet this long is more likely a pasted document than a quoted snippet.
    """
    by_id = {ev.id: ev for ev in twin.evidence}
    for ev_id, text in snippets.items():
        evidence = by_id.get(ev_id)
        if evidence is not None:
            evidence.snippet = text
            if len(text) > MAX_OVERLAY_SNIPPET_LENGTH:
                issue = ValidationIssue(
                    rule="overlay_snippet_length",
                    severity="warning",
                    message=f"overlaid snippet for {ev_id} is {len(text)} chars (max {MAX_OVERLAY_SNIPPET_LENGTH})",
                    ids=[ev_id],
                )
                log.warning("%s", issue.message)


def load_company_twin(path: str | Path | None = None) -> CompanyTwin:
    fixture_path = Path(path) if path else default_fixture_path()
    twin = CompanyTwin.model_validate(json.loads(fixture_path.read_text()))
    _populate_derived_profile_fields(twin)
    return twin


def _prepare(data: Twin | Mapping[str, Any], snippets: Mapping[str, str] | None) -> Twin:
    """A fresh ``Twin`` from ``data`` with snippets overlaid and every derived field computed."""
    twin = data.model_copy(deep=True) if isinstance(data, Twin) else Twin.model_validate(data)
    if snippets:
        _overlay_snippets(twin, snippets)
    _derive_documented_pct(twin)
    _populate_derived_profile_fields(twin)
    return twin


def build_twin(data: Twin | Mapping[str, Any], snippets: Mapping[str, str] | None = None) -> Twin:
    """Build a validated twin from in-memory data (plan B-01, B-04; schema v2.2.0 section 7.13).

    ``data`` is a ``Twin`` or its JSON-shaped mapping, e.g. a row loaded from the
    database; it is never mutated. ``snippets`` (ev_ id -> final snippet text) is
    overlaid onto the evidence when given. Every derived field is computed: each
    workflow's ``documented_pct`` (a stored value is kept) and every DepartmentProfile's
    ``owned_entity_ids``, ``critical_workflow_ids``, ``kpi_ids``, ``document_ids`` and
    ``documentation_coverage``. Recomputing is idempotent, so a twin that was built
    before it was persisted can be built again after it is loaded.

    Raises ``pydantic.ValidationError`` when ``data`` does not fit the contract and
    ``TwinValidationError`` when ``validate_twin`` reports an error; warnings are logged.
    """
    twin = _prepare(data, snippets)
    issues = validate_twin(twin)
    for issue in issues:
        if issue.severity == "warning":
            log.warning("twin validation warning, rule %s: %s", issue.rule, issue.message)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        raise TwinValidationError(errors)
    return twin


def load_twin(twin_path: str | Path, snippets_path: str | Path | None = None) -> Twin:
    """Load and prepare a twin from a JSON file (plan B-01; used for seeding and tests).

    Parses ``twin_path`` with the shared ``contracts_py.Twin`` model and prepares it
    as ``build_twin`` does, overlaying ``snippets_path`` (optional; a JSON object of
    ev_ id -> final snippet text) when given. It does not validate: call
    ``validate_twin`` for readable issues, or ``build_twin`` to raise on errors.
    """
    snippets = json.loads(Path(snippets_path).read_text()) if snippets_path is not None else None
    return _prepare(json.loads(Path(twin_path).read_text()), snippets)


def _check_reference(entry: Intervention, field: str, entity_id: Any, types: set[EntityType],
                     ents: Mapping[str, Any]) -> None:
    entity = ents.get(entity_id) if isinstance(entity_id, str) else None
    allowed = " or ".join(sorted(t.value for t in types))
    if entity is None:
        raise ValueError(f"mitigation {entry.id}: {field} {entity_id!r} is not in the twin")
    if entity.type not in types:
        raise ValueError(f"mitigation {entry.id}: {field} {entity_id} is a {entity.type.value}, expected {allowed}")


def load_mitigation_catalog(path: str | Path | None = None, twin: Twin | None = None) -> list[Intervention]:
    """Load the mitigation catalog (plan E-07, section 11.8): a JSON array of ``contracts_py`` interventions.

    ``path`` defaults to ``data/mitigations.json``. Every entry must be a mitigation (with its
    explicit ``one_time_cost_usd``) and IDs must be unique. With ``twin`` given, each entry's
    ``target_entity_id``, ``new_owner_id`` (a role) and ``params.replacement_vendor_id`` (a vendor)
    must exist in it with the right entity type (``MITIGATION_TARGET_TYPES`` for the target).
    Raises ``ValueError`` (a ``pydantic.ValidationError`` for an entry that is not an intervention).
    """
    catalog_path = Path(path) if path else default_mitigation_catalog_path()
    raw = json.loads(catalog_path.read_text())
    if not isinstance(raw, list):
        raise ValueError(f"{catalog_path}: the mitigation catalog must be a JSON array of interventions")
    entries = [Intervention.model_validate(item) for item in raw]
    actions = [e.id for e in entries if e.kind is not InterventionKind.mitigation]
    if actions:
        raise ValueError(f"{catalog_path}: catalog entries must be mitigations, not actions: {actions}")
    repeated = sorted(i for i, n in Counter(e.id for e in entries).items() if n > 1)
    if repeated:
        raise ValueError(f"{catalog_path}: mitigation ids must be unique, repeated: {repeated}")
    if twin is not None:
        ents = entity_map(twin)
        all_types = set(EntityType)
        for entry in entries:
            _check_reference(entry, "target_entity_id", entry.target_entity_id,
                             MITIGATION_TARGET_TYPES.get(entry.type, all_types), ents)
            if entry.new_owner_id is not None:
                _check_reference(entry, "new_owner_id", entry.new_owner_id, {EntityType.role}, ents)
            if "replacement_vendor_id" in entry.params:
                _check_reference(entry, "params.replacement_vendor_id", entry.params["replacement_vendor_id"],
                                 {EntityType.vendor}, ents)
    return entries
