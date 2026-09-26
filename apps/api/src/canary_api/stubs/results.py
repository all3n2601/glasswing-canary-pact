# story_values.json was generated once by a throwaway script from these stories; by rule its values stay literals.
"""Fixed stub engine outputs for the Northstar vendor and workforce briefs; no calculation happens here."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

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
    RiskScore,
    SimulationResult,
    ValueBreakdown,
    VendorOverlap,
    WorkflowCoverage,
)
from contracts_py.enums import (
    ClaimStatus,
    Direction,
    Future,
    ImpactCategory,
    ImpactLevel,
    MigrationDifficulty,
    Origin,
    OverlapDimension,
    Polarity,
    Relation,
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
# Every money, risk and delta value is a literal in this fixture; nothing below computes one.
STORY_VALUES: dict[str, Any] = json.loads((Path(__file__).parent / "story_values.json").read_text())


def scenario_id(run_id: str, future: Future, plan_id: str | None) -> str:
    return f"scn_{run_id}_{future.value}_{plan_id or 'none'}"


def result_id(run_id: str, future: Future, plan_id: str | None) -> str:
    return f"res_{run_id}_{future.value}_{plan_id or 'none'}"


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
    rejection: str
    headline: str
    act_headline: str
    impacts: Callable[[str, str, Future, str | None], list[Impact]]
    knowledge: dict[str, list[KnowledgeCoverage]] = field(default_factory=dict)


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
    rejection="Removing vendor_apex leaves ds_corporate_linkage with no provider, which breaks wf_kyc_screening "
              "and the mandatory control ctl_kyc_screening.",
    headline="Acting now is worth $2.1B more than doing nothing; waiting 90 days costs $0.71B.",
    act_headline="Remove BeaconIQ and EchoMarket now; keep ApexData, which alone provides ds_corporate_linkage.",
    impacts=_vendor_impacts,
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
    rejection="wf_financial_close and wf_billing_recon are stranded: every qualified owner is removed.",
    headline="Acting now is worth $10.66M more than doing nothing; waiting 90 days costs $4.32M.",
    act_headline="Remove the eight roles only with owner reassignment, runbooks and 90-day retention in place.",
    impacts=_workforce_impacts,
    knowledge=WORKFORCE_KNOWLEDGE,
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


def _result(run_id: str, decision_id: str, key: str, future: Future, plan_id: str | None, mode: str) -> SimulationResult:
    s = story(decision_id)
    stored = STORY_VALUES[story(decision_id).decision_id]["results"][key]
    naive = key == "naive"
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
        value=ValueBreakdown.model_validate(stored["value"]),
        goal_met=stored["goal_met"],
        constraint_results=[ConstraintResult.model_validate(c) for c in stored["constraint_results"]],
        impacts=impacts,
        workflow_coverage=[WorkflowCoverage.model_validate(w) for w in stored["workflow_coverage"]],
        knowledge_coverage=s.knowledge.get("naive" if naive else "inaction" if plan_id is None else "mitigated", []),
        pressures_triggered=[PressureTrigger.model_validate(t) for t in stored["pressures_triggered"]],
        risk=RiskScore.model_validate(stored["risk"]),
        affected_department_ids=sorted({i.affected_department for i in impacts if i.affected_department}),
        feasible=stored["feasible"],
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
    return FutureComparison(
        comparison_id=f"cmp_{run_id}",
        decision_id=decision_id,
        run_id=run_id,
        reference_result_id=results[Future.inaction].result_id,
        rows=[
            FutureRow.model_validate({**row, "plan_id": results[Future(row["future"])].plan_id,
                                      "result_id": results[Future(row["future"])].result_id})
            for row in STORY_VALUES[story(decision_id).decision_id]["rows"]
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


def _summaries(decision_id: str, key: str) -> list[DepartmentImpactSummary]:
    return [
        DepartmentImpactSummary.model_validate({**d, "impact_ids": [f"imp_{suffix}" for suffix in d["impact_ids"]]})
        for d in STORY_VALUES[story(decision_id).decision_id]["departments"][key]
    ]


def _blast(run_id: str, decision_id: str, result: SimulationResult, root_headline: str, key: str) -> BlastRadius:
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
        root_node_id=decision_id, nodes=nodes, edges=edges, departments=_summaries(decision_id, key),
        outcome=CompanyOutcome(net_value_usd=result.value.net_value_usd, risk_level=result.risk.level,
                               headline=f"Stub outcome for {result.future.value}."),
    )


def act_now_blast_radius(run_id: str, decision_id: str) -> BlastRadius:
    return _blast(run_id, decision_id, act_now_result(run_id, decision_id), story(decision_id).recommended_label, "act_now")


def inaction_blast_radius(run_id: str, decision_id: str) -> BlastRadius:
    return _blast(run_id, decision_id, inaction_result(run_id, decision_id), "Do nothing", "inaction")


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
