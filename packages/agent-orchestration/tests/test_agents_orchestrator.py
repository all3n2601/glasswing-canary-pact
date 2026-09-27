import threading

from contracts_py.agents import AgentContext, ChallengerOutput, ProposedDependency
from contracts_py.enums import Future
from contracts_py.events import EventType
from contracts_py.package import DecisionPackage
from contracts_py.twin import OrganizationSettings

import pytest
from canary_api.stubs import engine as stub_engine

from agent_orchestration import AgentLLM, RunCancelled, run_decision
from agent_orchestration.llm import LLMResult, LiveReply
from agent_orchestration.roster import MODEL_TIER, model_tier
from orchestration_helpers import NOW, Recorder, ScriptedLLM, SpyEngine, metrics, person_output, person_tokens

BASE_PHASES = ["validating", "building_futures", "optimizing", "running_agents", "propagating", "challenging",
               "propagating"]
TAIL_PHASES = ["comparing_futures", "mitigating", "generating_package", "awaiting_approval"]


def run(brief, twin, settings, llm, engine=None):
    recorder = Recorder()
    engine = engine or SpyEngine()
    package = run_decision(brief, engine=engine, settings=settings, llm=llm, emit=recorder, run_id="run_test",
                           twin=twin, clock=lambda: NOW)
    return package, recorder, engine


def test_full_mock_run_returns_package_and_exact_phase_order(brief, twin, settings) -> None:
    package, recorder, engine = run(brief, twin, settings, ScriptedLLM(settings, {}))
    assert isinstance(package, DecisionPackage)
    assert DecisionPackage.model_validate(package.model_dump(mode="json")) == package
    assert recorder.phases() == BASE_PHASES + TAIL_PHASES
    assert recorder.events[0].type is EventType.run_created
    assert recorder.events[-1].payload.to_status.value == "awaiting_approval"
    assert recorder.of(EventType.package_ready)[0].payload == package
    assert package.recommendation and package.recommendation.headline == package.futures.headline
    assert package.missing_perspectives == []
    assert "clone_with_edges" not in engine.names()
    assert engine.names().count("optimize") == 1
    assert "to_role_level" in engine.names()
    started = [e.payload.agent_id for e in recorder.of(EventType.agent_started)]
    assert started == ["finance", "engineering", "ai_data", "operations", "sales", "compliance", "challenger"]


def challenger_with_new_edge(context: AgentContext) -> LLMResult:
    # The planted dependency: known endpoints, not yet an edge, evidenced by the workflow map.
    dependency = ProposedDependency(source="wf_vendor_reconciliation", target="ds_account_intel",
                                    relation="consumes", rationale="The workflow map says account intel feeds it.",
                                    evidence_refs=["ev_echo_account_intel_feed"], confidence=1.7)
    return LLMResult(ChallengerOutput(missed_dependencies=[dependency], confidence=0.6), "ok", metrics("challenger"))


def test_validated_edge_resimulates_and_reoptimizes(brief, twin, settings) -> None:
    llm = ScriptedLLM(settings, {"challenger": challenger_with_new_edge})
    package, recorder, engine = run(brief, twin, settings, llm)
    assert recorder.phases() == BASE_PHASES + ["optimizing"] + TAIL_PHASES
    names = engine.names()
    clone = names.index("clone_with_edges")
    assert "simulate" in names[clone + 1:] and "optimize" in names[clone + 1:]
    assert names.count("optimize") == 2
    generated = [e.payload.plan_id for e in recorder.of(EventType.candidate_generated)]
    assert len(generated) == len(set(generated)) == 2
    assert len(recorder.of(EventType.portfolio_ranked)) == 2
    edge = recorder.of(EventType.dependency_validated)[0].payload.edge
    assert (edge.source, edge.target, edge.confidence) == ("wf_vendor_reconciliation", "ds_account_intel", 1.0)
    assert any(c.source == "agent_validated" for c in package.recommendation.claims)


def test_unavailable_agent_is_a_missing_perspective(brief, twin, settings) -> None:
    unavailable = lambda context: LLMResult(None, "unavailable", metrics("operations"), errors=["no cache"])
    package, recorder, engine = run(brief, twin, settings, ScriptedLLM(settings, {"operations": unavailable}))
    assert package.missing_perspectives == ["operations"]
    failed = recorder.of(EventType.agent_failed)
    assert [e.payload.agent_id for e in failed] == ["operations"] and not failed[0].payload.fallback_used
    widen = [args for name, args in engine.calls if name == "widen_uncertainty"]
    assert widen and widen[0][1] == ["dept_operations"]
    assert engine.names().index("widen_uncertainty") < engine.names().index("compare_futures")


