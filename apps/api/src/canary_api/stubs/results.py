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
    Portfolio,
    PortfolioComparison,
    PressureTrigger,
    RiskComponents,
    RiskScore,
    SimulationResult,
    ValueBreakdown,
    WorkflowCoverage,
)
from contracts_py.enums import (
    ClaimStatus,
    Criticality,
    Direction,
    Future,
    ImpactCategory,
    ImpactLevel,
    Origin,
    Polarity,
    Relation,
    RiskLevel,
)
from contracts_py.package import DecisionPackage, Recommendation
from contracts_py.twin import VersionInfo

from canary_api.stubs.twin import STUB_TIME, TWIN_VERSION

NAIVE_PLAN = "plan_naive"
RECOMMENDED_PLAN = "plan_recommended"
NAIVE_INTERVENTIONS = ["i_platform_ops", "i_auditlog", "i_migration", "i_eng"]
RECOMMENDED_INTERVENTIONS = ["i_platform_ops", "i_migration", "i_eng"]
STUB_AGENTS = ["finance", "operations", "engineering", "compliance", "challenger"]


def scenario_id(run_id: str, future: Future, plan_id: str | None) -> str:
    return f"scn_{run_id}_{future.value}_{plan_id or 'none'}"


def result_id(run_id: str, future: Future, plan_id: str | None) -> str:
    return f"res_{run_id}_{future.value}_{plan_id or 'none'}"


def plans() -> list[CandidatePlan]:
    return [
        CandidatePlan(plan_id=NAIVE_PLAN, label="All four cuts", intervention_ids=NAIVE_INTERVENTIONS, source="naive"),
        CandidatePlan(
            plan_id=RECOMMENDED_PLAN,
            label="Keep the audit log vendor",
            intervention_ids=RECOMMENDED_INTERVENTIONS,
            source="optimizer",
        ),
    ]


def scenario(run_id: str, future: Future, plan_id: str | None) -> Scenario:
    return Scenario(
        scenario_id=scenario_id(run_id, future, plan_id),
        run_id=run_id,
        future=future,
        plan_id=plan_id,
        delay_days=90 if future is Future.delay else 0,
        baseline_twin_version=TWIN_VERSION,
        created_at=STUB_TIME,
    )


def _impact(decision_id: str, scn: str, impact_id: str, source_entity: str, source_ref: str, affected: str,
            department: str | None, level: ImpactLevel, category: ImpactCategory, polarity: Polarity,
            direction: Direction, metric: str, magnitude: float, unit: str, value_usd: int | None, severity: int,
            first_day: int, peak_day: int, path: list[str], edges: list[str], evidence: list[str],
            source_kind: str = "intervention", constraint_refs: list[str] | None = None) -> Impact:
    return Impact(
        impact_id=impact_id,
        decision_id=decision_id,
        scenario_id=scn,
        source_entity=source_entity,
        source_kind=source_kind,  # type: ignore[arg-type]
        source_ref=source_ref,
        affected_entity=affected,
        affected_department=department,
        level=level,
        category=category,
        polarity=polarity,
        direction=direction,
        metric=metric,
        magnitude=magnitude,
        unit=unit,
        value_usd=value_usd,
        severity=severity,
        first_effect_day=first_day,
        peak_effect_day=peak_day,
        confidence=0.8,
        dependency_path=path,
        edge_path=edges,
        evidence_refs=evidence,
        constraint_refs=constraint_refs or [],
        origin=Origin.engine,
        status=ClaimStatus.computed,
    )


