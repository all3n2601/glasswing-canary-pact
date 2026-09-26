from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agent_orchestration import run_scenario
from company_twin import build_graph, load_company_twin
from simulation_engine import ScenarioRequest, ScenarioResult


app = FastAPI(
    title="Canary Pact API",
    version="0.1.0",
    description="Organizational decision simulation and blast-radius API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

twin = load_company_twin()
scenario_results: dict[str, ScenarioResult] = {}
scenario_summaries: dict[str, str] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "canary-pact-api"}


@app.get("/company")
def company():
    return twin


@app.get("/company/graph")
def company_graph() -> dict[str, object]:
    graph = build_graph(twin)
    return {
        "nodes": [
            {"id": node_id, **attributes}
            for node_id, attributes in graph.nodes(data=True)
        ],
        "edges": [
            {"source": source, "target": target, **attributes}
            for source, target, attributes in graph.edges(data=True)
        ],
    }


@app.post("/scenarios/simulate", response_model=ScenarioResult)
def simulate_scenario(request: ScenarioRequest) -> ScenarioResult:
    state = run_scenario(twin, request)
    result = state.get("result")
    if result is None:
        raise RuntimeError("Scenario workflow completed without a result")
    scenario_results[result.scenario_id] = result
    scenario_summaries[result.scenario_id] = state.get(
        "executive_summary", result.recommendation
    )
    return result


@app.get("/scenarios/{scenario_id}/results", response_model=ScenarioResult)
def get_scenario_result(scenario_id: str) -> ScenarioResult:
    result = scenario_results.get(scenario_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return result


@app.get("/scenarios/{scenario_id}/report")
def get_scenario_report(scenario_id: str) -> dict[str, str]:
    summary = scenario_summaries.get(scenario_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"scenario_id": scenario_id, "executive_summary": summary}
