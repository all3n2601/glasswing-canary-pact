"""Versioned department edits; never mutate a twin used by an active run."""
from datetime import datetime, timezone
from uuid import uuid4
import hashlib

from contracts_py.twin import DepartmentEdit
from contracts_py.enums import EntityType
from contracts_py.twin import DepartmentProfile, Entity, Twin, CORE_AGENT_IDS
from .validate import validate_twin


def edit_department(twin: Twin, edit: DepartmentEdit, *, actor: str) -> Twin:
    suffix = hashlib.sha256((twin.version.twin_version + edit.model_dump_json()).encode()).hexdigest()[:12] if actor == "scenario" else uuid4().hex[:12]
    now = twin.version.created_at if actor == "scenario" else datetime.now(timezone.utc)
    candidate = twin.model_copy(deep=True)
    if edit.agent_id is not None and edit.agent_id not in CORE_AGENT_IDS:
        raise ValueError("Choose an existing department specialist or leave the perspective unmapped")
    name, mission = edit.name.strip(), edit.mission.strip()
    if len(name) < 2 or len(mission) < 2 or len(edit.assumption.strip()) < 10:
        raise ValueError("Name, mission, and modeling assumption cannot be blank")
    entity = next((e for e in candidate.entities if e.id == edit.department_id), None)
    profile = next((p for p in candidate.department_profiles if p.department_id == edit.department_id), None)
    if entity and entity.type is not EntityType.department:
        raise ValueError("This ID already belongs to another entity")
    if not edit.active:
        owned = [e.id for e in candidate.entities if e.department_id == edit.department_id and e.id != edit.department_id]
        connected = [e.id for e in candidate.edges if edit.department_id in (e.source, e.target)]
        if owned or connected:
            raise ValueError("This department still owns work or dependencies. Test closure in a scenario first; resolve ownership before archiving the baseline.")
        if edit.actual_fte or edit.annual_budget_usd:
            raise ValueError("An archived baseline department must have zero staffing and budget")
    if profile is None:
        profile = DepartmentProfile(
            department_id=edit.department_id, mission=mission,
            staffing=dict(sanctioned_fte=edit.actual_fte, actual_fte=edit.actual_fte, contractors_fte=0,
                          open_positions=0, attrition_rate_annual=0, avg_time_to_hire_days=0, utilisation=edit.utilisation),
            budget=dict(annual_budget_usd=edit.annual_budget_usd, spent_ytd_usd=0, fixed_cost_pct=1),
            strengths=[dict(id=f"str_{suffix}", name="User-declared capacity; capability unverified",
                            category="capability", level=1, concentration=1)], maturity_level=1,
        )
        candidate.department_profiles.append(profile)
        entity = Entity(id=edit.department_id, type=EntityType.department, name=name,
                        annual_cost_usd=edit.annual_budget_usd, capacity_fte=edit.actual_fte)
        candidate.entities.append(entity)
    assert entity is not None
    profile.active, profile.agent_id, profile.mission = edit.active, edit.agent_id, mission
    profile.staffing.actual_fte = edit.actual_fte
    profile.staffing.utilisation = edit.utilisation
    profile.budget.annual_budget_usd = edit.annual_budget_usd
    entity.name, entity.annual_cost_usd = name, edit.annual_budget_usd
    entity.capacity_fte = edit.actual_fte + profile.staffing.contractors_fte
    # Preserve the stated assumption as evidence with an explicit source and actor.
    from contracts_py.twin import Document, Evidence
    from contracts_py.enums import DocumentType, DocumentStatus, EvidenceSource
    doc = Document(id=f"doc_{suffix}", title=f"Department declaration: {name}", doc_type=DocumentType.other,
                   department_id=edit.department_id, uri=f"canary://department-declarations/{suffix}",
                   mime_type="text/plain", status=DocumentStatus.current, summary=" ".join(edit.assumption.split()[:60]), synthetic=False, ingested=True,
                   checksum_sha256=hashlib.sha256(edit.assumption.encode()).hexdigest(), uploaded_at=now)
    evidence = Evidence(id=f"ev_{suffix}", source_type=EvidenceSource.architecture_note,
                        document_id=doc.id, snippet=edit.assumption, synthetic=False)
    candidate.documents.append(doc)
    candidate.evidence.append(evidence)
    entity.evidence_refs.append(evidence.id)
    profile.document_ids.append(doc.id)
    candidate.organization.total_annual_budget_usd = sum(p.budget.annual_budget_usd for p in candidate.department_profiles)
    candidate.organization.total_headcount_fte = sum(p.staffing.actual_fte + p.staffing.contractors_fte for p in candidate.department_profiles)
    candidate.version = candidate.version.model_copy(update={"twin_version": f"twin_office_{suffix}",
        "created_at": now, "as_of_date": now.date(), "created_by": actor})
    errors = [issue.message for issue in validate_twin(candidate) if issue.severity == "error"]
    if errors:
        raise ValueError(errors[0])
    return candidate


def edit_organization(twin, organization, departments, settings, *, actor):
    """Save the existing setup form as a single validated company version."""
    if organization.id != twin.organization.id or settings.organization_id != organization.id:
        raise ValueError("Organization identity cannot be changed")
    result = twin.model_copy(deep=True)
    for department in departments:
        result = edit_department(result, department, actor=actor)
    organization = organization.model_copy(deep=True)
    organization.total_annual_budget_usd = sum(p.budget.annual_budget_usd for p in result.department_profiles)
    organization.total_headcount_fte = sum(p.staffing.actual_fte + p.staffing.contractors_fte for p in result.department_profiles)
    result.organization = organization
    result.organization_settings = settings.model_copy(update={"updated_by":actor, "updated_at":datetime.now(timezone.utc), "settings_version":(twin.organization_settings.settings_version if twin.organization_settings else 1)+1})
    result.version = result.version.model_copy(update={"twin_version":f"twin_settings_{uuid4().hex}","created_by":actor,"created_at":datetime.now(timezone.utc), "settings_version":result.organization_settings.settings_version})
    errors = [i.message for i in validate_twin(result) if i.severity == "error"]
    if errors:
        raise ValueError(errors[0])
    return result
