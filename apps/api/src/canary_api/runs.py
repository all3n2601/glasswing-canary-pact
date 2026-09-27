import asyncio
import functools
import inspect
import logging
import os
import re
import uuid
from typing import Any, Callable, Coroutine

from agent_orchestration import run_decision
from pydantic import BaseModel

from contracts_py.decision import DecisionBrief
from contracts_py.enums import Future, RunStatus
from contracts_py.events import EventType, PhaseChanged, RunFailed
from contracts_py.package import find_person_tokens
from contracts_py.twin import OrganizationSettings, Twin

from canary_api import engine_port, runtime
log = logging.getLogger(__name__)

_tasks: set[asyncio.Task[None]] = set()


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:12]}"


def apply_settings_defaults(brief: DecisionBrief, settings: OrganizationSettings) -> DecisionBrief:
    provided = brief.model_fields_set
    data = brief.model_dump()
    defaults = {
        "horizon_days": settings.default_horizon_days,
        "futures": settings.default_futures,
        "delay_days": settings.default_delay_days,
        "seed": settings.default_seed,
        "mc_samples": settings.mc_samples,
    }
    data.update({key: value for key, value in defaults.items() if key not in provided})
    protected = [*data["protected_entity_ids"]]
    protected += [i for i in settings.always_protected_entity_ids if i not in protected]
    data["protected_entity_ids"] = protected
    own_ids = {c["id"] for c in data["constraints"]}
    data["constraints"] += [c.model_dump() for c in settings.default_constraints if c.id not in own_ids]
    return DecisionBrief.model_validate(data)


def _spawn(coro: Coroutine[Any, Any, None]) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def live_allowed() -> bool:
    return os.environ.get("CANARY_ALLOW_LIVE", "").strip().lower() == "true"
ENGINE_EVENTS = {
    EventType.impact_computed,
    EventType.simulation_completed,
    EventType.futures_compared,
    EventType.portfolio_ranked,
    EventType.blast_radius_ready,
    EventType.mitigation_applied,
    EventType.package_ready,
}
PERSON_TOKEN_TEXT = re.compile(r"(?<![a-z0-9])pt_[a-z0-9_]+")


class PersonTokenLeak(ValueError):
    pass


def _redact(text: str) -> str:
    return PERSON_TOKEN_TEXT.sub("[person]", text)


def fail_run(run_id: str, reason: str) -> None:
    run = runtime.bus.runs[run_id]
    if any(e.type is EventType.run_failed for e in run.events):
        return
    if run.state.status is not RunStatus.failed:
        runtime.bus.publish(run_id, EventType.phase_changed,
                            PhaseChanged(from_status=run.state.status, to_status=RunStatus.failed), actor="api")
    runtime.bus.publish(run_id, EventType.run_failed, RunFailed(reason=_redact(reason)), actor="api")


def prepare_payload(kind: EventType, payload: BaseModel, twin: Twin, extra_assumptions: list[str]) -> dict[str, Any]:
    leveled: Any = engine_port.to_role_level(payload, twin) if kind in ENGINE_EVENTS else payload
    data = leveled.model_dump(mode="json") if isinstance(leveled, BaseModel) else leveled
    if kind is EventType.package_ready and extra_assumptions:
        data = {**data, "assumptions": [*data.get("assumptions", []),
                                        *[a for a in extra_assumptions if a not in data.get("assumptions", [])]]}
    if find_person_tokens(data):
        raise PersonTokenLeak(f"{kind.value} payload still contains person tokens after to_role_level")
    return data


def _publish(run_id: str, kind: EventType, payload: BaseModel, actor: str, scenario_id: str | None,
             future: Future | None, twin: Twin, extra_assumptions: list[str]) -> None:
    run = runtime.bus.runs[run_id]
    if run.state.status is RunStatus.failed:
        # After a failure only the first run_failed (carrying the reason) is still published.
        if kind is not EventType.run_failed or any(e.type is EventType.run_failed for e in run.events):
            log.warning("run %s already failed; skipping %s", run_id, kind)
            return
    try:
        if kind is EventType.run_failed and isinstance(payload, RunFailed):
            payload = RunFailed(reason=_redact(payload.reason))
        data = prepare_payload(kind, payload, twin, extra_assumptions)
        runtime.bus.publish(run_id, kind, data, actor=actor, scenario_id=scenario_id, future=future)
    except Exception as exc:
        log.exception("could not publish %s for %s", kind, run_id)
        fail_run(run_id, f"could not publish {kind.value}: {exc}")


def cancelled_for(run_id: str) -> Callable[[], bool]:
    def cancelled() -> bool:
        run = runtime.bus.runs.get(run_id)
        return run is not None and (run.state.status is RunStatus.failed
                                    or any(e.type is EventType.run_failed for e in run.events))

    return cancelled


def _accepts_should_stop() -> bool:
    # The orchestrator gains should_stop in a parallel change; pass it only once run_decision accepts it.
    return "should_stop" in inspect.signature(run_decision).parameters


class ThreadEmitter:
    """Called from orchestrator worker threads; every publish is queued onto the event loop thread."""

    def __init__(self, run_id: str, loop: asyncio.AbstractEventLoop, twin: Twin,
                 extra_assumptions: list[str] | None = None) -> None:
        self.run_id, self.loop, self.twin = run_id, loop, twin
        self.extra_assumptions = extra_assumptions or []
        self.cancelled = cancelled_for(run_id)

    def __call__(self, type: EventType, payload: BaseModel, *, actor: str, scenario_id: str | None = None,
                 future: Future | None = None) -> None:
        if self.cancelled():
            log.info("run %s has failed; dropping %s from its worker", self.run_id, type)
            return
        # call_soon_threadsafe runs callbacks in submission order, so sequence follows emit order.
        self.loop.call_soon_threadsafe(functools.partial(
            _publish, self.run_id, type, payload, actor, scenario_id, future, self.twin, self.extra_assumptions
        ))


async def orchestrate(run_id: str, brief: DecisionBrief, twin: Twin, settings: OrganizationSettings) -> None:
    loop = asyncio.get_running_loop()
    try:
        emit = ThreadEmitter(run_id, loop, twin)
        # AgentLLM.model_label is a property, which pyright treats as not matching the LLMClient attribute.
        llm: Any = runtime.build_llm(settings)
        extra: dict[str, Any] = {"should_stop": emit.cancelled} if _accepts_should_stop() else {}
        await asyncio.to_thread(run_decision, brief, engine=engine_port, settings=settings, llm=llm, emit=emit,
                                run_id=run_id, twin=twin, **extra)
    except Exception as exc:
        await asyncio.sleep(0)
        fail_run(run_id, str(exc))


def start_run(brief: DecisionBrief) -> str:
    twin = runtime.twin()
    run_id = new_run_id()
    runtime.bus.create_run(run_id, brief.decision_id, twin.version.twin_version)
    _spawn(orchestrate(run_id, brief, twin, runtime.settings()))
    return run_id
