"""Stub Northstar twin and briefs. Every ID comes from the team ID registry; the numbers are fixed stub values."""

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
    StrategicPriority,
    Twin,
    VersionInfo,
)

STUB_TIME = datetime(2026, 9, 26, 17, 0, tzinfo=timezone.utc)
TWIN_VERSION = "stub-northstar-1"
VENDOR_DECISION = "dec_vendor_reduction"
WORKFORCE_DECISION = "dec_workforce_knowledge"

# department_id, name, mission, annual budget, actual fte, sanctioned fte, contractors, utilisation
DEPARTMENTS = [
    ("dept_finance", "Finance", "Budget, cost targets, vendor contracts and the monthly close.",
     2_000_000_000, 2_400, 2_500, 60, 0.95),
    ("dept_engineering", "Engineering", "Core platform, customer portal, billing platform and release quality.",
     14_000_000_000, 9_800, 10_200, 400, 1.04),
    ("dept_ai_data", "AI and Data", "Data pipeline, ML scoring, warehouse and analytics.",
     10_000_000_000, 3_600, 3_800, 150, 1.08),
    ("dept_operations", "Operations", "Billing operations, incident response, vendor reconciliation and risk monitoring.",
     6_000_000_000, 5_200, 5_500, 600, 1.12),
    ("dept_product", "Product", "Roadmap, releases, product analytics and transformation projects.",
     4_000_000_000, 2_600, 2_700, 40, 0.92),
    ("dept_marketing", "Marketing", "Demand generation, campaign targeting and attribution.",
     7_000_000_000, 3_400, 3_500, 120, 0.9),
    ("dept_sales", "Sales", "Pipeline, lead scoring, account planning and enterprise selling.",
     9_000_000_000, 7_800, 8_100, 0, 0.94),
    ("dept_customer_success", "Customer Success", "Onboarding, escalation, SLAs and retention.",
     5_000_000_000, 5_000, 5_200, 200, 1.01),
    ("dept_compliance", "Compliance", "Controls, KYC screening, audit evidence and privacy.",
     3_000_000_000, 2_200, 2_300, 30, 0.98),
]

# vendor_id, name, annual cost, one-time exit cost, evidence
VENDORS = [
    ("vendor_apex", "ApexData", 1_600_000_000, 60_000_000, "ev_apex_msa_renewal"),
    ("vendor_beacon", "BeaconIQ", 1_200_000_000, 45_000_000, "ev_beacon_msa_terms"),
    ("vendor_cinder", "CinderSignals", 1_400_000_000, 50_000_000, "ev_cinder_msa_terms"),
    ("vendor_delta", "DeltaVerify", 900_000_000, 35_000_000, "ev_delta_msa_terms"),
    ("vendor_echo", "EchoMarket", 1_100_000_000, 40_000_000, "ev_echo_msa_clause_9"),
    ("vendor_flux", "FluxBehavior", 800_000_000, 20_000_000, "ev_flux_usage_pricing"),
    ("vendor_granite", "GraniteGeo", 1_000_000_000, 30_000_000, "ev_granite_msa_terms"),
]

# dataset_id, name, criticality
DATASETS = [
    ("ds_firmographics", "Firmographics", Criticality.medium),
    ("ds_contact_data", "Contact data", Criticality.medium),
    ("ds_corporate_linkage", "Corporate linkage", Criticality.critical),
    ("ds_intent_signals", "Intent signals", Criticality.high),
    ("ds_identity_verification", "Identity verification", Criticality.critical),
    ("ds_market_intel", "Market intelligence", Criticality.medium),
    ("ds_account_intel", "Account intelligence", Criticality.medium),
    ("ds_usage", "Product usage signals", Criticality.medium),
    ("ds_geo_risk", "Geographic and macroeconomic risk", Criticality.medium),
]

