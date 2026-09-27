import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Set before canary_api is imported so the bus writes to a throwaway directory.
os.environ["CANARY_RUNS_DIR"] = tempfile.mkdtemp(prefix="canary_runs_")
os.environ["CANARY_REPLAY_STEP_SECONDS"] = "0.01"
os.environ["CANARY_LLM_CACHE_DIR"] = tempfile.mkdtemp(prefix="canary_llm_cache_")
os.environ["CANARY_ALLOW_LIVE"] = "true"
# Both switches default to real; tests that need the stub set them explicitly.
os.environ.pop("ENGINE_IMPL", None)
os.environ.pop("TWIN_IMPL", None)
# The default suite always runs on the file backend, whatever the shell exports.
os.environ.pop("DATABASE_URL", None)

from canary_api.app import app  # noqa: E402
from canary_api import runtime, storage  # noqa: E402
from agent_orchestration import AgentLLM  # noqa: E402
from agent_orchestration.llm import LiveReply  # noqa: E402
from contracts_py.agents import ChallengerOutput  # noqa: E402
from company_twin import load_company_twin  # noqa: E402
from real_data import sample_brief  # noqa: E402

# Production loads the active twin from Postgres. Tests seed the isolated SQLite
# backend explicitly so API behavior is exercised without a production database.
storage.current().save_twin(load_company_twin(), active=True)


def test_live_call(model_id, messages, output_model, *, timeout, temperature, structured_output="auto"):
    if output_model is ChallengerOutput:
        return LiveReply({"confidence": 0.5})
    return LiveReply({
        "act_now_view": {"summary": "Test live assessment."},
        "inaction_view": {"summary": "Test live baseline."},
        "confidence": 0.5,
    })


runtime.build_llm = lambda settings: AgentLLM(
    settings.model_copy(update={"model_id_strong": "test-live", "model_id_fast": "test-live"}),
    cache_dir=runtime.llm_cache_dir(),
    live_call=test_live_call,
)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def brief_json() -> dict:
    return sample_brief().model_dump(mode="json")
