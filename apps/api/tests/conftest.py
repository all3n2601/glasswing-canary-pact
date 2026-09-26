import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Set before canary_api is imported so the bus writes to a throwaway directory.
os.environ["CANARY_RUNS_DIR"] = tempfile.mkdtemp(prefix="canary_runs_")
os.environ["CANARY_REPLAY_STEP_SECONDS"] = "0.01"
os.environ["CANARY_LLM_CACHE_DIR"] = tempfile.mkdtemp(prefix="canary_llm_cache_")
os.environ.pop("ENGINE_IMPL", None)

from canary_api.app import app  # noqa: E402
from canary_api.stubs.twin import sample_brief  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def brief_json() -> dict:
    return sample_brief().model_dump(mode="json")
