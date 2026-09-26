from contracts_py.agents import AgentContext, ChallengerOutput, ProposedDependency
from contracts_py.enums import Future
from contracts_py.events import EventType
from contracts_py.package import DecisionPackage

from agent_orchestration import AgentLLM, run_decision
from agent_orchestration.llm import LLMResult
from orchestration_helpers import NOW, Recorder, ScriptedLLM, SpyEngine, metrics, person_output, person_tokens

BASE_PHASES = ["validating", "building_futures", "optimizing", "running_agents", "propagating", "challenging",
               "propagating"]
TAIL_PHASES = ["comparing_futures", "generating_package", "awaiting_approval"]


def run(brief, twin, settings, llm, engine=None):
    recorder = Recorder()
    engine = engine or SpyEngine()
    package = run_decision(brief, engine=engine, settings=settings, llm=llm, emit=recorder, run_id="run_test",
                           twin=twin, clock=lambda: NOW)
    return package, recorder, engine


def test_full_mock_run_returns_package_and_exact_phase_order(brief, twin, settings) -> None:
    package, recorder, engine = run(brief, twin, settings, AgentLLM(settings))
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
    assert started == ["finance", "engineering", "operations", "compliance", "people_knowledge", "challenger"]


def challenger_with_new_edge(context: AgentContext) -> LLMResult:
    dependency = ProposedDependency(source="role_billing_ops_lead", target="sys_cloud_platform",
                                    relation="maintains", rationale="The incident log names the lead on cloud fixes.",
                                    evidence_refs=["ev_ops_incident_log"], confidence=1.7)
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
    assert (edge.source, edge.target, edge.confidence) == ("role_billing_ops_lead", "sys_cloud_platform", 1.0)
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
    _, recorder, _ = run(brief, twin, settings, AgentLLM(settings))
    futures = {e.future for e in recorder.of(EventType.simulation_completed)}
    assert futures == {Future.act_now, Future.inaction, Future.delay}


def test_person_tokens_never_leave_the_agent_layer(brief, hr_twin, settings) -> None:
    seen: list[set[str]] = []

    def people(context: AgentContext) -> LLMResult:
        seen.append({e.id for e in context.view.entities})
        return LLMResult(person_output(), "ok", metrics("people_knowledge"))

    # Default settings: people_knowledge runs as a CORE agent and its HR view really contains the token.
    package, recorder, engine = run(brief, hr_twin, settings, ScriptedLLM(settings, {"people_knowledge": people}))
    assert seen and "pt_07" in seen[0]
    completed = [e for e in recorder.of(EventType.agent_completed) if e.payload.agent_id == "people_knowledge"]
    assert len(completed) == 1
    assert completed[0].payload.validation.rejected_entity_ids == ["[role]"]
    assert person_tokens(completed[0].model_dump_json()) == []
    assert person_tokens(package.model_dump_json()) == []
    assert "Can someone shadow [role]?" in package.open_questions
    assert "clone_with_edges" not in engine.names()


def test_fallback_cached_agent_widens_uncertainty(brief, twin, settings) -> None:
    fallback = lambda context: LLMResult(challenger_with_new_edge(context).output, "fallback_cached",
                                         metrics("challenger"), errors=["cache miss"])
    engineering = lambda context: LLMResult(None, "fallback_cached", metrics("engineering"))
    llm = ScriptedLLM(settings, {"challenger": fallback, "engineering": engineering})
    package, recorder, engine = run(brief, twin, settings, llm)
    assert recorder.phases() == BASE_PHASES + TAIL_PHASES
    assert "clone_with_edges" not in engine.names()
    assert package.missing_perspectives == ["engineering", "challenger"]
    widen = [args for name, args in engine.calls if name == "widen_uncertainty"]
    assert widen[0][1] == ["dept_engineering"]
