from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Protocol

from company_twin import CompanyTwin
from contracts_py.agents import AgentOutput
from simulation_engine import ScenarioRequest, ScenarioResult

from .client import SciforiumClient, SciforiumError


@dataclass(frozen=True)
class DepartmentAgent:
    agent_id: str
    department_id: str
    display_name: str
    responsibility: str


DEPARTMENT_AGENTS = {
    agent.department_id: agent
    for agent in (
        DepartmentAgent(
            "finance",
            "dept_finance",
            "Finance",
            "cost, payback, penalties, and displaced work",
        ),
        DepartmentAgent(
            "engineering",
            "dept_engineering",
            "Engineering",
            "integrations, reliability, migration, and technical debt",
        ),
        DepartmentAgent(
            "marketing",
            "dept_marketing",
            "Marketing",
            "audience coverage, campaigns, attribution, and acquisition",
        ),
        DepartmentAgent(
            "sales",
            "dept_sales",
            "Sales",
            "account coverage, pipeline, conversion, and renewals",
        ),
        DepartmentAgent(
            "operations",
            "dept_operations",
            "Operations",
            "process continuity, handoffs, workload, and service levels",
        ),
        DepartmentAgent(
            "ai_data",
            "dept_ai_data",
            "AI/Data",
            "data lineage, quality, freshness, features, and model effects",
        ),
        DepartmentAgent(
            "people_knowledge",
            "dept_people",
            "People/Knowledge",
            "skills, documentation, backups, and knowledge concentration",
        ),
        DepartmentAgent(
            "compliance",
            "dept_compliance",
            "Risk/Compliance",
            "policies, controls, legal limits, and hard constraints",
        ),
        DepartmentAgent(
            "customer_market",
            "dept_customer",
            "Customer/Market",
            "customer experience, churn, trust, and market reaction",
        ),
    )
}


class StructuredAgentClient(Protocol):
    def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[AgentOutput],
    ) -> AgentOutput: ...


def route_department_agents(
    twin: CompanyTwin, result: ScenarioResult
) -> list[DepartmentAgent]:
    available_departments = {
        entity.id for entity in twin.entities if entity.type.value == "department"
    }
    affected_departments = {impact.department for impact in result.impacts}
    # Finance evaluates the objective and Compliance evaluates hard constraints.
    affected_departments.update({"dept_finance", "dept_compliance"})
    return [
        DEPARTMENT_AGENTS[department_id]
        for department_id in sorted(affected_departments)
        if department_id in available_departments
        and department_id in DEPARTMENT_AGENTS
    ]


def run_department_agents(
    twin: CompanyTwin,
    request: ScenarioRequest,
    result: ScenarioResult,
    agents: list[DepartmentAgent],
    client: StructuredAgentClient | None = None,
) -> dict[str, AgentOutput]:
    if not agents:
        return {}

    live_mode = os.getenv("CANARY_OFFLINE_REPLAY", "true").lower() not in {
        "1",
        "true",
        "yes",
    }
    owned_client: SciforiumClient | None = None
    if live_mode and client is None:
        owned_client = SciforiumClient()
        client = owned_client

    try:
        if not live_mode or client is None:
            return {
                agent.department_id: _fallback_assessment(agent, result)
                for agent in agents
            }

        assessments: dict[str, AgentOutput] = {}
        with ThreadPoolExecutor(max_workers=min(4, len(agents))) as executor:
            futures = {
                executor.submit(
                    _run_one_agent, client, agent, twin, request, result
                ): agent
                for agent in agents
            }
            for future in as_completed(futures):
                agent = futures[future]
                try:
                    assessments[agent.department_id] = future.result()
                except (SciforiumError, ValueError):
                    assessments[agent.department_id] = _fallback_assessment(agent, result)
        return assessments
    finally:
        if owned_client is not None:
            owned_client.close()


