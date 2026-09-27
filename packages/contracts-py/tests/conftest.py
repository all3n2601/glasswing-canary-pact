from datetime import date, datetime, timezone

import pytest

from contracts_py.decision import Constraint, DecisionBrief, Goal, Intervention
from contracts_py.enums import (
    ActionType,
    BusinessModel,
    DecisionType,
    DocumentStatus,
    DocumentType,
    Future,
    InterventionKind,
    MitigationType,
    PressureKind,
    Sector,
    SizeBand,
    StrengthCategory,
)
from contracts_py.twin import (
    DepartmentBudget,
    DepartmentProfile,
    DepartmentStrength,
    Document,
    NeutraliserRef,
    Organization,
    Pressure,
    StaffingStrength,
)

NOW = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)


def constraint(cid: str, metric: str, operator: str, hard: bool, threshold: float = 0) -> Constraint:
    return Constraint(
        id=cid,
        metric=metric,
        operator=operator,
        threshold=threshold,
        unit="pct" if metric.endswith("_pct") else "count",
        hard=hard,
        description=f"{metric} {operator} {threshold}",
    )


VENDORS = ["apex", "beacon", "cinder", "delta", "echo", "flux", "granite"]
WORKFORCE_ROLES = [f"role_wk_{n:02d}" for n in range(1, 9)]


@pytest.fixture
def vendor_brief() -> DecisionBrief:
    return DecisionBrief(
        decision_id="dec_vendor_reduction",
        decision_type=DecisionType.vendor_consolidation,
        title="Consolidate data vendors",
        statement="Save at least $2B a year by removing overlapping data vendors without losing critical coverage.",
        goal=Goal(metric="annual_savings_usd", target=2_000_000_000, basis="gross", direction="at_least"),
        candidate_interventions=[
            Intervention(
                id=f"i_remove_{name}",
                kind=InterventionKind.action,
                type=ActionType.remove_vendor,
                target_entity_id=f"vendor_{name}",
                rationale=f"vendor_{name} overlaps with other data vendors.",
            )
            for name in VENDORS
        ],
        constraints=[
            constraint("c_compliance", "compliance_controls_broken", "==", True),
            constraint("c_critical_coverage", "critical_coverage_pct", ">=", True, threshold=100),
            constraint("c_revenue", "revenue_impact_pct", "<=", True, threshold=3),
            constraint("c_customer", "customer_impact_pct", "<=", True, threshold=2),
        ],
        created_by="demo_user",
    )


@pytest.fixture
def workforce_brief() -> DecisionBrief:
    return DecisionBrief(
        decision_id="dec_workforce_knowledge",
        decision_type=DecisionType.restructure,
        title="Restructure without losing critical knowledge",
        statement="Remove eight roles while keeping every critical workflow owned.",
        goal=Goal(metric="annual_savings_usd", target=1_000_000, basis="gross", direction="at_least"),
        candidate_interventions=[
            Intervention(
                id=f"i_remove_{role.removeprefix('role_')}",
                kind=InterventionKind.action,
                type=ActionType.remove_roles,
                target_entity_id=role,
                rationale=f"{role} is part of the proposed restructure.",
            )
            for role in WORKFORCE_ROLES
        ],
        constraints=[constraint("c_stranded", "stranded_workflows", "==", True)],
        created_by="demo_user",
    )


@pytest.fixture
def brief(vendor_brief: DecisionBrief) -> DecisionBrief:
    return vendor_brief


@pytest.fixture
def cut_2m_brief() -> DecisionBrief:
    return DecisionBrief(
        decision_id="dec_cut_2m",
        decision_type=DecisionType.cost_reduction,
        title="Cut $2M in annual cost",
        statement="Find at least $2M of gross annual savings without breaking compliance or critical systems.",
        goal=Goal(metric="annual_savings_usd", target=2_000_000, basis="gross", direction="at_least"),
        candidate_interventions=[
            Intervention(
                id="i_platform_ops",
                kind=InterventionKind.action,
                type=ActionType.reduce_capacity,
                target_entity_id="dept_operations",
                amount_pct=20,
                one_time_cost_usd=60_000,
                params={"scope": "platform_ops"},
                rationale="Platform operations is over sanctioned headcount.",
            ),
            Intervention(
                id="i_auditlog",
                kind=InterventionKind.action,
                type=ActionType.remove_vendor,
                target_entity_id="vendor_auditlog",
                start_day=30,
                rationale="Audit log vendor overlaps with in-house logging.",
            ),
            Intervention(
                id="i_migration",
                kind=InterventionKind.action,
                type=ActionType.stop_project,
                target_entity_id="proj_warehouse_migration",
                one_time_cost_usd=40_000,
                rationale="Warehouse migration is behind schedule.",
            ),
            Intervention(
                id="i_eng",
                kind=InterventionKind.action,
                type=ActionType.reduce_capacity,
                target_entity_id="dept_engineering",
                amount_pct=10,
                one_time_cost_usd=120_000,
                rationale="Engineering capacity trimmed to match roadmap.",
            ),
        ],
        protected_entity_ids=["ctl_soc2_audit_logging"],
        constraints=[
            constraint("c_compliance", "compliance_controls_broken", "==", True),
            constraint("c_critical", "critical_systems_degraded", "==", True),
            constraint("c_revenue", "revenue_impact_pct", "<=", True, threshold=3),
            constraint("c_stranded", "stranded_workflows", "==", False),
        ],
        futures=[Future.act_now, Future.inaction, Future.delay],
        delay_days=90,
        active_pressure_ids=["pr_cloud_growth", "pr_auditlog_renewal", "pr_billing_recon_hazard"],
        seed=42,
        mc_samples=1000,
        created_by="demo_user",
    )


