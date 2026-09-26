import pytest
from canary_api.stubs.twin import sample_brief, stub_twin
from contracts_py.decision import DecisionBrief
from contracts_py.twin import OrganizationSettings, Twin


@pytest.fixture
def twin() -> Twin:
    return stub_twin()


@pytest.fixture
def brief() -> DecisionBrief:
    return sample_brief()


@pytest.fixture
def settings() -> OrganizationSettings:
    return OrganizationSettings(llm_mode="mock")