def _run_one_agent(
    client: StructuredAgentClient,
    agent: DepartmentAgent,
    twin: CompanyTwin,
    request: ScenarioRequest,
    result: ScenarioResult,
) -> AgentOutput:
    context = _department_context(agent, twin, request, result)
    allowed_ids_value = context["allowed_entity_ids"]
    if not isinstance(allowed_ids_value, list):
        raise ValueError("Department context is missing allowed entity IDs")
    allowed_ids = {
        entity_id for entity_id in allowed_ids_value if isinstance(entity_id, str)
    }
    messages = [
        {
            "role": "system",
            "content": (
                f"You are Canary Pact's {agent.display_name} department assessor. "
                f"Focus on {agent.responsibility}. Identify risks, edge cases, missing "
                "dependencies, assumptions, and questions. Treat deterministic_result "
                "as authoritative: do not recalculate money, change feasibility, override "
                "constraints, invent entity IDs, or recommend autonomous action. Keep "
                "claims evidence-linked when evidence is available."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(context, separators=(",", ":")),
        },
    ]
    for attempt in range(2):
        output = client.generate_structured(messages, AgentOutput)
        try:
            _validate_entity_references(output, allowed_ids)
            return output
        except ValueError as error:
            if attempt == 1:
                raise
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Your prior JSON was rejected: {error}. Return corrected JSON "
                        "using only allowed_entity_ids from the supplied context."
                    ),
                }
            )
    raise SciforiumError("Department agent validation retry was exhausted")


def _department_context(
    agent: DepartmentAgent,
    twin: CompanyTwin,
    request: ScenarioRequest,
    result: ScenarioResult,
) -> dict[str, object]:
    relevant_impacts = [
        impact
        for impact in result.impacts
        if impact.department == agent.department_id
        or agent.agent_id in {"finance", "compliance"}
    ]
    relevant_ids = set(request.remove_entity_ids)
    for impact in relevant_impacts:
        relevant_ids.update(impact.path)

    entities = [
        entity.model_dump(mode="json")
        for entity in twin.entities
        if entity.id in relevant_ids or entity.id == agent.department_id
    ]
    dependencies = [
        dependency.model_dump(mode="json")
        for dependency in twin.edges
        if dependency.source in relevant_ids or dependency.target in relevant_ids
    ]
    return {
        "department": {
            "agent_id": agent.agent_id,
            "department_id": agent.department_id,
            "responsibility": agent.responsibility,
        },
        "scenario_request": request.model_dump(mode="json"),
        "deterministic_result": result.model_dump(mode="json"),
        "relevant_entities": entities,
        "relevant_dependencies": dependencies,
        "allowed_entity_ids": sorted(relevant_ids | {agent.department_id}),
        "required_perspectives": ["act_now", "inaction"],
    }


def _validate_entity_references(output: AgentOutput, known_ids: set[str]) -> None:
    referenced = set(output.affected_entities)
    for view in (output.act_now_view, output.inaction_view):
        for finding in (*view.failure_modes, *view.edge_cases):
            referenced.update(finding.entity_ids)
        for impact in view.proposed_impacts:
            referenced.add(impact.affected_entity)
            referenced.update(impact.dependency_path)
    for dependency in output.proposed_dependencies:
        referenced.update({dependency.source, dependency.target})
    for question in output.questions:
        referenced.update(question.entity_ids)

    unknown = sorted(referenced - known_ids)
    if unknown:
        raise ValueError(f"Agent returned unknown entity IDs: {', '.join(unknown)}")


def _fallback_assessment(
    agent: DepartmentAgent, result: ScenarioResult
) -> AgentOutput:
    relevant = [
        impact for impact in result.impacts if impact.department == agent.department_id
    ]
    affected_entities = [impact.entity_id for impact in relevant]
    if relevant:
        act_summary = (
            f"Deterministic simulation reports {len(relevant)} impact(s) for "
            f"{agent.display_name}; live qualitative assessment is unavailable."
        )
    else:
        act_summary = (
            f"{agent.display_name} was routed for objective or constraint review; "
            "live qualitative assessment is unavailable."
        )
    return AgentOutput.model_validate(
        {
            "affected_entities": affected_entities,
            "act_now_view": {"summary": act_summary},
            "inaction_view": {
                "summary": "No live inaction assessment was available; deterministic results are unchanged."
            },
            "assumptions": ["Fallback output contains no model-generated claims."],
            "confidence": 0.0,
        }
    )
