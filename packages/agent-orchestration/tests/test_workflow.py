from company_twin import load_company_twin
from contracts_py.agents import AgentOutput
from simulation_engine import ScenarioRequest, simulate

from agent_orchestration import run_scenario
from agent_orchestration.department_agents import DEPARTMENT_AGENTS, _run_one_agent


def test_offline_workflow_routes_and_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("CANARY_OFFLINE_REPLAY", "true")
    state = run_scenario(
        load_company_twin(),
        ScenarioRequest(
            title="Consolidate providers",
            objective="Reduce vendor spend",
            remove_entity_ids=["vendor_cloud", "vendor_enrichiq"],
        ),
    )

    assert state.get("departments") == [
        "dept_ai_data",
        "dept_compliance",
        "dept_engineering",
        "dept_finance",
        "dept_operations",
    ]
    assessments = state.get("department_assessments")
    assert assessments is not None
    assert set(assessments) == {
        "dept_ai_data",
        "dept_compliance",
        "dept_engineering",
        "dept_finance",
        "dept_operations",
    }
    assert all(
        assessment.confidence == 0
        for assessment in assessments.values()
    )


class FakeStructuredClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[AgentOutput],
    ) -> AgentOutput:
        self.calls += 1
        assert messages[0]["role"] == "system"
        return response_model.model_validate(
            {
                "act_now_view": {"summary": "Department-specific risk found."},
                "inaction_view": {"summary": "Existing pressure continues."},
                "confidence": 0.8,
            }
        )


def test_live_workflow_calls_each_routed_agent(monkeypatch) -> None:
    monkeypatch.setenv("CANARY_OFFLINE_REPLAY", "false")
    client = FakeStructuredClient()

    state = run_scenario(
        load_company_twin(),
        ScenarioRequest(
            title="Consolidate providers",
            objective="Reduce vendor spend",
            remove_entity_ids=["vendor_cloud", "vendor_enrichiq"],
        ),
        client=client,
    )

    assessments = state.get("department_assessments")
    assert assessments is not None
    assert client.calls == 5
    assert all(assessment.confidence == 0.8 for assessment in assessments.values())


class CorrectingStructuredClient(FakeStructuredClient):
    def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[AgentOutput],
    ) -> AgentOutput:
        self.calls += 1
        return response_model.model_validate(
            {
                "affected_entities": ["invented_entity"] if self.calls == 1 else [],
                "act_now_view": {"summary": "Corrected assessment."},
                "inaction_view": {"summary": "Pressure continues."},
                "confidence": 0.8,
            }
        )


def test_agent_retries_unknown_entity_ids_once() -> None:
    twin = load_company_twin()
    request = ScenarioRequest(
        title="Consolidate providers",
        objective="Reduce vendor spend",
        remove_entity_ids=["vendor_enrichiq"],
    )
    client = CorrectingStructuredClient()

    assessment = _run_one_agent(
        client,
        DEPARTMENT_AGENTS["dept_finance"],
        twin,
        request,
        simulate(twin, request),
    )

    assert client.calls == 2
    assert assessment.act_now_view.summary == "Corrected assessment."
