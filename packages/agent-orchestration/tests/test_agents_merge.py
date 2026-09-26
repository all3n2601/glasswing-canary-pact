import pytest
from contracts_py.agents import AgentOutput, ChallengerOutput, FutureView, ProposedDependency, ProposedImpact
from contracts_py.enums import ClaimStatus, Direction, Future, Origin, Polarity

from canary_api.stubs import results
from canary_api.stubs.twin import sample_brief, stub_twin

from agent_orchestration.llm import LLMResult
from agent_orchestration.merge import merge
from orchestration_helpers import NOW, make_context, metrics, person_output, person_tokens

SCENARIOS = {"act_now": results.scenario_id("run_test", Future.act_now, results.RECOMMENDED_PLAN),
             "inaction": results.scenario_id("run_test", Future.inaction, None)}
TWIN = stub_twin()
ENTITIES = {e.id: e for e in TWIN.entities}
# A known workflow the stub engine leaves untouched, with evidence the twin resolves.
IMPACT_TARGET = "wf_billing_recon"
IMPACT_EVIDENCE = ENTITIES[IMPACT_TARGET].evidence_refs[0]
# The planted missed dependency: both endpoints known, not an edge yet, evidenced in the twin.
NEW_DEPENDENCY = ("wf_vendor_reconciliation", "ds_account_intel", "CONSUMES", "ev_echo_account_intel_feed")
EXISTING_EDGE = TWIN.edges[0]


@pytest.fixture
def context(brief, twin, settings):
    return make_context(brief, twin, settings)


def impact(**overrides) -> ProposedImpact:
    values = {
        "affected_entity": IMPACT_TARGET,
        "metric": "backup_owners",
        "direction": "decrease",
        "polarity": "harm",
        "category": "ownership",
        "level": "dependent",
        "estimated_magnitude": 999.0,
        "unit": "owners",
        "first_effect_day": 400,
        "severity": 4,
        "rationale": "Only the billing lead can reconcile.",
        "evidence_refs": [IMPACT_EVIDENCE],
        "confidence": 0.7,
    }
    return ProposedImpact.model_validate(values | overrides)


def output(*impacts: ProposedImpact, dependencies=(), confidence: float = 0.6) -> AgentOutput:
    return AgentOutput(
        act_now_view=FutureView(summary="Act now.", proposed_impacts=list(impacts)),
        inaction_view=FutureView(summary="Do nothing."),
        proposed_dependencies=list(dependencies),
        confidence=confidence,
    )


def run_merge(context, result_output, status="ok", pass_type="first_pass", errors=()):
    result = LLMResult(result_output, status, metrics(), errors=list(errors))
    return merge("operations", result, context=context, pass_type=pass_type, scenario_ids=SCENARIOS, created_at=NOW)


def test_unknown_entity_rejected(context) -> None:
    outcome = run_merge(context, output(impact(affected_entity="wf_ghost"), impact(dependency_path=["pt_07"])))
    report = outcome.assessment.validation
    assert report.rejected_entity_ids == ["[role]", "wf_ghost"]
    assert outcome.assessment.accepted_impacts == []
    assert outcome.assessment.output.act_now_view.proposed_impacts == []


def test_known_ids_with_evidence_validated_without_agent_numbers(context) -> None:
    outcome = run_merge(context, output(impact()))
    accepted = outcome.assessment.accepted_impacts
    assert len(accepted) == 1 and accepted[0].status is ClaimStatus.validated
    assert accepted[0].origin is Origin.agent and accepted[0].scenario_id == SCENARIOS["act_now"]
    assert (accepted[0].magnitude, accepted[0].value_usd, accepted[0].first_effect_day) == (0.0, None, 0)


def test_no_evidence_becomes_hypothesis(context) -> None:
    outcome = run_merge(context, output(impact(evidence_refs=["ev_unknown"])))
    assert outcome.assessment.accepted_impacts[0].status is ClaimStatus.hypothesis
    assert outcome.assessment.validation.downgraded_to_hypothesis == ["act_now_view.proposed_impacts[0]"]


ENGINE_IMPACT = next(i for i in results.act_now_result("run_test", sample_brief().decision_id).impacts
                     if i.polarity is Polarity.harm and i.direction is Direction.decrease)
OPPOSITE_DIRECTION = {Direction.decrease: "increase", Direction.increase: "decrease"}


