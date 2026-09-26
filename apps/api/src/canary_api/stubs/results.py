"""Fixed stub engine outputs for the Northstar vendor and workforce briefs; no calculation happens here."""

from dataclasses import dataclass, field
from typing import Callable

from contracts_py.agents import (
    AgentAssessment,
    AgentOutput,
    CallMetrics,
    ChallengerOutput,
    Claim,
    Finding,
    FutureView,
    ProposedDependency,
)
from contracts_py.decision import CandidatePlan, DecisionBrief, Scenario
from contracts_py.engine import (
    BlastEdge,
    BlastNode,
    BlastRadius,
    CompanyOutcome,
    ConstraintResult,
    DepartmentImpactSummary,
    FutureComparison,
    FutureRow,
    Impact,
    KnowledgeCoverage,
    Portfolio,
    PortfolioComparison,
    PressureTrigger,
    RiskComponents,
    RiskScore,
    SimulationResult,
    ValueBreakdown,
    VendorOverlap,
    WorkflowCoverage,
)
from contracts_py.enums import (
    ClaimStatus,
    Criticality,
    Direction,
    Future,
    ImpactCategory,
    ImpactLevel,
    MigrationDifficulty,
    Origin,
    OverlapDimension,
    Polarity,
    Relation,
    RiskLevel,
)
from contracts_py.package import DecisionPackage, Recommendation
from contracts_py.twin import VersionInfo

from canary_api.stubs.twin import STUB_TIME, TWIN_VERSION, VENDOR_DECISION, WORKFORCE_DECISION, WORKFORCE_ROLES

NAIVE_PLAN = "plan_naive"
RECOMMENDED_PLAN = "plan_beacon_echo"
NAIVE_INTERVENTIONS = ["remove_apex", "remove_cinder"]
RECOMMENDED_INTERVENTIONS = ["remove_beacon", "remove_echo"]
WORKFORCE_PLAN = "plan_remove_eight_roles"
WORKFORCE_MITIGATED_PLAN = "plan_remove_eight_roles_mitigated"
WORKFORCE_INTERVENTIONS = [f"remove_{r.removeprefix('role_')}" for r in WORKFORCE_ROLES]
STUB_AGENTS = ["finance", "ai_data", "sales", "compliance", "challenger"]
STUB_ASSUMPTION = "Stub engine output: fixed constants, expected-value mode."


def scenario_id(run_id: str, future: Future, plan_id: str | None) -> str:
    return f"scn_{run_id}_{future.value}_{plan_id or 'none'}"


def result_id(run_id: str, future: Future, plan_id: str | None) -> str:
    return f"res_{run_id}_{future.value}_{plan_id or 'none'}"


