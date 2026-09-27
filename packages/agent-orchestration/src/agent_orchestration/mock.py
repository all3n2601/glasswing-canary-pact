from contracts_py.agents import AgentContext, AgentOutput, AgentQuestion, ChallengerOutput, Finding, FutureView
from contracts_py.engine import Impact
from contracts_py.enums import Polarity
from pydantic import BaseModel

MOCK_CONFIDENCE = 0.5


def _harms(impacts: list[Impact], limit: int = 3) -> list[Impact]:
    harms = [i for i in impacts if i.polarity is Polarity.harm]
    return sorted(harms, key=lambda i: (-i.severity, i.impact_id))[:limit]


def _finding(impact: Impact, evidence: set[str]) -> Finding:
    return Finding(
        text=f"{impact.metric} moves {impact.direction.value} on {impact.affected_entity}.",
        entity_ids=[impact.affected_entity],
        severity=impact.severity,
        evidence_refs=[r for r in impact.evidence_refs if r in evidence],
    )


def _view(label: str, impacts: list[Impact], evidence: set[str]) -> FutureView:
    harms = _harms(impacts)
    touched = ", ".join(i.affected_entity for i in harms) or "nothing in this view"
    return FutureView(summary=f"{label} harms {touched}.", failure_modes=[_finding(i, evidence) for i in harms])


def mock_output(output_model: type[BaseModel], context: AgentContext) -> BaseModel:
    """Deterministic stand-in built only from IDs and evidence refs already in the context."""
    evidence = {e.id for e in context.view.evidence}
    prompt_generated = any(i.params.get("prompt_generated") is True for i in context.brief.candidate_interventions)
    if prompt_generated:
        entity_ids = ([context.agent.department_id] if context.agent.department_id else []) or [
            i.target_entity_id for i in context.brief.candidate_interventions[:3]
        ]
        responsibility = context.agent.responsibilities[0] if context.agent.responsibilities else "cross-company risk"
        finding = Finding(
            text=f"Potential effects on {responsibility} are not yet supported by quantified evidence.",
            entity_ids=entity_ids,
            severity=2,
            evidence_refs=[],
        )
        if output_model is ChallengerOutput:
            return ChallengerOutput(unsupported_assumptions=[finding], confidence=MOCK_CONFIDENCE)
        return AgentOutput(
            affected_entities=entity_ids,
            act_now_view=FutureView(summary=f"This proposal may affect {responsibility}.", failure_modes=[finding]),
            inaction_view=FutureView(summary="Doing nothing preserves the modeled baseline but may forgo the proposal's objective."),
            questions=[AgentQuestion(
                text=f"What evidence quantifies the proposal's effect on {responsibility}?",
                why_it_matters="The deterministic engine cannot test feasibility without this input.",
                entity_ids=entity_ids,
            )],
            assumptions=["Offline assessment flags exposure but does not invent a magnitude."],
            confidence=MOCK_CONFIDENCE,
        )
    if output_model is ChallengerOutput:
        return ChallengerOutput(
            inaction_underestimated=[_finding(i, evidence) for i in _harms(context.inaction_effects)],
            confidence=MOCK_CONFIDENCE,
        )
    impacts = [*context.act_now_effects, *context.inaction_effects]
    return AgentOutput(
        affected_entities=sorted({i.affected_entity for i in impacts}),
        act_now_view=_view("Acting now", context.act_now_effects, evidence),
        inaction_view=_view("Doing nothing", context.inaction_effects, evidence),
        assumptions=["Mock output derived from the engine effects in this view."],
        evidence_refs=sorted({r for i in impacts for r in i.evidence_refs if r in evidence}),
        confidence=MOCK_CONFIDENCE,
    )
