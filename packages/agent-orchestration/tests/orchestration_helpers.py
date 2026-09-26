from datetime import datetime, timezone
from typing import Any, Callable

from canary_api.stubs import engine as stub_engine
from contracts_py.agents import AgentContext, CallMetrics
from contracts_py.enums import Future
from contracts_py.events import Event, EventType
from contracts_py.twin import OrganizationSettings
from pydantic import BaseModel

from agent_orchestration.llm import AgentLLM, LLMResult

NOW = datetime(2026, 9, 26, 18, 0, tzinfo=timezone.utc)


class SpyEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def __getattr__(self, name: str) -> Callable[..., Any]:
        function = getattr(stub_engine, name)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.calls.append((name, args))
            return function(*args, **kwargs)

        return wrapper

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]


class ScriptedLLM:
    """Mock LLM with per-agent overrides returning a fixed output or status."""

    model_label = "scripted"

    def __init__(self, settings: OrganizationSettings, overrides: dict[str, Callable[[AgentContext], LLMResult]]):
        self.base = AgentLLM(settings)
        self.overrides = overrides

    def call(self, agent_id: str, messages: list[dict[str, str]], output_model: type[BaseModel], *,
             prompt_version: str, context: AgentContext, fast: bool = False) -> LLMResult:
        if agent_id in self.overrides:
            return self.overrides[agent_id](context)
        return self.base.call(agent_id, messages, output_model, prompt_version=prompt_version, context=context)


def metrics(agent_id: str = "x") -> CallMetrics:
    return CallMetrics(model_id="test", prompt_version="p1", prompt_hash=f"h_{agent_id}", latency_ms=0,
                       input_tokens=0, output_tokens=0)


class Recorder:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def __call__(self, type: EventType, payload: BaseModel, *, actor: str, scenario_id: str | None = None,
                 future: Future | None = None) -> None:
        # Building the Event checks the payload is exactly the model the spec assigns to this type.
        self.events.append(Event(event_id=f"evt_{len(self.events) + 1}", run_id="run_test",
                                 sequence=len(self.events) + 1, type=type, actor=actor, scenario_id=scenario_id,
                                 future=future, timestamp=NOW, payload=payload))

    def phases(self) -> list[str]:
        return [e.payload.to_status.value for e in self.events if e.type is EventType.phase_changed]

    def of(self, kind: EventType) -> list[Event]:
        return [e for e in self.events if e.type is kind]


def make_context(brief: Any, twin: Any, settings: OrganizationSettings, agent_id: str = "operations",
                 run_id: str = "run_test") -> AgentContext:
    from canary_api.stubs import results

    from agent_orchestration.context import build_context
    from agent_orchestration.roster import ROSTER

    return build_context(ROSTER[agent_id], run_id=run_id, brief=brief, plan=results.plans()[1], twin=twin,
                         engine=stub_engine, act_now=results.act_now_result(run_id, brief.decision_id),
                         inaction=results.inaction_result(run_id, brief.decision_id), settings=settings)