@pytest.fixture
def pressures() -> list[Pressure]:
    return [
        Pressure(
            id="pr_cloud_growth",
            kind=PressureKind.cost_growth,
            name="Cloud cost growth",
            target_entity_id="sys_cloud_platform",
            rate=0.015,
            rate_range=(0.01, 0.02),
            description="Cloud platform spend grows each month.",
        ),
        Pressure(
            id="pr_auditlog_renewal",
            kind=PressureKind.renewal_step,
            name="Audit log renewal",
            target_entity_id="vendor_auditlog",
            start_day=120,
            step_pct=12,
            neutralised_by=[NeutraliserRef(intervention_type=ActionType.remove_vendor, target_entity_id="vendor_auditlog")],
            description="Audit log contract renews with a price step.",
        ),
        Pressure(
            id="pr_billing_recon_hazard",
            kind=PressureKind.hazard,
            name="Billing reconciliation failure",
            target_entity_id="wf_billing_recon",
            monthly_probability=0.04,
            probability_range=(0.02, 0.06),
            cost_per_event_usd=400_000,
            capacity_sensitivity=3.0,
            neutralised_by=[
                NeutraliserRef(intervention_type=MitigationType.document_runbook, target_entity_id="wf_billing_recon")
            ],
            description="Undocumented billing reconciliation can fail.",
        ),
    ]


@pytest.fixture
def organization() -> Organization:
    return Organization(
        id="org_novacorp",
        legal_name="NovaCorp",
        display_name="NovaCorp",
        sector=Sector.technology_saas,
        business_model=BusinessModel.b2b,
        size_band=SizeBand.mid_market,
        headquarters_country="US",
        annual_revenue_usd=48_000_000,
        total_annual_budget_usd=21_000_000,
        total_headcount_fte=420,
        fiscal_year_start_month=1,
        regulatory_frameworks=["SOC2", "GDPR", "PCI_DSS"],
        description="Synthetic mid-market B2B SaaS company.",
    )


@pytest.fixture
def operations_profile() -> DepartmentProfile:
    return DepartmentProfile(
        department_id="dept_operations",
        mission="Keep the platform and billing running.",
        staffing=StaffingStrength(
            sanctioned_fte=64,
            actual_fte=58,
            contractors_fte=6,
            open_positions=6,
            attrition_rate_annual=0.12,
            avg_time_to_hire_days=45,
            utilisation=1.12,
        ),
        budget=DepartmentBudget(annual_budget_usd=3_100_000, spent_ytd_usd=2_300_000, fixed_cost_pct=0.35),
        strengths=[
            DepartmentStrength(
                id="str_ops_incident_response",
                name="Incident response",
                category=StrengthCategory.process,
                level=4,
                concentration=0.4,
                evidence_refs=["ev_ops_incident_log"],
            ),
            DepartmentStrength(
                id="str_ops_billing_recon",
                name="Billing reconciliation",
                category=StrengthCategory.expertise,
                level=5,
                concentration=0.85,
                key_role_ids=["role_billing_ops_lead"],
                evidence_refs=["ev_billing_recon_matrix"],
            ),
        ],
        maturity_level=3,
    )


@pytest.fixture
def runbook() -> Document:
    return Document(
        id="doc_runbook_billing_recon",
        title="Billing reconciliation runbook",
        doc_type=DocumentType.runbook,
        department_id="dept_operations",
        uri="data/artifacts/doc_runbook_billing_recon.md",
        mime_type="text/markdown",
        status=DocumentStatus.outdated,
        last_reviewed=date(2025, 3, 10),
        review_cycle_days=180,
        covers_entity_ids=["wf_billing_recon"],
        framework_refs=["SOC2"],
        summary="Steps to reconcile billing records each month.",
        uploaded_at=NOW,
    )
