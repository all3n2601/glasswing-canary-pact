"""simulate in quick mode, constraints, risk, and department-profile effects (plan C-04, C-05; schema rules 9, 10, 12)."""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone

import pytest
from contracts_py.decision import ENGINE_METRICS, CandidatePlan, DecisionBrief, Intervention, Scenario
from contracts_py.enums import ActionType, EntityType, Future, InterventionKind
from contracts_py.twin import OrganizationSettings, RiskWeights

from company_twin import load_twin
from company_twin.loader import default_fixture_path
from simulation_engine import (
    apply_interventions,
    blast_radius,
    check_result,
    compare_futures,
    optimize,
    quick_impact,
    simulate,
)
from simulation_engine.knowledge import downgrade_documented

TWIN = load_twin(default_fixture_path())
DATA = default_fixture_path().parent
VENDOR = DecisionBrief.model_validate(json.loads((DATA / "vendor_scenario.json").read_text()))
WORKFORCE = DecisionBrief.model_validate(json.loads((DATA / "workforce_scenario.json").read_text()))
AT = datetime(2026, 9, 26, tzinfo=timezone.utc)


def plan(*names: str, plan_id: str = "plan_beacon_echo") -> CandidatePlan:
    return CandidatePlan(plan_id=plan_id, label=plan_id, intervention_ids=[f"remove_{n}" for n in names],
                         source="user")


def scenario(plan_id: str | None = "plan_beacon_echo", future: Future = Future.act_now) -> Scenario:
    return Scenario(scenario_id=f"scn_run_sim_{future.value}_{plan_id or 'none'}", run_id="run_sim", future=future,
                    plan_id=plan_id, delay_days=0, baseline_twin_version=TWIN.version.twin_version, created_at=AT)


def run(*names: str, plan_id: str = "plan_beacon_echo", settings: OrganizationSettings | None = None):
    return simulate(TWIN, VENDOR, scenario(plan_id), plan(*names, plan_id=plan_id), "quick", settings=settings)


# The calls apps/api engine_port.py and agent-orchestration ports.py make (they must not be imported here).
PORT_SIGNATURES = {
    simulate: ["twin", "brief", "scenario", "plan", "mode", "*settings"],
    optimize: ["twin", "brief", "*settings", "*run_id"],
    compare_futures: ["twin", "brief", "plan", "*alternatives", "*settings", "*run_id"],
    blast_radius: ["result", "twin"],
    quick_impact: ["twin", "interventions", "*brief", "*settings", "*run_id"],
}


def test_signatures_match_the_engine_port():
    for function, expected in PORT_SIGNATURES.items():
        params = inspect.signature(function).parameters.values()
        assert [("*" if p.kind is p.KEYWORD_ONLY else "") + p.name for p in params] == expected, function.__name__


def test_act_now_quick_result_is_tied_to_its_scenario_and_plan():
    result = run("beacon", "echo")
    assert result.future is Future.act_now and result.mode == "quick" and result.seed is None
    assert result.plan_id == "plan_beacon_echo"
    assert result.scenario_id == "scn_run_sim_act_now_plan_beacon_echo"
    assert result.intervention_ids == ["remove_beacon", "remove_echo"]
    assert check_result(result, TWIN) == []


def test_rule_9_every_value_line_is_separate_and_sums_exactly():
    v = run("beacon", "echo").value
    assert v.net_value_usd == (v.gross_savings_usd - v.transition_cost_usd - v.added_cost_usd - v.rebound_cost_usd
                               - v.expected_business_loss_usd - v.pressure_cost_usd + v.avoided_failure_cost_usd)
    assert (v.p10_net_value_usd, v.p50_net_value_usd, v.p90_net_value_usd) == (None, None, None)
    assert len(v.monthly_net_usd) == 12 and v.monthly_net_usd[-1] == v.net_value_usd
    # Cumulative: only pressure cost before the day-30 start, one-off costs when it lands, then savings accrue.
    assert v.pressure_cost_usd > 0
    assert v.monthly_net_usd[0] < 0 and v.monthly_net_usd[1] < 0 < v.monthly_net_usd[-1]
    assert v.monthly_net_usd[1:] == sorted(v.monthly_net_usd[1:])

    broken = run("beacon", "echo")
    broken.value.added_cost_usd += 1
    assert 9 in {i.rule for i in check_result(broken, TWIN)}