def _act_impacts(run_id: str, decision_id: str, future: Future, plan_id: str) -> list[Impact]:
    scn = scenario_id(run_id, future, plan_id)
    tag = f"imp_{future.value}_{plan_id}"
    return [
        _impact(decision_id, scn, f"{tag}_ops_capacity", "dept_operations", "i_platform_ops", "dept_operations",
                "dept_operations", ImpactLevel.direct, ImpactCategory.operational, Polarity.harm, Direction.decrease,
                "capacity_fte", 11.6, "fte", None, 3, 0, 30, [], [], []),
        _impact(decision_id, scn, f"{tag}_billing_recon", "dept_operations", "i_platform_ops", "wf_billing_recon",
                "dept_operations", ImpactLevel.dependent, ImpactCategory.ownership, Polarity.harm, Direction.increase,
                "failure_probability_monthly", 0.03, "ratio", 120_000, 4, 30, 120,
                ["role_billing_ops_lead", "wf_billing_recon"], ["e_role_owns_billing_recon"],
                ["ev_billing_recon_matrix"], constraint_refs=["c_stranded"]),
        _impact(decision_id, scn, f"{tag}_company_value", "wf_billing_recon", "i_platform_ops", "kpi_company", None,
                ImpactLevel.second_order, ImpactCategory.business, Polarity.harm, Direction.decrease,
                "net_value_usd", 120_000, "usd", 120_000, 3, 60, 150, ["wf_billing_recon", "kpi_company"],
                ["e_billing_recon_kpi"], ["ev_billing_recon_matrix"]),
        _impact(decision_id, scn, f"{tag}_eng_cost", "dept_engineering", "i_eng", "dept_engineering",
                "dept_engineering", ImpactLevel.direct, ImpactCategory.financial, Polarity.benefit, Direction.decrease,
                "annual_cost_usd", 620_000, "usd", 620_000, 2, 0, 30, [], [], []),
        _impact(decision_id, scn, f"{tag}_migration", "proj_warehouse_migration", "i_migration",
                "proj_warehouse_migration", "dept_engineering", ImpactLevel.direct, ImpactCategory.financial,
                Polarity.benefit, Direction.decrease, "remaining_cost_usd", 290_000, "usd", 290_000, 2, 0, 0, [], [],
                []),
    ]


def _pressure_impacts(run_id: str, decision_id: str, future: Future, plan_id: str | None) -> list[Impact]:
    scn = scenario_id(run_id, future, plan_id)
    tag = f"imp_{future.value}_{plan_id or 'none'}"
    return [
        _impact(decision_id, scn, f"{tag}_cloud_growth", "sys_cloud_platform", "pr_cloud_growth", "sys_cloud_platform",
                "dept_engineering", ImpactLevel.direct, ImpactCategory.financial, Polarity.harm, Direction.increase,
                "annual_cost_usd", 64_000, "usd", 64_000, 2, 30, 365, [], [], [], source_kind="pressure"),
        _impact(decision_id, scn, f"{tag}_auditlog_renewal", "vendor_auditlog", "pr_auditlog_renewal",
                "vendor_auditlog", "dept_operations", ImpactLevel.delayed, ImpactCategory.financial, Polarity.harm,
                Direction.increase, "annual_cost_usd", 36_000, "usd", 36_000, 2, 120, 120, [], [],
                ["ev_auditlog_contract"], source_kind="pressure"),
        _impact(decision_id, scn, f"{tag}_billing_hazard", "wf_billing_recon", "pr_billing_recon_hazard",
                "wf_billing_recon", "dept_operations", ImpactLevel.direct, ImpactCategory.operational, Polarity.harm,
                Direction.increase, "expected_failures", 0.48, "events", 192_000, 4, 0, 365, [], [],
                ["ev_billing_recon_matrix"], source_kind="pressure"),
    ]


def _constraints(compliance_broken: float, stranded: float) -> list[ConstraintResult]:
    return [
        ConstraintResult(constraint_id="c_compliance", metric="compliance_controls_broken", operator="==", threshold=0,
                         value=compliance_broken, hard=True, passed=compliance_broken == 0,
                         explanation="Mandatory controls keep their supporting systems."
                         if compliance_broken == 0 else "Removing vendor_auditlog breaks ctl_soc2_audit_logging."),
        ConstraintResult(constraint_id="c_critical", metric="critical_systems_degraded", operator="==", threshold=0,
                         value=0, hard=True, passed=True, explanation="No critical system loses its owner."),
        ConstraintResult(constraint_id="c_revenue", metric="revenue_impact_pct", operator="<=", threshold=3,
                         value=0.4, hard=True, passed=True, explanation="Revenue impact stays under 3 percent."),
        ConstraintResult(constraint_id="c_stranded", metric="stranded_workflows", operator="==", threshold=0,
                         value=stranded, hard=False, passed=stranded == 0,
                         explanation="Billing reconciliation keeps one qualified owner."),
    ]


