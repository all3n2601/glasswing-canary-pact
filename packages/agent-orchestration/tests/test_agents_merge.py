import pytest
from contracts_py.agents import AgentOutput, ChallengerOutput, FutureView, ProposedDependency, ProposedImpact
from contracts_py.enums import ClaimStatus, Origin

from agent_orchestration.llm import LLMResult
from agent_orchestration.merge import merge
from orchestration_helpers import NOW, make_context, metrics

SCENARIOS = {"act_now": "scn_run_test_act_now_plan_recommended", "inaction": "scn_run_test_inaction_none"}


@pytest.fixture
def context(brief, twin, settings):
    return make_context(brief, twin, settings)


def impact(**overrides) -> ProposedImpact:
    values = {
        "affected_entity": "wf_billing_recon",
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
        "evidence_refs": ["ev_billing_recon_matrix"],
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
    assert report.rejected_entity_ids == ["pt_07", "wf_ghost"]
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


@pytest.mark.parametrize("change", [{"direction": "decrease"}, {"polarity": "benefit"}])
def test_contradicting_engine_impact_rejected(context, change) -> None:
    # The stub engine says failure_probability_monthly on wf_billing_recon increases and is a harm.
    claim = impact(**({"metric": "failure_probability_monthly", "direction": "increase"} | change))
    outcome = run_merge(context, output(claim))
    assert outcome.assessment.accepted_impacts == []
    assert any("contradicts engine impact" in e for e in outcome.assessment.validation.errors)


def dependency(**overrides) -> ProposedDependency:
    values = {"source": "role_billing_ops_lead", "target": "sys_cloud_platform", "relation": "MAINTAINS",
              "rationale": "Incident log names the lead.", "evidence_refs": ["ev_ops_incident_log"], "confidence": 0.8}
    return ProposedDependency.model_validate(values | overrides)


def test_dependencies_become_edges_only_when_new_known_and_evidenced(context) -> None:
    deps = [
        dependency(),
        dependency(source="role_billing_ops_lead", target="wf_billing_recon", relation="OWNS",
                   evidence_refs=["ev_billing_recon_matrix"]),
        dependency(target="kpi_company", evidence_refs=[]),
        dependency(source="role_ghost"),
    ]
    outcome = run_merge(context, output(dependencies=deps))
    assert [(e.source, e.target, e.relation.value) for e in outcome.validated_edges] == [
        ("role_billing_ops_lead", "sys_cloud_platform", "MAINTAINS")
    ]
    edge = outcome.validated_edges[0]
    assert edge.evidence_refs == ["ev_ops_incident_log"] and edge.id.startswith("e_")
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
