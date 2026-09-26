"""Pre-contracts /scenarios routes, kept unchanged while the frontend still calls them."""

from functools import cache

from fastapi import APIRouter, HTTPException

from agent_orchestration import run_scenario
from company_twin import CompanyTwin, load_company_twin
from simulation_engine import ScenarioRequest, ScenarioResult

router = APIRouter()

scenario_results: dict[str, ScenarioResult] = {}
scenario_summaries: dict[str, str] = {}


@cache
def legacy_twin() -> CompanyTwin:
    return load_company_twin()


@router.post("/scenarios/simulate", response_model=ScenarioResult)
def simulate_scenario(request: ScenarioRequest) -> ScenarioResult:
    state = run_scenario(legacy_twin(), request)
    result = state.get("result")
    if result is None:
        raise RuntimeError("Scenario workflow completed without a result")
    scenario_results[result.scenario_id] = result
    scenario_summaries[result.scenario_id] = state.get(
        "executive_summary", result.recommendation
    )
    return result


@router.get("/scenarios/{scenario_id}/results", response_model=ScenarioResult)
def get_scenario_result(scenario_id: str) -> ScenarioResult:
    result = scenario_results.get(scenario_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return result


@router.get("/scenarios/{scenario_id}/report")
def get_scenario_report(scenario_id: str) -> dict[str, str]:
    summary = scenario_summaries.get(scenario_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"scenario_id": scenario_id, "executive_summary": summary}