def _coverage() -> list[WorkflowCoverage]:
    return [
        WorkflowCoverage(
            workflow_id="wf_billing_recon",
            criticality=Criticality.critical,
            owners_before=["role_billing_ops_lead"],
            owners_after=["role_billing_ops_lead"],
            min_qualified_owners=1,
            backup_count_after=0,
            documented_pct=30,
            stranded=False,
            reasons=["One qualified owner remains and has no backup."],
        )
    ]


def _risk(score: float, level: RiskLevel, parts: tuple[float, float, float, float, float]) -> RiskScore:
    return RiskScore(
        score=score,
        level=level,
        settings_version=1,
        components=RiskComponents(
            financial=parts[0],
            capability_workflow=parts[1],
            customer_revenue=parts[2],
            compliance_control=parts[3],
            execution_uncertainty=parts[4],
        ),
    )


def _triggers(cloud: int, auditlog: int, billing: int, auditlog_neutralised: bool = False) -> list[PressureTrigger]:
    return [
        PressureTrigger(pressure_id="pr_cloud_growth", expected_events=12.0, expected_cost_usd=cloud, neutralised=False),
        PressureTrigger(pressure_id="pr_auditlog_renewal", expected_events=0.0 if auditlog_neutralised else 1.0,
                        expected_cost_usd=auditlog, neutralised=auditlog_neutralised),
        PressureTrigger(pressure_id="pr_billing_recon_hazard", expected_events=0.48, expected_cost_usd=billing,
                        neutralised=False),
    ]


def _result(run_id: str, future: Future, plan_id: str | None, intervention_ids: list[str], value: ValueBreakdown,
            impacts: list[Impact], triggers: list[PressureTrigger], risk: RiskScore, feasible: bool,
            constraints: list[ConstraintResult], mode: str, rejection_reasons: list[str] | None = None) -> SimulationResult:
    return SimulationResult(
        result_id=result_id(run_id, future, plan_id),
        run_id=run_id,
        scenario_id=scenario_id(run_id, future, plan_id),
        future=future,
        plan_id=plan_id,
        mode=mode,  # type: ignore[arg-type]
        seed=42,
        intervention_ids=intervention_ids,
        value=value,
        goal_met=bool(intervention_ids),
        constraint_results=constraints,
        impacts=impacts,
        workflow_coverage=_coverage(),
        pressures_triggered=triggers,
        risk=risk,
        affected_department_ids=sorted({i.affected_department for i in impacts if i.affected_department}),
        feasible=feasible,
        rejection_reasons=rejection_reasons or [],
        assumptions=["Expected-value mode: pressure costs use mean probabilities."],
        computed_at=STUB_TIME,
    )


def act_now_result(run_id: str, decision_id: str, mode: str = "full") -> SimulationResult:
    value = ValueBreakdown(
        gross_savings_usd=2_150_000,
        transition_cost_usd=220_000,
        added_cost_usd=0,
        rebound_cost_usd=90_000,
        expected_business_loss_usd=120_000,
        pressure_cost_usd=410_000,
        avoided_failure_cost_usd=0,
        net_value_usd=1_310_000,
        monthly_net_usd=[-220_000, -95_000, 20_000, 140_000, 255_000, 370_000, 480_000, 640_000, 800_000, 970_000,
                         1_140_000, 1_310_000],
    )
    return _result(run_id, Future.act_now, RECOMMENDED_PLAN, RECOMMENDED_INTERVENTIONS, value,
                   _act_impacts(run_id, decision_id, Future.act_now, RECOMMENDED_PLAN),
                   _triggers(64_000, 36_000, 310_000), _risk(38, RiskLevel.medium, (8, 12, 6, 7, 5)), True,
                   _constraints(0, 0), mode)