def test_displaced_work_is_priced_on_the_impacts_that_cause_it():
    result = run("beacon", "echo")
    priced = [i for i in result.impacts if i.polarity.value == "harm" and i.value_usd and i.source_kind != "pressure"]
    assert {i.affected_entity for i in priced} >= {"wf_account_planning"}
    # The plan makes no investments, so added cost is displaced work alone.
    assert sum(i.value_usd for i in priced) == result.value.added_cost_usd
    pressures = [i for i in result.impacts if i.source_kind == "pressure"]
    assert sum(i.value_usd for i in pressures) == result.value.pressure_cost_usd


def test_every_brief_constraint_gets_a_result_including_critical_coverage():
    result = run("apex", "cinder", plan_id="plan_apex_cinder")
    assert [c.constraint_id for c in result.constraint_results] == [c.id for c in VENDOR.constraints]
    coverage = next(c for c in result.constraint_results if c.metric == "critical_coverage_pct")
    assert coverage.value == pytest.approx(200 / 3, abs=1e-3) and not coverage.passed
    assert coverage.impact_ids == ["imp_ds_corporate_linkage_loss"]
    for c in result.constraint_results:
        assert c.metric in ENGINE_METRICS and c.explanation


def test_rule_12_hard_failures_make_the_plan_infeasible_with_reasons_and_soft_ones_do_not():
    naive = run("apex", "cinder", plan_id="plan_apex_cinder")
    failed = [c.constraint_id for c in naive.constraint_results if c.hard and not c.passed]
    assert failed and not naive.feasible
    assert all(any(r.startswith(f"{c}:") for r in naive.rejection_reasons) for c in failed)

    soft = VENDOR.model_copy(update={"constraints": [c.model_copy(update={"hard": False}) for c in VENDOR.constraints]})
    relaxed = simulate(TWIN, soft, scenario("plan_apex_cinder"), plan("apex", "cinder", plan_id="plan_apex_cinder"),
                       "quick")
    assert relaxed.feasible and relaxed.rejection_reasons == []
    assert any(not c.passed for c in relaxed.constraint_results)

    naive.feasible = True
    assert 12 in {i.rule for i in check_result(naive, TWIN)}


def test_rule_10_risk_has_five_components_weighted_by_settings_and_equals_their_sum():
    result = run("delta", plan_id="plan_delta")
    c = result.risk.components
    assert result.risk.score == pytest.approx(c.financial + c.capability_workflow + c.customer_revenue
                                              + c.compliance_control + c.execution_uncertainty)
    assert c.compliance_control == 20 and c.financial == 25  # broken KYC control; goal missed
    heavier = OrganizationSettings(risk_weights=RiskWeights(financial=10, capability_workflow=10, customer_revenue=10,
                                                            compliance_control=60, execution_uncertainty=10))
    reweighted = run("delta", plan_id="plan_delta", settings=heavier)
    assert reweighted.risk.components.compliance_control == 60
    assert reweighted.risk.components.financial == 10

    result.risk.score += 1
    assert 10 in {i.rule for i in check_result(result, TWIN)}


def test_risk_level_follows_the_settings_thresholds():
    result = run("beacon", "echo")
    lenient = OrganizationSettings(risk_level_thresholds={"medium": 90, "high": 95, "critical": 99})
    assert run("beacon", "echo", settings=lenient).risk.level.value == "low"
    assert result.risk.level.value in {"low", "medium", "high", "critical"}


def test_quick_impact_evaluates_constraints_when_a_brief_is_given():
    by_id = {i.id: i for i in VENDOR.candidate_interventions}
    with_brief = quick_impact(TWIN, [by_id["remove_delta"]], brief=VENDOR)
    assert [c.constraint_id for c in with_brief.constraint_results] == [c.id for c in VENDOR.constraints]
    assert not with_brief.feasible and with_brief.rejection_reasons
    without = quick_impact(TWIN, [by_id["remove_delta"]])
    assert without.constraint_results == [] and without.feasible and not without.goal_met