# role_id, name, department, annual cost; the first eight are the workforce brief's roles
ROLES = [
    ("role_close_accountant", "Close Accountant", "dept_finance", 140_000),
    ("role_gl_accountant", "General Ledger Accountant", "dept_finance", 130_000),
    ("role_reporting_analyst", "Financial Reporting Analyst", "dept_finance", 120_000),
    ("role_data_platform_lead", "Data Platform Lead", "dept_ai_data", 190_000),
    ("role_billing_ops_lead", "Billing Operations Lead", "dept_operations", 150_000),
    ("role_billing_specialist", "Billing Specialist", "dept_operations", 110_000),
    ("role_revenue_accountant", "Revenue Accountant", "dept_finance", 125_000),
    ("role_ar_specialist", "Accounts Receivable Specialist", "dept_finance", 105_000),
    ("role_finance_analyst", "Finance Analyst", "dept_finance", 115_000),
    ("role_controller", "Controller", "dept_finance", 210_000),
    ("role_grc_lead", "GRC Lead", "dept_compliance", 180_000),
]
WORKFORCE_ROLES = [r[0] for r in ROLES[:8]]

# channel_id, source, target, kind, label
CHANNELS = [
    ("ch_finance_engineering_budget", "dept_finance", "dept_engineering", ChannelKind.budget, "budget limits"),
    ("ch_finance_marketing_budget", "dept_finance", "dept_marketing", ChannelKind.budget, "budget limits"),
    ("ch_finance_operations_cost", "dept_finance", "dept_operations", ChannelKind.budget, "cost targets"),
    ("ch_finance_sales_revenue", "dept_finance", "dept_sales", ChannelKind.budget, "revenue targets"),
    ("ch_ai_data_engineering_models", "dept_ai_data", "dept_engineering", ChannelKind.capability, "models and data"),
    ("ch_ai_data_marketing_scores", "dept_ai_data", "dept_marketing", ChannelKind.capability, "scores and segments"),
    ("ch_engineering_product_features", "dept_engineering", "dept_product", ChannelKind.capability,
     "features and platforms"),
    ("ch_engineering_operations_automation", "dept_engineering", "dept_operations", ChannelKind.capability,
     "automation"),
    ("ch_operations_engineering_incidents", "dept_operations", "dept_engineering", ChannelKind.signal,
     "incidents and capacity"),
    ("ch_product_sales_roadmap", "dept_product", "dept_sales", ChannelKind.signal, "roadmap and releases"),
    ("ch_product_cs_product", "dept_product", "dept_customer_success", ChannelKind.signal, "product changes"),
    ("ch_marketing_sales_qualified", "dept_marketing", "dept_sales", ChannelKind.value, "qualified leads"),
    ("ch_sales_product_customer", "dept_sales", "dept_product", ChannelKind.signal, "customer demand"),
    ("ch_sales_cs_commitments", "dept_sales", "dept_customer_success", ChannelKind.signal, "commitments"),
    ("ch_cs_product_feedback", "dept_customer_success", "dept_product", ChannelKind.signal,
     "feedback and churn signals"),
    ("ch_compliance_ai_data_controls", "dept_compliance", "dept_ai_data", ChannelKind.constraint, "controls"),
    ("ch_compliance_engineering_policies", "dept_compliance", "dept_engineering", ChannelKind.constraint, "policies"),
    ("ch_compliance_operations_process", "dept_compliance", "dept_operations", ChannelKind.constraint,
     "process controls"),
    ("ch_finance_kpi_profitability", "dept_finance", "kpi_company", ChannelKind.value, "profitability"),
    ("ch_marketing_kpi_acquisition", "dept_marketing", "kpi_company", ChannelKind.value, "acquisition cost"),
    ("ch_sales_kpi_pipeline", "dept_sales", "kpi_company", ChannelKind.value, "pipeline"),
    ("ch_product_kpi_delivery", "dept_product", "kpi_company", ChannelKind.value, "delivery"),
    ("ch_cs_kpi_retention", "dept_customer_success", "kpi_company", ChannelKind.value, "retention"),
    ("ch_sales_marketing_launch", "dept_sales", "dept_marketing", ChannelKind.signal, "launch timing"),
    ("ch_operations_compliance_evidence", "dept_operations", "dept_compliance", ChannelKind.constraint,
     "control evidence"),
]

