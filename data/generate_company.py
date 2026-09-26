"""Generate the Halcyon Freight company twin — conformant to Merged Schema v2.0.0.

Deterministic, standard-library only. Emits ``data/synthetic_company.json`` as a full
v2 ``Twin``: schema_version, version, organization, department_profiles, entities, edges,
pressures, documents, evidence.

Run:  python3 data/generate_company.py

Conformance highlights (see docs / CANARY_PACT_SCHEMA_v2_merged):
* R1 department set: dept_finance, dept_engineering, dept_ai_data, dept_operations,
  dept_product, dept_marketing, dept_sales, dept_customer_success, dept_compliance.
  Platform/Infra Ops -> dept_operations; vendor contracts -> dept_finance; projects -> dept_product.
* v2 EntityType (person_token, role, knowledge_asset, customer_segment; no team/employee/document-entity).
* Edges use strength / strength_range / lag_days / evidence_refs; FLOWS_TO channels carry channel_kind.
* R13 pressures: one cost_growth, one renewal_step, one hazard with capacity_sensitivity > 0.
* Money = integer USD. IDs = snake_case with the v2 prefixes.

The four planted decisions (v2 example ids):
  i_platform_ops : reduce_capacity dept_operations 20%  -> billing-recon loses owners (stranded)
  i_auditlog     : remove_vendor  vendor_auditlog        -> ds_audit_log gone -> SOC2 control broken
  i_migration    : stop_project   proj_warehouse_migration -> warehouse-legacy carry cost (rebound)
  i_eng          : reduce_capacity dept_engineering 10%  -> core-api maintenance -> uptime/customer

All data is synthetic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.0.0"
CREATED_AT = "2026-09-26T12:00:00Z"

REVENUE_USD = 40_000_000
TOTAL_BUDGET_USD = 8_000_000            # == sum of department budgets (rule 16)
SAVINGS_TARGET_USD = 2_000_000

entities: list[dict[str, Any]] = []
edges: list[dict[str, Any]] = []
pressures: list[dict[str, Any]] = []
documents: list[dict[str, Any]] = []
evidence: list[dict[str, Any]] = []
department_profiles: list[dict[str, Any]] = []


# --------------------------------------------------------------------------- helpers
def ent(id: str, type: str, name: str, *, department_id: str | None = None,
        criticality: str = "medium", sensitivity: str = "general", **fields: Any) -> str:
    rec: dict[str, Any] = {"id": id, "type": type, "name": name,
                           "criticality": criticality, "sensitivity": sensitivity}
    if department_id is not None:
        rec["department_id"] = department_id
    for k, v in fields.items():
        if v is not None:
            rec[k] = v
    rec.setdefault("tags", [])
    rec.setdefault("evidence_refs", [])
    entities.append(rec)
    return id


def edge(id: str, source: str, target: str, relation: str, *, strength: float,
         substitutability: float = 0.3, lag_days: int = 0, criticality: str = "medium",
         confidence: float = 0.9, label: str | None = None, channel_kind: str | None = None,
         evidence_refs: list[str] | None = None, strength_range: list[float] | None = None) -> None:
    if strength_range is None:
        strength_range = [round(strength * 0.7, 3), round(min(1.0, strength * 1.3), 3)]
    rec: dict[str, Any] = {
        "id": id, "source": source, "target": target, "relation": relation,
        "strength": strength, "strength_range": strength_range,
        "substitutability": substitutability, "lag_days": lag_days,
        "criticality": criticality, "confidence": confidence,
        "evidence_refs": evidence_refs or [],
    }
    if label is not None:
        rec["label"] = label
    if channel_kind is not None:
        rec["channel_kind"] = channel_kind
    edges.append(rec)


def chan(id: str, source: str, target: str, label: str, channel_kind: str) -> None:
    edge(id, source, target, "FLOWS_TO", strength=0.5, strength_range=[0.3, 0.7],
         substitutability=0.3, lag_days=30, criticality="medium", confidence=0.9,
         label=label, channel_kind=channel_kind, evidence_refs=["ev_department_map_v1"])


def doc(id: str, title: str, doc_type: str, *, department_id: str | None, status: str,
        covers: list[str], summary: str, framework_refs: list[str] | None = None,
        owner_role_id: str | None = None) -> str:
    documents.append({
        "id": id, "title": title, "doc_type": doc_type, "department_id": department_id,
        "owner_role_id": owner_role_id, "uri": f"artifacts/{id}.md", "mime_type": "text/markdown",
        "status": status, "sensitivity": "general", "covers_entity_ids": covers,
        "framework_refs": framework_refs or [], "summary": summary,
        "synthetic": True, "ingested": True, "uploaded_at": CREATED_AT,
    })
    return id


def evi(id: str, source_type: str, document_id: str, snippet: str, location: str | None = None) -> str:
    evidence.append({"id": id, "source_type": source_type, "document_id": document_id,
                     "location": location, "snippet": snippet, "synthetic": True})
    return id


# =========================================================================== DEPARTMENTS
# (id, name, budget, actual_fte, contractor_fte, head_role, agent, fixed_cost_pct, utilisation, mission)
DEPARTMENTS = [
    ("dept_engineering", "Engineering", 2_200_000, 95, 7, "role_staff_eng", "engineering", 0.30, 1.05,
     "Build and run the revenue-critical product systems."),
    ("dept_operations", "Operations", 1_500_000, 90, 15, "role_billing_ops_lead", "operations", 0.35, 1.12,
     "Keep customer-facing platforms, billing operations and on-call running."),
    ("dept_ai_data", "AI and Data", 700_000, 30, 4, "role_data_lead", "ai_data", 0.35, 1.00,
     "Own data pipelines, ML models and analytics."),
    ("dept_product", "Product", 600_000, 22, 3, "role_pm", "product", 0.25, 1.00,
     "Own roadmap, releases and transformation projects."),
    ("dept_sales", "Sales", 900_000, 40, 2, "role_ae", "sales", 0.20, 1.05,
     "Win and expand enterprise and mid-market revenue."),
    ("dept_marketing", "Marketing", 500_000, 20, 2, "role_pmm", "marketing", 0.15, 1.00,
     "Demand generation, segmentation and acquisition."),
    ("dept_customer_success", "Customer Success", 600_000, 45, 5, "role_csm", "customer_success", 0.40, 1.08,
     "Protect retention, SLAs and customer health."),
    ("dept_finance", "Finance", 600_000, 22, 2, "role_finance_analyst", "finance", 0.45, 1.00,
     "Own budget, cost targets, financial KPIs and vendor contracts."),
    ("dept_compliance", "Compliance", 400_000, 14, 2, "role_grc_lead", "compliance", 0.55, 1.05,
     "Own controls, auditability and regulatory posture."),
]
DEPT_STRENGTHS = {
    "dept_operations": [
        ("str_ops_incident", "Fast incident response", "process", 4, ["wf_incident_mgmt", "sys_billing_platform"],
         ["role_sre"], 0.40, ["ev_incident_review_q2"]),
        ("str_ops_billing_recon", "Billing reconciliation know-how", "expertise", 5, ["wf_billing_recon"],
         ["role_billing_ops_lead"], 0.85, ["ev_knowledge_matrix_billing"]),
    ],
    "dept_engineering": [
        ("str_eng_core", "Core platform engineering", "capability", 4, ["sys_core_api", "sys_dispatch_engine"],
         ["role_staff_eng"], 0.45, ["ev_architecture_core"]),
        ("str_eng_security", "Security engineering", "capability", 4, ["ctl_access_control"],
         ["role_security_eng"], 0.5, ["ev_architecture_core"]),
    ],
    "dept_ai_data": [
        ("str_data_pipeline", "Data pipeline & lineage", "data", 4, ["sys_data_pipeline"],
         ["role_data_lead"], 0.7, ["ev_knowledge_matrix_data"]),
        ("str_data_ml", "ML modeling & scoring", "capability", 3, ["sys_ml_scoring"], ["role_ml_eng"], 0.5, None),
        ("str_data_governance", "Data governance & lineage", "data", 3, ["ds_audit_log"], ["role_data_lead"], 0.5, None),
    ],
    "dept_compliance": [
        ("str_comp_soc2", "SOC 2 control mapping", "expertise", 5, ["ctl_soc2_audit_logging"],
         ["role_grc_lead"], 0.9, ["ev_soc2_register_intro"]),
        ("str_comp_privacy", "GDPR / PCI privacy program", "expertise", 4, ["ctl_data_retention", "ctl_pci_carddata"],
         ["role_privacy_counsel"], 0.7, ["ev_soc2_register_intro"]),
    ],
    "dept_product": [
        ("str_prod_delivery", "Migration & delivery management", "process", 3, ["proj_warehouse_migration"],
         ["role_pm"], 0.5, None),
        ("str_prod_discovery", "Product discovery & UX", "capability", 3, ["kpi_net_retention"],
         ["role_product_lead"], 0.4, None),
    ],
    "dept_sales": [
        ("str_sales_enterprise", "Enterprise selling", "relationship", 4, ["seg_enterprise"],
         ["role_ae"], 0.4, ["ev_finance_forecast_q3"]),
        ("str_sales_solutions", "Solutions & deal engineering", "capability", 3, ["seg_midmarket"],
         ["role_sales_eng"], 0.4, None),
    ],
    "dept_marketing": [
        ("str_mkt_demand", "Digital demand generation", "capability", 3, ["kpi_pipeline"], ["role_pmm"], 0.4, None),
        ("str_mkt_analytics", "Marketing analytics & attribution", "data", 3, ["kpi_pipeline"],
         ["role_demand_gen"], 0.4, None),
    ],
    "dept_customer_success": [
        ("str_cs_retention", "Retention & escalation management", "process", 3, ["kpi_net_retention"],
         ["role_csm"], 0.4, None),
        ("str_cs_support", "Support operations", "process", 3, ["wf_customer_onboarding"],
         ["role_support_lead"], 0.4, None),
    ],
    "dept_finance": [
        ("str_fin_fpna", "Driver-based FP&A", "capability", 4, ["kpi_gross_margin"],
         ["role_finance_analyst"], 0.5, ["ev_finance_forecast_q3"]),
        ("str_fin_procurement", "Vendor & procurement management", "process", 3, ["vendor_cloud"],
         ["role_procurement"], 0.4, None),
    ],
}
DEPT_STRENGTHS["dept_engineering"].append(
    ("str_eng_reliability", "Reliability engineering", "process", 3, ["kpi_uptime_sla"], ["role_eng_manager"], 0.4, None)
)
for did, name, budget, actual, contractor, head, agent, fixed, util, mission in DEPARTMENTS:
    cap = actual + contractor
    ent(did, "department", name, department_id=None, criticality="high",
        annual_cost_usd=budget, capacity_fte=float(cap))
    strengths = []
    for sid, sname, cat, level, supports, key_roles, conc, ev in DEPT_STRENGTHS.get(did, []):
        s = {"id": sid, "name": sname, "category": cat, "level": level,
             "supports_entity_ids": supports, "key_role_ids": key_roles,
             "concentration": conc, "evidence_refs": ev or []}
        strengths.append(s)
    department_profiles.append({
        "department_id": did, "mission": mission, "head_role_id": head, "agent_id": agent,
        "staffing": {"sanctioned_fte": float(cap + 4), "actual_fte": float(actual),
                     "contractors_fte": float(contractor), "open_positions": 4,
                     "attrition_rate_annual": 0.14, "avg_time_to_hire_days": 55, "utilisation": util},
        "budget": {"annual_budget_usd": budget, "spent_ytd_usd": int(budget * 0.7),
                   "fixed_cost_pct": fixed, "budget_owner_role_id": head},
        "strengths": strengths, "gaps": [], "maturity_level": 3,
    })

# Company-level KPI node (no department_id, allowed for kpi_company)
ent("kpi_company", "kpi", "Company KPIs", department_id=None,
    kpi_baseline=0.0, kpi_unit="index", higher_is_better=True)

# =========================================================================== ROLES
ROLES = [
    ("role_billing_ops_lead", "Billing Operations Lead", "dept_operations", 190_000, 3),
    ("role_sre", "Site Reliability Engineer", "dept_operations", 175_000, 12),
    ("role_platform_eng", "Platform Engineer", "dept_operations", 165_000, 8),
    ("role_staff_eng", "Staff Software Engineer", "dept_engineering", 205_000, 20),
    ("role_security_eng", "Security Engineer", "dept_engineering", 190_000, 8),
    ("role_data_lead", "Data Platform Lead", "dept_ai_data", 185_000, 4),
    ("role_ml_eng", "ML Engineer", "dept_ai_data", 180_000, 9),
    ("role_pm", "Product Manager", "dept_product", 175_000, 8),
    ("role_ae", "Account Executive", "dept_sales", 160_000, 20),
    ("role_pmm", "Product Marketing Manager", "dept_marketing", 150_000, 8),
    ("role_csm", "Customer Success Manager", "dept_customer_success", 140_000, 18),
    ("role_finance_analyst", "Finance Analyst", "dept_finance", 150_000, 9),
    ("role_grc_lead", "GRC Lead", "dept_compliance", 170_000, 3),
    # breadth: every department staffed with more than one role
    ("role_eng_manager", "Engineering Manager", "dept_engineering", 180_000, 6),
    ("role_qa_eng", "QA Engineer", "dept_engineering", 150_000, 8),
    ("role_analytics_eng", "Analytics Engineer", "dept_ai_data", 165_000, 6),
    ("role_product_lead", "Group Product Manager", "dept_product", 190_000, 3),
    ("role_ux", "UX Designer", "dept_product", 150_000, 5),
    ("role_sales_eng", "Solutions Engineer", "dept_sales", 175_000, 8),
    ("role_sdr", "Sales Development Rep", "dept_sales", 110_000, 12),
    ("role_demand_gen", "Demand Gen Manager", "dept_marketing", 150_000, 6),
    ("role_brand", "Brand & Comms Manager", "dept_marketing", 140_000, 4),
    ("role_support_lead", "Support Team Lead", "dept_customer_success", 130_000, 10),
    ("role_onboarding", "Onboarding Specialist", "dept_customer_success", 120_000, 12),
    ("role_procurement", "Procurement Manager", "dept_finance", 150_000, 3),
    ("role_controller", "Controller", "dept_finance", 170_000, 4),
    ("role_privacy_counsel", "Privacy Counsel", "dept_compliance", 175_000, 3),
]
for rid, name, did, salary, fte in ROLES:
    ent(rid, "role", name, department_id=did, annual_cost_usd=salary, capacity_fte=float(fte))

# =========================================================================== PERSON TOKENS (SPOFs only)
PERSON_TOKENS = [
    ("pt_billing_01", "Billing owner A", "role_billing_ops_lead", "dept_operations"),
    ("pt_billing_02", "Billing owner B", "role_billing_ops_lead", "dept_operations"),
    ("pt_grc_01", "GRC owner", "role_grc_lead", "dept_compliance"),
    ("pt_data_01", "Data platform owner", "role_data_lead", "dept_ai_data"),
    ("pt_sre_01", "Primary on-call", "role_sre", "dept_operations"),
]
for pid, name, role_id, did in PERSON_TOKENS:
    ent(pid, "person_token", name, department_id=did, sensitivity="hr", role_id=role_id)

# =========================================================================== SYSTEMS
SYSTEMS = [
    # id, name, dept, tier(crit), annual_cost, failure_cost_per_day, customer_facing
    ("sys_core_api", "core-api", "dept_engineering", "critical", 260_000, 120_000, True),
    ("sys_customer_portal", "customer-portal", "dept_engineering", "high", 140_000, 60_000, True),
    ("sys_dispatch_engine", "dispatch-engine", "dept_engineering", "high", 180_000, 70_000, True),
    ("sys_billing_platform", "billing-platform", "dept_operations", "critical", 220_000, 90_000, True),
    ("sys_invoicing", "invoicing-service", "dept_operations", "critical", 90_000, 80_000, True),
    ("sys_cloud_platform", "cloud-platform", "dept_operations", "critical", 300_000, 100_000, False),
    ("sys_sso_gateway", "sso-gateway", "dept_operations", "high", 60_000, 40_000, True),
    ("sys_warehouse_legacy", "warehouse-legacy", "dept_operations", "medium", 400_000, 20_000, False),
    ("sys_warehouse_new", "warehouse-new", "dept_ai_data", "medium", 120_000, 10_000, False),
    ("sys_data_pipeline", "data-pipeline", "dept_ai_data", "high", 150_000, 30_000, False),
    ("sys_ml_scoring", "ml-scoring-service", "dept_ai_data", "medium", 90_000, 15_000, False),
    ("sys_audit_service", "audit-log-service", "dept_compliance", "high", 70_000, 25_000, False),
]
for sid, name, did, crit, cost, fail, cust in SYSTEMS:
    ent(sid, "system", name, department_id=did, criticality=crit,
        annual_cost_usd=cost, failure_cost_per_day_usd=fail, customer_facing=cust,
        migration_cost_usd=int(cost * 0.4))

# =========================================================================== DATASETS
DATASETS = [
    ("ds_audit_log", "Audit-log event stream", "dept_compliance", "critical"),
    ("ds_telematics", "Telematics / GPS feed", "dept_ai_data", "high"),
    ("ds_enrichment", "Account enrichment data", "dept_ai_data", "low"),
    ("ds_usage", "Customer usage events", "dept_ai_data", "medium"),
    ("ds_shipments", "Shipment & dispatch records", "dept_ai_data", "high"),
]
for dsid, name, did, crit in DATASETS:
    ent(dsid, "dataset", name, department_id=did, criticality=crit)

# =========================================================================== VENDORS (owned by finance, R1)
VENDORS = [
    # id, name, cost, exit_cost, substitutability, criticality
    ("vendor_auditlog", "SentinelAudit (audit logging)", 300_000, 90_000, 0.10, "critical"),
    ("vendor_cloud", "CloudScale (cloud infra)", 520_000, 120_000, 0.50, "high"),
    ("vendor_telematics", "Telemetrix (telematics)", 180_000, 60_000, 0.40, "high"),
    ("vendor_enrichiq", "EnrichIQ (enrichment)", 140_000, 20_000, 0.85, "low"),
    ("vendor_observability", "ObserveNow (observability)", 90_000, 15_000, 0.70, "medium"),
    ("vendor_identity", "IdentityHub (SSO)", 70_000, 40_000, 0.30, "high"),
]
for vid, name, cost, exit_c, subst, crit in VENDORS:
    ent(vid, "vendor", name, department_id="dept_finance", criticality=crit,
        annual_cost_usd=cost, one_time_exit_cost_usd=exit_c)

# =========================================================================== WORKFLOWS
WORKFLOWS = [
    # id, name, dept, crit, min_owners, failure_cost_per_day, documented_pct, customer_facing
    ("wf_billing_recon", "Billing reconciliation", "dept_operations", "critical", 2, 50_000, 0.35, True),
    ("wf_invoicing", "Invoice generation & dispatch", "dept_operations", "critical", 2, 80_000, 0.6, True),
    ("wf_incident_mgmt", "Incident response / on-call", "dept_operations", "high", 2, 40_000, 0.7, False),
    ("wf_dispatch_opt", "Dispatch optimisation", "dept_engineering", "high", 2, 60_000, 0.6, True),
    ("wf_soc2_evidence", "SOC 2 audit-evidence collection", "dept_compliance", "high", 1, 10_000, 0.8, False),
    ("wf_customer_onboarding", "Customer onboarding", "dept_customer_success", "medium", 2, 20_000, 0.5, True),
    ("wf_data_refresh", "Data pipeline refresh", "dept_ai_data", "high", 2, 25_000, 0.6, False),
    ("wf_financial_close", "Monthly financial close", "dept_finance", "medium", 2, 15_000, 0.7, False),
]
for wid, name, did, crit, minown, fail, docp, cust in WORKFLOWS:
    ent(wid, "workflow", name, department_id=did, criticality=crit,
        min_qualified_owners=minown, failure_cost_per_day_usd=fail,
        documented_pct=docp, customer_facing=cust)

# =========================================================================== KNOWLEDGE
KNOWLEDGE = [
    ("kn_billing_exception", "Billing-recon exception handling", "dept_operations", 0.35, "critical"),
    ("kn_warehouse_cutover", "Warehouse migration cutover plan", "dept_ai_data", 0.5, "high"),
    ("kn_soc2_mapping", "SOC 2 control-to-evidence mapping", "dept_compliance", 0.4, "high"),
    ("kn_data_format", "Upstream data-format quirk handling", "dept_ai_data", 0.3, "high"),
    ("kn_oncall", "On-call escalation & recovery", "dept_operations", 0.7, "medium"),
    # breadth: a tribal-skill node in every department (well-documented -> not a SPOF)
    ("kn_core_arch", "Core-API architecture knowledge", "dept_engineering", 0.7, "medium"),
    ("kn_release_eng", "Release & deploy engineering", "dept_engineering", 0.75, "medium"),
    ("kn_ml_modeling", "Dispatch ML modeling", "dept_ai_data", 0.6, "medium"),
    ("kn_roadmap_context", "Product roadmap & customer context", "dept_product", 0.7, "medium"),
    ("kn_enterprise_deals", "Enterprise deal & pricing know-how", "dept_sales", 0.65, "medium"),
    ("kn_segmentation", "Audience segmentation & attribution", "dept_marketing", 0.7, "medium"),
    ("kn_onboarding_playbook", "Customer onboarding playbook", "dept_customer_success", 0.75, "medium"),
    ("kn_cs_escalation", "CS escalation handling", "dept_customer_success", 0.7, "medium"),
    ("kn_vendor_contracts", "Vendor contract & renewal know-how", "dept_finance", 0.6, "medium"),
    ("kn_privacy_program", "Privacy program operation", "dept_compliance", 0.7, "medium"),
]
for kid, name, did, docp, crit in KNOWLEDGE:
    ent(kid, "knowledge_asset", name, department_id=did, criticality=crit, documented_pct=docp)

# =========================================================================== CONTROLS
CONTROLS = [
    ("ctl_soc2_audit_logging", "SOC 2 CC7.2 – audit logging", "SOC2", True, "critical"),
    ("ctl_access_control", "SOC 2 CC6.1 – logical access", "SOC2", True, "high"),
    ("ctl_data_retention", "GDPR data retention", "GDPR", True, "high"),
    ("ctl_change_mgmt", "Change management", "SOC2", False, "medium"),
    ("ctl_incident_mgmt", "Incident management", "SOC2", True, "high"),
    ("ctl_pci_carddata", "PCI DSS cardholder data", "PCI_DSS", True, "high"),
]
for cid, name, fw, mand, crit in CONTROLS:
    ent(cid, "control", name, department_id="dept_compliance", criticality=crit,
        mandatory=mand, framework=fw)

# =========================================================================== PROJECTS (owned by product, R1)
PROJECTS = [
    # id, name, budget, completion, retires, cancel_cost
    ("proj_warehouse_migration", "Warehouse Migration", 400_000, 0.55, ["sys_warehouse_legacy"], 40_000),
    ("proj_billing_modernization", "Billing Modernization", 250_000, 0.30, [], 30_000),
    ("proj_ml_dispatch", "ML Dispatch Optimization", 300_000, 0.40, [], 20_000),
    ("proj_soc2_type2", "SOC 2 Type II Certification", 150_000, 0.60, [], 10_000),
]
for pid, name, budget, comp, retires, cancel in PROJECTS:
    ent(pid, "project", name, department_id="dept_product", criticality="medium",
        annual_cost_usd=budget, completion_pct=comp, retires_entity_ids=retires,
        one_time_exit_cost_usd=cancel)

# =========================================================================== KPIs
KPIS = [
    ("kpi_gross_margin", "Gross margin %", "dept_finance", 62.0, "percent", True),
    ("kpi_on_time_delivery", "On-time delivery %", "dept_customer_success", 94.0, "percent", True),
    ("kpi_net_retention", "Net revenue retention", "dept_sales", 112.0, "percent", True),
    ("kpi_pipeline", "Qualified pipeline", "dept_marketing", 18_000_000.0, "usd", True),
    ("kpi_soc2_coverage", "SOC 2 compliance coverage", "dept_compliance", 100.0, "percent", True),
    ("kpi_uptime_sla", "System uptime / SLA", "dept_operations", 99.9, "percent", True),
]
for kid, name, did, base, unit, hib in KPIS:
    ent(kid, "kpi", name, department_id=did, kpi_baseline=base, kpi_unit=unit, higher_is_better=hib)

# =========================================================================== CUSTOMER SEGMENTS
ent("seg_enterprise", "customer_segment", "Enterprise accounts", department_id="dept_sales",
    criticality="critical", arr_usd=28_000_000)
ent("seg_midmarket", "customer_segment", "Mid-market accounts", department_id="dept_sales",
    criticality="high", arr_usd=12_000_000)

# =========================================================================== DOCUMENTS + EVIDENCE
doc("doc_department_map", "Department operating-model map", "architecture_note",
    department_id=None, status="current", covers=[], summary="How departments fund, constrain and supply each other.")
evi("ev_department_map_v1", "architecture_note", "doc_department_map", "Finance sets budget limits for Engineering and Marketing.")

doc("doc_billing_recon_runbook", "Billing reconciliation runbook", "runbook",
    department_id="dept_operations", status="outdated", covers=["wf_billing_recon"],
    summary="Monthly reconciliation steps; exception-handling section missing since the 2025 vendor change.",
    framework_refs=["SOC2"], owner_role_id="role_billing_ops_lead")
evi("ev_billing_runbook_gap", "runbook", "doc_billing_recon_runbook",
    "Exception path is undocumented; only the two billing owners can resolve a failed run.", location="section 6")
evi("ev_knowledge_matrix_billing", "knowledge_matrix", "doc_billing_recon_runbook",
    "Billing reconciliation know-how concentrated in one role (bus factor 2).")

doc("doc_auditlog_contract", "SentinelAudit MSA", "contract",
    department_id="dept_finance", status="current", covers=["vendor_auditlog"],
    summary="Audit-log vendor master agreement; auto-renews at +12% on day 120.", framework_refs=["SOC2"])
evi("ev_auditlog_msa_clause_9", "contract", "doc_auditlog_contract",
    "Contract auto-renews at +12% at the renewal date unless cancelled 30 days prior.", location="clause 9")
evi("ev_auditlog_sole_feed", "contract", "doc_auditlog_contract",
    "SentinelAudit is the sole automated audit-log source feeding SOC 2 CC7.2.")

doc("doc_soc2_register", "SOC 2 control register", "audit_report",
    department_id="dept_compliance", status="current",
    covers=["ctl_soc2_audit_logging", "ctl_access_control", "wf_soc2_evidence"],
    summary="Mapping of SOC 2 controls to their evidence sources.", framework_refs=["SOC2"])
evi("ev_soc2_register_intro", "audit_report", "doc_soc2_register",
    "CC7.2 requires continuous audit-log evidence retained for 12 months.")
evi("ev_identity_access", "audit_report", "doc_soc2_register",
    "SSO via IdentityHub is the sole enforcement point for SOC 2 CC6.1 logical access.")

doc("doc_migration_charter", "Warehouse migration charter", "strategy_memo",
    department_id="dept_product", status="current", covers=["proj_warehouse_migration"],
    summary="Migration decommissions warehouse-legacy; halting mid-flight keeps ~$400K/yr running.")
evi("ev_migration_carry", "strategy_memo", "doc_migration_charter",
    "warehouse-legacy carries ~$400K/yr; retired only on migration completion.")

doc("doc_finance_forecast", "FY forecast", "financial_forecast",
    department_id="dept_finance", status="current", covers=["kpi_gross_margin"],
    summary="Cost and revenue forecast; cloud spend rising ~1.5%/month.")
evi("ev_finance_forecast_q3", "finance_forecast", "doc_finance_forecast",
    "Cloud spend grows ~1.5% per month on current usage.")

doc("doc_incident_report", "Q2 incident review", "incident_report",
    department_id="dept_operations", status="current", covers=["wf_incident_mgmt", "wf_billing_recon"],
    summary="Reconciliation failures ~twice a year; likelier when owners lose capacity.")
evi("ev_incident_22", "incident", "doc_incident_report",
    "Billing reconciliation failed twice in 12 months; each event cost ~$400K.", location="INC-22")
evi("ev_incident_review_q2", "incident", "doc_incident_report", "Incident response resolved P1s within SLA in Q2.")

doc("doc_architecture", "System architecture notes", "architecture_note",
    department_id="dept_engineering", status="current",
    covers=["sys_core_api", "sys_billing_platform", "sys_audit_service"],
    summary="Service dependency map for core, billing and audit systems.")
evi("ev_architecture_core", "architecture_note", "doc_architecture",
    "Invoicing consumes the reconciled ledger from billing-recon; billing runs on billing-platform.")

doc("doc_knowledge_matrix_data", "Data team knowledge matrix", "knowledge_matrix",
    department_id="dept_ai_data", status="current", covers=["kn_data_format", "kn_warehouse_cutover"],
    summary="Data-format quirks and cutover knowledge held by the data platform lead.")
evi("ev_knowledge_matrix_data", "knowledge_matrix", "doc_knowledge_matrix_data",
    "Upstream format-change handling is single-owner (bus factor 1).")

# --- breadth: a current document for every department + cover the remaining critical workflows ---
doc("doc_invoicing_sop", "Invoicing SOP", "sop", department_id="dept_operations", status="current",
    covers=["wf_invoicing"], summary="Standard operating procedure for invoice generation and dispatch.",
    framework_refs=["SOC2"], owner_role_id="role_billing_ops_lead")
evi("ev_invoicing_sop", "workflow_map", "doc_invoicing_sop", "Invoicing runs after reconciliation completes.")

doc("doc_dispatch_spec", "Dispatch optimisation spec", "architecture_note", department_id="dept_engineering",
    status="current", covers=["wf_dispatch_opt", "sys_dispatch_engine"],
    summary="How the dispatch engine optimises routes from telematics and shipment data.")
evi("ev_dispatch_spec", "architecture_note", "doc_dispatch_spec", "Dispatch optimisation consumes live telematics.")

doc("doc_data_pipeline_runbook", "Data pipeline runbook", "runbook", department_id="dept_ai_data",
    status="current", covers=["wf_data_refresh", "sys_data_pipeline"],
    summary="Refresh schedule, backfills and failure recovery for the data pipeline.")
evi("ev_data_pipeline_runbook", "runbook", "doc_data_pipeline_runbook", "Refresh recovers from a failed batch via replay.")

doc("doc_sales_playbook", "Enterprise sales playbook", "sop", department_id="dept_sales", status="current",
    covers=["seg_enterprise", "kn_enterprise_deals"], summary="Enterprise qualification, pricing and close motion.")
doc("doc_mkt_attribution", "Marketing attribution model", "kpi_report", department_id="dept_marketing",
    status="current", covers=["kpi_pipeline", "kn_segmentation"], summary="Multi-touch attribution feeding pipeline.")
doc("doc_cs_runbook", "Customer onboarding & escalation runbook", "runbook", department_id="dept_customer_success",
    status="current", covers=["wf_customer_onboarding", "kn_onboarding_playbook"],
    summary="Onboarding steps and escalation paths for enterprise accounts.")
doc("doc_procurement_register", "Vendor & procurement register", "contract", department_id="dept_finance",
    status="current", covers=["vendor_cloud", "vendor_telematics", "kn_vendor_contracts"],
    summary="Vendor spend, renewal dates and substitutability notes.")
doc("doc_product_roadmap", "Product roadmap", "strategy_memo", department_id="dept_product", status="current",
    covers=["proj_billing_modernization", "proj_ml_dispatch", "kn_roadmap_context"],
    summary="Sequenced roadmap of transformation projects and releases.")
doc("doc_eng_release", "Release engineering guide", "runbook", department_id="dept_engineering", status="current",
    covers=["kn_release_eng", "sys_core_api"], summary="Build, test and deploy pipeline for core services.")


# =========================================================================== EDGES
# --- ownership / knowledge (people -> workflows/knowledge) ---
edge("e_pt_billing01_owns", "pt_billing_01", "wf_billing_recon", "OWNS", strength=0.9, substitutability=0.1,
     criticality="critical", evidence_refs=["ev_knowledge_matrix_billing"])
edge("e_pt_billing02_owns", "pt_billing_02", "wf_billing_recon", "OWNS", strength=0.9, substitutability=0.1,
     criticality="critical", evidence_refs=["ev_knowledge_matrix_billing"])
edge("e_pt_billing01_knows", "pt_billing_01", "kn_billing_exception", "KNOWS", strength=0.95, substitutability=0.1,
     criticality="critical", evidence_refs=["ev_billing_runbook_gap"])
edge("e_pt_billing02_knows", "pt_billing_02", "kn_billing_exception", "KNOWS", strength=0.95, substitutability=0.1,
     criticality="critical", evidence_refs=["ev_billing_runbook_gap"])
edge("e_pt_grc_knows", "pt_grc_01", "kn_soc2_mapping", "KNOWS", strength=0.9, substitutability=0.15,
     criticality="high", evidence_refs=["ev_soc2_register_intro"])
edge("e_pt_data_knows_cutover", "pt_data_01", "kn_warehouse_cutover", "KNOWS", strength=0.85, substitutability=0.2,
     criticality="high", evidence_refs=["ev_knowledge_matrix_data"])
edge("e_pt_data_knows_format", "pt_data_01", "kn_data_format", "KNOWS", strength=0.9, substitutability=0.15,
     criticality="high", evidence_refs=["ev_knowledge_matrix_data"])
edge("e_pt_sre_owns_incident", "pt_sre_01", "wf_incident_mgmt", "OWNS", strength=0.7, substitutability=0.3,
     criticality="high", evidence_refs=["ev_incident_review_q2"])

# --- knowledge enables workflow (SUPPORTS) ---
edge("e_kn_billing_supports", "kn_billing_exception", "wf_billing_recon", "SUPPORTS", strength=0.9,
     substitutability=0.1, criticality="critical", evidence_refs=["ev_billing_runbook_gap"])
edge("e_kn_soc2_supports", "kn_soc2_mapping", "wf_soc2_evidence", "SUPPORTS", strength=0.85, substitutability=0.2,
     criticality="high", evidence_refs=["ev_soc2_register_intro"])
edge("e_kn_cutover_supports", "kn_warehouse_cutover", "proj_warehouse_migration", "SUPPORTS", strength=0.7,
     substitutability=0.3, criticality="high", evidence_refs=["ev_migration_carry"])
edge("e_kn_format_supports", "kn_data_format", "wf_data_refresh", "SUPPORTS", strength=0.8, substitutability=0.2,
     criticality="high", evidence_refs=["ev_knowledge_matrix_data"])

# --- systems support workflows / each other ---
edge("e_billing_platform_recon", "sys_billing_platform", "wf_billing_recon", "SUPPORTS", strength=0.85,
     substitutability=0.25, lag_days=15, criticality="critical", evidence_refs=["ev_architecture_core"])
edge("e_recon_invoicing", "wf_billing_recon", "wf_invoicing", "SUPPORTS", strength=0.9, substitutability=0.2,
     lag_days=15, criticality="critical", evidence_refs=["ev_architecture_core"])
edge("e_sso_portal", "sys_sso_gateway", "sys_customer_portal", "SUPPORTS", strength=0.7, substitutability=0.4,
     lag_days=7, criticality="high", evidence_refs=["ev_architecture_core"])
edge("e_cloud_core", "sys_cloud_platform", "sys_core_api", "SUPPORTS", strength=0.8, substitutability=0.5,
     lag_days=7, criticality="critical", evidence_refs=["ev_architecture_core"])
edge("e_telematics_dispatch", "sys_data_pipeline", "sys_dispatch_engine", "SUPPORTS", strength=0.6,
     substitutability=0.5, lag_days=14)
edge("e_pipeline_ml", "sys_data_pipeline", "sys_ml_scoring", "SUPPORTS", strength=0.65, substitutability=0.5,
     lag_days=14)
edge("e_core_dispatchwf", "sys_dispatch_engine", "wf_dispatch_opt", "SUPPORTS", strength=0.9, substitutability=0.3,
     criticality="high", evidence_refs=["ev_architecture_core"])

# --- vendors provide datasets/systems ---
edge("e_auditlog_provides", "vendor_auditlog", "ds_audit_log", "PROVIDES", strength=0.95, substitutability=0.1,
     lag_days=0, criticality="critical", evidence_refs=["ev_auditlog_sole_feed"])
edge("e_cloud_provides", "vendor_cloud", "sys_cloud_platform", "PROVIDES", strength=0.9, substitutability=0.5,
     criticality="critical", evidence_refs=["ev_architecture_core"])
edge("e_telemetrix_provides", "vendor_telematics", "ds_telematics", "PROVIDES", strength=0.85, substitutability=0.4,
     criticality="high", evidence_refs=["ev_architecture_core"])
edge("e_enrichiq_provides", "vendor_enrichiq", "ds_enrichment", "PROVIDES", strength=0.4, substitutability=0.85)
edge("e_identity_provides", "vendor_identity", "sys_sso_gateway", "PROVIDES", strength=0.9, substitutability=0.3,
     criticality="high", evidence_refs=["ev_architecture_core", "ev_identity_access"])
edge("e_observe_supports", "vendor_observability", "sys_core_api", "SUPPORTS", strength=0.4, substitutability=0.7)

# --- datasets support systems / workflows ---
edge("e_auditds_service", "ds_audit_log", "sys_audit_service", "SUPPORTS", strength=0.95, substitutability=0.1,
     lag_days=1, criticality="critical", evidence_refs=["ev_auditlog_sole_feed"])
edge("e_telematics_ingest", "ds_telematics", "sys_dispatch_engine", "SUPPORTS", strength=0.7, substitutability=0.4,
     lag_days=7, criticality="high", evidence_refs=["ev_architecture_core"])
edge("e_shipments_pipeline", "ds_shipments", "sys_data_pipeline", "SUPPORTS", strength=0.6, substitutability=0.5)

# --- feeds SUPPORT their control (propagation direction: failing feed breaks the control) ---
edge("e_ctl_cc72_auditsvc", "sys_audit_service", "ctl_soc2_audit_logging", "SUPPORTS", strength=0.95,
     substitutability=0.05, lag_days=1, criticality="critical", evidence_refs=["ev_soc2_register_intro"])
edge("e_ctl_cc72_auditds", "ds_audit_log", "ctl_soc2_audit_logging", "SUPPORTS", strength=1.0,
     substitutability=0.05, lag_days=1, criticality="critical", evidence_refs=["ev_auditlog_sole_feed"])
edge("e_ctl_access_sso", "sys_sso_gateway", "ctl_access_control", "SUPPORTS", strength=0.9, substitutability=0.2,
     criticality="high", evidence_refs=["ev_architecture_core", "ev_identity_access"])
edge("e_access_soc2_coverage", "ctl_access_control", "kpi_soc2_coverage", "CONTRIBUTES_TO", strength=0.8,
     substitutability=0.2, criticality="high", evidence_refs=["ev_identity_access"])
edge("e_ctl_incident_wf", "wf_incident_mgmt", "ctl_incident_mgmt", "SUPPORTS", strength=0.85, substitutability=0.3,
     criticality="high", evidence_refs=["ev_incident_review_q2"])
edge("e_ctl_pci_billing", "sys_billing_platform", "ctl_pci_carddata", "SUPPORTS", strength=0.8, substitutability=0.3,
     criticality="high", evidence_refs=["ev_architecture_core"])
edge("e_soc2evidence_coverage", "wf_soc2_evidence", "kpi_soc2_coverage", "CONTRIBUTES_TO", strength=0.9,
     substitutability=0.1, criticality="high", evidence_refs=["ev_soc2_register_intro"])
edge("e_cc72_coverage", "ctl_soc2_audit_logging", "kpi_soc2_coverage", "CONTRIBUTES_TO", strength=1.0,
     substitutability=0.05, criticality="critical", evidence_refs=["ev_soc2_register_intro"])

# --- projects retire legacy (SUBSTITUTES_FOR captures REPLACES intent; retires_entity_ids carries the rebound) ---
edge("e_migration_replaces_legacy", "proj_warehouse_migration", "sys_warehouse_legacy", "SUBSTITUTES_FOR",
     strength=0.9, substitutability=0.2, lag_days=60, criticality="high", evidence_refs=["ev_migration_carry"])

# --- value contributions to KPIs ---
edge("e_invoicing_margin", "wf_invoicing", "kpi_gross_margin", "CONTRIBUTES_TO", strength=0.8, substitutability=0.2,
     criticality="high", evidence_refs=["ev_finance_forecast_q3"])
edge("e_dispatch_ontime", "wf_dispatch_opt", "kpi_on_time_delivery", "CONTRIBUTES_TO", strength=0.85,
     substitutability=0.3, criticality="high", evidence_refs=["ev_architecture_core"])
edge("e_core_uptime", "sys_core_api", "kpi_uptime_sla", "CONTRIBUTES_TO", strength=0.9, substitutability=0.2,
     criticality="critical", evidence_refs=["ev_architecture_core"])
edge("e_onboarding_retention", "wf_customer_onboarding", "kpi_net_retention", "CONTRIBUTES_TO", strength=0.6,
     substitutability=0.4)
edge("e_enterprise_margin", "seg_enterprise", "kpi_gross_margin", "CONTRIBUTES_TO", strength=0.7, substitutability=0.3,
     criticality="high", evidence_refs=["ev_finance_forecast_q3"])

# --- breadth: every department's tribal knowledge wired into what it supports (medium = no SPOF) ---
edge("e_kn_core_arch", "kn_core_arch", "sys_core_api", "SUPPORTS", strength=0.5, substitutability=0.5)
edge("e_kn_release", "kn_release_eng", "sys_core_api", "SUPPORTS", strength=0.4, substitutability=0.6)
edge("e_kn_mlmodel", "kn_ml_modeling", "sys_ml_scoring", "SUPPORTS", strength=0.5, substitutability=0.5)
edge("e_kn_roadmap", "kn_roadmap_context", "proj_billing_modernization", "SUPPORTS", strength=0.4, substitutability=0.6)
edge("e_kn_deals", "kn_enterprise_deals", "seg_enterprise", "SUPPORTS", strength=0.4, substitutability=0.5)
edge("e_kn_segmentation", "kn_segmentation", "kpi_pipeline", "SUPPORTS", strength=0.4, substitutability=0.6)
edge("e_kn_onboarding", "kn_onboarding_playbook", "wf_customer_onboarding", "SUPPORTS", strength=0.5, substitutability=0.5)
edge("e_kn_cs_escalation", "kn_cs_escalation", "wf_customer_onboarding", "SUPPORTS", strength=0.4, substitutability=0.6)
edge("e_kn_vendorcontracts", "kn_vendor_contracts", "vendor_cloud", "SUPPORTS", strength=0.4, substitutability=0.6)
edge("e_kn_privacy", "kn_privacy_program", "ctl_data_retention", "SUPPORTS", strength=0.5, substitutability=0.5)

# =========================================================================== DEPARTMENT CHANNELS (§5.9)
chan("ch_finance_engineering_budget", "dept_finance", "dept_engineering", "budget limits", "budget")
chan("ch_finance_marketing_budget", "dept_finance", "dept_marketing", "budget limits", "budget")
chan("ch_finance_operations_cost", "dept_finance", "dept_operations", "cost targets", "budget")
chan("ch_finance_sales_revenue", "dept_finance", "dept_sales", "revenue targets", "budget")
chan("ch_ai_data_engineering_models", "dept_ai_data", "dept_engineering", "models and data", "capability")
chan("ch_ai_data_marketing_scores", "dept_ai_data", "dept_marketing", "scores and segments", "capability")
chan("ch_engineering_product_features", "dept_engineering", "dept_product", "features and platforms", "capability")
chan("ch_engineering_operations_automation", "dept_engineering", "dept_operations", "automation", "capability")
chan("ch_operations_engineering_incidents", "dept_operations", "dept_engineering", "incidents and capacity", "signal")
chan("ch_product_sales_roadmap", "dept_product", "dept_sales", "roadmap and releases", "capability")
chan("ch_product_cs_product", "dept_product", "dept_customer_success", "product changes", "capability")
chan("ch_marketing_sales_qualified", "dept_marketing", "dept_sales", "qualified leads", "signal")
chan("ch_sales_product_customer", "dept_sales", "dept_product", "customer demand", "signal")
chan("ch_sales_cs_commitments", "dept_sales", "dept_customer_success", "commitments", "signal")
chan("ch_cs_product_feedback", "dept_customer_success", "dept_product", "feedback and churn signals", "signal")
chan("ch_compliance_ai_data_controls", "dept_compliance", "dept_ai_data", "controls", "constraint")
chan("ch_compliance_engineering_policies", "dept_compliance", "dept_engineering", "policies", "constraint")
chan("ch_compliance_operations_process", "dept_compliance", "dept_operations", "process controls", "constraint")
chan("ch_finance_kpi_profitability", "dept_finance", "kpi_company", "profitability", "value")
chan("ch_marketing_kpi_acquisition", "dept_marketing", "kpi_company", "acquisition cost", "value")
chan("ch_sales_kpi_pipeline", "dept_sales", "kpi_company", "pipeline", "value")
chan("ch_product_kpi_delivery", "dept_product", "kpi_company", "delivery", "value")
chan("ch_cs_kpi_retention", "dept_customer_success", "kpi_company", "retention", "value")
chan("ch_sales_marketing_launch", "dept_sales", "dept_marketing", "launch timing", "signal")
chan("ch_operations_compliance_evidence", "dept_operations", "dept_compliance", "control evidence", "signal")

# =========================================================================== PRESSURES (R13)
pressures.append({
    "id": "pr_cloud_growth", "kind": "cost_growth", "name": "Cloud spend growth",
    "target_entity_id": "sys_cloud_platform", "start_day": 0, "end_day": None,
    "rate": 0.015, "rate_range": [0.01, 0.02], "capacity_sensitivity": 0.0,
    "neutralised_by": [], "evidence_refs": ["ev_finance_forecast_q3"],
    "description": "Cloud costs grow ~1.5% a month on current usage.",
})
pressures.append({
    "id": "pr_auditlog_renewal", "kind": "renewal_step", "name": "Audit-log vendor renewal uplift",
    "target_entity_id": "vendor_auditlog", "start_day": 120, "end_day": None,
    "step_pct": 12.0, "capacity_sensitivity": 0.0,
    "neutralised_by": [{"intervention_type": "remove_vendor", "target_entity_id": "vendor_auditlog"}],
    "evidence_refs": ["ev_auditlog_msa_clause_9"],
    "description": "Contract auto-renews at +12% on day 120.",
})
pressures.append({
    "id": "pr_billing_recon_hazard", "kind": "hazard", "name": "Billing reconciliation failure",
    "target_entity_id": "wf_billing_recon", "start_day": 0, "end_day": None,
    "monthly_probability": 0.04, "probability_range": [0.02, 0.06], "cost_per_event_usd": 400_000,
    "capacity_sensitivity": 3.0,
    "neutralised_by": [{"intervention_type": "document_runbook", "target_entity_id": "wf_billing_recon"}],
    "evidence_refs": ["ev_incident_22"],
    "description": "Reconciliation fails ~twice a year; likelier if its owners lose capacity.",
})


# =========================================================================== ASSEMBLE + VALIDATE
def build() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "version": {
            "twin_version": "twin_halcyon_v2", "settings_version": 1,
            "prompt_version": "p1", "model_id": "configurable",
            "engine_version": "e1", "created_at": CREATED_AT,
        },
        "organization": {
            "id": "org_halcyon", "legal_name": "Halcyon Freight Inc.", "display_name": "Halcyon Freight",
            "sector": "technology_saas", "sub_sector": "B2B logistics & freight software",
            "secondary_sectors": ["logistics_transport"], "business_model": "b2b", "size_band": "mid_market",
            "headquarters_country": "US", "operating_regions": ["US", "EU"],
            "annual_revenue_usd": REVENUE_USD, "total_annual_budget_usd": TOTAL_BUDGET_USD,
            "total_headcount_fte": 420.0, "fiscal_year_start_month": 1,
            "regulatory_frameworks": ["SOC2", "GDPR", "PCI_DSS"],
            "strategic_priorities": [
                {"id": "sp_retention", "text": "Protect enterprise retention", "rank": 1, "kpi_ids": ["kpi_net_retention"]},
                {"id": "sp_margin", "text": "Reach 20% operating margin", "rank": 2, "kpi_ids": ["kpi_gross_margin"]},
                {"id": "sp_compliance", "text": "Maintain SOC 2 / PCI compliance", "rank": 3, "kpi_ids": ["kpi_soc2_coverage"]},
            ],
            "description": "Mid-market B2B logistics-software company serving enterprise shippers in the US and EU.",
            "evidence_refs": ["ev_finance_forecast_q3"],
        },
        "department_profiles": department_profiles,
        "entities": entities,
        "edges": edges,
        "pressures": pressures,
        "documents": documents,
        "evidence": evidence,
    }


REQUIRED_BY_TYPE = {
    "department": ["annual_cost_usd", "capacity_fte"],
    "vendor": ["annual_cost_usd", "one_time_exit_cost_usd"],
    "system": ["annual_cost_usd", "failure_cost_per_day_usd"],
    "project": ["annual_cost_usd", "completion_pct"],
    "workflow": ["min_qualified_owners", "failure_cost_per_day_usd"],
    "role": ["annual_cost_usd", "capacity_fte"],
    "person_token": ["role_id"],
    "knowledge_asset": ["documented_pct"],
    "control": ["mandatory"],
    "kpi": ["kpi_baseline", "kpi_unit", "higher_is_better"],
    "customer_segment": ["arr_usd"],
}


def _self_check(twin: dict[str, Any]) -> None:
    ids = [e["id"] for e in twin["entities"]]
    assert len(ids) == len(set(ids)), "duplicate entity ids"
    idset = set(ids)
    doc_ids = {d["id"] for d in twin["documents"]}
    ev_ids = {v["id"] for v in twin["evidence"]}
    # required-per-type
    for e in twin["entities"]:
        for f in REQUIRED_BY_TYPE.get(e["type"], []):
            assert f in e, f"{e['id']} ({e['type']}) missing required field {f}"
        if e["type"] != "department" and e["id"] != "kpi_company":
            assert "department_id" in e, f"{e['id']} missing department_id"
        if e["type"] == "person_token":
            assert e["id"].startswith("pt_") and e["sensitivity"] == "hr", f"{e['id']} token rules"
    # edges
    edge_ids = set()
    for ed in twin["edges"]:
        assert ed["id"] not in edge_ids, f"dup edge {ed['id']}"
        edge_ids.add(ed["id"])
        assert ed["source"] in idset, f"edge {ed['id']} bad source {ed['source']}"
        assert ed["target"] in idset, f"edge {ed['id']} bad target {ed['target']}"
        lo, hi = ed["strength_range"]
        assert lo <= ed["strength"] <= hi, f"edge {ed['id']} strength out of range"
        if ed["relation"] == "FLOWS_TO":
            assert "channel_kind" in ed, f"FLOWS_TO {ed['id']} needs channel_kind"
        if ed["criticality"] in ("high", "critical"):
            assert ed["evidence_refs"], f"critical edge {ed['id']} needs evidence"
        for r in ed["evidence_refs"]:
            assert r in ev_ids, f"edge {ed['id']} bad evidence ref {r}"
    # evidence -> documents
    for v in twin["evidence"]:
        assert v["document_id"] in doc_ids, f"evidence {v['id']} bad document ref"
    # pressures
    for pr in twin["pressures"]:
        assert pr["target_entity_id"] in idset, f"pressure {pr['id']} bad target"
    # department profiles
    depts = {e["id"] for e in twin["entities"] if e["type"] == "department"}
    prof_depts = {p["department_id"] for p in twin["department_profiles"]}
    assert depts == prof_depts, f"profile mismatch {depts ^ prof_depts}"
    ent_by_id = {e["id"]: e for e in twin["entities"]}
    for p in twin["department_profiles"]:
        de = ent_by_id[p["department_id"]]
        assert p["budget"]["annual_budget_usd"] == de["annual_cost_usd"], f"budget mismatch {p['department_id']}"
        st = p["staffing"]
        assert st["actual_fte"] + st["contractors_fte"] == de["capacity_fte"], f"fte mismatch {p['department_id']}"
        for s in p["strengths"]:
            if s["level"] >= 4:
                assert s["evidence_refs"], f"strength {s['id']} level>=4 needs evidence"
    # org totals (rule 16)
    org = twin["organization"]
    dept_budget = sum(e["annual_cost_usd"] for e in twin["entities"] if e["type"] == "department")
    assert org["total_annual_budget_usd"] == dept_budget == TOTAL_BUDGET_USD, "budget total mismatch"
    fte = sum(p["staffing"]["actual_fte"] + p["staffing"]["contractors_fte"] for p in twin["department_profiles"])
    assert org["total_headcount_fte"] == fte, f"headcount total {fte} != {org['total_headcount_fte']}"
    # every regulatory framework has >=1 control
    for fw in org["regulatory_frameworks"]:
        assert any(e.get("framework") == fw for e in twin["entities"] if e["type"] == "control"), f"no control for {fw}"


PLANTED_ITEMS = {
    "note": "Reference for the demo + Member C AgentView filtering. Synthetic.",
    "missed_dependency": {
        "id": "planted_missed_dep_identity_access",
        "chain": ["vendor_identity", "sys_sso_gateway", "ctl_access_control", "kpi_soc2_coverage"],
        "edges": ["e_identity_provides", "e_ctl_access_sso", "e_access_soc2_coverage"],
        "evidence_refs": ["ev_identity_access", "ev_architecture_core"],
        "why_missed": ("Cross-domain: Finance owns the $70K vendor, Operations owns SSO, Compliance owns "
                       "the control. No single department agent sees the whole chain, so cutting "
                       "vendor_identity looks trivially cheap while it silently breaks SOC 2 CC6.1."),
        "challenger_should_flag": True,
    },
    "hidden_costs": [
        {"id": "hc_migration_carry", "entity": "sys_warehouse_legacy", "usd": 400000,
         "trigger": "stop proj_warehouse_migration",
         "why": "legacy warehouse keeps running; rebound cost reverses the headline saving"},
        {"id": "hc_billing_hazard", "pressure": "pr_billing_recon_hazard",
         "why": "reducing Operations raises billing-failure probability (capacity_sensitivity 3.0); ~$400K/event"},
        {"id": "hc_access_remediation", "control": "ctl_access_control",
         "why": "cutting vendor_identity breaks SOC 2 CC6.1 -> audit remediation + re-audit cost"},
    ],
}


def main() -> None:
    twin = build()
    _self_check(twin)
    base = Path(__file__).resolve().parent
    out = base / "synthetic_company.json"
    out.write_text(json.dumps(twin, indent=2) + "\n")
    (base / "planted_items.json").write_text(json.dumps(PLANTED_ITEMS, indent=2) + "\n")
    print(f"Wrote {base / 'planted_items.json'}")

    from collections import Counter
    kinds = Counter(e["type"] for e in twin["entities"])
    rels = Counter(e["relation"] for e in twin["edges"])
    print(f"Wrote {out}  (schema {twin['schema_version']})")
    print(f"  organization: {twin['organization']['display_name']}  sector={twin['organization']['sector']}")
    print(f"  entities={len(twin['entities'])} edges={len(twin['edges'])} pressures={len(twin['pressures'])} "
          f"documents={len(twin['documents'])} evidence={len(twin['evidence'])} profiles={len(twin['department_profiles'])}")
    print("  entity types:", dict(kinds))
    print("  relations:", dict(rels))
    print(f"  dept budget total=${TOTAL_BUDGET_USD:,}  revenue=${REVENUE_USD:,}  headcount={twin['organization']['total_headcount_fte']:.0f}  cut target=${SAVINGS_TARGET_USD:,}")


if __name__ == "__main__":
    main()
