"""Build the TSB 2018 migration twin, briefs, mitigations and provenance from public figures.

Run from the repo root:  uv run python data/cases/tsb-2018/build.py

Every money value is converted from GBP at the Federal Reserve G.5A 2018 annual average
(1.3363 USD per GBP). Each value is either sourced (a public figure, see SOURCES) or modeled
(an assumption, labelled in provenance.csv). Internal dependencies are never public: they are
modeled from public reporting. People appear only as roles.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FX = 1.3363  # USD per GBP, Federal Reserve G.5A annual average 2018

# Calibration (modeled): scale the displaced-work and revenue-at-risk inputs so the naive plan's
# modeled harm, once the planted dependency is validated, matches the documented 2018 charges
# (GBP 330.2M: GBP 189.4M rectification, fraud and resource costs as displaced work; GBP 140.8M
# redress and waived income as customer loss). See provenance.csv.
CAL_FCPD = 0.3715
CAL_ARR = 0.4205

SOURCES = {
    "fca_notice": "https://www.fca.org.uk/publication/final-notices/tsb-bank-plc-2022.pdf",
    "fca_press": "https://www.fca.org.uk/news/press-releases/tsb-fined-48m-operational-resilience-failings",
    "pra_press": "https://www.bankofengland.co.uk/news/2022/december/tsb-fined-for-operational-resilience-failings",
    "savings": "https://www.computerweekly.com/news/2240242809/Sabadell-to-migrate-TSB-IT-to-proprietary-banking-platform-with-450m-sweetener",
    "charges": "https://www.computing.co.uk/feature/3070358/tsb-pins-gbp330m-cost-on-it-meltdown-as-it-posts-gbp115m-annual-loss",
    "ara2018": "https://www.tsb.co.uk/content/dam/tsb-public/documents/investors/financial-results-and-reports/2018/tsb-banking-group-ara-2018.pdf",
    "fx": "https://www.federalreserve.gov/releases/g5a/20190102/",
}

# ---- public figures (GBP unless noted) -------------------------------------------------
F = {
    "customers_migrated": 5_200_000,          # FCA press release
    "expected_saving_gbp": 160_000_000,       # a year, pre-tax, by the third full year (Sabadell 2015 offer)
    "lbg_contribution_gbp": 450_000_000,      # LBG contribution to the IT migration
    "fourth_parties": 85,                     # FCA final notice
    "complaints": 225_492,                    # FCA final notice
    "redress_gbp": 32_705_762,                # FCA final notice
    "charges_2018_gbp": 330_200_000,          # post-migration charges in 2018
    "fca_fine_gbp": 29_750_000,
    "pra_fine_gbp": 18_900_000,
    "income_2017_gbp": 1_099_800_000,         # TSB 2017 total income (ARA 2018, 2017 comparative)
    "opex_2017_gbp": 859_300_000,             # TSB 2017 operating expenses (ARA 2018, 2017 comparative)
    "fte": 8_583,                             # TSB 2017 average headcount (ARA 2018, 2017 comparative)
    "branches": 551,                          # TSB branches (ARA 2018)
    "sabis_recovery_gbp": 153_000_000,        # estimated recovery from the provider, accrued not paid (ARA 2018)
}


def usd(gbp: float) -> int:
    return int(round(gbp * FX))


PROV: list[dict[str, str]] = []


def prov(field: str, value, kind: str, source: str = "", note: str = "") -> None:
    PROV.append({"entity_or_field": field, "value": str(value), "source_url": SOURCES.get(source, source),
                 "sourced_or_modeled": kind, "note": note})


# ---- documents and evidence (snippets summarize, never copy) ---------------------------
DOCS = [
    ("doc_fca_final_notice", "FCA Final Notice to TSB Bank plc (Dec 2022)", "audit_report", "dept_compliance",
     SOURCES["fca_notice"], "application/pdf",
     "Regulator's findings on the 2018 migration: outsourcing oversight, the new provider's sub-suppliers, rollback, complaints and redress. Linked, not copied."),
    ("doc_pra_notice", "PRA press release on TSB fine (Dec 2022)", "audit_report", "dept_compliance",
     SOURCES["pra_press"], "text/html",
     "Prudential regulator's summary of operational resilience and outsourcing failings and its fine. Linked, not copied."),
    ("doc_savings_plan", "Press report on the migration plan and savings (2015)", "strategy_memo", "dept_finance",
     SOURCES["savings"], "text/html",
     "Press report of the owner's plan to move the bank onto its own platform, the expected annual savings and the previous owner's contribution."),
    ("doc_charges_2018", "TSB Banking Group Annual Report and Accounts 2018", "financial_forecast", "dept_finance",
     SOURCES["ara2018"], "application/pdf",
     "Annual report: 2018 post-migration charges and their breakdown, the provider recovery estimate, 2017 comparatives for income, costs and headcount. Linked, not copied."),
    ("doc_platform_map_modeled", "Modeled platform and service dependency map", "architecture_note", "dept_engineering",
     "artifacts/tsb_platform_map_modeled.md", "text/markdown",
     "MODELED from public reporting: which channels, datasets and recovery paths depend on the old and new platforms. Not an internal document."),
    ("doc_supplier_register_modeled", "Modeled supplier and sub-supplier register", "contract", "dept_compliance",
     "artifacts/tsb_supplier_register_modeled.md", "text/markdown",
     "MODELED from public reporting: the platform provider, its sub-suppliers and the old host's exit terms. Not an internal document."),
    ("doc_recovery_runbook_modeled", "Modeled service recovery runbook", "runbook", "dept_operations",
     "artifacts/tsb_recovery_runbook_modeled.md", "text/markdown",
     "MODELED: recovery steps for customer channels after cutover. Public reporting says no tested rollback existed."),
]

EVIDENCE = [
    ("ev_tsb_customers", "doc_fca_final_notice", "audit_report_summary", "Regulator summary: about 5.2 million customers were moved to the new platform in April 2018."),
    ("ev_tsb_fourth_parties", "doc_fca_final_notice", "workflow_map",
     "Regulator summary: the new platform provider relied on 85 third parties of its own, which the bank had not assessed before migration."),
    ("ev_tsb_no_rollback", "doc_fca_final_notice", "workflow_map",
     "Regulator summary: once customer data moved there was no way back to the old platform, so customer service recovery depended on a fallback that would no longer exist."),
    ("ev_tsb_provider_experience", "doc_fca_final_notice", "architecture_note",
     "Regulator summary: the provider had not run a UK bank platform of this kind before."),
    ("ev_tsb_complaints", "doc_fca_final_notice", "incident", "Regulator summary: 225,492 complaints and about GBP 32.7M redress to customers."),
    ("ev_tsb_fines", "doc_pra_notice", "policy", "Regulator summary: fines of GBP 29.75M (FCA) and GBP 18.9M (PRA) in December 2022 for operational resilience failings."),
    ("ev_tsb_saving_target", "doc_savings_plan", "finance_forecast",
     "Press summary: the owner expected about GBP 160M a year of pre-tax savings by the third full year; the previous owner contributed GBP 450M."),
    ("ev_tsb_charges", "doc_charges_2018", "finance_forecast", "Annual report summary: GBP 330.2M of post-migration charges in 2018; about GBP 153M estimated recovery from the provider was accrued, not yet paid."),
    ("ev_tsb_platform_map", "doc_platform_map_modeled", "architecture_note",
     "Modeled: digital, telephone and branch channels run on the new platform; payments and fraud monitoring depend on the customer ledger."),
    ("ev_tsb_lbg_exit_terms", "doc_supplier_register_modeled", "contract",
     "Modeled: the exit terms with the old host do not say whether a usable copy of the service is kept after exit."),
    ("ev_tsb_recovery_runbook", "doc_recovery_runbook_modeled", "runbook",
     "Modeled: channel recovery steps assume a restore point; no rollback rehearsal is recorded."),
]


def evidence_records():
    out = []
    for eid, doc, stype, snippet in EVIDENCE:
        stype = "audit_report" if stype == "audit_report_summary" else stype
        stype = {"audit_report": "policy"}.get(stype, stype)
        modeled = "modeled" in doc
        out.append({"id": eid, "source_type": stype, "document_id": doc, "location": None,
                    "snippet": snippet, "synthetic": modeled})
    return out


def documents():
    out = []
    for did, title, dtype, dept, uri, mime, summary in DOCS:
        out.append({"id": did, "title": title, "doc_type": dtype, "department_id": dept, "owner_role_id": None,
                    "uri": uri, "mime_type": mime, "status": "current", "sensitivity": "general",
                    "covers_entity_ids": [], "framework_refs": [], "summary": summary, "synthetic": True,
                    "ingested": True, "uploaded_at": "2026-09-27T12:00:00Z"})
    # The runbook covers the recovery workflow (it exists but has no rehearsed rollback).
    for d in out:
        if d["id"] == "doc_recovery_runbook_modeled":
            d["covers_entity_ids"] = ["wf_service_recovery"]
    return out


# ---- departments ------------------------------------------------------------------------
# (id, name, agent, share of opex, share of FTE, mission)
DEPTS = [
    ("dept_engineering", "IT and Platform", "engineering", 0.24, 0.10, "Run the banking platform, the migration and the technology suppliers."),
    ("dept_operations", "Operations and Payments", "operations", 0.14, 0.12, "Process payments, run fraud monitoring and recover customer service."),
    ("dept_product", "Digital Banking", "product", 0.06, 0.03, "Run internet and mobile banking for customers."),
    ("dept_sales", "Branch Network and Lending", "sales", 0.26, 0.45, "Serve customers in about 551 branches and grow lending."),
    ("dept_customer_success", "Customer Service and Complaints", "customer_success", 0.12, 0.18, "Run telephone banking and handle complaints and redress."),
    ("dept_marketing", "Marketing and Communications", "marketing", 0.04, 0.02, "Customer communications and brand."),
    ("dept_ai_data", "Data and Analytics", "ai_data", 0.04, 0.03, "Customer data, reporting and data migration assurance."),
    ("dept_finance", "Finance", "finance", 0.05, 0.03, "Budget, savings case and supplier contracts."),
    ("dept_compliance", "Risk and Compliance", "compliance", 0.05, 0.04, "Operational resilience, outsourcing oversight and regulatory reporting."),
]


def dept_numbers():
    opex = usd(F["opex_2017_gbp"])
    budgets = [round(opex * s) for *_, s, _f, _m in [(d[0], d[1], d[2], d[3], d[4], d[5]) for d in DEPTS]]
    budgets[0] += opex - sum(budgets)
    ftes = [round(F["fte"] * d[4]) for d in DEPTS]
    ftes[3] += F["fte"] - sum(ftes)
    return opex, budgets, ftes


# ---- entities ---------------------------------------------------------------------------
def ent(id, type, name, dept=None, crit="medium", **kw):
    e = {"id": id, "type": type, "name": name, "criticality": crit, "sensitivity": kw.pop("sensitivity", "general"),
         "tags": kw.pop("tags", []), "evidence_refs": kw.pop("evidence_refs", [])}
    if dept:
        e["department_id"] = dept
    e.update(kw)
    return e


def build_entities(budgets, ftes):
    E = []
    for (did, name, *_), b, f in zip(DEPTS, budgets, ftes):
        E.append(ent(did, "department", name, crit="high", annual_cost_usd=b, capacity_fte=float(f)))

    roles = [
        ("role_head_it", "Head of IT", "dept_engineering", 250_000, 1, 180),
        ("role_platform_lead", "Platform Engineering Lead", "dept_engineering", 160_000, 40, 120),
        ("role_migration_lead", "Migration Programme Lead", "dept_engineering", 180_000, 6, 150),
        ("role_head_ops", "Head of Operations", "dept_operations", 200_000, 1, 150),
        ("role_payments_lead", "Payments Operations Lead", "dept_operations", 90_000, 60, 90),
        ("role_fraud_lead", "Fraud Operations Lead", "dept_operations", 85_000, 80, 90),
        ("role_head_digital", "Head of Digital", "dept_product", 190_000, 1, 150),
        ("role_branch_manager", "Branch Manager", "dept_sales", 55_000, 550, 60),
        ("role_contact_centre_lead", "Contact Centre Lead", "dept_customer_success", 60_000, 120, 60),
        ("role_complaints_lead", "Complaints Handling Lead", "dept_customer_success", 55_000, 150, 45),
        ("role_head_data", "Head of Data", "dept_ai_data", 170_000, 1, 150),
        ("role_head_finance", "Finance Director", "dept_finance", 260_000, 1, 180),
        ("role_head_risk", "Chief Risk Officer", "dept_compliance", 260_000, 1, 180),
        ("role_supplier_risk_lead", "Supplier and Outsourcing Risk Lead", "dept_compliance", 110_000, 8, 120),
        ("role_head_marketing", "Head of Marketing", "dept_marketing", 170_000, 1, 120),
    ]
    for rid, name, dept, cost_gbp, fte, train in roles:
        E.append(ent(rid, "role", name, dept, crit="high" if fte <= 8 else "medium",
                     annual_cost_usd=usd(cost_gbp * fte), capacity_fte=float(fte), time_to_train_days=train))
        prov(f"{rid}.annual_cost_usd", usd(cost_gbp * fte), "modeled", note=f"{fte} FTE at GBP {cost_gbp:,} loaded cost; role only, no individuals")

    saving = usd(F["expected_saving_gbp"])
    E += [
        ent("vendor_lbg", "vendor", "Lloyds Banking Group hosted platform (transitional services)", "dept_engineering", "critical",
            annual_cost_usd=saving, one_time_exit_cost_usd=0, migration_cost_usd=0,
            geographies=["UK"], history_years=20, freshness_days=1, accuracy=0.99,
            permitted_uses=["core_banking", "channels", "payments"], retains_history_after_termination=None,
            evidence_refs=["ev_tsb_saving_target", "ev_tsb_lbg_exit_terms"]),
        ent("vendor_sabis", "vendor", "SABIS (owner's IT subsidiary, Proteo4UK platform)", "dept_engineering", "critical",
            annual_cost_usd=usd(60_000_000), one_time_exit_cost_usd=usd(50_000_000), migration_cost_usd=usd(150_000_000),
            geographies=["UK", "ES"], history_years=0, freshness_days=1, accuracy=0.95,
            permitted_uses=["core_banking", "channels", "payments"], retains_history_after_termination=True,
            evidence_refs=["ev_tsb_provider_experience"]),
        ent("vendor_sabis_subsuppliers", "vendor", "SABIS sub-suppliers (85 third parties, unassessed)", "dept_engineering", "high",
            annual_cost_usd=0, one_time_exit_cost_usd=0, migration_cost_usd=0,
            geographies=["UK", "ES", "other"], history_years=0, freshness_days=1, accuracy=0.8,
            permitted_uses=["platform_components"], evidence_refs=["ev_tsb_fourth_parties"]),
    ]
    prov("vendor_lbg.annual_cost_usd", saving, "sourced", "savings",
         "Expected net saving GBP 160M a year (Sabadell 2015 offer) used as the recurring cost the plan stops; net of the new provider's run cost")
    prov("vendor_lbg.migration_cost_usd", 0, "modeled", "savings", "Migration build treated as sunk: funded by LBG's GBP 450M contribution (sourced)")
    prov("vendor_lbg.retains_history_after_termination", "null (unknown at decision time)", "modeled", "fca_notice",
         "Planted unknown; public record later showed no rollback was possible")
    prov("vendor_sabis.annual_cost_usd", usd(60_000_000), "modeled", note="Assumed platform run cost; not public")
    prov("vendor_sabis_subsuppliers", F["fourth_parties"], "sourced", "fca_notice", "85 third parties the bank had not assessed")

    systems = [
        ("sys_lbg_platform", "Legacy hosted core banking platform", "dept_engineering", "critical", 0, 0, False),
        ("sys_proteo4uk", "Proteo4UK core banking platform", "dept_engineering", "critical", usd(40_000_000), 900_000, True),
        ("sys_digital_channels", "Internet and mobile banking", "dept_product", "critical", usd(15_000_000), 600_000, True),
        ("sys_telephony", "Telephone banking platform", "dept_customer_success", "high", usd(6_000_000), 250_000, True),
        ("sys_branch_platform", "Branch teller and servicing system", "dept_sales", "high", usd(8_000_000), 300_000, True),
        ("sys_payments_gateway", "Payments gateway", "dept_operations", "critical", usd(10_000_000), 500_000, True),
    ]
    for sid, name, dept, crit, cost, fcpd, cf in systems:
        fcpd = round(fcpd * CAL_FCPD)
        E.append(ent(sid, "system", name, dept, crit, annual_cost_usd=cost, failure_cost_per_day_usd=fcpd,
                     customer_facing=cf, evidence_refs=["ev_tsb_platform_map"]))
        prov(f"{sid}.failure_cost_per_day_usd", fcpd, "modeled", note=f"Base assumption times calibration CAL_FCPD={CAL_FCPD}, so the naive plan's modeled harm matches the documented 2018 charges")

    E += [
        ent("ds_customer_ledger", "dataset", "Customer accounts and transaction ledger (5.2M customers)", "dept_ai_data", "critical",
            attribute_group="core_ledger", evidence_refs=["ev_tsb_customers"]),
        ent("ds_fallback_service", "dataset", "Working copy of customer services on the old platform (the rollback path)", "dept_engineering", "high",
            attribute_group="fallback", evidence_refs=["ev_tsb_lbg_exit_terms"]),
        ent("ds_payment_messages", "dataset", "Payment messages and standing orders", "dept_operations", "high",
            attribute_group="payments", evidence_refs=["ev_tsb_platform_map"]),
    ]
    prov("ds_customer_ledger.customers", F["customers_migrated"], "sourced", "fca_press")

    workflows = [
        ("wf_service_recovery", "Customer service recovery and rollback", "dept_operations", "critical", 2, 1_600_000, False),
        ("wf_digital_banking", "Internet and mobile banking service", "dept_product", "critical", 2, 700_000, True),
        ("wf_telephone_banking", "Telephone banking service", "dept_customer_success", "high", 2, 250_000, True),
        ("wf_branch_servicing", "Branch customer servicing", "dept_sales", "high", 2, 300_000, True),
        ("wf_payments_processing", "Payments processing", "dept_operations", "critical", 2, 400_000, True),
        ("wf_fraud_detection", "Fraud detection and prevention", "dept_operations", "critical", 2, 250_000, False),
        ("wf_complaints_handling", "Complaints handling and redress", "dept_customer_success", "high", 2, 350_000, True),
        ("wf_supplier_oversight", "Outsourcing and sub-supplier oversight", "dept_compliance", "high", 2, 60_000, False),
    ]
    for wid, name, dept, crit, owners, fcpd, cf in workflows:
        fcpd = round(fcpd * CAL_FCPD)
        E.append(ent(wid, "workflow", name, dept, crit, min_qualified_owners=owners, failure_cost_per_day_usd=fcpd,
                     customer_facing=cf, max_downtime_days=1 if crit == "critical" else 3,
                     evidence_refs=["ev_tsb_platform_map"] if wid != "wf_service_recovery" else ["ev_tsb_recovery_runbook"]))
        prov(f"{wid}.failure_cost_per_day_usd", fcpd, "modeled", note=f"Base assumption times calibration CAL_FCPD={CAL_FCPD}, so the naive plan's modeled harm matches the documented 2018 charges")

    E += [
        ent("ctl_operational_resilience", "control", "Operational resilience: restore important business services", "dept_compliance", "critical",
            mandatory=True, framework="PRA_Rulebook", evidence_refs=["ev_tsb_fines"]),
        ent("ctl_outsourcing_oversight", "control", "Outsourcing oversight of material suppliers and their sub-suppliers", "dept_compliance", "critical",
            mandatory=True, framework="FCA_SYSC", evidence_refs=["ev_tsb_fourth_parties"]),
        ent("ctl_fraud_controls", "control", "Fraud prevention controls", "dept_operations", "high", mandatory=True, framework="FCA_SYSC",
            evidence_refs=["ev_tsb_platform_map"]),
        ent("kpi_complaints", "kpi", "Customer complaints per year", "dept_customer_success", "high",
            kpi_baseline=30_000.0, kpi_unit="count", higher_is_better=False, evidence_refs=["ev_tsb_complaints"]),
        ent("kpi_channel_availability", "kpi", "Customer channel availability", "dept_product", "critical",
            kpi_baseline=99.5, kpi_unit="percent", higher_is_better=True, evidence_refs=["ev_tsb_platform_map"]),
        ent("kpi_customer_retention", "kpi", "Customer retention", "dept_sales", "high",
            kpi_baseline=95.0, kpi_unit="percent", higher_is_better=True),
        ent("seg_personal", "customer_segment", "Personal banking customers", "dept_sales", "critical",
            arr_usd=round(usd(F["income_2017_gbp"] * 0.9) * CAL_ARR), sensitivity="customer", evidence_refs=["ev_tsb_customers"]),
        ent("seg_business", "customer_segment", "Business banking customers", "dept_sales", "high",
            arr_usd=round(usd(F["income_2017_gbp"] * 0.1) * CAL_ARR), sensitivity="customer", evidence_refs=["ev_tsb_customers"]),
        ent("kn_platform_architecture", "knowledge_asset", "New platform architecture and component map", "dept_engineering", "high",
            documented_pct=0.4),
        ent("kn_cutover_plan", "knowledge_asset", "Cutover and rollback criteria", "dept_engineering", "critical", documented_pct=0.3),
    ]
    prov("kpi_complaints.kpi_baseline", 30_000, "modeled", note="Pre-migration yearly complaints assumed; 2018 actual 225,492 migration complaints is sourced")
    for sid, share in (("seg_personal", 0.9), ("seg_business", 0.1)):
        prov(f"{sid}.arr_usd", round(usd(F["income_2017_gbp"] * share) * CAL_ARR), "modeled", "ara2018",
             f"{share:.0%} of 2017 total income (sourced) times calibration CAL_ARR={CAL_ARR}: income exposed to channel disruption")
    return E


def edge(id, s, rel, t, strength, subst, crit="medium", conf=0.8, ev=(), lag=0, **kw):
    e = {"id": id, "source": s, "target": t, "relation": rel, "strength": strength, "substitutability": subst,
         "lag_days": lag, "criticality": crit, "confidence": conf, "evidence_refs": list(ev), "extraction_method": "seeded"}
    e.update(kw)
    return e


MAP = ["ev_tsb_platform_map"]


def build_edges():
    return [
        # Old host provides the ledger (already copied to the new platform) and the only working fallback.
        edge("e_lbg_provides_ledger", "vendor_lbg", "PROVIDES", "ds_customer_ledger", 0.9, 0.85, "critical", 0.8, ["ev_tsb_saving_target"]),
        edge("e_lbg_provides_fallback", "vendor_lbg", "PROVIDES", "ds_fallback_service", 0.95, 0.05, "critical", 0.8, ["ev_tsb_lbg_exit_terms"]),
        edge("e_lbg_provides_legacy_platform", "vendor_lbg", "PROVIDES", "sys_lbg_platform", 0.9, 0.1, "high", 0.9, ["ev_tsb_saving_target"]),
        edge("e_sabis_provides_ledger", "vendor_sabis", "PROVIDES", "ds_customer_ledger", 0.95, 0.3, "critical", 0.8, ["ev_tsb_provider_experience"]),
        edge("e_sabis_provides_proteo", "vendor_sabis", "PROVIDES", "sys_proteo4uk", 0.9, 0.1, "critical", 0.8, ["ev_tsb_provider_experience"]),
        edge("e_subsuppliers_provide_proteo", "vendor_sabis_subsuppliers", "PROVIDES", "sys_proteo4uk", 0.5, 0.3, "high", 0.4, ["ev_tsb_fourth_parties"]),
        # The new platform runs the channels.
        edge("e_proteo_runs_digital", "sys_proteo4uk", "DEPENDS_ON", "sys_digital_channels", 0.8, 0.1, "critical", 0.8, MAP),
        edge("e_proteo_runs_telephony", "sys_proteo4uk", "DEPENDS_ON", "sys_telephony", 0.6, 0.2, "high", 0.8, MAP),
        edge("e_proteo_runs_branch", "sys_proteo4uk", "DEPENDS_ON", "sys_branch_platform", 0.7, 0.2, "high", 0.8, MAP),
        edge("e_proteo_runs_payments", "sys_proteo4uk", "DEPENDS_ON", "sys_payments_gateway", 0.7, 0.2, "critical", 0.8, MAP),
        edge("e_ledger_consumed_digital", "ds_customer_ledger", "CONSUMES", "wf_digital_banking", 0.8, 0.1, "critical", 0.8, MAP),
        edge("e_ledger_consumed_payments", "ds_customer_ledger", "CONSUMES", "wf_payments_processing", 0.8, 0.1, "critical", 0.8, MAP),
        edge("e_ledger_consumed_fraud", "ds_customer_ledger", "CONSUMES", "wf_fraud_detection", 0.6, 0.2, "high", 0.8, MAP),
        edge("e_payment_msgs_consumed_payments", "ds_payment_messages", "CONSUMES", "wf_payments_processing", 0.7, 0.2, "high", 0.8, MAP),
        edge("e_sys_digital_runs_wf", "sys_digital_channels", "RUNS", "wf_digital_banking", 0.9, 0.1, "critical", 0.9, MAP),
        edge("e_sys_tel_runs_wf", "sys_telephony", "RUNS", "wf_telephone_banking", 0.9, 0.1, "high", 0.9, MAP),
        edge("e_sys_branch_runs_wf", "sys_branch_platform", "RUNS", "wf_branch_servicing", 0.9, 0.1, "high", 0.9, MAP),
        edge("e_sys_pay_runs_wf", "sys_payments_gateway", "RUNS", "wf_payments_processing", 0.9, 0.1, "critical", 0.9, MAP),
        # Recovery keeps the channels up; it is what the resilience control rests on.
        edge("e_recovery_supports_digital", "wf_service_recovery", "SUPPORTS", "wf_digital_banking", 0.7, 0.1, "critical", 0.7, ["ev_tsb_recovery_runbook"]),
        edge("e_recovery_supports_telephone", "wf_service_recovery", "SUPPORTS", "wf_telephone_banking", 0.6, 0.2, "high", 0.7, ["ev_tsb_recovery_runbook"]),
        edge("e_recovery_supports_branch", "wf_service_recovery", "SUPPORTS", "wf_branch_servicing", 0.6, 0.2, "high", 0.7, ["ev_tsb_recovery_runbook"]),
        edge("e_recovery_supports_payments", "wf_service_recovery", "SUPPORTS", "wf_payments_processing", 0.6, 0.2, "critical", 0.7, ["ev_tsb_recovery_runbook"]),
        edge("e_recovery_supports_resilience", "wf_service_recovery", "SUPPORTS", "ctl_operational_resilience", 0.85, 0.1, "critical", 0.8, ["ev_tsb_fines"]),
        edge("e_oversight_supports_outsourcing_ctl", "wf_supplier_oversight", "SUPPORTS", "ctl_outsourcing_oversight", 0.85, 0.1, "critical", 0.8, ["ev_tsb_fourth_parties"]),
        edge("e_fraud_supports_ctl", "wf_fraud_detection", "SUPPORTS", "ctl_fraud_controls", 0.85, 0.1, "high", 0.8, MAP),
        edge("e_cutover_supports_recovery", "kn_cutover_plan", "SUPPORTS", "wf_service_recovery", 0.5, 0.3, "high", 0.6, ["ev_tsb_recovery_runbook"]),
        edge("e_arch_supports_recovery", "kn_platform_architecture", "SUPPORTS", "wf_service_recovery", 0.4, 0.4, "medium", 0.6),
        # Channel failures reach customers and complaints.
        edge("e_digital_serves_personal", "wf_digital_banking", "CONTRIBUTES_TO", "seg_personal", 0.6, 0.3, "critical", 0.7, ["ev_tsb_customers"]),
        edge("e_digital_serves_business", "wf_digital_banking", "CONTRIBUTES_TO", "seg_business", 0.6, 0.3, "high", 0.7, ["ev_tsb_customers"]),
        edge("e_payments_serves_business", "wf_payments_processing", "CONTRIBUTES_TO", "seg_business", 0.6, 0.3, "high", 0.7, ["ev_tsb_customers"]),
        edge("e_branch_serves_personal", "wf_branch_servicing", "CONTRIBUTES_TO", "seg_personal", 0.4, 0.4, "high", 0.7, ["ev_tsb_customers"]),
        edge("e_tel_serves_personal", "wf_telephone_banking", "CONTRIBUTES_TO", "seg_personal", 0.3, 0.4, "medium", 0.7),
        edge("e_digital_drives_availability", "wf_digital_banking", "CONTRIBUTES_TO", "kpi_channel_availability", 0.9, 0.1, "critical", 0.8, MAP),
        edge("e_digital_drives_complaints", "wf_digital_banking", "CONTRIBUTES_TO", "kpi_complaints", 0.7, 0.2, "high", 0.7, ["ev_tsb_complaints"]),
        edge("e_complaints_load", "wf_digital_banking", "DEPENDS_ON", "wf_complaints_handling", 0.5, 0.3, "high", 0.7, ["ev_tsb_complaints"]),
        edge("e_personal_retention", "seg_personal", "CONTRIBUTES_TO", "kpi_customer_retention", 0.6, 0.3, "high", 0.7, ["ev_tsb_customers"]),
        # Owners.
        edge("e_head_it_owns_proteo", "role_head_it", "OWNS", "sys_proteo4uk", 0.8, 0.3, "high", 0.9, MAP),
        edge("e_migration_lead_knows_cutover", "role_migration_lead", "KNOWS", "kn_cutover_plan", 0.8, 0.2, "high", 0.8, ["ev_tsb_recovery_runbook"]),
        edge("e_platform_lead_knows_arch", "role_platform_lead", "KNOWS", "kn_platform_architecture", 0.7, 0.3, "medium", 0.8),
        edge("e_head_ops_owns_recovery", "role_head_ops", "OWNS", "wf_service_recovery", 0.8, 0.3, "high", 0.8, ["ev_tsb_recovery_runbook"]),
        edge("e_payments_lead_owns_payments", "role_payments_lead", "OWNS", "wf_payments_processing", 0.8, 0.3, "high", 0.8, MAP),
        edge("e_fraud_lead_owns_fraud", "role_fraud_lead", "OWNS", "wf_fraud_detection", 0.8, 0.3, "high", 0.8, MAP),
        edge("e_head_digital_owns_digital", "role_head_digital", "OWNS", "wf_digital_banking", 0.8, 0.3, "high", 0.8, MAP),
        edge("e_branch_mgr_owns_branch", "role_branch_manager", "OWNS", "wf_branch_servicing", 0.8, 0.3, "high", 0.8, MAP),
        edge("e_cc_lead_owns_tel", "role_contact_centre_lead", "OWNS", "wf_telephone_banking", 0.8, 0.3, "high", 0.8, MAP),
        edge("e_complaints_lead_owns", "role_complaints_lead", "OWNS", "wf_complaints_handling", 0.8, 0.3, "high", 0.8, ["ev_tsb_complaints"]),
        edge("e_supplier_lead_owns_oversight", "role_supplier_risk_lead", "OWNS", "wf_supplier_oversight", 0.8, 0.3, "high", 0.8, ["ev_tsb_fourth_parties"]),
        edge("e_head_risk_backs_oversight", "role_head_risk", "BACKS_UP", "wf_supplier_oversight", 0.5, 0.4, "high", 0.7, ["ev_tsb_fourth_parties"]),
        edge("e_platform_lead_backs_recovery", "role_platform_lead", "BACKS_UP", "wf_service_recovery", 0.5, 0.4, "high", 0.7, ["ev_tsb_recovery_runbook"]),
        edge("e_head_digital_backs_digital", "role_contact_centre_lead", "BACKS_UP", "wf_complaints_handling", 0.4, 0.4, "medium", 0.7),
        edge("e_head_ops_backs_payments", "role_head_ops", "BACKS_UP", "wf_payments_processing", 0.5, 0.4, "high", 0.7, MAP),
        edge("e_head_ops_backs_fraud", "role_head_ops", "BACKS_UP", "wf_fraud_detection", 0.5, 0.4, "high", 0.7, MAP),
        edge("e_head_digital_backs_dig", "role_head_it", "BACKS_UP", "wf_digital_banking", 0.4, 0.4, "high", 0.7, MAP),
        edge("e_branch_backs_tel", "role_branch_manager", "BACKS_UP", "wf_telephone_banking", 0.3, 0.5, "medium", 0.6),
        edge("e_cc_backs_branch", "role_contact_centre_lead", "BACKS_UP", "wf_branch_servicing", 0.3, 0.5, "medium", 0.6),
        edge("e_complaints_backs_cc", "role_head_marketing", "BACKS_UP", "wf_complaints_handling", 0.2, 0.5, "medium", 0.5),
        edge("e_platform_backs_recovery2", "role_migration_lead", "BACKS_UP", "wf_service_recovery", 0.4, 0.4, "high", 0.6, ["ev_tsb_recovery_runbook"]),
        # Department channels.
        edge("ch_finance_engineering_budget", "dept_finance", "FLOWS_TO", "dept_engineering", 0.5, 0.3, "medium", 0.9, ["ev_tsb_saving_target"],
             lag=30, label="budget and savings target", channel_kind="budget"),
        edge("ch_engineering_operations_capability", "dept_engineering", "FLOWS_TO", "dept_operations", 0.6, 0.2, "high", 0.8, MAP,
             lag=0, label="platform and recovery", channel_kind="capability"),
        edge("ch_engineering_product_capability", "dept_engineering", "FLOWS_TO", "dept_product", 0.6, 0.2, "high", 0.8, MAP,
             lag=0, label="platform for digital channels", channel_kind="capability"),
        edge("ch_engineering_sales_capability", "dept_engineering", "FLOWS_TO", "dept_sales", 0.5, 0.3, "high", 0.8, MAP,
             lag=0, label="branch systems", channel_kind="capability"),
        edge("ch_engineering_cs_capability", "dept_engineering", "FLOWS_TO", "dept_customer_success", 0.5, 0.3, "high", 0.8, MAP,
             lag=0, label="telephony", channel_kind="capability"),
        edge("ch_product_sales_value", "dept_product", "FLOWS_TO", "dept_sales", 0.4, 0.4, "medium", 0.7, lag=30, label="customer value", channel_kind="value"),
        edge("ch_product_cs_signal", "dept_product", "FLOWS_TO", "dept_customer_success", 0.4, 0.4, "medium", 0.7, lag=0, label="complaint volume", channel_kind="signal"),
        edge("ch_operations_product_capability", "dept_operations", "FLOWS_TO", "dept_product", 0.4, 0.4, "high", 0.7, MAP, lag=0, label="recovery", channel_kind="capability"),
        edge("ch_operations_sales_capability", "dept_operations", "FLOWS_TO", "dept_sales", 0.4, 0.4, "high", 0.7, MAP, lag=0, label="recovery and payments", channel_kind="capability"),
        edge("ch_operations_cs_capability", "dept_operations", "FLOWS_TO", "dept_customer_success", 0.4, 0.4, "high", 0.7, MAP, lag=0, label="recovery", channel_kind="capability"),
        edge("ch_operations_compliance_signal", "dept_operations", "FLOWS_TO", "dept_compliance", 0.4, 0.4, "high", 0.7, MAP, lag=0, label="resilience evidence", channel_kind="signal"),
        edge("ch_compliance_engineering_constraint", "dept_compliance", "FLOWS_TO", "dept_engineering", 0.5, 0.3, "high", 0.8, ["ev_tsb_fourth_parties"],
             lag=30, label="outsourcing rules", channel_kind="constraint"),
        edge("ch_engineering_ai_data_capability", "dept_engineering", "FLOWS_TO", "dept_ai_data", 0.5, 0.3, "high", 0.8, MAP, lag=0, label="ledger", channel_kind="capability"),
        edge("ch_ai_data_product_capability", "dept_ai_data", "FLOWS_TO", "dept_product", 0.4, 0.4, "high", 0.7, MAP, lag=0, label="ledger", channel_kind="capability"),
        edge("ch_ai_data_operations_capability", "dept_ai_data", "FLOWS_TO", "dept_operations", 0.4, 0.4, "high", 0.7, MAP, lag=0, label="ledger", channel_kind="capability"),
        edge("ch_sales_marketing_signal", "dept_sales", "FLOWS_TO", "dept_marketing", 0.3, 0.5, "medium", 0.6, lag=0, label="customer communications", channel_kind="signal"),
        edge("ch_customer_success_marketing_signal", "dept_customer_success", "FLOWS_TO", "dept_marketing", 0.3, 0.5, "medium", 0.6, lag=0, label="complaint communications", channel_kind="signal"),
        edge("ch_finance_compliance_budget", "dept_finance", "FLOWS_TO", "dept_compliance", 0.3, 0.5, "medium", 0.7, ["ev_tsb_saving_target"], lag=30, label="budget", channel_kind="budget"),
    ]


PLANTED_EDGE = edge("e_fallback_consumed_by_service_recovery", "ds_fallback_service", "CONSUMES", "wf_service_recovery",
                    0.85, 0.05, "critical", 0.8, ["ev_tsb_no_rollback", "ev_tsb_fourth_parties"])


def profiles(budgets, ftes):
    heads = {"dept_engineering": "role_head_it", "dept_operations": "role_head_ops", "dept_product": "role_head_digital",
             "dept_sales": "role_branch_manager", "dept_customer_success": "role_contact_centre_lead",
             "dept_marketing": "role_head_marketing", "dept_ai_data": "role_head_data", "dept_finance": "role_head_finance",
             "dept_compliance": "role_head_risk"}
    strengths = {
        "dept_engineering": ("Core platform delivery", "capability", ["sys_proteo4uk"], ["ev_tsb_provider_experience"]),
        "dept_operations": ("Payments and fraud operations", "process", ["wf_payments_processing"], ["ev_tsb_platform_map"]),
        "dept_product": ("Digital channel design", "capability", ["wf_digital_banking"], ["ev_tsb_platform_map"]),
        "dept_sales": ("Branch coverage (about 551 branches)", "asset", ["wf_branch_servicing"], ["ev_tsb_customers"]),
        "dept_customer_success": ("Contact centre scale", "capability", ["wf_telephone_banking"], ["ev_tsb_complaints"]),
        "dept_marketing": ("Customer communications", "relationship", [], ["ev_tsb_customers"]),
        "dept_ai_data": ("Customer ledger stewardship", "data", ["ds_customer_ledger"], ["ev_tsb_customers"]),
        "dept_finance": ("Savings case and supplier contracts", "process", ["vendor_lbg"], ["ev_tsb_saving_target"]),
        "dept_compliance": ("Regulatory relationships", "relationship", ["ctl_operational_resilience"], ["ev_tsb_fines"]),
    }
    gaps = {
        "dept_compliance": [{"id": "gap_fourth_party_oversight", "name": "Sub-suppliers of the platform provider not assessed",
                             "category": "process", "severity": 5, "affected_entity_ids": ["vendor_sabis_subsuppliers", "ctl_outsourcing_oversight"],
                             "evidence_refs": ["ev_tsb_fourth_parties"]}],
        "dept_engineering": [{"id": "gap_rollback", "name": "No tested rollback once customers move", "category": "process", "severity": 5,
                              "affected_entity_ids": ["kn_cutover_plan"], "evidence_refs": ["ev_tsb_recovery_runbook"]}],
    }
    out = []
    for (did, name, agent, *_rest), b, f in zip(DEPTS, budgets, ftes):
        mission = next(d[5] for d in DEPTS if d[0] == did)
        sname, cat, sup, ev = strengths[did]
        contractors = round(f * 0.05)
        out.append({
            "department_id": did, "mission": mission, "head_role_id": heads[did], "agent_id": agent,
            "staffing": {"sanctioned_fte": float(f + round(f * 0.03)), "actual_fte": float(f - contractors),
                         "contractors_fte": float(contractors), "open_positions": round(f * 0.03),
                         "attrition_rate_annual": 0.12, "avg_time_to_hire_days": 60,
                         "utilisation": 1.1 if did in ("dept_engineering", "dept_customer_success") else 1.0},
            "budget": {"annual_budget_usd": b, "spent_ytd_usd": round(b * 0.25), "fixed_cost_pct": 0.4, "budget_owner_role_id": heads[did]},
            "strengths": [{"id": f"str_{did[5:]}_core", "name": sname, "category": cat, "level": 3,
                           "supports_entity_ids": sup, "key_role_ids": [heads[did]], "concentration": 0.4, "evidence_refs": ev}],
            "gaps": gaps.get(did, []), "maturity_level": 3,
        })
    return out


def twin(include_planted: bool = False):
    opex, budgets, ftes = dept_numbers()
    prov("organization.total_annual_budget_usd", opex, "sourced", "ara2018", f"TSB 2017 operating expenses GBP {F['opex_2017_gbp']:,} at FX {FX}")
    prov("organization.total_headcount_fte", F["fte"], "sourced", "ara2018", "TSB 2017 average headcount (not labelled FTE); department split modeled")
    prov("organization.annual_revenue_usd", usd(F["income_2017_gbp"]), "sourced", "ara2018", "TSB 2017 total income")
    prov("department budgets and FTE split", "see twin.json", "modeled", note="Shares of the sourced totals by department are assumptions")
    edges = build_edges() + ([PLANTED_EDGE] if include_planted else [])
    return {
        "schema_version": "2.1.1",
        "version": {"twin_version": "twin_tsb_2018_v1", "settings_version": 1, "prompt_version": "p1", "model_id": "configurable",
                    "engine_version": "e1", "created_at": "2026-09-27T12:00:00Z", "as_of_date": "2018-03-31",
                    "data_snapshot_id": "public_record_tsb_2018"},
        "organization": {
            "id": "org_tsb", "legal_name": "TSB Bank plc", "display_name": "TSB Bank (public 2018 case, modeled twin)",
            "sector": "banking", "sub_sector": "UK retail and business banking", "secondary_sectors": ["financial_services"],
            "business_model": "b2c", "size_band": "large_enterprise", "headquarters_country": "GB", "operating_regions": ["UK"],
            "annual_revenue_usd": usd(F["income_2017_gbp"]), "total_annual_budget_usd": opex, "total_headcount_fte": float(F["fte"]),
            "fiscal_year_start_month": 1, "regulatory_frameworks": ["PRA_Rulebook", "FCA_SYSC"],
            "strategic_priorities": [
                {"id": "sp_platform_savings", "text": "Move off the transitional platform to save about GBP 160M a year", "rank": 1, "kpi_ids": []},
                {"id": "sp_customer_service", "text": "Keep customer service and complaints stable", "rank": 2, "kpi_ids": ["kpi_complaints", "kpi_channel_availability"]},
            ],
            "description": ("Modeled twin of a UK retail bank at the time of its April 2018 platform migration, built only from public "
                            "regulator and press figures. Money in USD at the 2018 Federal Reserve average rate. Internal dependencies are modeled."),
            "evidence_refs": ["ev_tsb_customers", "ev_tsb_saving_target"],
        },
        "department_profiles": profiles(budgets, ftes),
        "entities": build_entities(budgets, ftes),
        "edges": edges,
        "pressures": [
            {"id": "pr_tsa_fee_growth", "kind": "renewal_step", "name": "Transitional platform fee step-up",
             "target_entity_id": "vendor_lbg", "start_day": 180, "step_pct": 5.0, "capacity_sensitivity": 0.0,
             "neutralised_by": [{"intervention_type": "remove_vendor", "target_entity_id": "vendor_lbg"}],
             "evidence_refs": ["ev_tsb_saving_target"], "description": "Modeled: staying on the old host keeps its fees, with an assumed 5% step-up."},
        ],
        "documents": documents(),
        "evidence": evidence_records(),
    }


def brief_naive():
    return {
        "schema_version": "2.1.1", "decision_id": "dec_tsb_platform_exit", "decision_type": "vendor_consolidation",
        "title": "Exit the transitional platform and move all customers to the new platform",
        "statement": ("Move all 5.2 million customers off the Lloyds hosted platform onto Proteo4UK in one weekend and end the "
                      "transitional services, to save about GBP 160M (about $214M) a year, without breaking a mandatory control "
                      "or hurting customers by more than 2%."),
        "goal": {"metric": "annual_savings_usd", "target": usd(F["expected_saving_gbp"]), "unit": "usd", "basis": "gross", "direction": "at_least"},
        "horizon_days": 365,
        "candidate_interventions": [
            {"id": "exit_lbg_platform", "kind": "action", "type": "remove_vendor", "target_entity_id": "vendor_lbg", "start_day": 20,
             "one_time_cost_usd": 0, "params": {}, "rationale": "Single-weekend cutover, then end the transitional services"},
        ],
        "protected_entity_ids": [],
        "constraints": [
            {"id": "c_compliance", "metric": "compliance_controls_broken", "operator": "==", "threshold": 0, "unit": "count", "hard": True,
             "description": "No mandatory control may break"},
            {"id": "c_customer", "metric": "customer_impact_pct", "operator": "<=", "threshold": 2, "unit": "percent", "hard": True,
             "description": "Customer impact within 2%"},
            {"id": "c_coverage", "metric": "critical_coverage_pct", "operator": ">=", "threshold": 100, "unit": "percent", "hard": True,
             "description": "Every critical dataset keeps a provider"},
        ],
        "futures": ["act_now", "inaction", "delay"], "delay_days": 90,
        "active_pressure_ids": ["pr_tsa_fee_growth"], "seed": 42, "mc_samples": 1000, "created_by": "demo_user",
    }


def mitigations():
    return [
        {"id": "mit_assured_rollback_path", "kind": "mitigation", "type": "add_replacement_feed", "target_entity_id": "ds_fallback_service",
         "duration_days": 120, "one_time_cost_usd": usd(40_000_000), "params": {"replacement_vendor_id": "vendor_sabis"},
         "rationale": ("Before ending the old host's services, have the new provider stand up a tested fallback: assess all 85 of its "
                       "sub-suppliers and rehearse a reverse migration, so customer service can be restored if cutover fails.")},
        {"id": "mit_recovery_runbook", "kind": "mitigation", "type": "document_runbook", "target_entity_id": "wf_service_recovery",
         "duration_days": 45, "one_time_cost_usd": usd(3_000_000), "params": {"documented_pct": 0.9},
         "rationale": "Write and rehearse the cutover and recovery runbook with go or no-go and rollback criteria per channel."},
        {"id": "mit_complaints_surge_playbook", "kind": "mitigation", "type": "document_runbook", "target_entity_id": "wf_complaints_handling",
         "duration_days": 30, "one_time_cost_usd": usd(2_000_000), "params": {"documented_pct": 0.8},
         "rationale": "Prepare a complaints and redress surge playbook and trained backup staff before cutover."},
    ]


def planted():
    return {
        "note": "TSB 2018 case. The planted edge is left out of edges[] so the Challenger must find it from the regulator-summary evidence.",
        "planted_edge": {
            "id": PLANTED_EDGE["id"], "source": PLANTED_EDGE["source"], "relation": PLANTED_EDGE["relation"], "target": PLANTED_EDGE["target"],
            "evidence_refs": PLANTED_EDGE["evidence_refs"], "document_id": "doc_fca_final_notice",
            "description": ("Customer service recovery depends on the old platform's working copy: the new provider's own resilience rested on 85 "
                            "sub-suppliers the bank had not assessed, and after migration there was no rollback. Once validated, exiting the old "
                            "host breaks the mandatory operational resilience control until a tested fallback exists."),
            "challenger_should_flag": True,
        },
        "planted_unknown": {
            "entity_id": "vendor_lbg", "field": "retains_history_after_termination", "intended_value": False,
            "description": "Unknown at decision time whether the old host keeps a usable copy after exit (a rollback). The public record says it did not.",
            "evidence_refs": ["ev_tsb_lbg_exit_terms"],
        },
    }


def outcome_provenance():
    for field, value, src, note in [
        ("outcome.complaints", F["complaints"], "fca_notice", "Complaints linked to the migration"),
        ("outcome.redress_gbp", F["redress_gbp"], "fca_notice", "Redress paid to customers"),
        ("outcome.charges_2018_gbp", F["charges_2018_gbp"], "ara2018", "Post-migration charges in 2018; calibration target. Breakdown GBP M: redress 107.3, rectification 17.9, fraud and operational losses 49.1, additional resource 122.4, waived income 33.5"),
        ("outcome.sabis_recovery_gbp", F["sabis_recovery_gbp"], "ara2018", "Estimated recovery from the provider, accrued in 2018, not yet paid"),
        ("outcome.back_to_normal", "2018-12-10", "fca_notice", "Business as usual about 7.5 months after the 22 Apr 2018 go-live"),
        ("outcome.original_target_date", "2017-11-05", "fca_notice", "Delayed to April 2018; phased migration considered and rejected"),
        ("outcome.fca_fine_gbp", F["fca_fine_gbp"], "fca_press", "20 Dec 2022"),
        ("outcome.pra_fine_gbp", F["pra_fine_gbp"], "pra_press", "20 Dec 2022"),
        ("outcome.lbg_contribution_gbp", F["lbg_contribution_gbp"], "savings", "Previous owner's contribution to the migration"),
        ("fx_usd_per_gbp_2018", FX, "fx", "Federal Reserve G.5A annual average 2018"),
    ]:
        prov(field, value, "sourced", src, note)
    for m in mitigations():
        prov(f"{m['id']}.one_time_cost_usd", m["one_time_cost_usd"], "modeled", note="Assumed one-time cost; not public")


def main() -> None:
    PROV.clear()
    t = twin()
    outcome_provenance()
    (HERE / "twin.json").write_text(json.dumps(t, indent=1) + "\n")
    (HERE / "brief_naive.json").write_text(json.dumps(brief_naive(), indent=1) + "\n")
    (HERE / "mitigations.json").write_text(json.dumps(mitigations(), indent=1) + "\n")
    (HERE / "planted_items.json").write_text(json.dumps(planted(), indent=1) + "\n")
    with (HERE / "provenance.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["entity_or_field", "value", "source_url", "sourced_or_modeled", "note"])
        w.writeheader()
        w.writerows(PROV)
    print(f"wrote twin ({len(t['entities'])} entities, {len(t['edges'])} edges) and {len(PROV)} provenance rows")


if __name__ == "__main__":
    main()
