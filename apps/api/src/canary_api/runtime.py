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
from canary_api import storage
from canary_api.engine_port import EngineNotReady
from canary_api.paths import DATA_DIR

log = logging.getLogger(__name__)
bus = EventBus()
# Set once at startup; live runs are refused while it holds an error.
structured_output_error: str | None = None
# Set once at startup; every run is refused while it holds an error, since each run calls simulate.
sim_mode_error: str | None = None
_twin: Twin | None = None


def twin() -> Twin:
    global _twin
    if _twin is None:
        backend = storage.current()
        _twin = backend.load_active_twin()
        if _twin is None:
            seed_path = Path(os.environ.get("CANARY_TWIN_SEED_PATH") or DATA_DIR / "synthetic_company.json")
            try:
                seed = engine_port.load_twin(seed_path)
            except Exception as exc:
                raise EngineNotReady(
                    f"No active company twin exists and seed loading failed: {type(exc).__name__}"
                ) from exc
            errors = [issue for issue in engine_port.validate_twin(seed) if issue.severity == "error"]
            if errors:
                raise EngineNotReady(f"Company twin seed failed validation: {errors[0].message}")
            backend.save_twin(seed, active=True)
            _twin = backend.load_active_twin()
        if _twin is None:
            raise EngineNotReady("No active company twin exists in the configured database")
    return _twin


@cache
def _settings(organization_id: str) -> OrganizationSettings:
    return OrganizationSettings(organization_id=organization_id)


def settings() -> OrganizationSettings:
    return _settings(twin().organization.id)


def build_llm(run_settings: OrganizationSettings) -> AgentLLM:
    return AgentLLM(run_settings)


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
