import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from contracts_py.enums import Future, RunStatus
from contracts_py.events import Event, EventType, RunState
from contracts_py.package import DecisionPackage, HumanDecision


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Run:
    state: RunState
    events: list[Event] = field(default_factory=list)
    subscribers: set[asyncio.Queue[Event]] = field(default_factory=set)
    package: DecisionPackage | None = None
    served_package_hash: str | None = None
    decision: HumanDecision | None = None


class EventBus:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.runs: dict[str, Run] = {}

    def _dir(self, run_id: str) -> Path:
        return self.root / run_id

    def create_run(self, run_id: str, decision_id: str, baseline_twin_version: str) -> RunState:
        now = utc_now()
        state = RunState(
            run_id=run_id,
            decision_id=decision_id,
            baseline_twin_version=baseline_twin_version,
            status=RunStatus.created,
            created_at=now,
            updated_at=now,
        )
        self.runs[run_id] = Run(state=state)
        self._dir(run_id).mkdir(parents=True, exist_ok=True)
        self._write_state(run_id)
        return state

    def get(self, run_id: str) -> Run | None:
        run = self.runs.get(run_id)
        if run is None:
            run = self._load(run_id)
        return run

    def publish(self, run_id: str, kind: EventType, payload: Any, *, actor: str,
                scenario_id: str | None = None, future: Future | None = None) -> Event:
        # No await between assigning the sequence and fanning out, so ordering holds on one event loop.
        run = self.runs[run_id]
        sequence = run.state.last_sequence + 1
        event = Event(
            event_id=f"evt_{run_id}_{sequence}",
            run_id=run_id,
            sequence=sequence,
            type=kind,
            actor=actor,
            scenario_id=scenario_id,
            future=future,
            timestamp=utc_now(),
            payload=payload,
        )
        run.events.append(event)
        self._apply(run, event)
        with (self._dir(run_id) / "events.jsonl").open("a") as handle:
            handle.write(event.model_dump_json() + "\n")
        self._write_state(run_id)
        for queue in run.subscribers:
            queue.put_nowait(event)
        return event

    async def stream(self, run_id: str) -> AsyncIterator[Event]:
        run = self.runs[run_id]
        queue: asyncio.Queue[Event] = asyncio.Queue()
        run.subscribers.add(queue)
        try:
            last_sent = 0
            for event in list(run.events):
                last_sent = event.sequence
                yield event
            while True:
                event = await queue.get()
                if event.sequence <= last_sent:
                    continue
                last_sent = event.sequence
                yield event
        finally:
            run.subscribers.discard(queue)

    def _apply(self, run: Run, event: Event) -> None:
        state = run.state
        payload: Any = event.payload
        updates: dict[str, Any] = {"last_sequence": event.sequence, "updated_at": event.timestamp}
        if event.type is EventType.phase_changed:
            updates["status"] = payload.to_status
        elif event.type is EventType.scenario_created:
            updates["scenario_ids"] = [*state.scenario_ids, payload.scenario_id]
        elif event.type is EventType.candidate_generated:
            updates["candidate_plan_ids"] = [*state.candidate_plan_ids, payload.plan_id]
        elif event.type in (EventType.agent_completed, EventType.challenge_raised):
            updates["assessment_ids"] = [*state.assessment_ids, payload.assessment_id]
        elif event.type is EventType.simulation_completed:
            if payload.result_id not in state.result_ids:
                updates["result_ids"] = [*state.result_ids, payload.result_id]
        elif event.type is EventType.futures_compared:
            updates["comparison_id"] = payload.comparison_id
        elif event.type is EventType.package_ready:
            updates["package_id"] = payload.package_id
            run.package = payload
        elif event.type is EventType.human_decision_recorded:
            run.decision = payload
        run.state = state.model_copy(update=updates)

    def _write_state(self, run_id: str) -> None:
        (self._dir(run_id) / "state.json").write_text(self.runs[run_id].state.model_dump_json(indent=2))

    def _load(self, run_id: str) -> Run | None:
        directory = self._dir(run_id)
        state_path = directory / "state.json"
        if not state_path.is_file():
            return None
        run = Run(state=RunState.model_validate_json(state_path.read_text()))
        events_path = directory / "events.jsonl"
        if events_path.is_file():
            for line in events_path.read_text().splitlines():
                if line.strip():
                    event = Event.model_validate(json.loads(line))
                    run.events.append(event)
                    if event.type is EventType.package_ready:
                        run.package = event.payload  # type: ignore[assignment]
                    elif event.type is EventType.human_decision_recorded:
                        run.decision = event.payload  # type: ignore[assignment]
        self.runs[run_id] = run
        return run
