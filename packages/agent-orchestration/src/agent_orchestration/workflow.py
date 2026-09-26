from typing import NotRequired, TypedDict

from company_twin import CompanyTwin
from langgraph.graph import END, START, StateGraph
from simulation_engine import ScenarioRequest, ScenarioResult, simulate


class ScenarioState(TypedDict):
    twin: CompanyTwin
    request: ScenarioRequest
    result: NotRequired[ScenarioResult]
    departments: NotRequired[list[str]]
    executive_summary: NotRequired[str]


def run_simulation(state: ScenarioState) -> dict[str, object]:
    return {"result": simulate(state["twin"], state["request"])}


def route_departments(state: ScenarioState) -> dict[str, object]:
    result = state["result"]
    departments = sorted({impact.department for impact in result.impacts})
    return {"departments": departments}


def explain(state: ScenarioState) -> dict[str, object]:
    result = state["result"]
    department_text = ", ".join(state.get("departments", [])) or "no departments"
    summary = (
        f"Scenario is {result.status}. Net savings are "
        f"${result.net_savings:,.0f}; affected areas: {department_text}. "
        f"{result.recommendation}"
    )
    return {"executive_summary": summary}


def build_scenario_graph():
    graph = StateGraph(ScenarioState)
    graph.add_node("simulate", run_simulation)
    graph.add_node("route_departments", route_departments)
    graph.add_node("explain", explain)
    graph.add_edge(START, "simulate")
    graph.add_edge("simulate", "route_departments")
    graph.add_edge("route_departments", "explain")
    graph.add_edge("explain", END)
    return graph.compile()


def run_scenario(twin: CompanyTwin, request: ScenarioRequest) -> ScenarioState:
    return build_scenario_graph().invoke({"twin": twin, "request": request})

