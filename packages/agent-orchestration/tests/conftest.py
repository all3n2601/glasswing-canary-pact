import pytest
from canary_api.stubs.twin import sample_brief, stub_twin
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
def settings() -> OrganizationSettings:
    return OrganizationSettings(llm_mode="mock")


@pytest.fixture
def hr_twin(twin: Twin) -> Twin:
    person = Entity(id="pt_07", type=EntityType.person_token, name="Person 07", department_id="dept_operations",
                    sensitivity=Sensitivity.hr, role_id="role_billing_ops_lead")
    return twin.model_copy(update={"entities": [*twin.entities, person]})