# document_id, title, type, department, status, covers, evidence rows (id, source, location, snippet)
DOCUMENTS = [
    ("doc_department_map", "Department operating-model map", DocumentType.architecture_note, None,
     DocumentStatus.current, [], [
         ("ev_department_map_v1", EvidenceSource.architecture_note, "Channel table",
          "The 25 department channels, their labels and kinds."),
     ]),
    ("doc_procurement_register", "Vendor and procurement register", DocumentType.contract, "dept_finance",
     DocumentStatus.current, [v[0] for v in VENDORS], []),
    ("doc_apex_msa", "ApexData master services agreement", DocumentType.contract, "dept_finance",
     DocumentStatus.current, ["vendor_apex"], [
         ("ev_apex_msa_renewal", EvidenceSource.contract, "Renewal clause",
          "ApexData auto-renews on day 60 with an 8% price uplift."),
     ]),
    ("doc_beacon_msa", "BeaconIQ master services agreement", DocumentType.contract, "dept_finance",
     DocumentStatus.current, ["vendor_beacon"], [
         ("ev_beacon_msa_terms", EvidenceSource.contract, "Term and exit", "BeaconIQ term end, notice period and exit fee."),
     ]),
    ("doc_cinder_msa", "CinderSignals master services agreement", DocumentType.contract, "dept_finance",
     DocumentStatus.current, ["vendor_cinder"], [
         ("ev_cinder_msa_terms", EvidenceSource.contract, "Licence",
          "CinderSignals is the exclusive licensed source of intent signals."),
     ]),
    ("doc_delta_msa", "DeltaVerify master services agreement", DocumentType.contract, "dept_finance",
     DocumentStatus.current, ["vendor_delta"], [
         ("ev_delta_msa_terms", EvidenceSource.contract, "Term and exit", "DeltaVerify term end, notice period and exit fee."),
     ]),
    ("doc_echo_msa", "EchoMarket master services agreement", DocumentType.contract, "dept_finance",
     DocumentStatus.current, ["vendor_echo"], [
         ("ev_echo_msa_clause_9", EvidenceSource.contract, "Clause 9",
          "EchoMarket renews on day 120 with a 12% price uplift."),
     ]),
    ("doc_flux_msa", "FluxBehavior master services agreement", DocumentType.contract, "dept_finance",
     DocumentStatus.current, ["vendor_flux"], [
         ("ev_flux_usage_pricing", EvidenceSource.contract, "Pricing", "FluxBehavior is billed per record consumed."),
     ]),
    ("doc_granite_msa", "GraniteGeo master services agreement", DocumentType.contract, "dept_finance",
     DocumentStatus.current, ["vendor_granite"], [
         ("ev_granite_msa_terms", EvidenceSource.contract, "Term and exit", "GraniteGeo term end, notice period and exit fee."),
     ]),
    ("doc_data_vendor_inventory", "External data vendor inventory", DocumentType.architecture_note, "dept_ai_data",
     DocumentStatus.current, [d[0] for d in DATASETS], [
         ("ev_vendor_dataset_matrix", EvidenceSource.architecture_note, "Feed matrix",
          "Vendor-to-dataset feed matrix with attribute groups and consuming workflows."),
     ]),
    ("doc_kyc_screening_sop", "KYC screening SOP", DocumentType.sop, "dept_compliance", DocumentStatus.current,
     ["wf_kyc_screening", "ds_corporate_linkage", "ds_identity_verification"], [
         ("ev_kyc_screening_inputs", EvidenceSource.policy, "Inputs",
          "KYC screening reads the Identity verification dataset and the Corporate linkage dataset."),
     ]),
    ("doc_vendor_recon_workflow_map", "Vendor reconciliation workflow map", DocumentType.workflow_map,
     "dept_operations", DocumentStatus.current, ["wf_vendor_reconciliation"], [
         ("ev_echo_account_intel_feed", EvidenceSource.workflow_map, "Monthly inputs",
          "The Account intelligence dataset also feeds the Vendor reconciliation workflow each month."),
     ]),
    ("doc_billing_recon_runbook", "Billing reconciliation runbook", DocumentType.runbook, "dept_operations",
     DocumentStatus.outdated, ["wf_billing_recon"], [
         ("ev_billing_runbook_gap", EvidenceSource.runbook, "Exceptions",
          "The exception path is undocumented; only the billing owners can resolve a failed run."),
     ]),
    ("doc_knowledge_matrix", "Role knowledge matrix", DocumentType.knowledge_matrix, "dept_operations",
     DocumentStatus.current, ["kn_billing_exception", "kn_warehouse_lineage"], [
         ("ev_knowledge_matrix_billing", EvidenceSource.knowledge_matrix, "Billing",
          "Billing reconciliation know-how is concentrated in two roles."),
         ("ev_knowledge_matrix_3", EvidenceSource.knowledge_matrix, "Warehouse",
          "Warehouse lineage is held by one role and is about 20% documented."),
     ]),
    ("doc_sop_financial_close", "Monthly financial close SOP", DocumentType.sop, "dept_finance",
     DocumentStatus.current, ["wf_financial_close"], [
         ("ev_sop_financial_close_lineage", EvidenceSource.policy, "Lineage",
          "The monthly close SOP defers warehouse lineage questions to the Data Platform Lead."),
     ]),
]