def inaction_result(run_id: str, decision_id: str, mode: str = "full") -> SimulationResult:
    value = ValueBreakdown(
        gross_savings_usd=0,
        transition_cost_usd=0,
        added_cost_usd=0,
        rebound_cost_usd=0,
        expected_business_loss_usd=0,
        pressure_cost_usd=292_000,
        avoided_failure_cost_usd=0,
        net_value_usd=-292_000,
        monthly_net_usd=[-24_000, -48_000, -72_000, -96_000, -120_000, -144_000, -168_000, -192_000, -216_000,
                         -240_000, -266_000, -292_000],
    )
    return _result(run_id, Future.inaction, None, [], value, _pressure_impacts(run_id, decision_id, Future.inaction, None),
                   _triggers(64_000, 36_000, 192_000), _risk(52, RiskLevel.high, (14, 16, 8, 6, 8)), True,
                   _constraints(0, 0), mode)


def delay_result(run_id: str, decision_id: str, mode: str = "full") -> SimulationResult:
    value = ValueBreakdown(
        gross_savings_usd=1_610_000,
        transition_cost_usd=220_000,
        added_cost_usd=0,
        rebound_cost_usd=90_000,
        expected_business_loss_usd=120_000,
        pressure_cost_usd=458_000,
        avoided_failure_cost_usd=0,
        net_value_usd=722_000,
        monthly_net_usd=[-24_000, -48_000, -72_000, -290_000, -200_000, -95_000, 20_000, 150_000, 290_000, 430_000,
                         580_000, 722_000],
    )
    return _result(run_id, Future.delay, RECOMMENDED_PLAN, RECOMMENDED_INTERVENTIONS, value,
                   _act_impacts(run_id, decision_id, Future.delay, RECOMMENDED_PLAN),
                   _triggers(64_000, 36_000, 358_000), _risk(44, RiskLevel.medium, (10, 13, 7, 7, 7)), True,
                   _constraints(0, 0), mode)


def naive_result(run_id: str, decision_id: str, mode: str = "full") -> SimulationResult:
    value = ValueBreakdown(
        gross_savings_usd=2_480_000,
        transition_cost_usd=220_000,
        added_cost_usd=0,
        rebound_cost_usd=90_000,
        expected_business_loss_usd=120_000,
        pressure_cost_usd=374_000,
        avoided_failure_cost_usd=0,
        net_value_usd=1_676_000,
        monthly_net_usd=[-220_000, -80_000, 60_000, 200_000, 340_000, 480_000, 640_000, 850_000, 1_060_000,
                         1_270_000, 1_470_000, 1_676_000],
    )
    return _result(run_id, Future.act_now, NAIVE_PLAN, NAIVE_INTERVENTIONS, value,
                   _act_impacts(run_id, decision_id, Future.act_now, NAIVE_PLAN),
                   _triggers(64_000, 0, 310_000, auditlog_neutralised=True), _risk(71, RiskLevel.high, (9, 14, 6, 35, 7)),
                   False, _constraints(1, 0), mode,
                   rejection_reasons=["Removing vendor_auditlog breaks the protected control ctl_soc2_audit_logging."])


def future_results(run_id: str, decision_id: str) -> dict[Future, SimulationResult]:
    return {
        Future.act_now: act_now_result(run_id, decision_id),
        Future.inaction: inaction_result(run_id, decision_id),
        Future.delay: delay_result(run_id, decision_id),
    }


