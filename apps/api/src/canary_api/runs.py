import asyncio
import os
import uuid
from pathlib import Path
from typing import Any, Coroutine

from contracts_py.api import ReplayInfo
from contracts_py.decision import DecisionBrief
from contracts_py.enums import RunStatus
from contracts_py.events import Event, EventLog, EventType, PhaseChanged, RunFailed
from contracts_py.twin import OrganizationSettings

from canary_api import runtime
from canary_api.paths import REPLAYS_DIR
from canary_api.stubs.run import stub_run_events

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


def start_run(brief: DecisionBrief) -> str:
    twin = runtime.twin()
    run_id = new_run_id()
    runtime.bus.create_run(run_id, brief.decision_id, twin.version.twin_version)
    _spawn(play(run_id, stub_run_events(brief, run_id, twin.version), step_seconds()))
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
