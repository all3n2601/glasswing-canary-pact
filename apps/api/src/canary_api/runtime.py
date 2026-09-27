import logging
import os
from functools import cache
from pathlib import Path

from agent_orchestration import AgentLLM
from agent_orchestration.llm import structured_output_mode
from agent_orchestration.orchestrator import simulation_mode
from contracts_py.twin import OrganizationSettings, Twin

from canary_api import engine_port
from canary_api.events import EventBus
from canary_api.paths import DATA_DIR

log = logging.getLogger(__name__)
bus = EventBus()
# Set once at startup; live runs are refused while it holds an error, mock and replay are unaffected.
structured_output_error: str | None = None
# Set once at startup; every run is refused while it holds an error, since each run calls simulate.
sim_mode_error: str | None = None
_twins: dict[str, Twin] = {}


def twin() -> Twin:
    impl = engine_port.twin_impl()
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


def check_structured_output() -> str | None:
    global structured_output_error
    try:
        structured_output_mode()
        structured_output_error = None
    except ValueError as exc:
        structured_output_error = str(exc)
        log.error("live runs disabled: %s", exc)
    return structured_output_error


def check_sim_mode() -> str | None:
    global sim_mode_error
    try:
        simulation_mode()
        sim_mode_error = None
    except ValueError as exc:
        sim_mode_error = str(exc)
        log.error("decision runs disabled: %s", exc)
    return sim_mode_error