def future_comparison(run_id: str, decision_id: str) -> FutureComparison:
    return FutureComparison(
        comparison_id=f"cmp_{run_id}",
        decision_id=decision_id,
        run_id=run_id,
        reference_result_id=result_id(run_id, Future.inaction, None),
        rows=[
            FutureRow(
                future=Future.act_now, plan_id=RECOMMENDED_PLAN, result_id=result_id(run_id, Future.act_now, RECOMMENDED_PLAN),
                label="Act now", net_value_p50_usd=1_310_000, delta_vs_inaction_p10_usd=1_602_000,
                delta_vs_inaction_p50_usd=1_602_000, delta_vs_inaction_p90_usd=1_602_000, p_better_than_inaction=1.0,
                breakeven_day=60, feasible=True, risk_score=38,
                monthly_delta_usd=[-196_000, -47_000, 92_000, 236_000, 375_000, 514_000, 648_000, 832_000, 1_016_000,
                                   1_210_000, 1_406_000, 1_602_000],
            ),
            FutureRow(
                future=Future.inaction, plan_id=None, result_id=result_id(run_id, Future.inaction, None),
                label="Do nothing", net_value_p50_usd=-292_000, delta_vs_inaction_p10_usd=0,
                delta_vs_inaction_p50_usd=0, delta_vs_inaction_p90_usd=0, p_better_than_inaction=0.0, feasible=True,
                risk_score=52, monthly_delta_usd=[0] * 12,
            ),
            FutureRow(
                future=Future.delay, plan_id=RECOMMENDED_PLAN, result_id=result_id(run_id, Future.delay, RECOMMENDED_PLAN),
                label="Wait 90 days", net_value_p50_usd=722_000, delta_vs_inaction_p10_usd=1_014_000,
                delta_vs_inaction_p50_usd=1_014_000, delta_vs_inaction_p90_usd=1_014_000, p_better_than_inaction=1.0,
                breakeven_day=150, cost_of_delay_usd=588_000, feasible=True, risk_score=44,
                monthly_delta_usd=[0, 0, 0, -194_000, -80_000, 49_000, 188_000, 342_000, 506_000, 670_000, 846_000,
                                   1_014_000],
            ),
        ],
        best_row_index=0,
        headline="Acting now is worth $1.6M more than doing nothing; waiting 90 days costs $0.59M.",
    )


def portfolio_comparison(run_id: str, decision_id: str) -> PortfolioComparison:
    naive = Portfolio(plan_id=NAIVE_PLAN, intervention_ids=NAIVE_INTERVENTIONS, result=naive_result(run_id, decision_id))
    recommended = Portfolio(plan_id=RECOMMENDED_PLAN, intervention_ids=RECOMMENDED_INTERVENTIONS, rank=1,
                            result=act_now_result(run_id, decision_id))
    return PortfolioComparison(evaluated_count=15, naive=naive, recommended=recommended, alternatives=[])


def _node(node_id: str, kind: str, headline: str, **fields: object) -> BlastNode:
    return BlastNode(node_id=node_id, kind=kind, headline=headline, **fields)  # type: ignore[arg-type]


def act_now_blast_radius(run_id: str, decision_id: str) -> BlastRadius:
    tag = f"imp_act_now_{RECOMMENDED_PLAN}"
    return BlastRadius(
        run_id=run_id,
        scenario_id=scenario_id(run_id, Future.act_now, RECOMMENDED_PLAN),
        future=Future.act_now,
        plan_id=RECOMMENDED_PLAN,
        root_node_id=decision_id,
        nodes=[
            _node(decision_id, "decision", "Cut $2M in annual cost"),
            _node("dept_operations", "department", "Operations loses 20 percent platform capacity",
                  department_id="dept_operations", level=ImpactLevel.direct, category=ImpactCategory.operational,
                  polarity=Polarity.harm, severity=3, first_effect_day=0, impact_ids=[f"{tag}_ops_capacity"]),
            _node("wf_billing_recon", "entity", "Billing reconciliation left with one owner",
                  department_id="dept_operations", entity_id="wf_billing_recon", level=ImpactLevel.dependent,
                  category=ImpactCategory.ownership, polarity=Polarity.harm, severity=4, value_usd=120_000,
                  first_effect_day=30, impact_ids=[f"{tag}_billing_recon"]),
            _node("dept_engineering", "department", "Engineering saves $0.62M a year",
                  department_id="dept_engineering", level=ImpactLevel.direct, category=ImpactCategory.financial,
                  polarity=Polarity.benefit, severity=2, value_usd=620_000, first_effect_day=0,
                  impact_ids=[f"{tag}_eng_cost", f"{tag}_migration"]),
            _node("kpi_company", "outcome", "Company net value rises by $1.31M", value_usd=1_310_000),
        ],
        edges=[
            BlastEdge(source=decision_id, target="dept_operations", label="reduce capacity 20%",
                      level=ImpactLevel.direct, critical_constraint=False),
            BlastEdge(source="dept_operations", target="wf_billing_recon", label="owner capacity drops",
                      level=ImpactLevel.dependent, critical_constraint=True),
            BlastEdge(source=decision_id, target="dept_engineering", label="reduce capacity 10%, stop migration",
                      level=ImpactLevel.direct, critical_constraint=False),
            BlastEdge(source="wf_billing_recon", target="kpi_company", label="reconciliation risk",
                      level=ImpactLevel.second_order, critical_constraint=False),
            BlastEdge(source="dept_engineering", target="kpi_company", label="annual savings",
                      level=ImpactLevel.direct, critical_constraint=False),
        ],
        departments=[
            DepartmentImpactSummary(department_id="dept_operations", headline="Billing reconciliation risk rises",
                                    polarity=Polarity.harm, severity=4,
                                    impact_ids=[f"{tag}_ops_capacity", f"{tag}_billing_recon"]),
            DepartmentImpactSummary(department_id="dept_engineering", headline="Capacity and project savings",
                                    polarity=Polarity.benefit, severity=2,
                                    impact_ids=[f"{tag}_eng_cost", f"{tag}_migration"]),
        ],
        outcome=CompanyOutcome(net_value_usd=1_310_000, risk_level=RiskLevel.medium,
                               headline="Net value $1.31M with medium risk."),
    )


