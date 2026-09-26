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
        return self.base.call(agent_id, messages, output_model, prompt_version=prompt_version, context=context,
                              fast=fast)


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


def person_tokens(text: str) -> list[str]:
    from agent_orchestration.prompts import PERSON_TOKEN

    return PERSON_TOKEN.findall(text)


def person_output() -> Any:
    from contracts_py.agents import AgentOutput

    return AgentOutput.model_validate({
        "affected_entities": ["pt_07", "wf_billing_recon"],
        "act_now_view": {
            "summary": "pt_07 is the only person who reconciles billing.",
            "failure_modes": [{"text": "Losing pt_07 strands billing.", "entity_ids": ["pt_07"], "severity": 4},
                              {"text": "Ask pt_07 first.", "entity_ids": ["wf_billing_recon"], "severity": 3}],
            "proposed_impacts": [{"affected_entity": "pt_07", "metric": "load", "direction": "increase",
                                  "polarity": "harm", "category": "ownership", "level": "direct", "severity": 4,
                                  "rationale": "pt_07 absorbs the work.", "evidence_refs": ["ev_knowledge_matrix_billing"],
                                  "confidence": 0.8},
                                 {"affected_entity": "wf_billing_recon", "metric": "owners", "direction": "decrease",
                                  "polarity": "harm", "category": "ownership", "level": "dependent", "severity": 4,
                                  "rationale": "Via pt_07.", "dependency_path": ["pt_07", "wf_billing_recon"],
                                  "evidence_refs": ["ev_knowledge_matrix_billing"], "confidence": 0.8}],
        },
        "inaction_view": {"summary": "pt_07 burns out."},
        "proposed_dependencies": [{"source": "pt_07", "target": "wf_billing_recon", "relation": "OWNS",
                                   "rationale": "pt_07 runs it.", "evidence_refs": ["ev_knowledge_matrix_billing"],
                                   "confidence": 0.9}],
        "questions": [{"text": "Can someone shadow pt_07?", "why_it_matters": "pt_07 is a single point.",
                       "entity_ids": ["wf_billing_recon"]}],
        "assumptions": ["pt_07 stays until day 30."],
        "confidence": 0.7,
    })