@pytest.mark.parametrize("change", [{"direction": OPPOSITE_DIRECTION[ENGINE_IMPACT.direction]}, {"polarity": "benefit"}])
def test_contradicting_engine_impact_rejected(context, change) -> None:
    same = {"affected_entity": ENGINE_IMPACT.affected_entity, "metric": ENGINE_IMPACT.metric,
            "direction": ENGINE_IMPACT.direction.value, "polarity": ENGINE_IMPACT.polarity.value,
            "evidence_refs": ENGINE_IMPACT.evidence_refs or [IMPACT_EVIDENCE]}
    assert run_merge(context, output(impact(**same))).assessment.accepted_impacts, "the agreeing claim is accepted"
    claim = impact(**(same | change))
    outcome = run_merge(context, output(claim))
    assert outcome.assessment.accepted_impacts == []
    assert any("contradicts engine impact" in e for e in outcome.assessment.validation.errors)


def dependency(**overrides) -> ProposedDependency:
    source, target, relation, evidence = NEW_DEPENDENCY
    values = {"source": source, "target": target, "relation": relation,
              "rationale": "The workflow map says account intelligence feeds vendor reconciliation.",
              "evidence_refs": [evidence], "confidence": 0.8}
    return ProposedDependency.model_validate(values | overrides)


def test_dependencies_become_edges_only_when_new_known_and_evidenced(context) -> None:
    deps = [
        dependency(),
        dependency(source=EXISTING_EDGE.source, target=EXISTING_EDGE.target, relation=EXISTING_EDGE.relation.value,
                   evidence_refs=EXISTING_EDGE.evidence_refs),
        dependency(target="kpi_company", evidence_refs=[]),
        dependency(source="role_ghost"),
    ]
    outcome = run_merge(context, output(dependencies=deps))
    assert [(e.source, e.target, e.relation.value) for e in outcome.validated_edges] == [NEW_DEPENDENCY[:3]]
    edge = outcome.validated_edges[0]
    assert edge.evidence_refs == [NEW_DEPENDENCY[3]] and edge.id.startswith("e_")
    report = outcome.assessment.validation
    assert report.downgraded_to_hypothesis == ["proposed_dependencies[2]"]
    assert report.rejected_entity_ids == ["role_ghost"]


def test_challenger_dependencies_and_confidence_clamp(context) -> None:
    challenge = ChallengerOutput(missed_dependencies=[dependency(confidence=-0.3)], confidence=1.4)
    outcome = run_merge(context, challenge, pass_type="challenge")
    assessment = outcome.assessment
    assert assessment.challenge.confidence == 1.0
    assert assessment.challenge.missed_dependencies[0].confidence == 0.0
    assert assessment.validation.clamped_fields == ["missed_dependencies[0].confidence", "confidence"]
    assert outcome.validated_edges[0].confidence == 0.0


def test_failed_call_keeps_status_and_errors(context) -> None:
    outcome = run_merge(context, None, status="unavailable", errors=["no cached answer"])
    assert outcome.assessment.status == "unavailable" and outcome.assessment.output is None
    assert outcome.assessment.validation.errors == ["no cached answer"]


def test_fallback_cached_claims_are_hypotheses_only(context) -> None:
    outcome = run_merge(context, output(impact(), dependencies=[dependency()]), status="fallback_cached")
    assert outcome.validated_edges == []
    assert [i.status for i in outcome.assessment.accepted_impacts] == [ClaimStatus.hypothesis]
    assert outcome.assessment.validation.downgraded_to_hypothesis == [
        "act_now_view.proposed_impacts[0]", "proposed_dependencies[0]"
    ]


def test_person_tokens_rejected_even_when_visible(brief, hr_twin, settings) -> None:
    context = make_context(brief, hr_twin, settings, agent_id="people_knowledge")
    assert "pt_07" in {e.id for e in context.view.entities}
    outcome = merge("people_knowledge", LLMResult(person_output(), "ok", metrics()), context=context,
                    pass_type="first_pass", scenario_ids=SCENARIOS, created_at=NOW)
    assert outcome.validated_edges == [] and outcome.assessment.accepted_impacts == []
    assert "[role]" in outcome.assessment.validation.rejected_entity_ids
    assert person_tokens(outcome.assessment.model_dump_json()) == []
