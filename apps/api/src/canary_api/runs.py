import asyncio
import functools
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Coroutine, Literal

from agent_orchestration import run_decision
from pydantic import BaseModel

from contracts_py.api import ReplayInfo
from contracts_py.decision import DecisionBrief
from contracts_py.enums import Future, RunStatus
from contracts_py.events import Event, EventLog, EventType, PhaseChanged, RunFailed, SettingsUpdated
from contracts_py.twin import OrganizationSettings, Twin

from canary_api import engine_port, runtime
from canary_api.paths import REPLAYS_DIR

LlmMode = Literal["mock", "replay", "live"]
log = logging.getLogger(__name__)

_tasks: set[asyncio.Task[None]] = set()


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:12]}"


def step_seconds(speed: int = 1) -> float:
    return float(os.environ.get("CANARY_REPLAY_STEP_SECONDS", "0.5")) / speed


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


def rewrite_run_ids(value: Any, run_id: str) -> Any:
    if isinstance(value, dict):
        return {k: run_id if k == "run_id" and isinstance(v, str) else rewrite_run_ids(v, run_id) for k, v in value.items()}
    if isinstance(value, list):
        return [rewrite_run_ids(item, run_id) for item in value]
    return value


async def play(run_id: str, events: list[Event], delay: float) -> None:
    try:
        for event in events:
            payload = rewrite_run_ids(event.payload.model_dump(mode="json"), run_id)
            runtime.bus.publish(run_id, event.type, payload, actor=event.actor, scenario_id=event.scenario_id,
                                future=event.future)
            await asyncio.sleep(delay)
    except Exception as exc:
        state = runtime.bus.runs[run_id].state
        runtime.bus.publish(run_id, EventType.phase_changed,
                            PhaseChanged(from_status=state.status, to_status=RunStatus.failed), actor="api")
        runtime.bus.publish(run_id, EventType.run_failed, RunFailed(reason=str(exc)), actor="api")


def resolve_llm_settings(settings: OrganizationSettings, llm_mode: LlmMode | None) -> tuple[OrganizationSettings, bool]:
    mode = llm_mode or settings.llm_mode
    # An empty replay cache would mark every agent unavailable, so the run falls back to mock answers.
    fell_back = mode == "replay" and runtime.cache_is_empty(runtime.llm_cache_dir())
    return settings.model_copy(update={"llm_mode": "mock" if fell_back else mode}), fell_back


def _publish(run_id: str, kind: EventType, payload: BaseModel, actor: str, scenario_id: str | None,
             future: Future | None) -> None:
    try:
        runtime.bus.publish(run_id, kind, payload, actor=actor, scenario_id=scenario_id, future=future)
    except Exception:
        log.exception("dropped %s event for %s", kind, run_id)


class ThreadEmitter:
    """Called from orchestrator worker threads; every publish is queued onto the event loop thread."""

    def __init__(self, run_id: str, loop: asyncio.AbstractEventLoop, after_created: list[tuple[EventType, BaseModel]]):
        self.run_id, self.loop, self.after_created = run_id, loop, after_created

    def _schedule(self, kind: EventType, payload: BaseModel, actor: str, scenario_id: str | None,
                  future: Future | None) -> None:
        # call_soon_threadsafe runs callbacks in submission order, so sequence follows emit order.
        self.loop.call_soon_threadsafe(functools.partial(_publish, self.run_id, kind, payload, actor, scenario_id, future))

    def __call__(self, type: EventType, payload: BaseModel, *, actor: str, scenario_id: str | None = None,
                 future: Future | None = None) -> None:
        self._schedule(type, payload, actor, scenario_id, future)
        if type is EventType.run_created:
            for kind, note in self.after_created:
                self._schedule(kind, note, "api", None, None)
            self.after_created = []


async def orchestrate(run_id: str, brief: DecisionBrief, twin: Twin, settings: OrganizationSettings,
                      llm_mode: LlmMode | None) -> None:
    loop = asyncio.get_running_loop()
    try:
        run_settings, fell_back = resolve_llm_settings(settings, llm_mode)
        notes: list[tuple[EventType, BaseModel]] = []
        if fell_back:
            notes.append((EventType.settings_updated,
                          SettingsUpdated(settings_version=run_settings.settings_version, changed_fields=["llm_mode"])))
        emit = ThreadEmitter(run_id, loop, notes)
        # AgentLLM.model_label is a property, which pyright treats as not matching the LLMClient attribute.
        llm: Any = runtime.build_llm(run_settings)
        await asyncio.to_thread(run_decision, brief, engine=engine_port, settings=run_settings, llm=llm, emit=emit,
                                run_id=run_id, twin=twin)
    except Exception as exc:
        await asyncio.sleep(0)
        state = runtime.bus.runs[run_id].state
        if state.status is not RunStatus.failed:
            runtime.bus.publish(run_id, EventType.phase_changed,
                                PhaseChanged(from_status=state.status, to_status=RunStatus.failed), actor="api")
            runtime.bus.publish(run_id, EventType.run_failed, RunFailed(reason=str(exc)), actor="api")


def start_run(brief: DecisionBrief, llm_mode: LlmMode | None = None) -> str:
    twin = runtime.twin()
    run_id = new_run_id()
    runtime.bus.create_run(run_id, brief.decision_id, twin.version.twin_version)
    _spawn(orchestrate(run_id, brief, twin, runtime.settings(), llm_mode))
    return run_id


def replay_path(name: str) -> Path | None:
    candidates = {p.stem: p for p in REPLAYS_DIR.glob("*.json")}
    return candidates.get(name)


def load_replay(name: str) -> EventLog | None:
    path = replay_path(name)
    if path is None:
        return None
    return EventLog.model_validate_json(path.read_text())


def list_replays() -> list[ReplayInfo]:
    infos = []
    for path in sorted(REPLAYS_DIR.glob("*.json")):
        log = EventLog.model_validate_json(path.read_text())
        first = log.root[0] if log.root else None
        decision_id = first.payload.decision_id if first and isinstance(first.payload, DecisionBrief) else None
        infos.append(ReplayInfo(name=path.stem, decision_id=decision_id, event_count=len(log.root)))
    return infos


def play_replay(log: EventLog, speed: int) -> str:
    events = log.root
    first = events[0].payload if events else None
    decision_id = first.decision_id if isinstance(first, DecisionBrief) else "dec_replay"
    run_id = new_run_id()
    runtime.bus.create_run(run_id, decision_id, runtime.twin().version.twin_version)
    _spawn(play(run_id, events, step_seconds(speed)))
    return run_id
