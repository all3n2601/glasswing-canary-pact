"""Generate the Northstar Technologies company twin - conformant to contracts_py schema 2.1.0.

Deterministic, standard-library only. Emits ``data/synthetic_company.json`` as a full
Twin: schema_version, version, organization, department_profiles, entities, edges,
pressures, documents, evidence.

Run:  uv run python data/generate_company.py

Northstar Technologies is a large-enterprise SaaS company (master plan Milestone A / A-03, A-04):

* Vendor consolidation (plan section 4.1): seven external-data vendors totalling exactly
  $8,000,000,000/yr. Naive plan (Apex + Cinder, greedy by gross savings) is infeasible because
  Apex is the sole provider of the critical ds_corporate_linkage. The recommended plan
  (Beacon + Echo) saves $2.3B gross before transition costs. A planted missed dependency
  (ds_account_intel CONSUMES -> wf_vendor_reconciliation) is deliberately left out of edges[];
  its evidence (ev_echo_account_intel_feed) names both endpoints by display name.
* Workforce knowledge loss (plan section 4.2): eight roles across Finance/Operations/AI-and-Data
  own or back up exactly two critical workflows (wf_financial_close, wf_billing_recon).
  role_controller and role_finance_analyst are qualified backups outside the eight, used only
  by the mitigation, never in the base twin's OWNS/BACKS_UP edges for these two workflows.

All data is synthetic. IDs are frozen in data/id_registry.json (ADHI_BRIEF section 6, A-01).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.1.0"
CREATED_AT = "2026-09-26T12:00:00Z"
AS_OF_DATE = "2026-09-26"

REVENUE_USD = 120_000_000_000
TOTAL_BUDGET_USD = 40_000_000_000        # == sum of department budgets (rule 16)
TOTAL_HEADCOUNT_FTE = 60_000.0           # == sum of department profile FTE (rule 16)
VENDOR_TOTAL_USD = 8_000_000_000         # == sum of the 7 vendors' annual_cost_usd (A-03)

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
        owner_role_id: str | None = None, version: str | None = None,
        last_reviewed: str | None = None, review_cycle_days: int | None = None) -> str:
    rec: dict[str, Any] = {
        "id": id, "title": title, "doc_type": doc_type, "department_id": department_id,
        "owner_role_id": owner_role_id, "uri": f"artifacts/{id}.md", "mime_type": "text/markdown",
        "status": status, "sensitivity": "general", "covers_entity_ids": covers,
        "framework_refs": framework_refs or [], "summary": summary,
        "synthetic": True, "ingested": True, "uploaded_at": CREATED_AT,
    }
    if version is not None:
        rec["version"] = version
    if last_reviewed is not None:
        rec["last_reviewed"] = last_reviewed
    if review_cycle_days is not None:
        rec["review_cycle_days"] = review_cycle_days
    documents.append(rec)
    return id


def evi(id: str, source_type: str, document_id: str, snippet: str, location: str | None = None) -> str:
    evidence.append({"id": id, "source_type": source_type, "document_id": document_id,
                     "location": location, "snippet": snippet, "synthetic": True})
    return id


# =========================================================================== DEPARTMENTS
# (id, name, budget, actual_fte, contractor_fte, head_role, agent, fixed_cost_pct, utilisation,
#  attrition, avg_hire_days, open_positions, mission)
DEPARTMENTS = [
    ("dept_engineering", "Engineering", 9_000_000_000, 16_300, 1_000, "role_eng_manager",
     "engineering", 0.30, 1.05, 0.14, 55, 900,
     "Build and run the revenue-critical product systems."),
    ("dept_operations", "Operations", 3_100_000_000, 5_800, 600, "role_sre",
     "operations", 0.35, 1.12, 0.14, 55, 400,
     "Keep customer-facing platforms and billing operations running."),
    ("dept_ai_data", "AI and Data", 4_000_000_000, 4_500, 500, "role_data_lead",
     "ai_data", 0.35, 1.00, 0.14, 55, 300,
     "Own data pipelines, models, scores and analytics."),
    ("dept_product", "Product", 3_500_000_000, 4_000, 300, "role_product_lead",
     "product", 0.25, 1.00, 0.14, 55, 250,
     "Own roadmap, releases and transformation projects."),
    ("dept_sales", "Sales", 8_000_000_000, 9_000, 500, "role_ae",
     "sales", 0.20, 1.05, 0.14, 55, 600,
     "Win and expand enterprise and mid-market revenue."),
    ("dept_marketing", "Marketing", 2_500_000_000, 2_500, 200, "role_pmm",
     "marketing", 0.15, 1.00, 0.14, 55, 150,
     "Demand generation, segmentation and acquisition."),
    ("dept_customer_success", "Customer Success", 4_500_000_000, 8_000, 800, "role_support_lead",
     "customer_success", 0.40, 1.08, 0.14, 55, 500,
     "Protect retention, SLAs and customer health."),
    ("dept_finance", "Finance", 3_400_000_000, 3_000, 200, "role_controller",
     "finance", 0.45, 1.00, 0.14, 55, 200,
     "Own budget, cost targets, financial KPIs, vendor contracts and the close."),
    ("dept_compliance", "Compliance", 2_000_000_000, 2_500, 300, "role_grc_lead",
     "compliance", 0.55, 1.05, 0.14, 55, 200,
     "Own controls, auditability and regulatory posture."),
]
assert sum(d[2] for d in DEPARTMENTS) == TOTAL_BUDGET_USD
assert sum(d[3] + d[4] for d in DEPARTMENTS) == TOTAL_HEADCOUNT_FTE

DEPT_STRENGTHS = {
    "dept_operations": [
        ("str_ops_incident_response", "Fast incident response", "process", 4,
         ["wf_incident_mgmt", "sys_billing_platform"], ["role_sre"], 0.40, ["ev_incident_review_q2"]),
        ("str_ops_billing_recon", "Billing reconciliation know-how", "expertise", 5,
         ["wf_billing_recon"], ["role_billing_ops_lead"], 0.85, ["ev_knowledge_matrix_billing"]),
    ],
    "dept_engineering": [
        ("str_eng_core", "Core platform engineering", "capability", 4,
         ["sys_core_api"], ["role_eng_manager"], 0.45, ["ev_architecture_core"]),
        ("str_eng_security", "Security engineering", "capability", 4,
         ["ctl_access_control"], ["role_security_eng"], 0.5, ["ev_architecture_core"]),
        ("str_eng_reliability", "Reliability engineering", "process", 3,
         ["kpi_uptime_sla"], ["role_eng_manager"], 0.4, None),
    ],
    "dept_ai_data": [
        ("str_data_pipeline", "Data pipeline engineering", "data", 4,
         ["sys_data_pipeline"], ["role_data_lead"], 0.7, ["ev_data_pipeline_runbook"]),
        ("str_data_ml", "ML modeling and scoring", "capability", 3,
         ["sys_ml_scoring"], ["role_ml_eng"], 0.5, None),
        ("str_data_lineage", "Warehouse lineage knowledge", "data", 4,
         ["wf_financial_close"], ["role_data_platform_lead"], 0.9, ["ev_knowledge_matrix_3"]),
    ],
    "dept_compliance": [
        ("str_comp_soc2", "SOC 2 control mapping", "expertise", 5,
         ["ctl_soc2_audit_logging"], ["role_grc_lead"], 0.9, ["ev_soc2_register_intro"]),
        ("str_comp_privacy", "GDPR / PCI privacy program", "expertise", 4,
         ["ctl_data_retention", "ctl_pci_carddata"], ["role_privacy_counsel"], 0.7,
         ["ev_soc2_register_intro"]),
        ("str_comp_kyc", "KYC screening operation", "process", 3,
         ["wf_kyc_screening", "ctl_kyc_screening"], ["role_grc_lead"], 0.5, None),
    ],
    "dept_product": [
        ("str_prod_delivery", "Roadmap and delivery management", "process", 3,
         ["proj_billing_modernization"], ["role_product_lead"], 0.5, None),
        ("str_prod_discovery", "Product discovery and UX", "capability", 3,
         ["kpi_net_retention"], ["role_ux"], 0.4, None),
    ],
    "dept_sales": [
        ("str_sales_enterprise", "Enterprise selling", "relationship", 4,
         ["seg_enterprise"], ["role_ae"], 0.4, ["ev_finance_forecast_q3"]),
        ("str_sales_solutions", "Solutions and deal engineering", "capability", 3,
         ["seg_midmarket"], ["role_sales_eng"], 0.4, None),
    ],
    "dept_marketing": [
        ("str_mkt_demand", "Digital demand generation", "capability", 3,
         ["kpi_pipeline"], ["role_pmm"], 0.4, None),
        ("str_mkt_analytics", "Marketing analytics and attribution", "data", 3,
         ["kpi_pipeline"], ["role_demand_gen"], 0.4, None),
    ],
    "dept_customer_success": [
        ("str_cs_retention", "Retention and escalation management", "process", 3,
         ["kpi_net_retention"], ["role_csm"], 0.4, None),
        ("str_cs_support", "Support operations", "process", 3,
         ["wf_customer_onboarding"], ["role_support_lead"], 0.4, None),
    ],
    "dept_finance": [
        ("str_fin_fpna", "Driver-based FP&A", "capability", 4,
         ["kpi_gross_margin"], ["role_finance_analyst"], 0.5, ["ev_finance_forecast_q3"]),
        ("str_fin_close", "Monthly close know-how", "expertise", 4,
         ["wf_financial_close"], ["role_controller"], 0.6, ["ev_sop_financial_close_lineage"]),
        ("str_fin_procurement", "Vendor and procurement management", "process", 3,
         ["kn_vendor_contracts"], ["role_procurement"], 0.4, None),
    ],
}

for did, name, budget, actual, contractor, head, agent, fixed, util, attr, hire, openpos, mission in DEPARTMENTS:
    cap = actual + contractor
    ent(did, "department", name, department_id=None, criticality="high",
        annual_cost_usd=budget, capacity_fte=float(cap))
    strengths = []
    for sid, sname, cat, level, supports, key_roles, conc, ev in DEPT_STRENGTHS.get(did, []):
        strengths.append({"id": sid, "name": sname, "category": cat, "level": level,
                          "supports_entity_ids": supports, "key_role_ids": key_roles,
                          "concentration": conc, "evidence_refs": ev or []})
    department_profiles.append({
        "department_id": did, "mission": mission, "head_role_id": head, "agent_id": agent,
        "staffing": {"sanctioned_fte": float(cap), "actual_fte": float(actual),
                     "contractors_fte": float(contractor), "open_positions": openpos,
                     "attrition_rate_annual": attr, "avg_time_to_hire_days": hire, "utilisation": util},
        "budget": {"annual_budget_usd": budget, "spent_ytd_usd": round(budget * 0.726),
                   "fixed_cost_pct": fixed, "budget_owner_role_id": head},
        "strengths": strengths, "gaps": [], "maturity_level": 3,
    })

# Company-level KPI node (no department_id, allowed for kpi_company)
ent("kpi_company", "kpi", "Company KPIs", department_id=None,
    kpi_baseline=0.0, kpi_unit="index", higher_is_better=True)

# =========================================================================== ROLES
# Kept from Mithuna's skill files (ADHI_BRIEF 4.2) + the 8 workforce roles + 2 outside backups.
ROLES = [
    # Engineering
    ("role_staff_eng", "Staff Software Engineer", "dept_engineering", 205_000, 20),
    ("role_security_eng", "Security Engineer", "dept_engineering", 190_000, 8),
    ("role_eng_manager", "Engineering Manager", "dept_engineering", 210_000, 6),
    ("role_qa_eng", "QA Engineer", "dept_engineering", 150_000, 8),
    # Operations
    ("role_billing_ops_lead", "Billing Operations Lead", "dept_operations", 190_000, 3),
    ("role_sre", "Site Reliability Engineer", "dept_operations", 175_000, 12),
    ("role_platform_eng", "Platform Engineer", "dept_operations", 165_000, 8),
    # AI and Data
    ("role_data_lead", "Head of AI and Data", "dept_ai_data", 220_000, 4),
    ("role_ml_eng", "ML Engineer", "dept_ai_data", 180_000, 9),
    ("role_analytics_eng", "Analytics Engineer", "dept_ai_data", 165_000, 6),
    # Product
    ("role_pm", "Product Manager", "dept_product", 175_000, 8),
    ("role_product_lead", "Group Product Manager", "dept_product", 195_000, 3),
    ("role_ux", "UX Designer", "dept_product", 150_000, 5),
    # Sales
    ("role_ae", "Account Executive", "dept_sales", 160_000, 20),
    ("role_sales_eng", "Solutions Engineer", "dept_sales", 175_000, 8),
    ("role_sdr", "Sales Development Rep", "dept_sales", 110_000, 12),
    # Marketing
    ("role_pmm", "Product Marketing Manager", "dept_marketing", 150_000, 8),
    ("role_demand_gen", "Demand Gen Manager", "dept_marketing", 150_000, 6),
    ("role_brand", "Brand and Comms Manager", "dept_marketing", 140_000, 4),
    # Customer Success
    ("role_csm", "Customer Success Manager", "dept_customer_success", 140_000, 18),
    ("role_support_lead", "Support Team Lead", "dept_customer_success", 130_000, 10),
    ("role_onboarding", "Onboarding Specialist", "dept_customer_success", 120_000, 12),
    # Finance
    ("role_finance_analyst", "Finance Analyst", "dept_finance", 150_000, 9),
    ("role_procurement", "Procurement Manager", "dept_finance", 150_000, 3),
    ("role_controller", "Controller", "dept_finance", 175_000, 4),
    # Compliance
    ("role_grc_lead", "GRC Lead", "dept_compliance", 170_000, 3),
    ("role_privacy_counsel", "Privacy Counsel", "dept_compliance", 175_000, 3),
    # --- workforce knowledge-loss scenario: the 8 roles (ADHI_BRIEF 4.4) ---
    ("role_close_accountant", "Close Accountant", "dept_finance", 145_000, 4),
    ("role_gl_accountant", "General Ledger Accountant", "dept_finance", 120_000, 5),
    ("role_reporting_analyst", "Financial Reporting Analyst", "dept_finance", 110_000, 3),
    ("role_data_platform_lead", "Data Platform Lead", "dept_ai_data", 195_000, 2),
    ("role_billing_specialist", "Billing Specialist", "dept_operations", 95_000, 6),
    ("role_revenue_accountant", "Revenue Accountant", "dept_finance", 130_000, 4),
    ("role_ar_specialist", "Accounts Receivable Specialist", "dept_finance", 85_000, 8),
]
for rid, name, did, salary, fte in ROLES:
    ent(rid, "role", name, department_id=did, annual_cost_usd=salary, capacity_fte=float(fte))

# Every workforce role that eliminating strands a workflow (goal target = exact sum, ADHI_BRIEF 13.1).
WORKFORCE_ROLE_IDS = [
    "role_close_accountant", "role_gl_accountant", "role_reporting_analyst", "role_data_platform_lead",
    "role_billing_ops_lead", "role_billing_specialist", "role_revenue_accountant", "role_ar_specialist",
]
WORKFORCE_BACKUP_ROLE_IDS = ["role_controller", "role_finance_analyst"]

# =========================================================================== PERSON TOKENS
# One anonymised token per role (role-level logic only; A5). Never carries OWNS/BACKS_UP/KNOWS.
for i, (rid, _name, did, _salary, _fte) in enumerate(ROLES, start=1):
    ent(f"pt_{i:02d}", "person_token", f"Person token {i:02d}", department_id=did,
        sensitivity="hr", role_id=rid)

# =========================================================================== SYSTEMS
SYSTEMS = [
    # id, name, dept, tier(crit), annual_cost, failure_cost_per_day, customer_facing, tags
    ("sys_core_api", "core-api", "dept_engineering", "critical", 8_000_000, 3_000_000, True, []),
    ("sys_customer_portal", "customer-portal", "dept_engineering", "high", 4_000_000, 1_500_000, True, []),
    ("sys_billing_platform", "billing-platform", "dept_operations", "critical", 6_000_000, 2_500_000, True, []),
    ("sys_invoicing", "invoicing-service", "dept_operations", "critical", 3_000_000, 2_000_000, True, []),
    ("sys_cloud_platform", "cloud-platform", "dept_operations", "critical", 9_000_000, 3_000_000, False, []),
    ("sys_sso_gateway", "sso-gateway", "dept_operations", "high", 2_000_000, 1_000_000, True, []),
    ("sys_data_pipeline", "data-pipeline", "dept_ai_data", "high", 4_500_000, 800_000, False, []),
    ("sys_ml_scoring", "ml-scoring-service", "dept_ai_data", "medium", 3_500_000, 500_000, False, ["ml_model"]),
    ("sys_audit_service", "audit-log-service", "dept_compliance", "high", 2_200_000, 700_000, False, []),
    ("sys_data_warehouse", "data-warehouse", "dept_ai_data", "medium", 3_800_000, 300_000, False, []),
    ("sys_crm", "crm", "dept_sales", "high", 5_000_000, 1_200_000, False, []),
]
for sid, name, did, crit, cost, fail, cust, tags in SYSTEMS:
    ent(sid, "system", name, department_id=did, criticality=crit,
        annual_cost_usd=cost, failure_cost_per_day_usd=fail, customer_facing=cust,
        migration_cost_usd=round(cost * 0.4), tags=tags)

# =========================================================================== DATASETS
# ds_audit_log is internal (produced by sys_audit_service, not vendor-provided).
DATASETS = [
    ("ds_audit_log", "Audit-log event stream", "dept_compliance", "critical"),
    ("ds_firmographics", "Firmographics", "dept_sales", "medium"),
    ("ds_contact_data", "Contact data", "dept_sales", "medium"),
    ("ds_corporate_linkage", "Corporate linkage", "dept_compliance", "critical"),
    ("ds_intent_signals", "Intent signals", "dept_marketing", "medium"),
    ("ds_identity_verification", "Identity verification", "dept_compliance", "critical"),
    ("ds_market_intel", "Market intelligence", "dept_marketing", "medium"),
    ("ds_account_intel", "Account intelligence", "dept_sales", "medium"),
    ("ds_usage", "Product usage signals", "dept_product", "medium"),
    ("ds_geo_risk", "Geographic and macroeconomic risk", "dept_operations", "medium"),
]
for dsid, name, did, crit in DATASETS:
    ent(dsid, "dataset", name, department_id=did, criticality=crit)

# =========================================================================== VENDORS (plan section 4.1)
# id, name, dept (main consumer), cost, exit_cost, migration_cost, criticality
VENDORS = [
    ("vendor_apex", "ApexData", "dept_sales", 1_600_000_000, 60_000_000, 100_000_000, "high"),
    ("vendor_beacon", "BeaconIQ", "dept_sales", 1_200_000_000, 40_000_000, 55_000_000, "medium"),
    ("vendor_cinder", "CinderSignals", "dept_marketing", 1_400_000_000, 50_000_000, 90_000_000, "medium"),
    ("vendor_delta", "DeltaVerify", "dept_compliance", 900_000_000, 30_000_000, 50_000_000, "critical"),
    ("vendor_echo", "EchoMarket", "dept_product", 1_100_000_000, 50_000_000, 75_000_000, "medium"),
    ("vendor_flux", "FluxBehavior", "dept_product", 800_000_000, 25_000_000, 40_000_000, "low"),
    ("vendor_granite", "GraniteGeo", "dept_operations", 1_000_000_000, 35_000_000, 55_000_000, "medium"),
]
assert sum(v[3] for v in VENDORS) == VENDOR_TOTAL_USD
assert sum(v[3] for v in VENDORS if v[0] in ("vendor_beacon", "vendor_echo")) == 2_300_000_000
assert sum(v[4] for v in VENDORS if v[0] in ("vendor_beacon", "vendor_echo")) == 90_000_000
assert sum(v[5] for v in VENDORS if v[0] in ("vendor_beacon", "vendor_echo")) == 130_000_000
for vid, name, did, cost, exit_c, mig_c, crit in VENDORS:
    ent(vid, "vendor", name, department_id=did, criticality=crit,
        annual_cost_usd=cost, one_time_exit_cost_usd=exit_c, migration_cost_usd=mig_c)

# =========================================================================== WORKFLOWS
# id, name, dept, crit, min_owners, failure_cost_per_day, documented_pct, customer_facing
WORKFLOWS = [
    ("wf_billing_recon", "Billing reconciliation", "dept_operations", "critical", 2, 900_000, 0.35, True),
    ("wf_invoicing", "Invoice generation and dispatch", "dept_operations", "critical", 2, 1_200_000, 0.6, True),
    ("wf_incident_mgmt", "Incident response and on-call", "dept_operations", "high", 2, 600_000, 0.7, False),
    ("wf_soc2_evidence", "SOC 2 audit-evidence collection", "dept_compliance", "high", 1, 150_000, 0.8, False),
    ("wf_customer_onboarding", "Customer onboarding", "dept_customer_success", "medium", 2, 300_000, 0.5, True),
    ("wf_data_refresh", "Data pipeline refresh", "dept_ai_data", "high", 2, 400_000, 0.6, False),
    ("wf_financial_close", "Monthly financial close", "dept_finance", "critical", 2, 250_000, 0.6, False),
    ("wf_lead_scoring", "Lead scoring", "dept_sales", "medium", 1, 500_000, 0.7, False),
    ("wf_campaign_targeting", "Campaign targeting", "dept_marketing", "medium", 1, 400_000, 0.65, False),
    ("wf_account_planning", "Account planning", "dept_sales", "medium", 1, 600_000, 0.6, False),
    ("wf_kyc_screening", "KYC screening", "dept_compliance", "critical", 1, 2_000_000, 0.8, False),
    ("wf_vendor_reconciliation", "Vendor reconciliation", "dept_operations", "high", 2, 2_500_000, 0.55, False),
    ("wf_product_analytics", "Product analytics", "dept_product", "medium", 1, 300_000, 0.6, False),
    ("wf_risk_monitoring", "Risk monitoring", "dept_operations", "high", 1, 800_000, 0.5, False),
]
for wid, name, did, crit, minown, fail, docp, cust in WORKFLOWS:
    ent(wid, "workflow", name, department_id=did, criticality=crit,
        min_qualified_owners=minown, failure_cost_per_day_usd=fail,
        documented_pct=docp, customer_facing=cust)

# =========================================================================== KNOWLEDGE
KNOWLEDGE = [
    ("kn_billing_exception", "Billing-recon exception handling", "dept_operations", 0.35, "critical"),
    ("kn_warehouse_lineage", "Warehouse lineage knowledge", "dept_ai_data", 0.2, "critical"),
    ("kn_soc2_mapping", "SOC 2 control-to-evidence mapping", "dept_compliance", 0.4, "high"),
    ("kn_data_format", "Upstream data-format quirk handling", "dept_ai_data", 0.3, "high"),
    ("kn_oncall", "On-call escalation and recovery", "dept_operations", 0.7, "medium"),
    ("kn_core_arch", "Core-API architecture knowledge", "dept_engineering", 0.7, "medium"),
    ("kn_release_eng", "Release and deploy engineering", "dept_engineering", 0.75, "medium"),
    ("kn_ml_modeling", "ML scoring model knowledge", "dept_ai_data", 0.6, "medium"),
    ("kn_roadmap_context", "Product roadmap and customer context", "dept_product", 0.7, "medium"),
    ("kn_enterprise_deals", "Enterprise deal and pricing know-how", "dept_sales", 0.65, "medium"),
    ("kn_segmentation", "Audience segmentation and attribution", "dept_marketing", 0.7, "medium"),
    ("kn_onboarding_playbook", "Customer onboarding playbook", "dept_customer_success", 0.75, "medium"),
    ("kn_cs_escalation", "CS escalation handling", "dept_customer_success", 0.7, "medium"),
    ("kn_vendor_contracts", "Vendor contract and renewal know-how", "dept_finance", 0.6, "medium"),
    ("kn_privacy_program", "Privacy program operation", "dept_compliance", 0.7, "medium"),
]
for kid, name, did, docp, crit in KNOWLEDGE:
    ent(kid, "knowledge_asset", name, department_id=did, criticality=crit, documented_pct=docp)

# =========================================================================== CONTROLS
CONTROLS = [
    ("ctl_soc2_audit_logging", "SOC 2 CC7.2 - audit logging", "SOC2", True, "critical"),
    ("ctl_access_control", "SOC 2 CC6.1 - logical access", "SOC2", True, "high"),
    ("ctl_data_retention", "GDPR data retention", "GDPR", True, "high"),
    ("ctl_pci_carddata", "PCI DSS cardholder data", "PCI_DSS", True, "high"),
    ("ctl_incident_mgmt", "Incident management", "SOC2", True, "high"),
    ("ctl_change_mgmt", "Change management", "SOC2", False, "medium"),
    ("ctl_kyc_screening", "KYC screening control", "SOX", True, "critical"),
    ("ctl_sox_reconciliation", "SOX vendor-spend reconciliation", "SOX", True, "high"),
]
for cid, name, fw, mand, crit in CONTROLS:
    ent(cid, "control", name, department_id="dept_compliance", criticality=crit,
        mandatory=mand, framework=fw)

# =========================================================================== PROJECTS
PROJECTS = [
    # id, name, dept, budget, completion, cancel_cost, expected_completion_day
    ("proj_billing_modernization", "Billing Modernization", "dept_product", 8_000_000, 0.30, 1_000_000, 240),
    ("proj_soc2_type2", "SOC 2 Type II Certification", "dept_product", 4_000_000, 0.60, 500_000, 90),
]
for pid, name, did, budget, comp, cancel, exp_day in PROJECTS:
    ent(pid, "project", name, department_id=did, criticality="medium",
        annual_cost_usd=budget, completion_pct=comp, retires_entity_ids=[],
        one_time_exit_cost_usd=cancel,
        remaining_cost_usd=round(budget * (1 - comp)),
        expected_completion_day=exp_day)

# =========================================================================== KPIs
KPIS = [
    ("kpi_gross_margin", "Gross margin %", "dept_finance", 62.0, "percent", True),
    ("kpi_net_retention", "Net revenue retention", "dept_sales", 112.0, "percent", True),
    ("kpi_pipeline", "Qualified pipeline", "dept_marketing", 4_500_000_000.0, "usd", True),
    ("kpi_uptime_sla", "System uptime / SLA", "dept_operations", 99.9, "percent", True),
    ("kpi_soc2_coverage", "SOC 2 compliance coverage", "dept_compliance", 100.0, "percent", True),
    ("kpi_cac", "Customer acquisition cost", "dept_marketing", 42_000.0, "usd", False),
    ("kpi_close_cycle_days", "Close cycle days", "dept_finance", 6.5, "days", False),
]
for kid, name, did, base, unit, hib in KPIS:
    ent(kid, "kpi", name, department_id=did, kpi_baseline=base, kpi_unit=unit, higher_is_better=hib)

# =========================================================================== CUSTOMER SEGMENTS
ent("seg_enterprise", "customer_segment", "Enterprise accounts", department_id="dept_sales",
    criticality="critical", arr_usd=80_000_000_000)
ent("seg_midmarket", "customer_segment", "Mid-market accounts", department_id="dept_sales",
    criticality="high", arr_usd=25_000_000_000)

# =========================================================================== DOCUMENTS + EVIDENCE
doc("doc_department_map", "Department operating-model map", "architecture_note",
    department_id=None, status="current", covers=[],
    summary="How departments fund, constrain and supply each other.")
evi("ev_department_map_v1", "architecture_note", "doc_department_map",
    "Finance sets budget limits for Engineering and Marketing.")

doc("doc_billing_recon_runbook", "Billing reconciliation runbook", "runbook",
    department_id="dept_operations", status="outdated", covers=["wf_billing_recon"],
    summary="Monthly reconciliation steps; exception-handling section missing since the vendor change.",
    framework_refs=["SOX"], owner_role_id="role_billing_ops_lead", version="v1.4",
    last_reviewed="2025-03-10", review_cycle_days=180)
evi("ev_billing_runbook_gap", "runbook", "doc_billing_recon_runbook",
    "Exception path is undocumented; only the billing owners can resolve a failed run.",
    location="section 6")
evi("ev_knowledge_matrix_billing", "knowledge_matrix", "doc_billing_recon_runbook",
    "Billing reconciliation know-how is concentrated in two roles.")

doc("doc_invoicing_sop", "Invoicing SOP", "sop", department_id="dept_operations", status="current",
    covers=["wf_invoicing"], summary="Standard operating procedure for invoice generation and dispatch.",
    framework_refs=["SOX"], owner_role_id="role_billing_ops_lead")
evi("ev_invoicing_sop", "workflow_map", "doc_invoicing_sop", "Invoicing runs after reconciliation completes.")

doc("doc_incident_report", "Incident review", "incident_report",
    department_id="dept_operations", status="current",
    covers=["wf_incident_mgmt", "wf_billing_recon", "wf_vendor_reconciliation"],
    summary="Reconciliation failures happen a few times a year; likelier when owners lose capacity.")
evi("ev_incident_22", "incident", "doc_incident_report",
    "A failed vendor reconciliation cost about $40M to correct.", location="INC-22")
evi("ev_incident_31", "incident", "doc_incident_report",
    "A failed billing reconciliation cost about $60M in credits and rework.", location="INC-31")
evi("ev_incident_review_q2", "incident", "doc_incident_report",
    "Incident response resolved P1s within SLA in Q2.")

doc("doc_soc2_register", "SOC 2 control register", "audit_report",
    department_id="dept_compliance", status="current",
    covers=["ctl_soc2_audit_logging", "ctl_access_control", "wf_soc2_evidence",
            "ctl_data_retention", "ctl_pci_carddata"],
    summary="Mapping of SOC 2, GDPR and PCI controls to their evidence sources.",
    framework_refs=["SOC2", "GDPR", "PCI_DSS"])
evi("ev_soc2_register_intro", "policy", "doc_soc2_register",
    "CC7.2 requires continuous audit-log evidence retained for 12 months.")

doc("doc_finance_forecast", "FY forecast", "financial_forecast",
    department_id="dept_finance", status="current", covers=["kpi_gross_margin"],
    summary="Cost and revenue forecast; Flux usage and contractor rates both rising.")
evi("ev_finance_forecast_q3", "finance_forecast", "doc_finance_forecast",
    "Flux usage costs rise about 1.5% a month; contractor rates rise about 1% a month.")

doc("doc_procurement_register", "Vendor and procurement register", "contract",
    department_id="dept_finance", status="current",
    covers=["vendor_apex", "vendor_beacon", "vendor_cinder", "vendor_delta", "vendor_echo",
            "vendor_flux", "vendor_granite", "kn_vendor_contracts"],
    summary="Vendor spend, renewal dates and substitutability notes across all seven vendors.")

doc("doc_knowledge_matrix", "Role knowledge matrix", "knowledge_matrix",
    department_id=None, status="current",
    covers=["kn_billing_exception", "kn_warehouse_lineage", "kn_soc2_mapping"],
    summary="Role holders and documentation status for each critical knowledge area.")
evi("ev_knowledge_matrix_3", "knowledge_matrix", "doc_knowledge_matrix",
    "Warehouse lineage is held by one role and is about 20% documented.")

doc("doc_data_pipeline_runbook", "Data pipeline runbook", "runbook", department_id="dept_ai_data",
    status="current", covers=["wf_data_refresh", "sys_data_pipeline"],
    summary="Refresh schedule, backfills and failure recovery for the data pipeline.")
evi("ev_data_pipeline_runbook", "runbook", "doc_data_pipeline_runbook",
    "Refresh recovers from a failed batch via replay.")

doc("doc_architecture", "System architecture notes", "architecture_note",
    department_id="dept_engineering", status="current",
    covers=["sys_core_api", "sys_billing_platform", "sys_audit_service", "sys_crm"],
    summary="Service dependency map for core, billing, audit and CRM systems.")
evi("ev_architecture_core", "architecture_note", "doc_architecture",
    "Invoicing consumes the reconciled ledger from billing-recon; billing runs on billing-platform.")

doc("doc_eng_release", "Release engineering guide", "runbook", department_id="dept_engineering",
    status="current", covers=["kn_release_eng", "sys_core_api"],
    summary="Build, test and deploy pipeline for core services.")

doc("doc_product_roadmap", "Product roadmap", "strategy_memo", department_id="dept_product",
    status="current", covers=["proj_billing_modernization", "kn_roadmap_context"],
    summary="Sequenced roadmap of transformation projects and releases.")

doc("doc_mkt_attribution", "Marketing attribution model", "kpi_report", department_id="dept_marketing",
    status="current", covers=["kpi_pipeline", "kn_segmentation"],
    summary="Multi-touch attribution feeding qualified pipeline.")

doc("doc_sales_playbook", "Enterprise sales playbook", "sop", department_id="dept_sales",
    status="current", covers=["seg_enterprise", "kn_enterprise_deals"],
    summary="Enterprise qualification, pricing and close motion.")

doc("doc_cs_runbook", "Customer onboarding and escalation runbook", "runbook",
    department_id="dept_customer_success", status="current",
    covers=["wf_customer_onboarding", "kn_onboarding_playbook"],
    summary="Onboarding steps and escalation paths for enterprise accounts.")

doc("doc_sop_financial_close", "Monthly financial close SOP", "sop", department_id="dept_finance",
    status="current", covers=["wf_financial_close", "kn_warehouse_lineage"],
    owner_role_id="role_controller",
    summary="Monthly close steps; defers warehouse-lineage questions to the Data Platform Lead.")
evi("ev_sop_financial_close_lineage", "workflow_map", "doc_sop_financial_close",
    "The monthly close SOP defers warehouse lineage questions to the Data Platform Lead.")

doc("doc_kyc_screening_sop", "KYC screening SOP", "sop", department_id="dept_compliance",
    status="current", covers=["wf_kyc_screening", "ds_identity_verification", "ds_corporate_linkage"],
    framework_refs=["SOX"],
    summary="KYC screening uses the Identity verification and Corporate linkage datasets.")
evi("ev_kyc_screening_inputs", "workflow_map", "doc_kyc_screening_sop",
    "KYC screening reads the Identity verification dataset and the Corporate linkage dataset.")

# --- vendor MSAs ---
VENDOR_MSA_TEXT = {
    "vendor_apex": ("ApexData", "Apex Data auto-renews on day 60 with an 8% price uplift.", "clause 12.2"),
    "vendor_beacon": ("BeaconIQ", "BeaconIQ term end, notice period and exit fee.", "schedule 1"),
    "vendor_cinder": ("CinderSignals", "CinderSignals is the exclusive licensed source of intent signals.",
                       "clause 4"),
    "vendor_delta": ("DeltaVerify", "DeltaVerify term end, notice period and exit fee.", "schedule 1"),
    "vendor_echo": ("EchoMarket", "EchoMarket renews on day 120 with a 12% price uplift; the termination "
                    "section does not say whether EchoMarket history is retained after exit.", "clause 9"),
    "vendor_flux": ("FluxBehavior", "FluxBehavior is billed per record consumed.", "schedule 2"),
    "vendor_granite": ("GraniteGeo", "GraniteGeo term end, notice period and exit fee.", "schedule 1"),
}
VENDOR_MSA_EVIDENCE_ID = {
    "vendor_apex": "ev_apex_msa_renewal",
    "vendor_beacon": "ev_beacon_msa_terms",
    "vendor_cinder": "ev_cinder_msa_terms",
    "vendor_delta": "ev_delta_msa_terms",
    "vendor_echo": "ev_echo_msa_clause_9",
    "vendor_flux": "ev_flux_usage_pricing",
    "vendor_granite": "ev_granite_msa_terms",
}
for vid, (vname, snippet, location) in VENDOR_MSA_TEXT.items():
    short = vid.removeprefix("vendor_")
    doc(f"doc_{short}_msa", f"{vname} master services agreement", "contract",
        department_id="dept_finance", status="current", covers=[vid],
        owner_role_id="role_procurement",
        summary=f"{vname} master services agreement: term, renewal, pricing and exit terms.")
    evi(VENDOR_MSA_EVIDENCE_ID[vid], "contract", f"doc_{short}_msa", snippet, location=location)
evi("ev_echo_history_retention", "contract", "doc_echo_msa",
    "The termination section does not say whether EchoMarket history is retained after exit.",
    location="section 14")

doc("doc_data_vendor_inventory", "External data vendor inventory", "architecture_note",
    department_id="dept_ai_data", status="current",
    covers=["vendor_apex", "vendor_beacon", "vendor_cinder", "vendor_delta", "vendor_echo",
            "vendor_flux", "vendor_granite", "ds_firmographics", "ds_contact_data",
            "ds_corporate_linkage", "ds_intent_signals", "ds_identity_verification",
            "ds_market_intel", "ds_account_intel", "ds_usage", "ds_geo_risk"],
    summary="Vendor-to-dataset feed matrix with attribute groups and consuming workflows.")
evi("ev_vendor_dataset_matrix", "architecture_note", "doc_data_vendor_inventory",
    "Vendor-to-dataset feed matrix with attribute groups and consuming workflows.", location="table 1")

doc("doc_vendor_recon_workflow_map", "Vendor reconciliation workflow map", "workflow_map",
    department_id="dept_operations", status="current",
    covers=["wf_vendor_reconciliation", "ds_audit_log", "ctl_sox_reconciliation"],
    framework_refs=["SOX"],
    summary="Inputs and control dependencies for the monthly vendor reconciliation workflow.")
evi("ev_vendor_recon_inputs", "workflow_map", "doc_vendor_recon_workflow_map",
    "Vendor reconciliation inputs include the internal audit-log dataset.", location="step 2")
# Planted evidence (A16): names both endpoints of the omitted edge by display name.
evi("ev_echo_account_intel_feed", "workflow_map", "doc_vendor_recon_workflow_map",
    "The Account intelligence dataset also feeds the Vendor reconciliation workflow each month.",
    location="section 3.4")


# =========================================================================== EDGES
# --- role-level ownership / knowledge (A5: role-level logic only) ---
edge("e_close_accountant_owns_close", "role_close_accountant", "wf_financial_close", "OWNS",
     strength=0.5, substitutability=0.2, criticality="critical",
     evidence_refs=["ev_sop_financial_close_lineage"])
edge("e_gl_accountant_owns_close", "role_gl_accountant", "wf_financial_close", "OWNS",
     strength=0.5, substitutability=0.2, criticality="critical",
     evidence_refs=["ev_sop_financial_close_lineage"])
edge("e_reporting_analyst_backs_close", "role_reporting_analyst", "wf_financial_close", "BACKS_UP",
     strength=0.3, substitutability=0.3, criticality="high",
     evidence_refs=["ev_sop_financial_close_lineage"])
edge("e_data_platform_lead_knows_lineage", "role_data_platform_lead", "kn_warehouse_lineage", "KNOWS",
     strength=0.95, substitutability=0.05, criticality="critical", evidence_refs=["ev_knowledge_matrix_3"])
edge("e_lineage_supports_close", "kn_warehouse_lineage", "wf_financial_close", "SUPPORTS",
     strength=0.8, substitutability=0.1, criticality="critical", evidence_refs=["ev_knowledge_matrix_3"])

edge("e_billing_ops_lead_owns_recon", "role_billing_ops_lead", "wf_billing_recon", "OWNS",
     strength=0.6, substitutability=0.2, criticality="critical",
     evidence_refs=["ev_knowledge_matrix_billing"])
edge("e_billing_specialist_owns_recon", "role_billing_specialist", "wf_billing_recon", "OWNS",
     strength=0.5, substitutability=0.2, criticality="critical",
     evidence_refs=["ev_knowledge_matrix_billing"])
edge("e_revenue_accountant_backs_recon", "role_revenue_accountant", "wf_billing_recon", "BACKS_UP",
     strength=0.3, substitutability=0.3, criticality="high", evidence_refs=["ev_billing_runbook_gap"])
edge("e_ar_specialist_backs_recon", "role_ar_specialist", "wf_billing_recon", "BACKS_UP",
     strength=0.3, substitutability=0.3, criticality="high", evidence_refs=["ev_billing_runbook_gap"])
edge("e_billing_ops_lead_knows_exception", "role_billing_ops_lead", "kn_billing_exception", "KNOWS",
     strength=0.9, substitutability=0.1, criticality="critical", evidence_refs=["ev_billing_runbook_gap"])
edge("e_billing_specialist_knows_exception", "role_billing_specialist", "kn_billing_exception", "KNOWS",
     strength=0.9, substitutability=0.1, criticality="critical", evidence_refs=["ev_billing_runbook_gap"])
edge("e_kn_billing_supports_recon", "kn_billing_exception", "wf_billing_recon", "SUPPORTS",
     strength=0.9, substitutability=0.1, criticality="critical", evidence_refs=["ev_billing_runbook_gap"])

edge("e_sre_owns_incident", "role_sre", "wf_incident_mgmt", "OWNS", strength=0.7, substitutability=0.3,
     criticality="high", evidence_refs=["ev_incident_review_q2"])
edge("e_grc_lead_knows_soc2_mapping", "role_grc_lead", "kn_soc2_mapping", "KNOWS", strength=0.9,
     substitutability=0.15, criticality="high", evidence_refs=["ev_soc2_register_intro"])
edge("e_kn_soc2_supports_evidence", "kn_soc2_mapping", "wf_soc2_evidence", "SUPPORTS", strength=0.85,
     substitutability=0.2, criticality="high", evidence_refs=["ev_soc2_register_intro"])
edge("e_data_lead_knows_format", "role_data_lead", "kn_data_format", "KNOWS", strength=0.85,
     substitutability=0.2, criticality="high", evidence_refs=["ev_data_pipeline_runbook"])
edge("e_kn_format_supports_refresh", "kn_data_format", "wf_data_refresh", "SUPPORTS", strength=0.8,
     substitutability=0.2, criticality="high", evidence_refs=["ev_data_pipeline_runbook"])
edge("e_privacy_counsel_knows_privacy", "role_privacy_counsel", "kn_privacy_program", "KNOWS",
     strength=0.8, substitutability=0.3, criticality="medium")

# --- systems support workflows / each other ---
edge("e_billing_platform_recon", "sys_billing_platform", "wf_billing_recon", "SUPPORTS", strength=0.85,
     substitutability=0.25, lag_days=15, criticality="critical", evidence_refs=["ev_architecture_core"])
edge("e_recon_invoicing", "wf_billing_recon", "wf_invoicing", "SUPPORTS", strength=0.9,
     substitutability=0.2, lag_days=15, criticality="critical", evidence_refs=["ev_architecture_core"])
edge("e_sso_portal", "sys_sso_gateway", "sys_customer_portal", "SUPPORTS", strength=0.7,
     substitutability=0.4, lag_days=7, criticality="high", evidence_refs=["ev_architecture_core"])
edge("e_cloud_core", "sys_cloud_platform", "sys_core_api", "SUPPORTS", strength=0.8,
     substitutability=0.5, lag_days=7, criticality="critical", evidence_refs=["ev_architecture_core"])
edge("e_crm_lead_scoring", "sys_crm", "wf_lead_scoring", "SUPPORTS", strength=0.8, substitutability=0.3,
     criticality="medium", evidence_refs=["ev_architecture_core"])
edge("e_crm_account_planning", "sys_crm", "wf_account_planning", "SUPPORTS", strength=0.7,
     substitutability=0.3, criticality="medium", evidence_refs=["ev_architecture_core"])

# --- internal audit-log dataset (produced by sys_audit_service, not vendor-provided) ---
edge("e_auditsvc_provides_auditlog", "sys_audit_service", "ds_audit_log", "PROVIDES", strength=0.95,
     substitutability=0.1, lag_days=1, criticality="critical", evidence_refs=["ev_soc2_register_intro"])
edge("e_auditlog_supports_soc2", "ds_audit_log", "ctl_soc2_audit_logging", "SUPPORTS", strength=1.0,
     substitutability=0.05, lag_days=1, criticality="critical", evidence_refs=["ev_soc2_register_intro"])
edge("e_auditlog_consumed_by_recon", "ds_audit_log", "wf_vendor_reconciliation", "CONSUMES", strength=0.6,
     substitutability=0.3, criticality="medium", evidence_refs=["ev_vendor_recon_inputs"])

# --- vendors PROVIDE datasets (plan section 4.1 / ADHI_BRIEF 4.3) ---
edge("e_apex_provides_firmographics", "vendor_apex", "ds_firmographics", "PROVIDES", strength=0.8,
     substitutability=0.5, evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_beacon_provides_firmographics", "vendor_beacon", "ds_firmographics", "PROVIDES", strength=0.7,
     substitutability=0.5, evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_echo_provides_firmographics", "vendor_echo", "ds_firmographics", "PROVIDES", strength=0.5,
     substitutability=0.6, evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_apex_provides_contact_data", "vendor_apex", "ds_contact_data", "PROVIDES", strength=0.8,
     substitutability=0.4, evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_beacon_provides_contact_data", "vendor_beacon", "ds_contact_data", "PROVIDES", strength=0.7,
     substitutability=0.4, evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_apex_provides_corporate_linkage", "vendor_apex", "ds_corporate_linkage", "PROVIDES", strength=0.95,
     substitutability=0.05, criticality="critical", evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_cinder_provides_intent", "vendor_cinder", "ds_intent_signals", "PROVIDES", strength=0.8,
     substitutability=0.5, evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_echo_provides_intent", "vendor_echo", "ds_intent_signals", "PROVIDES", strength=0.6,
     substitutability=0.5, evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_delta_provides_identity", "vendor_delta", "ds_identity_verification", "PROVIDES", strength=0.95,
     substitutability=0.05, criticality="critical", evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_apex_provides_market_intel", "vendor_apex", "ds_market_intel", "PROVIDES", strength=0.7,
     substitutability=0.4, evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_cinder_provides_market_intel", "vendor_cinder", "ds_market_intel", "PROVIDES", strength=0.7,
     substitutability=0.4, evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_echo_provides_market_intel", "vendor_echo", "ds_market_intel", "PROVIDES", strength=0.7,
     substitutability=0.4, evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_echo_provides_account_intel", "vendor_echo", "ds_account_intel", "PROVIDES", strength=0.9,
     substitutability=0.15, criticality="high", evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_flux_provides_usage", "vendor_flux", "ds_usage", "PROVIDES", strength=0.9, substitutability=0.3,
     evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_granite_provides_geo_risk", "vendor_granite", "ds_geo_risk", "PROVIDES", strength=0.8,
     substitutability=0.4, evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_delta_provides_geo_risk", "vendor_delta", "ds_geo_risk", "PROVIDES", strength=0.6,
     substitutability=0.4, evidence_refs=["ev_vendor_dataset_matrix"])

# --- datasets CONSUMED by workflows / systems (base twin; the planted edge is NOT here) ---
edge("e_firmographics_consumed_leadscoring", "ds_firmographics", "wf_lead_scoring", "CONSUMES",
     strength=0.7, substitutability=0.4, criticality="medium")
edge("e_firmographics_consumed_campaign", "ds_firmographics", "wf_campaign_targeting", "CONSUMES",
     strength=0.6, substitutability=0.4, criticality="medium")
edge("e_contactdata_consumed_leadscoring", "ds_contact_data", "wf_lead_scoring", "CONSUMES",
     strength=0.7, substitutability=0.4, criticality="medium")
edge("e_corporate_linkage_consumed_kyc", "ds_corporate_linkage", "wf_kyc_screening", "CONSUMES",
     strength=0.9, substitutability=0.05, criticality="critical", evidence_refs=["ev_kyc_screening_inputs"])
edge("e_intent_consumed_campaign", "ds_intent_signals", "wf_campaign_targeting", "CONSUMES",
     strength=0.7, substitutability=0.4, criticality="medium")
edge("e_identity_consumed_kyc", "ds_identity_verification", "wf_kyc_screening", "CONSUMES",
     strength=0.95, substitutability=0.05, criticality="critical", evidence_refs=["ev_kyc_screening_inputs"])
edge("e_market_intel_consumed_campaign", "ds_market_intel", "wf_campaign_targeting", "CONSUMES",
     strength=0.5, substitutability=0.5, criticality="medium")
edge("e_market_intel_consumed_account_planning", "ds_market_intel", "wf_account_planning", "CONSUMES",
     strength=0.6, substitutability=0.5, criticality="medium")
edge("e_account_intel_consumed_account_planning", "ds_account_intel", "wf_account_planning", "CONSUMES",
     strength=0.8, substitutability=0.2, criticality="high", evidence_refs=["ev_vendor_dataset_matrix"])
edge("e_usage_consumed_product_analytics", "ds_usage", "wf_product_analytics", "CONSUMES",
     strength=0.8, substitutability=0.3, criticality="medium")
edge("e_geo_risk_consumed_risk_monitoring", "ds_geo_risk", "wf_risk_monitoring", "CONSUMES",
     strength=0.7, substitutability=0.4, criticality="medium")
edge("e_market_intel_consumed_ml_scoring", "ds_market_intel", "sys_ml_scoring", "CONSUMES",
     strength=0.5, substitutability=0.5, criticality="medium")
edge("e_intent_consumed_ml_scoring", "ds_intent_signals", "sys_ml_scoring", "CONSUMES",
     strength=0.5, substitutability=0.5, criticality="medium")
# NOTE: the planted edge (ds_account_intel CONSUMES -> wf_vendor_reconciliation) is deliberately
# NOT added here. See PLANTED_ITEMS below and ev_echo_account_intel_feed above.

# --- workflows SUPPORT controls / KPIs ---
edge("e_kyc_supports_control", "wf_kyc_screening", "ctl_kyc_screening", "SUPPORTS", strength=0.9,
     substitutability=0.1, criticality="critical", evidence_refs=["ev_kyc_screening_inputs"])
edge("e_recon_supports_sox", "wf_vendor_reconciliation", "ctl_sox_reconciliation", "SUPPORTS",
     strength=0.85, substitutability=0.15, criticality="high", evidence_refs=["ev_vendor_recon_inputs"])
edge("e_ctl_access_sso", "sys_sso_gateway", "ctl_access_control", "SUPPORTS", strength=0.9,
     substitutability=0.2, criticality="high", evidence_refs=["ev_architecture_core"])
edge("e_access_soc2_coverage", "ctl_access_control", "kpi_soc2_coverage", "CONTRIBUTES_TO", strength=0.8,
     substitutability=0.2, criticality="high", evidence_refs=["ev_architecture_core"])
edge("e_ctl_incident_wf", "wf_incident_mgmt", "ctl_incident_mgmt", "SUPPORTS", strength=0.85,
     substitutability=0.3, criticality="high", evidence_refs=["ev_incident_review_q2"])
edge("e_ctl_pci_billing", "sys_billing_platform", "ctl_pci_carddata", "SUPPORTS", strength=0.8,
     substitutability=0.3, criticality="high", evidence_refs=["ev_architecture_core"])
edge("e_soc2evidence_coverage", "wf_soc2_evidence", "kpi_soc2_coverage", "CONTRIBUTES_TO", strength=0.9,
     substitutability=0.1, criticality="high", evidence_refs=["ev_soc2_register_intro"])
edge("e_cc72_coverage", "ctl_soc2_audit_logging", "kpi_soc2_coverage", "CONTRIBUTES_TO", strength=1.0,
     substitutability=0.05, criticality="critical", evidence_refs=["ev_soc2_register_intro"])
edge("e_leadscoring_pipeline", "wf_lead_scoring", "kpi_pipeline", "CONTRIBUTES_TO", strength=0.7,
     substitutability=0.3, criticality="medium")
edge("e_campaign_pipeline", "wf_campaign_targeting", "kpi_pipeline", "CONTRIBUTES_TO", strength=0.6,
     substitutability=0.3, criticality="medium")
edge("e_account_planning_retention", "wf_account_planning", "kpi_net_retention", "CONTRIBUTES_TO",
     strength=0.6, substitutability=0.4, criticality="medium")
edge("e_product_analytics_retention", "wf_product_analytics", "kpi_net_retention", "CONTRIBUTES_TO",
     strength=0.5, substitutability=0.4, criticality="medium")
edge("e_risk_monitoring_margin", "wf_risk_monitoring", "kpi_gross_margin", "CONTRIBUTES_TO",
     strength=0.5, substitutability=0.4, criticality="medium")
edge("e_invoicing_margin", "wf_invoicing", "kpi_gross_margin", "CONTRIBUTES_TO", strength=0.8,
     substitutability=0.2, criticality="high", evidence_refs=["ev_finance_forecast_q3"])
edge("e_core_uptime", "sys_core_api", "kpi_uptime_sla", "CONTRIBUTES_TO", strength=0.9,
     substitutability=0.2, criticality="critical", evidence_refs=["ev_architecture_core"])
edge("e_onboarding_retention", "wf_customer_onboarding", "kpi_net_retention", "CONTRIBUTES_TO",
     strength=0.6, substitutability=0.4)
edge("e_enterprise_margin", "seg_enterprise", "kpi_gross_margin", "CONTRIBUTES_TO", strength=0.7,
     substitutability=0.3, criticality="high", evidence_refs=["ev_finance_forecast_q3"])

# --- breadth: every department's tribal knowledge wired into what it supports ---
edge("e_kn_core_arch", "kn_core_arch", "sys_core_api", "SUPPORTS", strength=0.5, substitutability=0.5)
edge("e_kn_release", "kn_release_eng", "sys_core_api", "SUPPORTS", strength=0.4, substitutability=0.6)
edge("e_kn_mlmodel", "kn_ml_modeling", "sys_ml_scoring", "SUPPORTS", strength=0.5, substitutability=0.5)
edge("e_kn_roadmap", "kn_roadmap_context", "proj_billing_modernization", "SUPPORTS", strength=0.4,
     substitutability=0.6)
edge("e_kn_deals", "kn_enterprise_deals", "seg_enterprise", "SUPPORTS", strength=0.4, substitutability=0.5)
edge("e_kn_segmentation", "kn_segmentation", "kpi_pipeline", "SUPPORTS", strength=0.4, substitutability=0.6)
edge("e_kn_onboarding", "kn_onboarding_playbook", "wf_customer_onboarding", "SUPPORTS", strength=0.5,
     substitutability=0.5)
edge("e_kn_cs_escalation", "kn_cs_escalation", "wf_customer_onboarding", "SUPPORTS", strength=0.4,
     substitutability=0.6)
edge("e_kn_vendorcontracts", "kn_vendor_contracts", "wf_vendor_reconciliation", "SUPPORTS", strength=0.4,
     substitutability=0.6)
edge("e_kn_privacy", "kn_privacy_program", "ctl_data_retention", "SUPPORTS", strength=0.5,
     substitutability=0.5)

# =========================================================================== DEPARTMENT CHANNELS (SCHEMA 5.9)
chan("ch_finance_engineering_budget", "dept_finance", "dept_engineering", "budget limits", "budget")
chan("ch_finance_marketing_budget", "dept_finance", "dept_marketing", "budget limits", "budget")
chan("ch_finance_operations_cost", "dept_finance", "dept_operations", "cost targets", "budget")
chan("ch_finance_sales_revenue", "dept_finance", "dept_sales", "revenue targets", "budget")
chan("ch_ai_data_engineering_models", "dept_ai_data", "dept_engineering", "models and data", "capability")
chan("ch_ai_data_marketing_scores", "dept_ai_data", "dept_marketing", "scores and segments", "capability")
chan("ch_engineering_product_features", "dept_engineering", "dept_product", "features and platforms",
     "capability")
chan("ch_engineering_operations_automation", "dept_engineering", "dept_operations", "automation",
     "capability")
chan("ch_operations_engineering_incidents", "dept_operations", "dept_engineering",
     "incidents and capacity", "signal")
chan("ch_product_sales_roadmap", "dept_product", "dept_sales", "roadmap and releases", "capability")
chan("ch_product_cs_product", "dept_product", "dept_customer_success", "product changes", "capability")
chan("ch_marketing_sales_qualified", "dept_marketing", "dept_sales", "qualified leads", "signal")
chan("ch_sales_product_customer", "dept_sales", "dept_product", "customer demand", "signal")
chan("ch_sales_cs_commitments", "dept_sales", "dept_customer_success", "commitments", "signal")
chan("ch_cs_product_feedback", "dept_customer_success", "dept_product", "feedback and churn signals",
     "signal")
chan("ch_compliance_ai_data_controls", "dept_compliance", "dept_ai_data", "controls", "constraint")
chan("ch_compliance_engineering_policies", "dept_compliance", "dept_engineering", "policies", "constraint")
chan("ch_compliance_operations_process", "dept_compliance", "dept_operations", "process controls",
     "constraint")
chan("ch_finance_kpi_profitability", "dept_finance", "kpi_company", "profitability", "value")
chan("ch_marketing_kpi_acquisition", "dept_marketing", "kpi_company", "acquisition cost", "value")
chan("ch_sales_kpi_pipeline", "dept_sales", "kpi_company", "pipeline", "value")
chan("ch_product_kpi_delivery", "dept_product", "kpi_company", "delivery", "value")
chan("ch_cs_kpi_retention", "dept_customer_success", "kpi_company", "retention", "value")
chan("ch_sales_marketing_launch", "dept_sales", "dept_marketing", "launch timing", "signal")
chan("ch_operations_compliance_evidence", "dept_operations", "dept_compliance", "control evidence",
     "signal")

# =========================================================================== PRESSURES (SCHEMA 13.2, R13)
pressures.extend([
    {"id": "pr_apex_renewal", "kind": "renewal_step", "name": "Apex auto-renewal uplift",
     "target_entity_id": "vendor_apex", "start_day": 60, "end_day": None,
     "step_pct": 8.0, "capacity_sensitivity": 0.0,
     "neutralised_by": [{"intervention_type": "remove_vendor", "target_entity_id": "vendor_apex"}],
     "evidence_refs": ["ev_apex_msa_renewal"], "description": "Apex auto-renews at +8% on day 60."},
    {"id": "pr_echo_renewal", "kind": "renewal_step", "name": "Echo renewal uplift",
     "target_entity_id": "vendor_echo", "start_day": 120, "end_day": None,
     "step_pct": 12.0, "capacity_sensitivity": 0.0,
     "neutralised_by": [{"intervention_type": "remove_vendor", "target_entity_id": "vendor_echo"}],
     "evidence_refs": ["ev_echo_msa_clause_9"], "description": "Echo renews at +12% on day 120."},
    {"id": "pr_flux_usage_growth", "kind": "cost_growth", "name": "Flux usage-based growth",
     "target_entity_id": "vendor_flux", "start_day": 0, "end_day": None,
     "rate": 0.015, "rate_range": [0.01, 0.02], "capacity_sensitivity": 0.0,
     "neutralised_by": [{"intervention_type": "remove_vendor", "target_entity_id": "vendor_flux"}],
     "evidence_refs": ["ev_finance_forecast_q3"], "description": "Flux usage costs grow about 1.5% a month."},
    {"id": "pr_vendor_recon_hazard", "kind": "hazard", "name": "Vendor reconciliation failure",
     "target_entity_id": "wf_vendor_reconciliation", "start_day": 0, "end_day": None,
     "monthly_probability": 0.03, "probability_range": [0.02, 0.05], "cost_per_event_usd": 40_000_000,
     "capacity_sensitivity": 2.5, "neutralised_by": [], "evidence_refs": ["ev_incident_22"],
     "description": "Reconciliation fails a few times a year; likelier if its inputs or owners weaken."},
    {"id": "pr_billing_recon_hazard", "kind": "hazard", "name": "Billing reconciliation failure",
     "target_entity_id": "wf_billing_recon", "start_day": 0, "end_day": None,
     "monthly_probability": 0.04, "probability_range": [0.02, 0.06], "cost_per_event_usd": 60_000_000,
     "capacity_sensitivity": 3.0,
     "neutralised_by": [{"intervention_type": "document_runbook", "target_entity_id": "wf_billing_recon"}],
     "evidence_refs": ["ev_incident_31"],
     "description": "Billing reconciliation fails about twice a year; likelier if its owners lose capacity."},
    {"id": "pr_lineage_holder_attrition", "kind": "hazard", "name": "Warehouse lineage holder leaves",
     "target_entity_id": "kn_warehouse_lineage", "start_day": 0, "end_day": None,
     "monthly_probability": 0.03, "probability_range": [0.02, 0.05], "cost_per_event_usd": 45_000_000,
     "capacity_sensitivity": 2.0,
     "neutralised_by": [{"intervention_type": "document_runbook",
                          "target_entity_id": "kn_warehouse_lineage"}],
     "evidence_refs": ["ev_knowledge_matrix_3"],
     "description": "Only one role knows the warehouse lineage; if it leaves, the financial close slips."},
    {"id": "pr_contractor_cost_growth", "kind": "cost_growth", "name": "Contractor rate growth",
     "target_entity_id": "dept_operations", "start_day": 0, "end_day": None,
     "rate": 0.01, "rate_range": [0.005, 0.015], "capacity_sensitivity": 0.0,
     "neutralised_by": [], "evidence_refs": ["ev_finance_forecast_q3"],
     "description": "Contractor rates rise about 1% a month."},
])


# =========================================================================== ASSEMBLE + VALIDATE
def build() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "version": {
            "twin_version": "twin_northstar_v1", "settings_version": 1,
            "prompt_version": "p1", "model_id": "configurable",
            "engine_version": "e1", "created_at": CREATED_AT, "as_of_date": AS_OF_DATE,
        },
        "organization": {
            "id": "org_northstar", "legal_name": "Northstar Technologies Inc.",
            "display_name": "Northstar Technologies",
            "sector": "technology_saas", "sub_sector": "Enterprise revenue, billing, and data software",
            "secondary_sectors": ["financial_services"], "business_model": "b2b",
            "size_band": "large_enterprise",
            "headquarters_country": "US", "operating_regions": ["US", "EU", "APAC"],
            "annual_revenue_usd": REVENUE_USD, "total_annual_budget_usd": TOTAL_BUDGET_USD,
            "total_headcount_fte": TOTAL_HEADCOUNT_FTE, "fiscal_year_start_month": 1,
            "regulatory_frameworks": ["SOC2", "GDPR", "PCI_DSS", "SOX"],
            "strategic_priorities": [
                {"id": "sp_retention", "text": "Protect enterprise retention", "rank": 1,
                 "kpi_ids": ["kpi_net_retention"]},
                {"id": "sp_margin", "text": "Expand gross margin by two points", "rank": 2,
                 "kpi_ids": ["kpi_gross_margin"]},
            ],
            "description": ("Large enterprise software company selling revenue, billing, and data "
                             "products to businesses in the US, EU, and APAC. It buys external data "
                             "from seven vendors costing $8B a year."),
            "evidence_refs": ["ev_strategy_memo_1"],
        },
        "department_profiles": department_profiles,
        "entities": entities,
        "edges": edges,
        "pressures": pressures,
        "documents": documents,
        "evidence": evidence,
    }


# ev_strategy_memo_1 is referenced by the organization; add it against the department map doc.
evi("ev_strategy_memo_1", "policy", "doc_department_map",
    "Protect enterprise retention first, then expand gross margin.")


REQUIRED_BY_TYPE = {
    "department": ["annual_cost_usd", "capacity_fte"],
    "vendor": ["annual_cost_usd", "one_time_exit_cost_usd", "migration_cost_usd"],
    "system": ["annual_cost_usd", "failure_cost_per_day_usd"],
    "project": ["annual_cost_usd", "completion_pct", "remaining_cost_usd", "expected_completion_day"],
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
    for e in twin["entities"]:
        for f in REQUIRED_BY_TYPE.get(e["type"], []):
            assert f in e, f"{e['id']} ({e['type']}) missing required field {f}"
        if e["type"] != "department" and e["id"] != "kpi_company":
            assert "department_id" in e, f"{e['id']} missing department_id"
        if e["type"] == "person_token":
            assert e["id"].startswith("pt_") and e["sensitivity"] == "hr", f"{e['id']} token rules"
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
    for v in twin["evidence"]:
        assert v["document_id"] in doc_ids, f"evidence {v['id']} bad document ref"
    for pr in twin["pressures"]:
        assert pr["target_entity_id"] in idset, f"pressure {pr['id']} bad target"
    depts = {e["id"] for e in twin["entities"] if e["type"] == "department"}
    prof_depts = {p["department_id"] for p in twin["department_profiles"]}
    assert depts == prof_depts, f"profile mismatch {depts ^ prof_depts}"
    ent_by_id = {e["id"]: e for e in twin["entities"]}
    for p in twin["department_profiles"]:
        de = ent_by_id[p["department_id"]]
        assert p["budget"]["annual_budget_usd"] == de["annual_cost_usd"], f"budget mismatch {p['department_id']}"
        st = p["staffing"]
        assert st["actual_fte"] + st["contractors_fte"] == de["capacity_fte"], f"fte mismatch {p['department_id']}"
        assert 2 <= len(p["strengths"]) <= 4, f"strengths count {p['department_id']}"
        for s in p["strengths"]:
            if s["level"] >= 4:
                assert s["evidence_refs"], f"strength {s['id']} level>=4 needs evidence"
    org = twin["organization"]
    dept_budget = sum(e["annual_cost_usd"] for e in twin["entities"] if e["type"] == "department")
    assert org["total_annual_budget_usd"] == dept_budget == TOTAL_BUDGET_USD, "budget total mismatch"
    fte = sum(p["staffing"]["actual_fte"] + p["staffing"]["contractors_fte"] for p in twin["department_profiles"])
    assert org["total_headcount_fte"] == fte, f"headcount total {fte} != {org['total_headcount_fte']}"
    for fw in org["regulatory_frameworks"]:
        assert any(e.get("framework") == fw for e in twin["entities"] if e["type"] == "control"), \
            f"no control for {fw}"
    vendor_total = sum(e["annual_cost_usd"] for e in twin["entities"] if e["type"] == "vendor")
    assert vendor_total == VENDOR_TOTAL_USD, f"vendor total {vendor_total} != {VENDOR_TOTAL_USD}"
    # A-04 acceptance: only the 8 workforce roles OWN/BACKS_UP the two stranded workflows.
    strand_targets = {"wf_financial_close", "wf_billing_recon"}
    owners = {ed["source"] for ed in twin["edges"]
              if ed["relation"] in ("OWNS", "BACKS_UP") and ed["target"] in strand_targets}
    assert owners <= set(WORKFORCE_ROLE_IDS), f"owners outside the 8 workforce roles: {owners - set(WORKFORCE_ROLE_IDS)}"
    for bid in WORKFORCE_BACKUP_ROLE_IDS:
        assert bid not in owners, f"{bid} must not own/back the base twin's stranded workflows"
    # planted edge omitted from edges[]
    planted_targets = {(ed["source"], ed["target"]) for ed in twin["edges"]}
    assert ("ds_account_intel", "wf_vendor_reconciliation") not in planted_targets, "planted edge leaked into edges[]"


PLANTED_ITEMS = {
    "note": ("Reference for the demo and the Challenger's AgentView filtering (plan D-06). Synthetic. "
             "Replaces the removed identity -> SSO -> SOC 2 planted chain."),
    "planted_edge": {
        "id": "e_account_intel_consumed_by_vendor_reconciliation",
        "source": "ds_account_intel",
        "relation": "CONSUMES",
        "target": "wf_vendor_reconciliation",
        "evidence_refs": ["ev_echo_account_intel_feed"],
        "document_id": "doc_vendor_recon_workflow_map",
        "description": ("Account intelligence (vendor_echo's unique dataset) also feeds Vendor "
                         "reconciliation, which supports the SOX reconciliation control. Left out of "
                         "edges[] so the Challenger must find it; once validated, removing Beacon + Echo "
                         "breaks ctl_sox_reconciliation until add_replacement_feed is applied."),
        "challenger_should_flag": True,
    },
    "planted_unknown": {
        "entity_id": "vendor_echo",
        "field": "retains_history_after_termination",
        "intended_value": None,
        "description": ("Unknown whether EchoMarket retains history after contract termination (2.1.1 "
                         "CR3 field; not yet in the 2.1.0 model). The missing-fact selector should rank "
                         "this question first (plan E-06, V-11)."),
        "evidence_refs": ["ev_echo_history_retention"],
    },
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
          f"documents={len(twin['documents'])} evidence={len(twin['evidence'])} "
          f"profiles={len(twin['department_profiles'])}")
    print("  entity types:", dict(kinds))
    print("  relations:", dict(rels))
    print(f"  dept budget total=${TOTAL_BUDGET_USD:,}  revenue=${REVENUE_USD:,}  "
          f"headcount={twin['organization']['total_headcount_fte']:.0f}  "
          f"vendor total=${VENDOR_TOTAL_USD:,}")


if __name__ == "__main__":
    main()