def test_same_inputs_give_byte_identical_results_and_leave_the_baseline_alone():
    before = TWIN.model_dump_json()
    assert run("beacon", "echo").model_dump_json() == run("beacon", "echo").model_dump_json()
    assert TWIN.model_dump_json() == before


def test_modes_and_plans_must_match_the_scenario():
    with pytest.raises(ValueError):
        simulate(TWIN, VENDOR, scenario(), plan("beacon", "echo"), "monte_carlo")
    with pytest.raises(ValueError):
        simulate(TWIN, VENDOR, scenario(None, Future.inaction), plan("beacon", "echo"), "quick")
    with pytest.raises(ValueError):
        simulate(TWIN, VENDOR, scenario(), None, "quick")
    with pytest.raises(ValueError):
        simulate(TWIN, VENDOR, scenario("plan_other"), plan("beacon", "echo"), "quick")
    with pytest.raises(ValueError):
        simulate(TWIN, VENDOR, scenario("plan_x"), CandidatePlan(plan_id="plan_x", label="x",
                                                                   intervention_ids=["remove_nobody"], source="user"),
                 "quick")


def cut(target: str, pct: float) -> Intervention:
    return Intervention(id="act_cut", kind=InterventionKind.action, type=ActionType.reduce_capacity,
                        target_entity_id=target, amount_pct=pct, rationale="test")


def test_fixed_cost_pct_caps_department_level_savings():
    twin = TWIN.model_copy(deep=True)
    profile = next(p for p in twin.department_profiles if p.department_id == "dept_finance")
    profile.budget.annual_budget_usd = 1_000_000
    profile.budget.fixed_cost_pct = 0.9
    applied = apply_interventions(twin, [cut("dept_finance", 50)])
    assert applied.gross_savings_usd == 100_000
    assert any("fixed_cost_pct" in a for a in applied.assumptions)


def test_utilisation_above_one_makes_a_cut_remove_more_capacity():
    operations = next(p for p in TWIN.department_profiles if p.department_id == "dept_operations")
    assert operations.staffing.utilisation > 1
    applied = apply_interventions(TWIN, [cut("role_sre", 10)])
    assert applied.losses["role_sre"].magnitude == pytest.approx(0.1 * operations.staffing.utilisation)
    finance = next(p for p in TWIN.department_profiles if p.department_id == "dept_finance")
    assert finance.staffing.utilisation == 1
    assert apply_interventions(TWIN, [cut("role_controller", 10)]).losses["role_controller"].magnitude == \
        pytest.approx(0.1)


def test_documentation_coverage_downgrades_stranded_workflows_one_severity_level():
    result = quick_impact(TWIN, WORKFORCE.candidate_interventions, brief=WORKFORCE)
    stranded = {c.workflow_id for c in result.workflow_coverage if c.stranded}
    assert {"wf_financial_close", "wf_billing_recon"} <= stranded
    harms = [i for i in result.impacts if i.affected_entity in stranded and i.polarity.value == "harm"]
    assert harms and all("documentation coverage" in " ".join(i.assumptions) for i in harms)
    undocumented = TWIN.model_copy(deep=True)
    for p in undocumented.department_profiles:
        p.documentation_coverage = 0.0
    kept = downgrade_documented(harms, result.workflow_coverage, undocumented)
    assert [i.severity for i in kept] == [i.severity for i in harms]
    lowered = downgrade_documented(harms, result.workflow_coverage, TWIN)
    assert [i.severity for i in lowered] == [max(1, i.severity - 1) for i in harms]


def test_workflow_coverage_follows_rule_11():
    result = quick_impact(TWIN, WORKFORCE.candidate_interventions, brief=WORKFORCE)
    assert result.workflow_coverage
    for c in result.workflow_coverage:
        assert c.stranded == (len(c.owners_after) < c.min_qualified_owners)
    stranded = next(c for c in result.constraint_results if c.metric == "stranded_workflows")
    assert stranded.value == sum(1 for c in result.workflow_coverage if c.stranded)
    vendor = run("beacon", "echo")
    assert vendor.workflow_coverage == []
    assert all(e.type is not EntityType.person_token for e in TWIN.entities if e.id in
               {o for c in result.workflow_coverage for o in c.owners_before})
