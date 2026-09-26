import os
from functools import cache
from pathlib import Path

from agent_orchestration import AgentLLM
from contracts_py.twin import OrganizationSettings, Twin

from canary_api import engine_port
from canary_api.events import EventBus
from canary_api.paths import DATA_DIR, runs_dir

bus = EventBus(runs_dir())
_twins: dict[str, Twin] = {}


def twin() -> Twin:
    impl = engine_port.engine_impl()
    if impl not in _twins:
        snippets = DATA_DIR / "artifacts" / "snippets.json"
        _twins[impl] = engine_port.load_twin(
            DATA_DIR / "synthetic_company.json", snippets if snippets.is_file() else None
        )
    return _twins[impl]


@cache
def _settings(organization_id: str) -> OrganizationSettings:
    return OrganizationSettings(organization_id=organization_id)


def settings() -> OrganizationSettings:
    return _settings(twin().organization.id)


def llm_cache_dir() -> Path:
    return Path(os.environ.get("CANARY_LLM_CACHE_DIR", DATA_DIR / "artifacts" / "llm_cache"))


def cache_is_empty(cache_dir: Path) -> bool:
    return not cache_dir.is_dir() or next(cache_dir.rglob("*.json"), None) is None


def build_llm(run_settings: OrganizationSettings) -> AgentLLM:
    return AgentLLM(run_settings, cache_dir=llm_cache_dir())