def _profile(department_id: str, name: str, mission: str, budget: int, actual: float, sanctioned: float,
             contractors: float, utilisation: float) -> DepartmentProfile:
    key_roles = [r[0] for r in ROLES if r[2] == department_id][:2]
    return DepartmentProfile(
        department_id=department_id,
        mission=mission,
        agent_id=department_id.removeprefix("dept_"),
        staffing=StaffingStrength(
            sanctioned_fte=sanctioned,
            actual_fte=actual,
            contractors_fte=contractors,
            open_positions=20,
            attrition_rate_annual=0.12,
            avg_time_to_hire_days=45,
            utilisation=utilisation,
        ),
        budget=DepartmentBudget(annual_budget_usd=budget, spent_ytd_usd=0, fixed_cost_pct=0.35),
        strengths=[
            DepartmentStrength(
                # The registry has no strength IDs, so the stub derives one per department.
                id=f"str_{department_id.removeprefix('dept_')}_core",
                name=f"{name} core practice",
                category=StrengthCategory.capability,
                level=3,
                key_role_ids=key_roles,
                concentration=0.3,
            )
        ],
        maturity_level=3,
        critical_workflow_ids=[w for w, _, d, *_ in WORKFLOWS if d == department_id],
        kpi_ids=["kpi_company"],
        document_ids=[d[0] for d in DOCUMENTS if d[3] == department_id],
    )


# workflow_id, name, department, criticality, min owners, failure cost per day, documented, evidence
WORKFLOWS = [
    ("wf_kyc_screening", "KYC screening", "dept_compliance", Criticality.critical, 1, 5_000_000, 0.7,
     ["ev_kyc_screening_inputs"]),
    ("wf_account_planning", "Account planning", "dept_sales", Criticality.medium, 1, 400_000, 0.6, []),
    ("wf_lead_scoring", "Lead scoring", "dept_sales", Criticality.high, 1, 900_000, 0.6, []),
    ("wf_vendor_reconciliation", "Vendor reconciliation", "dept_operations", Criticality.high, 1, 1_300_000, 0.5,
     ["ev_echo_account_intel_feed"]),
    ("wf_billing_recon", "Billing reconciliation", "dept_operations", Criticality.critical, 2, 2_000_000, 0.35,
     ["ev_billing_runbook_gap", "ev_knowledge_matrix_billing"]),
    ("wf_financial_close", "Monthly financial close", "dept_finance", Criticality.critical, 2, 1_500_000, 0.4,
     ["ev_sop_financial_close_lineage"]),
]


