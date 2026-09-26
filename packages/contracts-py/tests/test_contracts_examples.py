from contracts_py.decision import ENGINE_METRICS, DecisionBrief
from contracts_py.enums import Future
from contracts_py.twin import DepartmentProfile, Document, Organization, OrganizationSettings, Pressure


def test_vendor_reduction_brief_validates(vendor_brief: DecisionBrief) -> None:
    again = DecisionBrief.model_validate(vendor_brief.model_dump(mode="json"))
    assert again == vendor_brief
    assert again.schema_version == "2.1.1"
    assert [i.target_entity_id for i in again.candidate_interventions] == [
        f"vendor_{name}" for name in ("apex", "beacon", "cinder", "delta", "echo", "flux", "granite")
    ]
    assert all(c.hard and c.metric in ENGINE_METRICS for c in again.constraints)
    assert again.futures == [Future.act_now, Future.inaction, Future.delay]


def test_workforce_knowledge_brief_validates(workforce_brief: DecisionBrief) -> None:
    again = DecisionBrief.model_validate(workforce_brief.model_dump(mode="json"))
    assert again == workforce_brief
    assert [i.type for i in again.candidate_interventions] == ["remove_roles"] * 8
    assert [i.target_entity_id for i in again.candidate_interventions] == [f"role_wk_{n:02d}" for n in range(1, 9)]
    assert [(c.metric, c.hard) for c in again.constraints] == [("stranded_workflows", True)]


def test_cut_2m_brief_still_validates(cut_2m_brief: DecisionBrief) -> None:
    brief = cut_2m_brief
    again = DecisionBrief.model_validate(brief.model_dump(mode="json"))
    assert again == brief
    assert [i.id for i in again.candidate_interventions] == ["i_platform_ops", "i_auditlog", "i_migration", "i_eng"]
    assert again.futures == [Future.act_now, Future.inaction, Future.delay]
    assert all(c.metric in ENGINE_METRICS for c in again.constraints)


def test_pressures_validate(pressures: list[Pressure]) -> None:
    for pressure in pressures:
        assert Pressure.model_validate(pressure.model_dump(mode="json")) == pressure
    hazard = pressures[2]
    assert hazard.monthly_probability == 0.04 and hazard.capacity_sensitivity == 3.0


def test_organization_profile_document_validate(
    organization: Organization, operations_profile: DepartmentProfile, runbook: Document
) -> None:
    assert Organization.model_validate(organization.model_dump(mode="json")) == organization
    assert DepartmentProfile.model_validate(operations_profile.model_dump(mode="json")) == operations_profile
    assert Document.model_validate(runbook.model_dump(mode="json")) == runbook


def test_settings_defaults() -> None:
    settings = OrganizationSettings()
    assert settings.settings_id == "set_default"
    assert settings.mc_samples == 1000 and settings.propagation_max_hops == 4
    assert settings.risk_weights.financial == 25
    assert {"finance", "compliance", "challenger"} <= set(OrganizationSettings(enabled_agent_ids=["sales"]).enabled_agent_ids)
