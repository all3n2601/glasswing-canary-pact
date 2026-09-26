from datetime import date, datetime, timezone

from contracts_py.decision import Constraint, DecisionBrief, Goal, Intervention
from contracts_py.enums import (
    ActionType,
    BusinessModel,
    ChannelKind,
    Criticality,
    DecisionType,
    DocumentStatus,
    DocumentType,
    EntityType,
    EvidenceSource,
    Future,
    InterventionKind,
    MitigationType,
    PressureKind,
    Relation,
    Sector,
    SizeBand,
    StrengthCategory,
)
from contracts_py.twin import (
    DepartmentBudget,
    DepartmentProfile,
    DepartmentStrength,
    Document,
    Edge,
    Entity,
    Evidence,
    NeutraliserRef,
    Organization,
    Pressure,
    StaffingStrength,
    Twin,
    VersionInfo,
)

STUB_TIME = datetime(2026, 9, 26, 17, 0, tzinfo=timezone.utc)
TWIN_VERSION = "stub-twin-1"

# department_id, name, mission, annual budget, actual fte, sanctioned fte, contractors, utilisation
DEPARTMENTS = [
    ("dept_finance", "Finance", "Plan, report and control company spend.", 1_500_000, 28, 30, 1, 0.95),
    ("dept_engineering", "Engineering", "Build and run the product platform.", 6_200_000, 110, 118, 8, 1.05),
    ("dept_ai_data", "AI and Data", "Own the data warehouse and analytics models.", 1_900_000, 30, 32, 2, 0.98),
    ("dept_operations", "Operations", "Keep the platform and billing running.", 3_100_000, 58, 64, 6, 1.12),
    ("dept_product", "Product", "Decide what the platform builds next.", 1_800_000, 34, 36, 0, 0.9),
    ("dept_marketing", "Marketing", "Generate demand for the platform.", 2_000_000, 36, 38, 3, 0.88),
    ("dept_sales", "Sales", "Win and expand customer contracts.", 2_600_000, 60, 64, 0, 0.93),
    ("dept_customer_success", "Customer Success", "Keep customers healthy and renewing.", 1_200_000, 44, 46, 2, 1.0),
    ("dept_compliance", "Compliance", "Keep SOC2, GDPR and PCI DSS controls passing.", 700_000, 20, 22, 1, 1.02),
]


def _profile(department_id: str, name: str, mission: str, budget: int, actual: float, sanctioned: float,
             contractors: float, utilisation: float) -> DepartmentProfile:
    if department_id == "dept_operations":
        strengths = [
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
                supports_entity_ids=["wf_billing_recon"],
                key_role_ids=["role_billing_ops_lead"],
                concentration=0.85,
                evidence_refs=["ev_billing_recon_matrix"],
            ),
        ]
    else:
        strengths = [
            DepartmentStrength(
                id=f"str_{department_id.removeprefix('dept_')}_core",
                name=f"{name} core practice",
                category=StrengthCategory.capability,
                level=3,
                concentration=0.3,
            )
        ]
    return DepartmentProfile(
        department_id=department_id,
        mission=mission,
        agent_id=department_id.removeprefix("dept_"),
        staffing=StaffingStrength(
            sanctioned_fte=sanctioned,
            actual_fte=actual,
            contractors_fte=contractors,
            open_positions=2,
            attrition_rate_annual=0.12,
            avg_time_to_hire_days=45,
            utilisation=utilisation,
        ),
        budget=DepartmentBudget(annual_budget_usd=budget, spent_ytd_usd=0, fixed_cost_pct=0.35),
        strengths=strengths,
        maturity_level=3,
        critical_workflow_ids=["wf_billing_recon"] if department_id == "dept_operations" else [],
        kpi_ids=["kpi_company"],
        document_ids=["doc_runbook_billing_recon"] if department_id == "dept_operations" else [],
    )


