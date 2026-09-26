from functools import partial
from typing import NotRequired, TypedDict, cast

from company_twin import CompanyTwin
from contracts_py.agents import AgentOutput
from langgraph.graph import END, START, StateGraph
from simulation_engine import ScenarioRequest, ScenarioResult, simulate

from .department_agents import (
    StructuredAgentClient,
    route_department_agents,
    run_department_agents,
)


class ScenarioState(TypedDict):
    twin: CompanyTwin
    request: ScenarioRequest
    result: NotRequired[ScenarioResult]
    departments: NotRequired[list[str]]
    department_assessments: NotRequired[dict[str, AgentOutput]]
    executive_summary: NotRequired[str]


def run_simulation(state: ScenarioState) -> dict[str, object]:
    return {"result": simulate(state["twin"], state["request"])}


def route_departments(state: ScenarioState) -> dict[str, object]:
    result = state.get("result")
    if result is None:
        raise RuntimeError("Department routing requires a simulation result")
    departments = [
        agent.department_id
        for agent in route_department_agents(state["twin"], result)
    ]
    return {"departments": departments}


def assess_departments(
    state: ScenarioState,
    client: StructuredAgentClient | None = None,
) -> dict[str, object]:
    result = state.get("result")
    if result is None:
        raise RuntimeError("Department assessment requires a simulation result")
    routed = route_department_agents(state["twin"], result)
    assessments = run_department_agents(
        state["twin"], state["request"], result, routed, client
    )
    return {"department_assessments": assessments}


def explain(state: ScenarioState) -> dict[str, object]:
    result = state.get("result")
    if result is None:
        raise RuntimeError("Explanation requires a simulation result")
    department_text = ", ".join(state.get("departments", [])) or "no departments"
    assessment_count = len(state.get("department_assessments", {}))
    summary = (
        f"Scenario is {result.status}. Net savings are "
        f"${result.net_savings:,.0f}; affected areas: {department_text}. "
        f"Collected {assessment_count} department assessment(s). "
        f"{result.recommendation}"
    )
    return {"executive_summary": summary}


def build_scenario_graph(client: StructuredAgentClient | None = None):
    graph = StateGraph(ScenarioState)
    graph.add_node("simulate", run_simulation)
    graph.add_node("route_departments", route_departments)
    graph.add_node(
        "assess_departments",
        partial(assess_departments, client=client),
    )
    graph.add_node("explain", explain)
    graph.add_edge(START, "simulate")
    graph.add_edge("simulate", "route_departments")
    graph.add_edge("route_departments", "assess_departments")
    graph.add_edge("assess_departments", "explain")
    graph.add_edge("explain", END)
    return graph.compile()


def run_scenario(
    twin: CompanyTwin,
    request: ScenarioRequest,
    client: StructuredAgentClient | None = None,
) -> ScenarioState:
    return cast(
        ScenarioState,
        build_scenario_graph(client).invoke({"twin": twin, "request": request}),
    )