def inaction_blast_radius(run_id: str, decision_id: str) -> BlastRadius:
    tag = "imp_inaction_none"
    return BlastRadius(
        run_id=run_id,
        scenario_id=scenario_id(run_id, Future.inaction, None),
        future=Future.inaction,
        plan_id=None,
        root_node_id=decision_id,
        nodes=[
            _node(decision_id, "decision", "Do nothing"),
            _node("pr_cloud_growth", "pressure", "Cloud spend keeps growing", pressure_id="pr_cloud_growth",
                  polarity=Polarity.harm, severity=2, value_usd=64_000, impact_ids=[f"{tag}_cloud_growth"]),
            _node("pr_auditlog_renewal", "pressure", "Audit log renewal price step on day 120",
                  pressure_id="pr_auditlog_renewal", polarity=Polarity.harm, severity=2, value_usd=36_000,
                  first_effect_day=120, impact_ids=[f"{tag}_auditlog_renewal"]),
            _node("pr_billing_recon_hazard", "pressure", "Billing reconciliation can fail",
                  pressure_id="pr_billing_recon_hazard", polarity=Polarity.harm, severity=4, value_usd=192_000,
                  impact_ids=[f"{tag}_billing_hazard"]),
            _node("kpi_company", "outcome", "Company net value falls by $0.29M", value_usd=-292_000),
        ],
        edges=[
            BlastEdge(source=decision_id, target="pr_cloud_growth", label="pressure continues", critical_constraint=False),
            BlastEdge(source=decision_id, target="pr_auditlog_renewal", label="pressure continues",
                      critical_constraint=False),
            BlastEdge(source=decision_id, target="pr_billing_recon_hazard", label="pressure continues",
                      critical_constraint=False),
            BlastEdge(source="pr_billing_recon_hazard", target="kpi_company", label="expected failure cost",
                      level=ImpactLevel.direct, critical_constraint=False),
        ],
        departments=[
            DepartmentImpactSummary(department_id="dept_operations", headline="Billing hazard and renewal step",
                                    polarity=Polarity.harm, severity=4,
                                    impact_ids=[f"{tag}_auditlog_renewal", f"{tag}_billing_hazard"]),
            DepartmentImpactSummary(department_id="dept_engineering", headline="Cloud cost growth",
                                    polarity=Polarity.harm, severity=2, impact_ids=[f"{tag}_cloud_growth"]),
        ],
        outcome=CompanyOutcome(net_value_usd=-292_000, risk_level=RiskLevel.high,
                               headline="Net value -$0.29M with high risk."),
    )


def _metrics(agent_id: str) -> CallMetrics:
    return CallMetrics(model_id="replay", prompt_version="stub", prompt_hash=f"stub_{agent_id}", latency_ms=0,
                       input_tokens=0, output_tokens=0)