def test_futures_cover_inaction_and_delay(brief, twin, settings) -> None:
    _, recorder, _ = run(brief, twin, settings, ScriptedLLM(settings, {}))
    futures = {e.future for e in recorder.of(EventType.simulation_completed)}
    assert futures == {Future.act_now, Future.inaction, Future.delay}


def test_person_tokens_never_leave_the_agent_layer(people_brief, hr_twin, settings) -> None:
    seen: list[set[str]] = []

    def people(context: AgentContext) -> LLMResult:
        seen.append({e.id for e in context.view.entities})
        return LLMResult(person_output(), "ok", metrics("people_knowledge"))

    # Default settings: people_knowledge runs as a CORE agent and its HR view really contains the token.
    package, recorder, engine = run(people_brief, hr_twin, settings,
                                    ScriptedLLM(settings, {"people_knowledge": people}))
    assert seen and "pt_07" in seen[0]
    completed = [e for e in recorder.of(EventType.agent_completed) if e.payload.agent_id == "people_knowledge"]
    assert len(completed) == 1
    assert completed[0].payload.validation.rejected_entity_ids == ["[role]"]
    assert person_tokens(completed[0].model_dump_json()) == []
    assert person_tokens(package.model_dump_json()) == []
    assert "Can someone shadow [role]?" in package.open_questions
    assert "clone_with_edges" not in engine.names()


class CountingLLM(AgentLLM):
    def __init__(self, settings):
        super().__init__(settings)
        self.calls: list[str] = []

    def call(self, agent_id, *args, **kwargs):
        self.calls.append(agent_id)
        return super().call(agent_id, *args, **kwargs)


def cancelled_run(brief, twin, settings, stop_when):
    recorder, llm = Recorder(), CountingLLM(settings)
    checks = {"count": 0, "stopped_at": None}
    lock = threading.Lock()

    def should_stop() -> bool:
        with lock:
            checks["count"] += 1
            if checks["stopped_at"] is None and stop_when(recorder, checks["count"]):
                checks["stopped_at"] = len(recorder.events)
            return checks["stopped_at"] is not None

    with pytest.raises(RunCancelled):
        run_decision(brief, engine=SpyEngine(), settings=settings, llm=llm, emit=recorder, run_id="run_test",
                     twin=twin, clock=lambda: NOW, should_stop=should_stop)
    return recorder, llm, checks["stopped_at"]


def test_should_stop_between_phases_emits_nothing_more(brief, twin, settings) -> None:
    recorder, llm, stopped_at = cancelled_run(brief, twin, settings, lambda rec, _: "optimizing" in rec.phases())
    assert len(recorder.events) == stopped_at
    assert recorder.phases() == ["validating", "building_futures", "optimizing"]
    assert llm.calls == []
    kinds = {e.type for e in recorder.events}
    assert not kinds & {EventType.package_ready, EventType.run_failed, EventType.agent_started}


def test_should_stop_before_agent_calls(brief, twin, settings) -> None:
    recorder, llm, stopped_at = cancelled_run(brief, twin, settings,
                                              lambda rec, _: "running_agents" in rec.phases())
    assert len(recorder.events) == stopped_at
    assert llm.calls == [] and recorder.of(EventType.agent_completed) == []
    assert recorder.phases()[-1] == "running_agents"


# Checks before the agents: run_created plus the validating, building_futures, optimizing and running_agents phases.
CHECKS_BEFORE_AGENTS = 5


def test_should_stop_mid_agents_stops_remaining_calls(brief, twin, settings) -> None:
    # Exactly one agent passes its check; every later check, in any thread, sees the stop.
    recorder, llm, _ = cancelled_run(brief, twin, settings, lambda _, count: count > CHECKS_BEFORE_AGENTS + 1)
    assert len(llm.calls) == 1
    assert recorder.phases()[-1] == "running_agents"
    assert not {e.type for e in recorder.events} & {EventType.package_ready, EventType.run_failed,
                                                    EventType.challenge_raised}


def test_should_stop_immediately_emits_nothing(brief, twin, settings) -> None:
    recorder, llm, _ = cancelled_run(brief, twin, settings, lambda *_: True)
    assert recorder.events == [] and llm.calls == []