def _entities() -> list[Entity]:
    entities = [
        Entity(id=d, type=EntityType.department, name=n, annual_cost_usd=b, capacity_fte=a, criticality=Criticality.high)
        for d, n, _, b, a, _, _, _ in DEPARTMENTS
    ]
    entities += [
        Entity(id="kpi_company", type=EntityType.kpi, name="Company KPIs", criticality=Criticality.critical,
               kpi_baseline=100, kpi_unit="index", higher_is_better=True),
        Entity(id="kpi_pipeline", type=EntityType.kpi, name="Qualified pipeline", department_id="dept_sales",
               criticality=Criticality.high, kpi_baseline=4_500_000_000, kpi_unit="usd", higher_is_better=True),
        Entity(id="kpi_close_cycle_days", type=EntityType.kpi, name="Close cycle days", department_id="dept_finance",
               kpi_baseline=6.5, kpi_unit="days", higher_is_better=False),
    ]
    entities += [
        Entity(id=v, type=EntityType.vendor, name=n, department_id="dept_ai_data", criticality=Criticality.high,
               annual_cost_usd=cost, one_time_exit_cost_usd=exit_cost, evidence_refs=[ev])
        for v, n, cost, exit_cost, ev in VENDORS
    ]
    entities += [
        Entity(id=d, type=EntityType.dataset, name=n, department_id="dept_ai_data", criticality=c,
               evidence_refs=["ev_vendor_dataset_matrix"])
        for d, n, c in DATASETS
    ]
    entities.append(Entity(id="ds_audit_log", type=EntityType.dataset, name="Audit-log event stream",
                           department_id="dept_compliance", criticality=Criticality.critical))
    entities += [
        Entity(id="sys_audit_service", type=EntityType.system, name="audit-log-service", department_id="dept_engineering",
               criticality=Criticality.high, annual_cost_usd=40_000_000, failure_cost_per_day_usd=3_000_000),
        Entity(id="sys_cloud_platform", type=EntityType.system, name="cloud-platform", department_id="dept_engineering",
               criticality=Criticality.critical, annual_cost_usd=900_000_000, failure_cost_per_day_usd=20_000_000),
    ]
    entities += [
        Entity(id=w, type=EntityType.workflow, name=n, department_id=d, criticality=c, min_qualified_owners=m,
               failure_cost_per_day_usd=f, documented_pct=doc, evidence_refs=ev)
        for w, n, d, c, m, f, doc, ev in WORKFLOWS
    ]
    entities += [
        Entity(id="ctl_kyc_screening", type=EntityType.control, name="KYC screening control",
               department_id="dept_compliance", criticality=Criticality.critical, mandatory=True, framework="SOX",
               evidence_refs=["ev_kyc_screening_inputs"]),
        Entity(id="ctl_sox_reconciliation", type=EntityType.control, name="SOX vendor-spend reconciliation",
               department_id="dept_compliance", criticality=Criticality.critical, mandatory=True, framework="SOX"),
        Entity(id="ctl_soc2_audit_logging", type=EntityType.control, name="SOC 2 CC7.2 audit logging",
               department_id="dept_compliance", criticality=Criticality.critical, mandatory=True, framework="SOC2"),
    ]
    entities += [
        Entity(id=r, type=EntityType.role, name=n, department_id=d, annual_cost_usd=cost, capacity_fte=1,
               criticality=Criticality.high if r in WORKFORCE_ROLES else Criticality.medium)
        for r, n, d, cost in ROLES
    ]
    entities += [
        Entity(id="kn_billing_exception", type=EntityType.knowledge_asset, name="Billing-recon exception handling",
               department_id="dept_operations", criticality=Criticality.critical, documented_pct=0.35,
               evidence_refs=["ev_knowledge_matrix_billing"]),
        Entity(id="kn_warehouse_lineage", type=EntityType.knowledge_asset, name="Warehouse lineage knowledge",
               department_id="dept_ai_data", criticality=Criticality.critical, documented_pct=0.2,
               evidence_refs=["ev_knowledge_matrix_3"]),
    ]
    return entities


def _edges() -> list[Edge]:
    return [
        Edge(id=cid, source=source, target=target, relation=Relation.FLOWS_TO, label=label, channel_kind=kind,
             strength=0.6, substitutability=0.3, lag_days=0 if kind is ChannelKind.constraint else 14,
             criticality=Criticality.medium, confidence=0.8, evidence_refs=["ev_department_map_v1"])
        for cid, source, target, kind, label in CHANNELS
    ]


