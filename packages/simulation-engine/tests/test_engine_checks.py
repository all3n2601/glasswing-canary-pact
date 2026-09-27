"""check_result catches every rule 8-14 violation (schema v2.2.0 section 12).

Each test builds a valid output, confirms it has no issues, then breaks one rule by mutating
the model after construction (the contracts validators only run at construction time).
"""

from __future__ import annotations

from datetime import datetime, timezone

from contracts_py.engine import (
    BlastEdge,
    BlastNode,
    BlastRadius,
    CompanyOutcome,
    ConstraintResult,
    FutureComparison,
    FutureRow,
    Impact,
    KnowledgeCoverage,
    MitigationComparison,
    Portfolio,
    PortfolioComparison,
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
    RiskLevel,
)

from company_twin import load_twin
from company_twin.loader import default_fixture_path
from simulation_engine import check_result

TWIN = load_twin(default_fixture_path())
AT = datetime(2026, 9, 26, tzinfo=timezone.utc)


def impact() -> Impact:
    return Impact(
        impact_id="imp_ctl_kyc_screening", decision_id="dec_vendor_reduction", scenario_id="scn_run_t_act_now_none",
        source_entity="ds_identity_verification", source_kind="intervention", source_ref="remove_delta",
        affected_entity="ctl_kyc_screening", affected_department="dept_compliance", level=ImpactLevel.second_order,
        category=ImpactCategory.compliance, polarity=Polarity.harm, direction=Direction.decrease,
        metric="capacity_loss", magnitude=0.7, unit="ratio", severity=4, first_effect_day=30, peak_effect_day=30,
        confidence=0.81, dependency_path=["ds_identity_verification", "wf_kyc_screening", "ctl_kyc_screening"],
        edge_path=["e_identity_consumed_kyc", "e_kyc_supports_control"], origin=Origin.engine,
        status=ClaimStatus.computed,
    )


def result(**update) -> SimulationResult:
    value = ValueBreakdown(gross_savings_usd=900, transition_cost_usd=80, added_cost_usd=0, rebound_cost_usd=0,
                           expected_business_loss_usd=0, pressure_cost_usd=0, avoided_failure_cost_usd=0,
                           net_value_usd=820, monthly_net_usd=[-80, 820])
    risk = RiskScore(score=30, level=RiskLevel.medium, settings_version=1,
                     components=RiskComponents(financial=5, capability_workflow=5, customer_revenue=0,
                                               compliance_control=20, execution_uncertainty=0))
    base = SimulationResult(
        result_id="res_t", run_id="run_t", scenario_id="scn_run_t_act_now_none", future=Future.act_now,
        mode="quick", intervention_ids=["remove_delta"], value=value, goal_met=False, impacts=[impact()],
        risk=risk, affected_department_ids=["dept_compliance"], feasible=True, computed_at=AT,
    )
    return base.model_copy(update=update)


def rules(issues) -> set:
    return {i.rule for i in issues if i.severity == "error"}


def test_valid_result_has_no_issues():
    assert check_result(result(), TWIN) == []


def test_rule_8_impact_path_must_run_source_to_affected():
    bad = result()
    bad.impacts[0].dependency_path = list(reversed(bad.impacts[0].dependency_path))
    assert 8 in rules(check_result(bad, TWIN))


def test_rule_8_edge_path_length_and_endpoints():
    bad = result()
    bad.impacts[0].edge_path = ["e_identity_consumed_kyc"]
    assert 8 in rules(check_result(bad, TWIN))
    swapped = result()
    swapped.impacts[0].edge_path = ["e_kyc_supports_control", "e_identity_consumed_kyc"]
    assert 8 in rules(check_result(swapped, TWIN))


def test_rule_8_peak_before_first_and_engine_status():
    bad = result()
    bad.impacts[0].peak_effect_day = 10
    assert 8 in rules(check_result(bad, TWIN))
    hypothesis = result()
    hypothesis.impacts[0].status = ClaimStatus.hypothesis
    assert 8 in rules(check_result(hypothesis, TWIN))


def test_rule_8_unknown_entities_and_edges():
    bad = result()
    bad.impacts[0].affected_entity = "ctl_not_in_twin"
    assert 8 in rules(check_result(bad, TWIN))
    clone_edge = result()
    clone_edge.impacts[0].edge_path = ["e_identity_consumed_kyc", "e_only_on_the_clone"]
    issues = check_result(clone_edge, TWIN)
    assert [i.severity for i in issues] == ["warning"]


def test_rule_9_net_value_and_monthly_series():
    bad = result()
    bad.value.net_value_usd = 821
    assert 9 in rules(check_result(bad, TWIN))
    series = result()
    series.value.monthly_net_usd = [0, 1]
    assert 9 in rules(check_result(series, TWIN))


def test_rule_10_risk_sum_and_percentiles():
    bad = result()
    bad.risk.score = 31
    assert 10 in rules(check_result(bad, TWIN))
    partial = result()
    partial.value.p10_net_value_usd = 1
    assert 10 in rules(check_result(partial, TWIN))


