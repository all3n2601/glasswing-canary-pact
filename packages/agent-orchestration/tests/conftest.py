import pytest
from canary_api.stubs.twin import sample_brief, stub_twin, workforce_brief
from contracts_py.decision import DecisionBrief
from contracts_py.enums import EntityType, Sensitivity
from contracts_py.twin import Entity, OrganizationSettings, Twin


@pytest.fixture
def twin() -> Twin:
    return stub_twin()


@pytest.fixture
def brief() -> DecisionBrief:
    return sample_brief()


@pytest.fixture
def people_brief() -> DecisionBrief:
    # The restructure brief is the one that routes people_knowledge.
    return workforce_brief()


@pytest.fixture
def settings() -> OrganizationSettings:
    return OrganizationSettings(llm_mode="live")


@pytest.fixture
def hr_twin(twin: Twin) -> Twin:
    person = Entity(id="pt_07", type=EntityType.person_token, name="Person 07", department_id="dept_operations",
                    sensitivity=Sensitivity.hr, role_id="role_billing_ops_lead")
    return twin.model_copy(update={"entities": [*twin.entities, person]})


# Developer shells may export demo settings; tests must not inherit them (a fake live call would then receive
# arguments it does not accept, or a run would pick up the wrong mode). Tests that need one set it themselves.
ISOLATED_ENV = ("CANARY_LLM_THINKING", "CANARY_CHALLENGER_THINKING", "CANARY_STRUCTURED_OUTPUT", "CANARY_SIM_MODE",
                "CANARY_AGENT_CONTEXT_HOPS")


@pytest.fixture(autouse=True)
def isolated_demo_env(monkeypatch):
    for name in ISOLATED_ENV:
        monkeypatch.delenv(name, raising=False)