class InfeasibleOnReoptimize(SpyEngine):
    def optimize(self, twin, brief, **kwargs):
        self.calls.append(("optimize", (twin, brief)))
        portfolio = stub_engine.optimize(twin, brief, **kwargs)
        if self.names().count("optimize") < 2:
            return portfolio
        field = "recommended" if portfolio.recommended else "naive"
        chosen = getattr(portfolio, field)
        result = chosen.result.model_copy(update={"feasible": False,
                                                  "rejection_reasons": ["The new dependency breaks a hard constraint."]})
        return portfolio.model_copy(update={field: chosen.model_copy(update={"result": result})})


def test_reoptimization_rejects_plan_that_became_infeasible(brief, twin, settings) -> None:
    llm = ScriptedLLM(settings, {"challenger": challenger_with_new_edge})
    engine = InfeasibleOnReoptimize()
    first = stub_engine.optimize(twin, brief)
    chosen_id = (first.recommended or first.naive).plan_id
    assert (first.recommended or first.naive).result.feasible
    _, recorder, _ = run(brief, twin, settings, llm, engine=engine)
    kinds = [e.type for e in recorder.events]
    second_ranking = [i for i, k in enumerate(kinds) if k is EventType.portfolio_ranked][1]
    late_rejections = [e.payload for e in recorder.events[:second_ranking]
                       if e.type is EventType.candidate_rejected and e.payload.plan_id == chosen_id]
    assert [r.reasons for r in late_rejections] == [["The new dependency breaks a hard constraint."]]
    generated = [e.payload.plan_id for e in recorder.of(EventType.candidate_generated)]
    assert len(generated) == len(set(generated))
    assert len({e.payload.plan_id for e in recorder.of(EventType.candidate_rejected)}) == \
        len(recorder.of(EventType.candidate_rejected))



MODEL_ENV = ["CANARY_MODEL_STRONG", "CANARY_MODEL_FAST", "MODEL_STRONG", "MODEL_FAST", "SCIFORIUM_MODEL"]


def live_run(brief, twin, tmp_path, monkeypatch, **env):
    for name in MODEL_ENV:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    used: list[tuple[str, str]] = []

    def live(model_id, messages, output_model, *, timeout, temperature, structured_output="auto"):
        used.append((output_model.__name__, model_id))
        if output_model is ChallengerOutput:
            return LiveReply({"confidence": 0.5})
        return LiveReply({"act_now_view": {"summary": "ok"}, "inaction_view": {"summary": "ok"}, "confidence": 0.5})

    settings = OrganizationSettings(llm_mode="live")
    llm = AgentLLM(settings, live_call=live)
    _, recorder, _ = run(brief, twin, settings, llm)
    metrics_by_agent = {e.payload.agent_id: e.payload for e in recorder.of(EventType.agent_completed)}
    return metrics_by_agent, used


def test_model_tier_table() -> None:
    assert MODEL_TIER == {"challenger": "strong"}
    assert model_tier("challenger") == "strong" and model_tier("finance") == "fast"


def test_departments_use_fast_model_and_challenger_strong(brief, twin, tmp_path, monkeypatch) -> None:
    assessments, used = live_run(brief, twin, tmp_path, monkeypatch,
                                 CANARY_MODEL_FAST="deepseek-fast-test", CANARY_MODEL_STRONG="glm-strong-test")
    assert assessments["challenger"].metrics.model_id == "glm-strong-test"
    departments = {a: v for a, v in assessments.items() if a != "challenger"}
    assert departments and {v.metrics.model_id for v in departments.values()} == {"deepseek-fast-test"}
    assert ("ChallengerOutput", "glm-strong-test") in used
    assert {m for name, m in used if name == "AgentOutput"} == {"deepseek-fast-test"}
    assert all(not v.validation.errors for v in assessments.values())


def test_missing_strong_model_runs_challenger_on_fast(brief, twin, tmp_path, monkeypatch) -> None:
    assessments, _ = live_run(brief, twin, tmp_path, monkeypatch, CANARY_MODEL_FAST="deepseek-fast-test")
    challenger = assessments["challenger"]
    assert challenger.status == "ok" and challenger.metrics.model_id == "deepseek-fast-test"
    assert any("strong model not configured" in e for e in challenger.validation.errors)