def _view(summary: str, finding: str, entity_ids: list[str], severity: int) -> FutureView:
    return FutureView(summary=summary,
                      failure_modes=[Finding(text=finding, entity_ids=entity_ids, severity=severity)])


AGENT_NOTES = {
    "finance": ("Savings clear the $2M gross goal.", "Pressure costs keep rising while nothing changes.",
                ["kpi_company"]),
    "operations": ("Billing reconciliation keeps one owner with no backup.", "Reconciliation hazard persists.",
                   ["wf_billing_recon"]),
    "engineering": ("Capacity cut is absorbed by stopping the migration.", "Cloud spend keeps growing.",
                    ["sys_cloud_platform", "proj_warehouse_migration"]),
    "compliance": ("SOC2 audit logging stays covered because the vendor is kept.", "No control change.",
                   ["ctl_soc2_audit_logging"]),
}


def assessment(run_id: str, agent_id: str) -> AgentAssessment:
    if agent_id == "challenger":
        return AgentAssessment(
            assessment_id=f"asm_{run_id}_{agent_id}",
            run_id=run_id,
            plan_id=RECOMMENDED_PLAN,
            agent_id=agent_id,
            pass_type="challenge",
            status="replayed",
            challenge=ChallengerOutput(
                missed_dependencies=[
                    ProposedDependency(source="vendor_auditlog", target="ctl_soc2_audit_logging",
                                       relation=Relation.SUPPORTS,
                                       rationale="The contract says the vendor stores the SOC2 audit trail.",
                                       evidence_refs=["ev_auditlog_contract"], confidence=0.8)
                ],
                inaction_underestimated=[
                    Finding(text="The billing hazard grows as operations stays over capacity.",
                            entity_ids=["wf_billing_recon"], severity=3, evidence_refs=["ev_billing_recon_matrix"])
                ],
                confidence=0.7,
            ),
            metrics=_metrics(agent_id),
            created_at=STUB_TIME,
        )
    act, inaction, ids = AGENT_NOTES[agent_id]
    return AgentAssessment(
        assessment_id=f"asm_{run_id}_{agent_id}",
        run_id=run_id,
        plan_id=RECOMMENDED_PLAN,
        agent_id=agent_id,
        pass_type="first_pass",
        status="replayed",
        output=AgentOutput(
            affected_entities=ids,
            act_now_view=_view(act, act, ids, 3),
            inaction_view=_view(inaction, inaction, ids, 2),
            assumptions=["Stub assessment."],
            confidence=0.7,
        ),
        metrics=_metrics(agent_id),
        created_at=STUB_TIME,
    )


def decision_package(run_id: str, brief: DecisionBrief, versions: VersionInfo) -> DecisionPackage:
    decision_id = brief.decision_id
    act_now = act_now_result(run_id, decision_id)
    blast = act_now_blast_radius(run_id, decision_id)
    return DecisionPackage(
        package_id=f"pkg_{run_id}",
        run_id=run_id,
        decision_id=decision_id,
        versions=versions,
        brief=brief,
        recommendation=Recommendation(
            plan_id=RECOMMENDED_PLAN,
            future=Future.act_now,
            result_id=act_now.result_id,
            headline="Cut operations, engineering and the migration now; keep the audit log vendor.",
            claims=[
                Claim(text="Acting now is worth $1.6M more than doing nothing.", source="calculation",
                      ref=f"cmp_{run_id}"),
                Claim(text="Removing the audit log vendor would break SOC2 audit logging.", source="evidence",
                      ref="ev_auditlog_contract"),
            ],
        ),
        futures=future_comparison(run_id, decision_id),
        portfolios=portfolio_comparison(run_id, decision_id),
        blast_radius_act_now=blast,
        blast_radius_inaction=inaction_blast_radius(run_id, decision_id),
        department_impacts=blast.departments,
        critical_risks=[i for i in act_now.impacts if i.severity >= 4],
        assumptions=["Expected-value mode: pressure costs use mean probabilities."],
        open_questions=["Can a second owner be trained on billing reconciliation before day 30?"],
        created_at=STUB_TIME,
    )