def stub_pressures() -> list[Pressure]:
    return [
        Pressure(id="pr_apex_renewal", kind=PressureKind.renewal_step, name="ApexData renewal uplift",
                 target_entity_id="vendor_apex", start_day=60, step_pct=8,
                 neutralised_by=[NeutraliserRef(intervention_type=ActionType.remove_vendor, target_entity_id="vendor_apex")],
                 evidence_refs=["ev_apex_msa_renewal"], description="ApexData auto-renews at +8% on day 60."),
        Pressure(id="pr_echo_renewal", kind=PressureKind.renewal_step, name="EchoMarket renewal uplift",
                 target_entity_id="vendor_echo", start_day=120, step_pct=12,
                 neutralised_by=[NeutraliserRef(intervention_type=ActionType.remove_vendor, target_entity_id="vendor_echo")],
                 evidence_refs=["ev_echo_msa_clause_9"], description="EchoMarket renews at +12% on day 120."),
        Pressure(id="pr_flux_usage_growth", kind=PressureKind.cost_growth, name="FluxBehavior usage growth",
                 target_entity_id="vendor_flux", rate=0.015, rate_range=(0.01, 0.02),
                 neutralised_by=[NeutraliserRef(intervention_type=ActionType.remove_vendor, target_entity_id="vendor_flux")],
                 evidence_refs=["ev_flux_usage_pricing"], description="Flux usage costs grow about 1.5% a month."),
        Pressure(id="pr_vendor_recon_hazard", kind=PressureKind.hazard, name="Vendor reconciliation failure",
                 target_entity_id="wf_vendor_reconciliation", monthly_probability=0.03, probability_range=(0.02, 0.04),
                 cost_per_event_usd=40_000_000, capacity_sensitivity=2.5,
                 description="A failed vendor reconciliation costs about $40M to correct."),
        Pressure(id="pr_billing_recon_hazard", kind=PressureKind.hazard, name="Billing reconciliation failure",
                 target_entity_id="wf_billing_recon", monthly_probability=0.04, probability_range=(0.02, 0.06),
                 cost_per_event_usd=60_000_000, capacity_sensitivity=3.0,
                 neutralised_by=[NeutraliserRef(intervention_type=MitigationType.document_runbook,
                                                target_entity_id="wf_billing_recon")],
                 evidence_refs=["ev_billing_runbook_gap"], description="A failed billing reconciliation costs about $60M."),
        Pressure(id="pr_lineage_holder_attrition", kind=PressureKind.hazard, name="Warehouse lineage holder leaves",
                 target_entity_id="kn_warehouse_lineage", monthly_probability=0.03, probability_range=(0.02, 0.04),
                 cost_per_event_usd=45_000_000, capacity_sensitivity=2.0,
                 neutralised_by=[NeutraliserRef(intervention_type=MitigationType.document_runbook,
                                                target_entity_id="kn_warehouse_lineage")],
                 evidence_refs=["ev_knowledge_matrix_3"], description="Losing the only lineage holder costs about $45M."),
        Pressure(id="pr_contractor_cost_growth", kind=PressureKind.cost_growth, name="Operations contractor rates",
                 target_entity_id="dept_operations", rate=0.01, rate_range=(0.005, 0.015),
                 description="Operations contractor rates grow about 1% a month."),
    ]


def _documents() -> list[Document]:
    return [
        Document(id=doc_id, title=title, doc_type=doc_type, department_id=department, uri=f"data/artifacts/{doc_id}.md",
                 mime_type="text/markdown", status=status, last_reviewed=date(2026, 1, 15), review_cycle_days=365,
                 covers_entity_ids=covers, summary=f"{title}.", uploaded_at=STUB_TIME)
        for doc_id, title, doc_type, department, status, covers, _ in DOCUMENTS
    ]


def _evidence() -> list[Evidence]:
    return [
        Evidence(id=ev_id, source_type=source, document_id=doc_id, location=location, snippet=snippet)
        for doc_id, *_, rows in DOCUMENTS
        for ev_id, source, location, snippet in rows
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
            id="org_northstar",
            legal_name="Northstar Technologies, Inc.",
            display_name="Northstar Technologies",
            sector=Sector.technology_saas,
            business_model=BusinessModel.b2b,
            size_band=SizeBand.large_enterprise,
            headquarters_country="US",
            operating_regions=["US", "EU", "APAC"],
            annual_revenue_usd=120_000_000_000,
            total_annual_budget_usd=60_000_000_000,
            total_headcount_fte=42_000,
            fiscal_year_start_month=1,
            regulatory_frameworks=["SOC2", "GDPR", "PCI_DSS", "SOX"],
            strategic_priorities=[
                StrategicPriority(id="sp_retention", text="Protect enterprise retention", rank=1),
                StrategicPriority(id="sp_margin", text="Expand gross margin by two points", rank=2),
            ],
            description="Synthetic large-enterprise B2B software company (stub twin).",
            evidence_refs=["ev_department_map_v1"],
        ),
        department_profiles=[_profile(*row) for row in DEPARTMENTS],
        entities=_entities(),
        edges=_edges(),
        pressures=stub_pressures(),
        documents=_documents(),
        evidence=_evidence(),
    )


