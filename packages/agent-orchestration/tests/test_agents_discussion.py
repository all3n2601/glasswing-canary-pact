from contracts_py.agents import AgentOutput, ChallengerOutput, Objection, ReviewIssue, ReviewReply
from contracts_py.events import EventType

from agent_orchestration.discussion import visible_issues
from agent_orchestration.llm import LLMResult
from orchestration_helpers import ScriptedLLM, make_context, metrics
from test_agents_orchestrator import challenger_with_new_edge, run


def initial_output():
    return AgentOutput(act_now_view={"summary": "The workflow can continue."},
                       inaction_view={"summary": "The current dependency remains."}, confidence=0.7)


def challenge(context):
    assert any("assessment_id=asm_run_test_operations" in s for s in context.known_impact_summaries)
    return LLMResult(ChallengerOutput(objections=[Objection(target_ref="asm_run_test_operations",
        text="What supports continuity of the account intelligence feed?", severity=4)], confidence=0.8),
        "ok", metrics("challenger"))


def test_targeted_reply_sees_prior_claim_and_objection_then_feeds_engine(brief, twin, settings):
    seen = []

    def operations(context):
        seen.append(context)
        output = initial_output()
        if context.review_issues:
            assert context.previous_output.act_now_view.summary == "The workflow can continue."
            assert context.previous_assessment_id == "asm_run_test_operations"
            issue = context.review_issues[0]
            assert issue.source_agent_id == "challenger"
            output.act_now_view.summary = "Continuity depends on the account intelligence feed."
            output.proposed_dependencies = challenger_with_new_edge(context).output.missed_dependencies
            output.review_replies = [ReviewReply(issue_id=issue.issue_id, position="revised",
                explanation="The workflow map establishes a dependency that my initial assessment missed.",
                evidence_refs=["ev_echo_account_intel_feed"])]
        return LLMResult(output, "ok", metrics("operations"))

    package, recorder, engine = run(brief, twin, settings,
        ScriptedLLM(settings, {"operations": operations, "challenger": challenge}))
    assert len(seen) == 2
    responses = [e.payload for e in recorder.of(EventType.agent_completed) if e.payload.pass_type == "response"]
    assert len(responses) == 1
    response = responses[0]
    assert response.assessment_id != response.responds_to_assessment_id
    assert response.output.review_replies[0].position == "revised"
    assert engine.names().count("optimize") == 2
    assert any(e.payload.assessment_id == response.assessment_id
               for e in recorder.of(EventType.dependency_validated))
    response_index = next(i for i, e in enumerate(recorder.events)
                          if e.type == EventType.agent_completed and e.payload.pass_type == "response")
    assert any(e.type == EventType.simulation_completed for e in recorder.events[response_index + 1:])
    assert package.status == "awaiting_approval"


def test_unsupported_reply_and_unknown_issue_never_become_resolution(brief, twin, settings):
    def operations(context):
        output = initial_output()
        if context.review_issues:
            output.review_replies = [ReviewReply(issue_id=context.review_issues[0].issue_id,
                position="supported", explanation="Trust me.", evidence_refs=["ev_invented"]),
                ReviewReply(issue_id="invented_issue", position="revised", explanation="Done.")]
        return LLMResult(output, "ok", metrics("operations"))

    package, recorder, _ = run(brief, twin, settings,
        ScriptedLLM(settings, {"operations": operations, "challenger": challenge}))
    response = next(e.payload for e in recorder.of(EventType.agent_completed) if e.payload.pass_type == "response")
    assert len(response.output.review_replies) == 1
    assert response.output.review_replies[0].position == "unresolved"
    assert response.output.review_replies[0].evidence_refs == []
    assert any("unknown or duplicate" in e for e in response.validation.errors)
    assert any("Unresolved response" in q for q in package.open_questions)


def test_response_failure_retains_initial_assessment_and_missing_perspective(brief, twin, settings):
    def operations(context):
        if context.review_issues:
            return LLMResult(None, "unavailable", metrics(), errors=["Provider timed out"])
        return LLMResult(initial_output(), "ok", metrics())

    package, recorder, _ = run(brief, twin, settings,
        ScriptedLLM(settings, {"operations": operations, "challenger": challenge}))
    assessments = [e.payload for e in recorder.of(EventType.agent_completed) if e.payload.agent_id == "operations"]
    assert [a.status for a in assessments] == ["ok", "unavailable"]
    assert "operations" in package.missing_perspectives
    assert recorder.of(EventType.agent_failed)[0].payload.pass_type == "response"
    assert package.open_questions


def test_response_round_is_bounded_and_does_not_reply_to_replies(brief, twin, settings):
    def many(context):
        return LLMResult(ChallengerOutput(objections=[Objection(target_ref=agent,
            text=f"Check assumption {n}.", severity=5 if agent == "operations" else 3)
            for agent in ["operations", "finance", "engineering", "sales", "compliance"]
            for n in range(5)], confidence=0.7), "ok", metrics())

    _, recorder, _ = run(brief, twin, settings, ScriptedLLM(settings, {"challenger": many}))
    responses = [e.payload for e in recorder.of(EventType.agent_completed) if e.payload.pass_type == "response"]
    assert len(responses) == 3
    assert all(len(a.review_issues) == 3 for a in responses)
    assert "operations" in [a.agent_id for a in responses]
    assert all(r.position == "unresolved" for a in responses for r in a.output.review_replies)


def test_review_context_does_not_expand_department_permissions(brief, twin, settings):
    context = make_context(brief, twin, settings, "operations")
    issue = ReviewIssue(issue_id="issue_test", source_assessment_id="asm_finance", source_agent_id="finance",
                        source_ref="objections.0", target_assessment_id="asm_operations", text="Restricted claim.",
                        severity=4)
    assert visible_issues([issue], context) == []
    issue.source_agent_id = "challenger"
    issue.evidence_refs = ["ev_not_visible"]
    assert visible_issues([issue], context) == []


def test_reply_validation_preserves_complete_explanation():
    explanation = "This concern still needs supporting evidence. " * 15
    reply = ReviewReply(issue_id="issue_test", position="unresolved", explanation=explanation)
    assert reply.explanation == explanation
