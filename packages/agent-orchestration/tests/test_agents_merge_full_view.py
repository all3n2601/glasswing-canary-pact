from canary_api.stubs import engine as stub_engine
from contracts_py.agents import AgentOutput, FutureView, ProposedImpact
from contracts_py.events import EventType

from agent_orchestration import run_decision
from agent_orchestration.llm import LLMResult
from agent_orchestration.merge import merge
from agent_orchestration.roster import ROSTER
from orchestration_helpers import NOW, Recorder, ScriptedLLM, SpyEngine, make_context, metrics, person_output
from test_agents_merge import SCENARIOS


def full_view(twin, agent_id):
    spec = ROSTER[agent_id]
    return stub_engine.build_agent_view(twin, agent_id=agent_id, department_id=spec.department_id,
                                        visible_entity_types=spec.visible_entity_types,
                                        visible_sensitivity=spec.visible_sensitivity)


def claim(entity_id: str) -> AgentOutput:
    impact = ProposedImpact.model_validate({
        "affected_entity": entity_id, "metric": "exposure", "direction": "increase", "polarity": "harm",
        "category": "operational", "level": "dependent", "severity": 3, "rationale": "Seen in the full view.",
        "confidence": 0.6,
    })
    return AgentOutput(act_now_view=FutureView(summary="Act now.", proposed_impacts=[impact]),
                       inaction_view=FutureView(summary="Do nothing."), confidence=0.6)


def outside_trim(context, view) -> str:
    trimmed = {e.id for e in context.view.entities}
    return next(e.id for e in view.entities if e.id not in trimmed and e.type.value != "person_token")


def test_id_in_full_view_but_not_trimmed_context_is_accepted(brief, twin, settings) -> None:
    context = make_context(brief, twin, settings, trim=True)
    view = full_view(twin, "operations")
    entity_id = outside_trim(context, view)
    result = LLMResult(claim(entity_id), "ok", metrics())
    accepted = merge("operations", result, context=context, pass_type="first_pass", scenario_ids=SCENARIOS,
                     created_at=NOW, known_view=view)
    assert [i.affected_entity for i in accepted.assessment.accepted_impacts] == [entity_id]
    assert accepted.assessment.validation.rejected_entity_ids == []
    # Validated against the trimmed slice alone, the same real entity would have been rejected.
    trimmed_only = merge("operations", result, context=context, pass_type="first_pass", scenario_ids=SCENARIOS,
                         created_at=NOW)
    assert trimmed_only.assessment.validation.rejected_entity_ids == [entity_id]


def test_id_outside_full_view_is_still_rejected(brief, twin, settings) -> None:
    context = make_context(brief, twin, settings, trim=True)
    outcome = merge("operations", LLMResult(claim("wf_ghost"), "ok", metrics()), context=context,
                    pass_type="first_pass", scenario_ids=SCENARIOS, created_at=NOW,
                    known_view=full_view(twin, "operations"))
    assert outcome.assessment.accepted_impacts == []
    assert outcome.assessment.validation.rejected_entity_ids == ["wf_ghost"]


def test_person_tokens_rejected_even_in_the_full_view(people_brief, hr_twin, settings) -> None:
    context = make_context(people_brief, hr_twin, settings, agent_id="people_knowledge", trim=True)
    view = full_view(hr_twin, "people_knowledge")
    assert "pt_07" in {e.id for e in view.entities}
    outcome = merge("people_knowledge", LLMResult(person_output(), "ok", metrics()), context=context,
                    pass_type="first_pass", scenario_ids=SCENARIOS, created_at=NOW, known_view=view)
    assert "[role]" in outcome.assessment.validation.rejected_entity_ids
    assert all(i.affected_entity != "pt_07" for i in outcome.assessment.accepted_impacts)


def test_run_validates_claims_against_the_full_permitted_view(brief, twin, settings) -> None:
    chosen: list[str] = []

    def operations(context):
        chosen.append(outside_trim(context, full_view(twin, "operations")))
        return LLMResult(claim(chosen[0]), "ok", metrics("operations"))

    recorder = Recorder()
    run_decision(brief, engine=SpyEngine(), settings=settings, llm=ScriptedLLM(settings, {"operations": operations}),
                 emit=recorder, run_id="run_test", twin=twin, clock=lambda: NOW)
    assessment = next(e.payload for e in recorder.of(EventType.agent_completed) if e.payload.agent_id == "operations")
    assert chosen and chosen[0] in [i.affected_entity for i in assessment.accepted_impacts]
    assert chosen[0] not in assessment.validation.rejected_entity_ids
