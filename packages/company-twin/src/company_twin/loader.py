import json
from pathlib import Path

from .models import CompanyTwin, EntityType, Twin


def default_fixture_path() -> Path:
    return Path(__file__).resolve().parents[4] / "data" / "synthetic_company.json"


def _populate_derived_profile_fields(twin: Twin) -> None:
    """Compute the derived DepartmentProfile fields from the graph rather than
    hand-setting them in the fixture (schema v2.1 §5.11). Mutates in place."""
    # entity ids covered by at least one *current* document
    covered_by_current_doc: set[str] = set()
    for d in twin.documents:
        if getattr(d, "status", None) == "current":
            covered_by_current_doc.update(d.covers_entity_ids)

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
            covered = sum(1 for w in crit_wf if w in covered_by_current_doc)
            p.documentation_coverage = round(covered / len(crit_wf), 3)
        else:
            p.documentation_coverage = 1.0  # nothing critical to document


def load_company_twin(path: str | Path | None = None) -> CompanyTwin:
    fixture_path = Path(path) if path else default_fixture_path()
    twin = CompanyTwin.model_validate(json.loads(fixture_path.read_text()))
    _populate_derived_profile_fields(twin)
    return twin