def _constraint(cid: str, metric: str, operator: str, threshold: float, unit: str, hard: bool, description: str,
                scope: str | None = None) -> Constraint:
    return Constraint(id=cid, metric=metric, operator=operator, threshold=threshold, unit=unit,  # type: ignore[arg-type]
                      hard=hard, scope_entity_id=scope, description=description)


def _remove(intervention_id: str, target: str, action: ActionType, one_time_cost: int = 0,
            rationale: str = "Candidate for consolidation") -> Intervention:
    return Intervention(id=intervention_id, kind=InterventionKind.action, type=action, target_entity_id=target,
                        start_day=30, one_time_cost_usd=one_time_cost, rationale=rationale)


def sample_brief() -> DecisionBrief:
    return DecisionBrief(
        decision_id=VENDOR_DECISION,
        decision_type=DecisionType.vendor_consolidation,
        title="Consolidate external data vendors",
        statement="Reduce annual external-data spending from $8B to no more than $6B without breaking compliance, "
                  "reducing critical data coverage below 100%, reducing sales performance by more than 3%, or "
                  "creating unacceptable customer impact.",
        goal=Goal(metric="annual_savings_usd", target=2_000_000_000, basis="gross", direction="at_least"),
        horizon_days=365,
        candidate_interventions=[
            _remove(f"remove_{v.removeprefix('vendor_')}", v, ActionType.remove_vendor) for v, *_ in VENDORS
        ],
        constraints=[
            _constraint("c_compliance", "compliance_controls_broken", "==", 0, "count", True,
                        "No mandatory control may break"),
            _constraint("c_sales", "revenue_impact_pct", "<=", 3, "percent", True,
                        "Sales performance falls by no more than 3%", scope="kpi_pipeline"),
            _constraint("c_customer", "customer_impact_pct", "<=", 2, "percent", True, "Customer impact within 2%"),
            _constraint("c_stranded", "stranded_workflows", "==", 0, "count", False, "Prefer no stranded workflows"),
        ],
        futures=[Future.act_now, Future.inaction, Future.delay],
        delay_days=90,
        active_pressure_ids=["pr_apex_renewal", "pr_echo_renewal", "pr_flux_usage_growth", "pr_vendor_recon_hazard"],
        seed=42,
        mc_samples=1000,
        created_by="demo_user",
    )


WORKFORCE_ONE_TIME_COSTS = {
    "role_close_accountant": 40_000,
    "role_gl_accountant": 40_000,
    "role_reporting_analyst": 30_000,
    "role_data_platform_lead": 60_000,
    "role_billing_ops_lead": 50_000,
    "role_billing_specialist": 30_000,
    "role_revenue_accountant": 40_000,
    "role_ar_specialist": 30_000,
}


def workforce_brief() -> DecisionBrief:
    return DecisionBrief(
        decision_id=WORKFORCE_DECISION,
        decision_type=DecisionType.restructure,
        title="Eliminate eight staff roles",
        statement="Evaluate the operational consequences of eliminating eight staff roles that currently support "
                  "two workflows.",
        goal=Goal(metric="annual_savings_usd", target=1_070_000, basis="gross", direction="at_least"),
        horizon_days=365,
        candidate_interventions=[
            _remove(f"remove_{role.removeprefix('role_')}", role, ActionType.remove_roles,
                    WORKFORCE_ONE_TIME_COSTS[role], "Role elimination under review")
            for role in WORKFORCE_ROLES
        ],
        constraints=[
            _constraint("c_compliance", "compliance_controls_broken", "==", 0, "count", True,
                        "No mandatory control may break"),
            _constraint("c_stranded", "stranded_workflows", "==", 0, "count", True,
                        "Every critical workflow keeps its minimum qualified owners"),
            _constraint("c_customer", "customer_impact_pct", "<=", 2, "percent", True, "Customer impact within 2%"),
        ],
        futures=[Future.act_now, Future.inaction, Future.delay],
        delay_days=90,
        active_pressure_ids=["pr_billing_recon_hazard", "pr_lineage_holder_attrition", "pr_contractor_cost_growth"],
        seed=42,
        mc_samples=1000,
        created_by="demo_user",
    )
