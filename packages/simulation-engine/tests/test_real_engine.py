from datetime import datetime, timezone
from pathlib import Path

from company_twin import load_company_twin
from contracts_py.decision import CandidatePlan, DecisionBrief, Goal, Scenario
from contracts_py.enums import Future
from simulation_engine import optimize, simulate


def vendor_brief() -> DecisionBrief:
    path = Path(__file__).resolve().parents[3] / "data" / "vendor_scenario.json"
    full = DecisionBrief.model_validate_json(path.read_text())
    candidates = [
        item for item in full.candidate_interventions
        if item.id in {"remove_beacon", "remove_delta"}
    ]
    return full.model_copy(update={
        "candidate_interventions": candidates,
        "goal": Goal(metric="annual_savings_usd", target=1_200_000_000),
        "active_pressure_ids": [],
    })


def test_simulation_reads_cost_and_dependencies_from_the_twin() -> None:
    twin = load_company_twin()
    brief = vendor_brief()
    plan = CandidatePlan(plan_id="plan_beacon", label="Remove BeaconIQ",
                         intervention_ids=["remove_beacon"], source="user")
    scenario = Scenario(scenario_id="scn_real_act_now", run_id="run_real", future=Future.act_now,
                        plan_id=plan.plan_id, delay_days=0, baseline_twin_version=twin.version.twin_version,
                        created_at=datetime.now(timezone.utc))
    result = simulate(twin, brief, scenario, plan, "full")

    vendor = next(entity for entity in twin.entities if entity.id == "vendor_beacon")
    assert result.value.gross_savings_usd == vendor.annual_cost_usd
    assert "vendor_beacon" in {impact.affected_entity for impact in result.impacts}


def test_optimizer_enumerates_real_candidates_and_rejects_compliance_breakage() -> None:
    comparison = optimize(load_company_twin(), vendor_brief(), run_id="run_real")

    assert comparison.evaluated_count == 4
    assert comparison.recommended is not None
    assert comparison.recommended.intervention_ids == ["remove_beacon"]
    compliance_portfolio = next(
        portfolio for portfolio in [comparison.naive, *comparison.alternatives]
        if "remove_delta" in portfolio.intervention_ids
    )
    assert not compliance_portfolio.result.feasible
    assert any(row.metric == "compliance_controls_broken" and not row.passed
               for row in compliance_portfolio.result.constraint_results)