def _entities() -> list[Entity]:
    departments = [
        Entity(id=d, type=EntityType.department, name=n, annual_cost_usd=b, capacity_fte=a, criticality=Criticality.high)
        for d, n, _, b, a, _, _, _ in DEPARTMENTS
    ]
    return departments + [
        Entity(
            id="kpi_company",
            type=EntityType.kpi,
            name="Company net value",
            criticality=Criticality.critical,
            kpi_baseline=48_000_000,
            kpi_unit="usd",
            higher_is_better=True,
        ),
        Entity(
            id="role_billing_ops_lead",
            type=EntityType.role,
            name="Billing operations lead",
            department_id="dept_operations",
            annual_cost_usd=160_000,
            capacity_fte=1,
            criticality=Criticality.high,
        ),
        Entity(
            id="wf_billing_recon",
            type=EntityType.workflow,
            name="Monthly billing reconciliation",
            department_id="dept_operations",
            criticality=Criticality.critical,
            min_qualified_owners=1,
            failure_cost_per_day_usd=40_000,
            customer_facing=True,
            evidence_refs=["ev_billing_recon_matrix"],
        ),
        Entity(
            id="vendor_auditlog",
            type=EntityType.vendor,
            name="Audit log vendor",
            department_id="dept_operations",
            criticality=Criticality.high,
            annual_cost_usd=330_000,
            one_time_exit_cost_usd=25_000,
            evidence_refs=["ev_auditlog_contract"],
        ),
        Entity(
            id="ctl_soc2_audit_logging",
            type=EntityType.control,
            name="SOC2 audit logging",
            department_id="dept_compliance",
            criticality=Criticality.critical,
            mandatory=True,
            framework="SOC2",
        ),
        Entity(
            id="sys_cloud_platform",
            type=EntityType.system,
            name="Cloud platform",
            department_id="dept_engineering",
            criticality=Criticality.critical,
            annual_cost_usd=1_600_000,
            failure_cost_per_day_usd=120_000,
        ),
        Entity(
            id="proj_warehouse_migration",
            type=EntityType.project,
            name="Warehouse migration",
            department_id="dept_engineering",
            annual_cost_usd=450_000,
            completion_pct=0.35,
            remaining_cost_usd=290_000,
            expected_completion_day=210,
        ),
    ]


def _edge(edge_id: str, source: str, target: str, relation: Relation, strength: float, criticality: Criticality,
          evidence_refs: list[str], channel_kind: ChannelKind | None = None, lag_days: int = 0) -> Edge:
    return Edge(
        id=edge_id,
        source=source,
        target=target,
        relation=relation,
        channel_kind=channel_kind,
        strength=strength,
        substitutability=0.2,
        lag_days=lag_days,
        criticality=criticality,
        confidence=0.8,
        evidence_refs=evidence_refs,
    )


def _edges() -> list[Edge]:
    return [
        _edge("ch_operations_compliance_evidence", "dept_operations", "dept_compliance", Relation.FLOWS_TO, 0.7,
              Criticality.high, ["ev_auditlog_contract"], ChannelKind.constraint),
        _edge("ch_sales_marketing_launch", "dept_sales", "dept_marketing", Relation.FLOWS_TO, 0.4,
              Criticality.medium, [], ChannelKind.signal, lag_days=14),
        _edge("e_role_owns_billing_recon", "role_billing_ops_lead", "wf_billing_recon", Relation.OWNS, 0.9,
              Criticality.critical, ["ev_billing_recon_matrix"]),
        _edge("e_billing_recon_kpi", "wf_billing_recon", "kpi_company", Relation.CONTRIBUTES_TO, 0.6,
              Criticality.high, ["ev_billing_recon_matrix"], lag_days=30),
        _edge("e_auditlog_supports_soc2", "vendor_auditlog", "ctl_soc2_audit_logging", Relation.SUPPORTS, 0.8,
              Criticality.critical, ["ev_auditlog_contract"]),
        _edge("e_cloud_supports_kpi", "sys_cloud_platform", "kpi_company", Relation.SUPPORTS, 0.7,
              Criticality.critical, ["ev_ops_incident_log"]),
    ]