def test_rule_11_stranded_and_lost_agree_with_owners():
    wf = WorkflowCoverage(workflow_id="wf_billing_recon", criticality=Criticality.critical,
                          owners_before=["role_billing_ops_lead"], owners_after=[], min_qualified_owners=2,
                          backup_count_after=0, documented_pct=0.35, stranded=True)
    kn = KnowledgeCoverage(knowledge_id="kn_warehouse_lineage", holders_before=["role_data_platform_lead"],
                           holder_capacity_fte_before=2, holder_capacity_fte_after=0, documented_pct=0.2, lost=True)
    ok = result(workflow_coverage=[wf], knowledge_coverage=[kn])
    assert check_result(ok, TWIN) == []
    ok.workflow_coverage[0].stranded = False
    assert 11 in rules(check_result(ok, TWIN))
    lost = result(knowledge_coverage=[kn.model_copy(update={"lost": False})])
    assert 11 in rules(check_result(lost, TWIN))


def test_rule_12_hard_failure_needs_infeasible_with_reasons_and_full_needs_seed():
    failed = ConstraintResult(constraint_id="c_compliance", metric="compliance_controls_broken", operator="==",
                              threshold=0, value=1, hard=True, passed=False, explanation="ctl_kyc_screening broken")
    assert 12 in rules(check_result(result(constraint_results=[failed]), TWIN))
    assert 12 in rules(check_result(result(feasible=False), TWIN))
    assert check_result(result(constraint_results=[failed], feasible=False,
                               rejection_reasons=["c_compliance failed"]), TWIN) == []
    assert 12 in rules(check_result(result(mode="full"), TWIN))


def test_rule_7_inaction_cannot_apply_interventions():
    assert 7 in rules(check_result(result(future=Future.inaction), TWIN))


def row(future: Future, delta: int, p: float, plan_id: str | None = None) -> FutureRow:
    return FutureRow(future=future, plan_id=plan_id, result_id=f"res_{future.value}", label=future.value,
                     net_value_p50_usd=delta, delta_vs_inaction_p10_usd=delta, delta_vs_inaction_p50_usd=delta,
                     delta_vs_inaction_p90_usd=delta, p_better_than_inaction=p, feasible=True, risk_score=10)


def comparison() -> FutureComparison:
    return FutureComparison(comparison_id="cmp_t", decision_id="dec_vendor_reduction", run_id="run_t",
                            reference_result_id="res_act_now", rows=[row(Future.act_now, 100, 1.0, "plan_a"),
                                                                     row(Future.inaction, 0, 0.0)],
                            best_row_index=0, headline="Act now")


def test_rule_13_future_comparison():
    assert check_result(comparison(), TWIN) == []
    duplicate = comparison()
    duplicate.rows.append(row(Future.act_now, 50, 1.0, "plan_b"))
    assert 13 in rules(check_result(duplicate, TWIN))
    no_inaction = comparison()
    no_inaction.rows = no_inaction.rows[:1]
    no_inaction.best_row_index = 0
    assert 13 in rules(check_result(no_inaction, TWIN))
    inaction_delta = comparison()
    inaction_delta.rows[1].delta_vs_inaction_p50_usd = 0
    inaction_delta.rows[1].p_better_than_inaction = 0.5
    assert 13 in rules(check_result(inaction_delta, TWIN))
    out_of_range = comparison()
    out_of_range.best_row_index = 5
    assert 13 in rules(check_result(out_of_range, TWIN))


def test_portfolio_and_mitigation_recurse_into_results():
    portfolio = PortfolioComparison(evaluated_count=128,
                                    naive=Portfolio(plan_id="plan_naive", intervention_ids=["remove_delta"],
                                                    result=result(plan_id="plan_naive")))
    assert check_result(portfolio, TWIN) == []
    portfolio.naive.result.value.net_value_usd = 1
    assert 9 in rules(check_result(portfolio, TWIN))
    infeasible = result(plan_id="plan_x", feasible=False, rejection_reasons=["goal missed"])
    recommended = PortfolioComparison(evaluated_count=128, naive=Portfolio(plan_id="plan_x",
                                      intervention_ids=["remove_delta"], result=infeasible),
                                      recommended=Portfolio(plan_id="plan_x", intervention_ids=["remove_delta"],
                                                            rank=1, result=infeasible))
    assert 12 in rules(check_result(recommended, TWIN))

    mitigation = MitigationComparison(plan_id_before="plan_a", plan_id_after="plan_b", actions=[],
                                      before=result(), after=result(), feasible_before=True, feasible_after=True)
    assert check_result(mitigation, TWIN) == []
    mitigation.feasible_after = False
    assert 12 in rules(check_result(mitigation, TWIN))


def test_rule_14_blast_edges_reference_existing_nodes():
    blast = BlastRadius(
        run_id="run_t", scenario_id="scn_run_t_act_now_none", future=Future.act_now, root_node_id="decision",
        nodes=[BlastNode(node_id="decision", kind="decision", headline="Remove Delta"),
               BlastNode(node_id="dept_compliance", kind="department", department_id="dept_compliance",
                         headline="KYC control breaks")],
        edges=[BlastEdge(source="decision", target="dept_compliance", label="breaks", critical_constraint=True)],
        outcome=CompanyOutcome(net_value_usd=820, risk_level=RiskLevel.medium, headline="Risky"),
    )
    assert check_result(blast, TWIN) == []
    blast.edges.append(BlastEdge(source="decision", target="missing_node", label="x", critical_constraint=False))
    assert 14 in rules(check_result(blast, TWIN))
    blast.edges.pop()
    blast.root_node_id = "not_a_node"
    assert 14 in rules(check_result(blast, TWIN))


def test_unknown_type_is_reported():
    assert check_result("not an output", TWIN)[0].rule == "type"  # type: ignore[arg-type]
