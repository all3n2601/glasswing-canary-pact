from canary_api.paths import DATA_DIR
from contracts_py.decision import DecisionBrief


def sample_brief() -> DecisionBrief:
    return DecisionBrief.model_validate_json((DATA_DIR / "vendor_scenario.json").read_text())


def workforce_brief() -> DecisionBrief:
    return DecisionBrief.model_validate_json((DATA_DIR / "workforce_scenario.json").read_text())