def stub_pressures() -> list[Pressure]:
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
            evidence_refs=["ev_auditlog_contract"],
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
            evidence_refs=["ev_billing_recon_matrix"],
            description="Undocumented billing reconciliation can fail.",
        ),
    ]


def _documents() -> list[Document]:
    return [
        Document(
            id="doc_runbook_billing_recon",
            title="Billing reconciliation runbook",
            doc_type=DocumentType.runbook,
            department_id="dept_operations",
            owner_role_id="role_billing_ops_lead",
            uri="data/artifacts/doc_runbook_billing_recon.md",
            mime_type="text/markdown",
            status=DocumentStatus.outdated,
            last_reviewed=date(2025, 3, 10),
            review_cycle_days=180,
            covers_entity_ids=["wf_billing_recon"],
            framework_refs=["SOC2"],
            summary="Steps to reconcile billing records each month.",
            uploaded_at=STUB_TIME,
        ),
        Document(
            id="doc_contract_auditlog",
            title="Audit log vendor contract",
            doc_type=DocumentType.contract,
            department_id="dept_operations",
            uri="data/artifacts/doc_contract_auditlog.md",
            mime_type="text/markdown",
            status=DocumentStatus.current,
            last_reviewed=date(2026, 1, 15),
            review_cycle_days=365,
            covers_entity_ids=["vendor_auditlog", "ctl_soc2_audit_logging"],
            framework_refs=["SOC2"],
            summary="Annual audit log retention contract with a renewal price step.",
            uploaded_at=STUB_TIME,
        ),
    ]


def _evidence() -> list[Evidence]:
    return [
        Evidence(
            id="ev_ops_incident_log",
            source_type=EvidenceSource.activity_log,
            document_id="doc_runbook_billing_recon",
            location="Incident history",
            snippet="Operations resolved every platform incident in the last two quarters within the target window.",
        ),
        Evidence(
            id="ev_billing_recon_matrix",
            source_type=EvidenceSource.knowledge_matrix,
            document_id="doc_runbook_billing_recon",
            location="Section 2",
            snippet="Only the billing operations lead can complete the month-end reconciliation unaided.",
        ),
        Evidence(
            id="ev_auditlog_contract",
            source_type=EvidenceSource.contract,
            document_id="doc_contract_auditlog",
            location="Clause 4",
            snippet="The audit log vendor stores the SOC2 audit trail; renewal adds a 12 percent price step.",
        ),
    ]


def stub_twin() -> Twin:
    return Twin(
        version=VersionInfo(
            twin_version=TWIN_VERSION,
            settings_version=1,
            prompt_version="stub",
            model_id="stub",
            engine_version="stub",
            created_at=STUB_TIME,
            as_of_date=date(2026, 9, 26),
        ),
        organization=Organization(
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
        ),
        department_profiles=[_profile(*row) for row in DEPARTMENTS],
        entities=_entities(),
        edges=_edges(),
        pressures=stub_pressures(),
        documents=_documents(),
        evidence=_evidence(),
    )


def _constraint(cid: str, metric: str, operator: str, threshold: float, hard: bool) -> Constraint:
    return Constraint(
        id=cid,
        metric=metric,  # type: ignore[arg-type]
        operator=operator,  # type: ignore[arg-type]
        threshold=threshold,
        unit="pct" if metric.endswith("_pct") else "count",
        hard=hard,
        description=f"{metric} {operator} {threshold:g}",
    )


def sample_brief() -> DecisionBrief:
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
            _constraint("c_compliance", "compliance_controls_broken", "==", 0, True),
            _constraint("c_critical", "critical_systems_degraded", "==", 0, True),
            _constraint("c_revenue", "revenue_impact_pct", "<=", 3, True),
            _constraint("c_stranded", "stranded_workflows", "==", 0, False),
        ],
        futures=[Future.act_now, Future.inaction, Future.delay],
        delay_days=90,
        active_pressure_ids=["pr_cloud_growth", "pr_auditlog_renewal", "pr_billing_recon_hazard"],
        seed=42,
        mc_samples=1000,
        created_by="demo_user",
    )