def monthly(first: int, last: int) -> list[int]:
    return [first + (last - first) * month // 11 for month in range(12)]


@dataclass(frozen=True)
class Value:
    gross: int
    transition: int
    added: int
    rebound: int
    loss: int
    pressures: dict[str, int]
    neutralised: tuple[str, ...] = ()
    first_month: int = 0

    @property
    def pressure_total(self) -> int:
        return sum(self.pressures.values())

    @property
    def net(self) -> int:
        return self.gross - self.transition - self.added - self.rebound - self.loss - self.pressure_total


@dataclass(frozen=True)
class Story:
    decision_id: str
    naive_plan: str
    naive_label: str
    naive_ids: list[str]
    recommended_plan: str
    recommended_label: str
    recommended_source: str
    recommended_ids: list[str]
    values: dict[str, Value]
    risks: dict[str, tuple[float, float, float, float, float]]
    constraints: dict[str, list[tuple[str, str, str, float, float, bool, str]]]
    rejection: str
    headline: str
    act_headline: str
    impacts: Callable[[str, str, Future, str | None], list[Impact]]
    coverage: dict[str, list[WorkflowCoverage]] = field(default_factory=dict)
    knowledge: dict[str, list[KnowledgeCoverage]] = field(default_factory=dict)
    breakeven: tuple[int | None, int | None] = (None, None)


def _impact(decision_id: str, scn: str, impact_id: str, source_entity: str, source_ref: str, affected: str,
            department: str | None, level: ImpactLevel, category: ImpactCategory, polarity: Polarity,
            direction: Direction, metric: str, magnitude: float, unit: str, value_usd: int | None, severity: int,
            first_day: int, peak_day: int, evidence: list[str], source_kind: str = "intervention",
            path: list[str] | None = None, edges: list[str] | None = None,
            constraint_refs: list[str] | None = None) -> Impact:
    return Impact(
        impact_id=impact_id, decision_id=decision_id, scenario_id=scn, source_entity=source_entity,
        source_kind=source_kind, source_ref=source_ref, affected_entity=affected,  # type: ignore[arg-type]
        affected_department=department, level=level, category=category, polarity=polarity, direction=direction,
        metric=metric, magnitude=magnitude, unit=unit, value_usd=value_usd, severity=severity,
        first_effect_day=first_day, peak_effect_day=peak_day, confidence=0.8, dependency_path=path or [],
        edge_path=edges or [], evidence_refs=evidence, constraint_refs=constraint_refs or [], origin=Origin.engine,
        status=ClaimStatus.computed,
    )


LV = ImpactLevel
CAT = ImpactCategory
POL = Polarity
DIR = Direction


def _vendor_impacts(run_id: str, decision_id: str, future: Future, plan_id: str | None) -> list[Impact]:
    scn = scenario_id(run_id, future, plan_id)
    tag = f"imp_{future.value}_{plan_id or 'none'}"
    if plan_id is None:
        return [
            _impact(decision_id, scn, f"{tag}_apex_renewal", "vendor_apex", "pr_apex_renewal", "vendor_apex",
                    "dept_ai_data", LV.delayed, CAT.financial, POL.harm, DIR.increase, "annual_cost_usd", 128_000_000, "usd",
                    128_000_000, 3, 60, 60, ["ev_apex_msa_renewal"], "pressure"),
            _impact(decision_id, scn, f"{tag}_echo_renewal", "vendor_echo", "pr_echo_renewal", "vendor_echo",
                    "dept_ai_data", LV.delayed, CAT.financial, POL.harm, DIR.increase, "annual_cost_usd", 132_000_000, "usd",
                    132_000_000, 3, 120, 120, ["ev_echo_msa_clause_9"], "pressure"),
            _impact(decision_id, scn, f"{tag}_flux_growth", "vendor_flux", "pr_flux_usage_growth", "vendor_flux",
                    "dept_ai_data", LV.direct, CAT.financial, POL.harm, DIR.increase, "annual_cost_usd", 76_000_000, "usd",
                    76_000_000, 2, 30, 365, ["ev_flux_usage_pricing"], "pressure"),
            _impact(decision_id, scn, f"{tag}_vendor_recon", "wf_vendor_reconciliation", "pr_vendor_recon_hazard",
                    "wf_vendor_reconciliation", "dept_operations", LV.direct, CAT.operational, POL.harm, DIR.increase,
                    "expected_failures", 0.36, "events", 14_400_000, 3, 0, 365, [], "pressure"),
        ]
    if plan_id == NAIVE_PLAN:
        return [
            _impact(decision_id, scn, f"{tag}_apex_cost", "vendor_apex", "remove_apex", "vendor_apex", "dept_ai_data",
                    LV.direct, CAT.financial, POL.benefit, DIR.decrease, "annual_cost_usd", 1_600_000_000, "usd",
                    1_600_000_000, 2, 30, 30, ["ev_apex_msa_renewal"]),
            _impact(decision_id, scn, f"{tag}_corporate_linkage", "vendor_apex", "remove_apex", "ds_corporate_linkage",
                    "dept_ai_data", LV.dependent, CAT.technical, POL.harm, DIR.decrease, "coverage_pct", 1.0, "ratio", None,
                    5, 30, 30, ["ev_vendor_dataset_matrix"]),
            _impact(decision_id, scn, f"{tag}_kyc", "vendor_apex", "remove_apex", "ctl_kyc_screening",
                    "dept_compliance", LV.second_order, CAT.compliance, POL.harm, DIR.decrease, "control_passing", 1.0,
                    "count", None, 5, 30, 30, ["ev_kyc_screening_inputs"], constraint_refs=["c_compliance"]),
            _impact(decision_id, scn, f"{tag}_cinder_cost", "vendor_cinder", "remove_cinder", "vendor_cinder",
                    "dept_ai_data", LV.direct, CAT.financial, POL.benefit, DIR.decrease, "annual_cost_usd", 1_400_000_000,
                    "usd", 1_400_000_000, 2, 30, 30, ["ev_cinder_msa_terms"]),
        ]
    return [
        _impact(decision_id, scn, f"{tag}_beacon_cost", "vendor_beacon", "remove_beacon", "vendor_beacon",
                "dept_ai_data", LV.direct, CAT.financial, POL.benefit, DIR.decrease, "annual_cost_usd", 1_200_000_000, "usd",
                1_200_000_000, 2, 30, 30, ["ev_beacon_msa_terms"]),
        _impact(decision_id, scn, f"{tag}_echo_cost", "vendor_echo", "remove_echo", "vendor_echo", "dept_ai_data",
                LV.direct, CAT.financial, POL.benefit, DIR.decrease, "annual_cost_usd", 1_100_000_000, "usd", 1_100_000_000,
                2, 30, 30, ["ev_echo_msa_clause_9"]),
        _impact(decision_id, scn, f"{tag}_account_intel", "vendor_echo", "remove_echo", "ds_account_intel",
                "dept_ai_data", LV.dependent, CAT.technical, POL.harm, DIR.decrease, "coverage_pct", 1.0, "ratio", None, 3,
                30, 30, ["ev_vendor_dataset_matrix"]),
        _impact(decision_id, scn, f"{tag}_account_planning", "vendor_echo", "remove_echo", "wf_account_planning",
                "dept_sales", LV.second_order, CAT.operational, POL.harm, DIR.decrease, "input_coverage_pct", 0.5, "ratio",
                90_000_000, 3, 30, 60, ["ev_vendor_dataset_matrix"]),
        _impact(decision_id, scn, f"{tag}_pipeline", "dept_sales", "remove_echo", "kpi_pipeline", "dept_sales",
                LV.second_order, CAT.business, POL.harm, DIR.decrease, "revenue_impact_pct", 1.2, "percent", 54_000_000, 4,
                60, 120, [], path=["dept_sales", "kpi_company"], edges=["ch_sales_kpi_pipeline"],
                constraint_refs=["c_sales"]),
    ]


def _workforce_impacts(run_id: str, decision_id: str, future: Future, plan_id: str | None) -> list[Impact]:
    scn = scenario_id(run_id, future, plan_id)
    tag = f"imp_{future.value}_{plan_id or 'none'}"
    if plan_id is None:
        return [
            _impact(decision_id, scn, f"{tag}_billing_hazard", "wf_billing_recon", "pr_billing_recon_hazard",
                    "wf_billing_recon", "dept_operations", LV.direct, CAT.operational, POL.harm, DIR.increase,
                    "expected_failures", 0.48, "events", 28_800_000, 3, 0, 365, ["ev_billing_runbook_gap"], "pressure"),
            _impact(decision_id, scn, f"{tag}_lineage", "kn_warehouse_lineage", "pr_lineage_holder_attrition",
                    "kn_warehouse_lineage", "dept_ai_data", LV.direct, CAT.ownership, POL.harm, DIR.increase,
                    "expected_failures", 0.36, "events", 16_200_000, 3, 0, 365, ["ev_knowledge_matrix_3"], "pressure"),
        ]
    stranded = plan_id == WORKFORCE_PLAN
    return [
        _impact(decision_id, scn, f"{tag}_role_cost", "dept_finance", "remove_close_accountant", "dept_finance",
                "dept_finance", LV.direct, CAT.financial, POL.benefit, DIR.decrease, "annual_cost_usd", 1_070_000, "usd",
                1_070_000, 1, 30, 30, []),
        _impact(decision_id, scn, f"{tag}_billing_owners", "role_billing_ops_lead", "remove_billing_ops_lead",
                "wf_billing_recon", "dept_operations", LV.dependent, CAT.ownership, POL.harm, DIR.decrease,
                "qualified_owners", 2.0 if stranded else 0.0, "count", 86_400_000 if stranded else 28_800_000,
                5 if stranded else 3, 30, 30, ["ev_knowledge_matrix_billing"], constraint_refs=["c_stranded"]),
        _impact(decision_id, scn, f"{tag}_close_owners", "role_close_accountant", "remove_close_accountant",
                "wf_financial_close", "dept_finance", LV.dependent, CAT.ownership, POL.harm, DIR.decrease,
                "qualified_owners", 2.0 if stranded else 0.0, "count", 45_000_000 if stranded else 5_400_000,
                5 if stranded else 3, 30, 60, ["ev_sop_financial_close_lineage"], constraint_refs=["c_stranded"]),
    ]


def _coverage(workflow_id: str, before: list[str], after: list[str], documented: float, reason: str) -> WorkflowCoverage:
    return WorkflowCoverage(workflow_id=workflow_id, criticality=Criticality.critical, owners_before=before,
                            owners_after=after, min_qualified_owners=2, backup_count_after=max(len(after) - 1, 0),
                            documented_pct=documented, stranded=len(after) < 2, reasons=[reason])


BILLING_OWNERS = ["role_billing_ops_lead", "role_billing_specialist", "role_revenue_accountant", "role_ar_specialist"]
CLOSE_OWNERS = ["role_close_accountant", "role_gl_accountant", "role_reporting_analyst"]
WORKFORCE_COVERAGE = {
    "naive": [
        _coverage("wf_billing_recon", BILLING_OWNERS, [], 0.35, "Every qualified owner is removed."),
        _coverage("wf_financial_close", CLOSE_OWNERS, [], 0.4, "Every qualified owner is removed."),
    ],
    "mitigated": [
        _coverage("wf_billing_recon", BILLING_OWNERS, ["role_finance_analyst", "role_billing_ops_lead"], 0.7,
                  "Finance analyst reassigned; billing ops lead retained for 90 days."),
        _coverage("wf_financial_close", CLOSE_OWNERS, ["role_controller", "role_close_accountant"], 0.7,
                  "Controller reassigned; close accountant retained for 90 days."),
    ],
    "inaction": [
        _coverage("wf_billing_recon", BILLING_OWNERS, BILLING_OWNERS, 0.35, "No change."),
        _coverage("wf_financial_close", CLOSE_OWNERS, CLOSE_OWNERS, 0.4, "No change."),
    ],
}
WORKFORCE_KNOWLEDGE = {
    "naive": [KnowledgeCoverage(knowledge_id="kn_warehouse_lineage", holders_before=["role_data_platform_lead"],
                                holders_after=[], holder_capacity_fte_before=1.0, holder_capacity_fte_after=0.0,
                                documented_pct=0.2, lost=True, dependent_workflow_ids=["wf_financial_close"],
                                reasons=["The only holder is removed."])],
    "mitigated": [KnowledgeCoverage(knowledge_id="kn_warehouse_lineage", holders_before=["role_data_platform_lead"],
                                    holders_after=["role_data_platform_lead"], holder_capacity_fte_before=1.0,
                                    holder_capacity_fte_after=1.0, documented_pct=0.6, lost=False,
                                    dependent_workflow_ids=["wf_financial_close"],
                                    reasons=["Holder retained for 90 days while the lineage runbook is written."])],
}

VENDOR = Story(
    decision_id=VENDOR_DECISION,
    naive_plan=NAIVE_PLAN,
    naive_label="Remove the two most expensive vendors",
    naive_ids=NAIVE_INTERVENTIONS,
    recommended_plan=RECOMMENDED_PLAN,
    recommended_label="Remove BeaconIQ and EchoMarket",
    recommended_source="optimizer",
    recommended_ids=RECOMMENDED_INTERVENTIONS,
    values={
        "act_now": Value(2_300_000_000, 180_000_000, 0, 60_000_000, 90_000_000,
                         {"pr_apex_renewal": 128_000_000, "pr_echo_renewal": 0, "pr_flux_usage_growth": 76_000_000,
                          "pr_vendor_recon_hazard": 14_400_000}, ("pr_echo_renewal",), -180_000_000),
        "inaction": Value(0, 0, 0, 0, 0,
                          {"pr_apex_renewal": 128_000_000, "pr_echo_renewal": 132_000_000,
                           "pr_flux_usage_growth": 76_000_000, "pr_vendor_recon_hazard": 14_400_000},
                          first_month=-29_200_000),
        "delay": Value(1_725_000_000, 180_000_000, 0, 60_000_000, 90_000_000,
                       {"pr_apex_renewal": 128_000_000, "pr_echo_renewal": 132_000_000,
                        "pr_flux_usage_growth": 76_000_000, "pr_vendor_recon_hazard": 14_400_000},
                       first_month=-29_200_000),
        "naive": Value(3_000_000_000, 180_000_000, 0, 60_000_000, 400_000_000,
                       {"pr_apex_renewal": 0, "pr_echo_renewal": 132_000_000, "pr_flux_usage_growth": 76_000_000,
                        "pr_vendor_recon_hazard": 14_400_000}, ("pr_apex_renewal",), -180_000_000),
    },
    risks={"act_now": (8, 10, 6, 6, 6), "inaction": (15, 14, 10, 8, 8), "delay": (9, 11, 7, 7, 8),
           "naive": (10, 14, 12, 34, 8)},
    constraints={
        "pass": [("c_compliance", "compliance_controls_broken", "==", 0, 0, True, "No mandatory control breaks."),
                 ("c_sales", "revenue_impact_pct", "<=", 3, 1.2, True, "Pipeline falls 1.2%, within 3%."),
                 ("c_customer", "customer_impact_pct", "<=", 2, 0.4, True, "Customer impact 0.4%, within 2%."),
                 ("c_stranded", "stranded_workflows", "==", 0, 0, False, "No workflow is stranded.")],
        "naive": [("c_compliance", "compliance_controls_broken", "==", 0, 1, True,
                   "ctl_kyc_screening breaks: ds_corporate_linkage has no provider after vendor_apex is removed."),
                  ("c_sales", "revenue_impact_pct", "<=", 3, 2.1, True, "Pipeline falls 2.1%, within 3%."),
                  ("c_customer", "customer_impact_pct", "<=", 2, 0.9, True, "Customer impact 0.9%, within 2%."),
                  ("c_stranded", "stranded_workflows", "==", 0, 0, False, "No workflow is stranded.")],
    },
    rejection="Removing vendor_apex leaves ds_corporate_linkage with no provider, which breaks wf_kyc_screening "
              "and the mandatory control ctl_kyc_screening.",
    headline="Acting now is worth $2.1B more than doing nothing; waiting 90 days costs $0.71B.",
    act_headline="Remove BeaconIQ and EchoMarket now; keep ApexData, which alone provides ds_corporate_linkage.",
    impacts=_vendor_impacts,
    breakeven=(60, 150),
)

WORKFORCE = Story(
    decision_id=WORKFORCE_DECISION,
    naive_plan=WORKFORCE_PLAN,
    naive_label="Remove all eight roles",
    naive_ids=WORKFORCE_INTERVENTIONS,
    recommended_plan=WORKFORCE_MITIGATED_PLAN,
    recommended_label="Remove all eight roles with owner reassignment, runbooks and temporary retention",
    recommended_source="mitigated",
    recommended_ids=WORKFORCE_INTERVENTIONS,
    values={
        "act_now": Value(1_070_000, 730_000, 480_000, 0, 0,
                         {"pr_billing_recon_hazard": 28_800_000, "pr_lineage_holder_attrition": 5_400_000,
                          "pr_contractor_cost_growth": 1_200_000}, first_month=-3_000_000),
        "inaction": Value(0, 0, 0, 0, 0,
                          {"pr_billing_recon_hazard": 28_800_000, "pr_lineage_holder_attrition": 16_200_000,
                           "pr_contractor_cost_growth": 1_200_000}, first_month=-3_850_000),
        "delay": Value(802_500, 730_000, 480_000, 0, 0,
                       {"pr_billing_recon_hazard": 28_800_000, "pr_lineage_holder_attrition": 9_450_000,
                        "pr_contractor_cost_growth": 1_200_000}, first_month=-3_850_000),
        "naive": Value(1_070_000, 320_000, 0, 0, 45_000_000,
                       {"pr_billing_recon_hazard": 86_400_000, "pr_lineage_holder_attrition": 16_200_000,
                        "pr_contractor_cost_growth": 1_200_000}, first_month=-12_000_000),
    },
    risks={"act_now": (6, 14, 4, 4, 8), "inaction": (8, 16, 4, 4, 8), "delay": (7, 15, 4, 4, 8),
           "naive": (20, 40, 8, 6, 10)},
    constraints={
        "pass": [("c_compliance", "compliance_controls_broken", "==", 0, 0, True, "No mandatory control breaks."),
                 ("c_stranded", "stranded_workflows", "==", 0, 0, True, "Both critical workflows keep two owners."),
                 ("c_customer", "customer_impact_pct", "<=", 2, 0.3, True, "Customer impact 0.3%, within 2%.")],
        "naive": [("c_compliance", "compliance_controls_broken", "==", 0, 0, True, "No mandatory control breaks."),
                  ("c_stranded", "stranded_workflows", "==", 0, 2, True,
                   "wf_financial_close and wf_billing_recon are left without qualified owners."),
                  ("c_customer", "customer_impact_pct", "<=", 2, 1.1, True, "Customer impact 1.1%, within 2%.")],
    },
    rejection="wf_financial_close and wf_billing_recon are stranded: every qualified owner is removed.",
    headline="Acting now is worth $10.66M more than doing nothing; waiting 90 days costs $4.32M.",
    act_headline="Remove the eight roles only with owner reassignment, runbooks and 90-day retention in place.",
    impacts=_workforce_impacts,
    coverage=WORKFORCE_COVERAGE,
    knowledge=WORKFORCE_KNOWLEDGE,
    breakeven=(None, None),
)

STORIES = {VENDOR.decision_id: VENDOR, WORKFORCE.decision_id: WORKFORCE}


def story(decision_id: str) -> Story:
    return STORIES.get(decision_id, VENDOR)


def plans(decision_id: str = VENDOR_DECISION) -> list[CandidatePlan]:
    s = story(decision_id)
    return [
        CandidatePlan(plan_id=s.naive_plan, label=s.naive_label, intervention_ids=s.naive_ids, source="naive"),
        CandidatePlan(plan_id=s.recommended_plan, label=s.recommended_label, intervention_ids=s.recommended_ids,
                      source=s.recommended_source,  # type: ignore[arg-type]
                      parent_plan_id=s.naive_plan if s.recommended_source == "mitigated" else None),
    ]


def scenario(run_id: str, future: Future, plan_id: str | None, delay_days: int = 90) -> Scenario:
    return Scenario(scenario_id=scenario_id(run_id, future, plan_id), run_id=run_id, future=future, plan_id=plan_id,
                    delay_days=delay_days if future is Future.delay else 0, baseline_twin_version=TWIN_VERSION,
                    created_at=STUB_TIME)


def _breakdown(value: Value) -> ValueBreakdown:
    return ValueBreakdown(
        gross_savings_usd=value.gross, transition_cost_usd=value.transition, added_cost_usd=value.added,
        rebound_cost_usd=value.rebound, expected_business_loss_usd=value.loss,
        pressure_cost_usd=value.pressure_total, avoided_failure_cost_usd=0, net_value_usd=value.net,
        monthly_net_usd=monthly(value.first_month, value.net),
    )


def _risk(parts: tuple[float, float, float, float, float]) -> RiskScore:
    score = sum(parts)
    level = RiskLevel.low if score < 25 else RiskLevel.medium if score < 50 else RiskLevel.high if score < 75 \
        else RiskLevel.critical
    return RiskScore(score=score, level=level, settings_version=1, components=RiskComponents(
        financial=parts[0], capability_workflow=parts[1], customer_revenue=parts[2], compliance_control=parts[3],
        execution_uncertainty=parts[4]))


def _result(run_id: str, decision_id: str, key: str, future: Future, plan_id: str | None, mode: str) -> SimulationResult:
    s = story(decision_id)
    value = s.values[key]
    naive = key == "naive"
    coverage_key = "naive" if naive else "inaction" if plan_id is None else "mitigated"
    constraint_rows = s.constraints["naive" if naive else "pass"]
    impacts = s.impacts(run_id, decision_id, future, plan_id)
    return SimulationResult(
        result_id=result_id(run_id, future, plan_id),
        run_id=run_id,
        scenario_id=scenario_id(run_id, future, plan_id),
        future=future,
        plan_id=plan_id,
        mode=mode,  # type: ignore[arg-type]
        seed=42,
        intervention_ids=[] if plan_id is None else (s.naive_ids if naive else s.recommended_ids),
        value=_breakdown(value),
        goal_met=plan_id is not None and future is not Future.delay,
        constraint_results=[
            ConstraintResult(constraint_id=cid, metric=metric, operator=op, threshold=threshold,  # type: ignore[arg-type]
                             value=actual, hard=hard, passed=actual == 0 if op == "==" else actual <= threshold,
                             explanation=text)
            for cid, metric, op, threshold, actual, hard, text in constraint_rows
        ],
        impacts=impacts,
        workflow_coverage=s.coverage.get(coverage_key, []),
        knowledge_coverage=s.knowledge.get(coverage_key, []),
        pressures_triggered=[
            PressureTrigger(pressure_id=pid, expected_events=0.0 if pid in value.neutralised else 1.0,
                            expected_cost_usd=cost, neutralised=pid in value.neutralised)
            for pid, cost in value.pressures.items()
        ],
        risk=_risk(s.risks[key]),
        affected_department_ids=sorted({i.affected_department for i in impacts if i.affected_department}),
        feasible=not naive,
        rejection_reasons=[s.rejection] if naive else [],
        assumptions=[STUB_ASSUMPTION],
        computed_at=STUB_TIME,
    )


def act_now_result(run_id: str, decision_id: str, mode: str = "full") -> SimulationResult:
    return _result(run_id, decision_id, "act_now", Future.act_now, story(decision_id).recommended_plan, mode)


def inaction_result(run_id: str, decision_id: str, mode: str = "full") -> SimulationResult:
    return _result(run_id, decision_id, "inaction", Future.inaction, None, mode)


def delay_result(run_id: str, decision_id: str, mode: str = "full") -> SimulationResult:
    return _result(run_id, decision_id, "delay", Future.delay, story(decision_id).recommended_plan, mode)


def naive_result(run_id: str, decision_id: str, mode: str = "full") -> SimulationResult:
    return _result(run_id, decision_id, "naive", Future.act_now, story(decision_id).naive_plan, mode)


def future_results(run_id: str, decision_id: str) -> dict[Future, SimulationResult]:
    return {
        Future.act_now: act_now_result(run_id, decision_id),
        Future.inaction: inaction_result(run_id, decision_id),
        Future.delay: delay_result(run_id, decision_id),
    }


def future_comparison(run_id: str, decision_id: str) -> FutureComparison:
    s = story(decision_id)
    results = future_results(run_id, decision_id)
    base = results[Future.inaction].value
    act_breakeven, delay_breakeven = s.breakeven

    def row(future: Future, label: str, breakeven: int | None, cost_of_delay: int | None = None) -> FutureRow:
        result = results[future]
        delta = result.value.net_value_usd - base.net_value_usd
        return FutureRow(
            future=future, plan_id=result.plan_id, result_id=result.result_id, label=label,
            net_value_p50_usd=result.value.net_value_usd, delta_vs_inaction_p10_usd=delta,
            delta_vs_inaction_p50_usd=delta, delta_vs_inaction_p90_usd=delta,
            p_better_than_inaction=1.0 if delta > 0 else 0.0, breakeven_day=breakeven, cost_of_delay_usd=cost_of_delay,
            feasible=result.feasible, risk_score=result.risk.score,
            monthly_delta_usd=[a - b for a, b in zip(result.value.monthly_net_usd, base.monthly_net_usd)],
        )

    act_delta = results[Future.act_now].value.net_value_usd - base.net_value_usd
    delay_delta = results[Future.delay].value.net_value_usd - base.net_value_usd
    return FutureComparison(
        comparison_id=f"cmp_{run_id}",
        decision_id=decision_id,
        run_id=run_id,
        reference_result_id=results[Future.inaction].result_id,
        rows=[
            row(Future.act_now, "Act now", act_breakeven),
            row(Future.inaction, "Do nothing", None),
            row(Future.delay, "Wait 90 days", delay_breakeven, act_delta - delay_delta),
        ],
        best_row_index=0,
        headline=s.headline,
    )


def portfolio_comparison(run_id: str, decision_id: str) -> PortfolioComparison:
    s = story(decision_id)
    naive = Portfolio(plan_id=s.naive_plan, intervention_ids=s.naive_ids, result=naive_result(run_id, decision_id))
    recommended = Portfolio(plan_id=s.recommended_plan, intervention_ids=s.recommended_ids, rank=1,
                            result=act_now_result(run_id, decision_id))
    evaluated = 128 if decision_id == VENDOR_DECISION else 2
    return PortfolioComparison(evaluated_count=evaluated, naive=naive, recommended=recommended, alternatives=[])


def _node(node_id: str, kind: str, headline: str, **fields: object) -> BlastNode:
    return BlastNode(node_id=node_id, kind=kind, headline=headline, **fields)  # type: ignore[arg-type]


def _summaries(impacts: list[Impact]) -> list[DepartmentImpactSummary]:
    departments: dict[str, list[Impact]] = {}
    for impact in impacts:
        if impact.affected_department:
            departments.setdefault(impact.affected_department, []).append(impact)
    return [
        DepartmentImpactSummary(
            department_id=department,
            headline=f"{len(items)} stub impact(s)",
            polarity=Polarity.harm if any(i.polarity is Polarity.harm for i in items) else Polarity.benefit,
            severity=max(i.severity for i in items),
            impact_ids=[i.impact_id for i in items],
        )
        for department, items in sorted(departments.items())
    ]


def _blast(run_id: str, decision_id: str, result: SimulationResult, root_headline: str) -> BlastRadius:
    nodes = [_node(decision_id, "decision", root_headline)]
    edges: list[BlastEdge] = []
    for impact in result.impacts:
        node_id = impact.affected_entity
        if any(n.node_id == node_id for n in nodes):
            continue
        is_pressure = impact.source_kind == "pressure"
        nodes.append(_node(node_id, "entity", f"{impact.metric} {impact.direction.value}",
                           department_id=impact.affected_department, entity_id=node_id, level=impact.level,
                           category=impact.category, polarity=impact.polarity, severity=impact.severity,
                           value_usd=impact.value_usd, first_effect_day=impact.first_effect_day,
                           impact_ids=[impact.impact_id]))
        edges.append(BlastEdge(source=decision_id, target=node_id,
                               label="pressure continues" if is_pressure else impact.source_ref,
                               level=impact.level, critical_constraint=bool(impact.constraint_refs)))
    nodes.append(_node("kpi_company", "outcome", "Company outcome", value_usd=result.value.net_value_usd))
    return BlastRadius(
        run_id=run_id, scenario_id=result.scenario_id, future=result.future, plan_id=result.plan_id,
        root_node_id=decision_id, nodes=nodes, edges=edges, departments=_summaries(result.impacts),
        outcome=CompanyOutcome(net_value_usd=result.value.net_value_usd, risk_level=result.risk.level,
                               headline=f"Stub outcome for {result.future.value}."),
    )


def act_now_blast_radius(run_id: str, decision_id: str) -> BlastRadius:
    return _blast(run_id, decision_id, act_now_result(run_id, decision_id), story(decision_id).recommended_label)


def inaction_blast_radius(run_id: str, decision_id: str) -> BlastRadius:
    return _blast(run_id, decision_id, inaction_result(run_id, decision_id), "Do nothing")


def _metrics(agent_id: str) -> CallMetrics:
    return CallMetrics(model_id="replay", prompt_version="stub", prompt_hash=f"stub_{agent_id}", latency_ms=0,
                       input_tokens=0, output_tokens=0)


AGENT_NOTES = {
    "finance": ("Removing BeaconIQ and EchoMarket clears the $2B gross goal.",
                "Apex and Echo renewal uplifts keep adding cost.", ["vendor_beacon", "vendor_echo"]),
    "ai_data": ("ds_account_intel must be migrated before EchoMarket is removed.",
                "Flux usage keeps growing.", ["ds_account_intel", "vendor_echo"]),
    "sales": ("Account planning loses its EchoMarket input; pipeline falls about 1.2%.",
              "No pipeline change.", ["wf_account_planning", "kpi_pipeline"]),
    "compliance": ("KYC screening keeps ds_corporate_linkage because ApexData stays.",
                   "No control change.", ["ctl_kyc_screening", "ds_corporate_linkage"]),
    "operations": ("Billing reconciliation needs two qualified owners after the change.",
                   "Reconciliation hazard persists.", ["wf_billing_recon"]),
}


def assessment(run_id: str, agent_id: str) -> AgentAssessment:
    if agent_id == "challenger":
        return AgentAssessment(
            assessment_id=f"asm_{run_id}_{agent_id}", run_id=run_id, plan_id=RECOMMENDED_PLAN, agent_id=agent_id,
            pass_type="challenge", status="replayed",
            challenge=ChallengerOutput(
                missed_dependencies=[ProposedDependency(
                    source="wf_vendor_reconciliation", target="ds_account_intel", relation=Relation.CONSUMES,
                    rationale="The workflow map says Account intelligence also feeds Vendor reconciliation.",
                    evidence_refs=["ev_echo_account_intel_feed"], confidence=0.8)],
                inaction_underestimated=[Finding(text="The Echo renewal uplift lands on day 120.",
                                                 entity_ids=["vendor_echo"], severity=3,
                                                 evidence_refs=["ev_echo_msa_clause_9"])],
                confidence=0.7,
            ),
            metrics=_metrics(agent_id), created_at=STUB_TIME,
        )
    act, inaction, ids = AGENT_NOTES[agent_id]
    return AgentAssessment(
        assessment_id=f"asm_{run_id}_{agent_id}", run_id=run_id, plan_id=RECOMMENDED_PLAN, agent_id=agent_id,
        pass_type="first_pass", status="replayed",
        output=AgentOutput(
            affected_entities=ids,
            act_now_view=FutureView(summary=act, failure_modes=[Finding(text=act, entity_ids=ids, severity=3)]),
            inaction_view=FutureView(summary=inaction,
                                     failure_modes=[Finding(text=inaction, entity_ids=ids, severity=2)]),
            assumptions=["Stub assessment."],
            confidence=0.7,
        ),
        metrics=_metrics(agent_id), created_at=STUB_TIME,
    )


def vendor_overlaps(decision_id: str) -> list[VendorOverlap]:
    if decision_id != VENDOR_DECISION:
        return []
    return [VendorOverlap(
        vendor_a="vendor_apex", vendor_b="vendor_beacon",
        dimensions={dimension: 0.6 for dimension in OverlapDimension}, overall_overlap=0.62,
        shared_dataset_ids=["ds_firmographics", "ds_contact_data"], unique_dataset_ids_a=["ds_corporate_linkage"],
        unique_dataset_ids_b=[], migration_difficulty=MigrationDifficulty.medium,
    )]


def decision_package(run_id: str, brief: DecisionBrief, versions: VersionInfo) -> DecisionPackage:
    decision_id = brief.decision_id
    s = story(decision_id)
    act_now = act_now_result(run_id, decision_id)
    blast = act_now_blast_radius(run_id, decision_id)
    return DecisionPackage(
        package_id=f"pkg_{run_id}", run_id=run_id, decision_id=decision_id, versions=versions, brief=brief,
        recommendation=Recommendation(
            plan_id=s.recommended_plan, future=Future.act_now, result_id=act_now.result_id, headline=s.act_headline,
            claims=[Claim(text=s.headline, source="calculation", ref=f"cmp_{run_id}"),
                    Claim(text=s.rejection, source="calculation", ref=s.naive_plan)],
        ),
        futures=future_comparison(run_id, decision_id),
        portfolios=portfolio_comparison(run_id, decision_id),
        blast_radius_act_now=blast,
        blast_radius_inaction=inaction_blast_radius(run_id, decision_id),
        department_impacts=blast.departments,
        critical_risks=[i for i in act_now.impacts if i.severity >= 4],
        vendor_overlaps=vendor_overlaps(decision_id),
        assumptions=[STUB_ASSUMPTION],
        open_questions=["Does EchoMarket history stay available after termination?"],
        created_at=STUB_TIME,
    )
