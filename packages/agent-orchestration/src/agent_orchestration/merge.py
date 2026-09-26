import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from contracts_py.agents import (
    AgentAssessment,
    AgentContext,
    AgentOutput,
    ChallengerOutput,
    Finding,
    FutureView,
    ProposedDependency,
    ProposedImpact,
    ValidationReport,
)
from contracts_py.engine import Impact
from contracts_py.enums import ClaimStatus, Criticality, Direction, Origin
from contracts_py.twin import Edge

from agent_orchestration.llm import LLMResult
from agent_orchestration.prompts import redact_people

log = logging.getLogger(__name__)
PERSON_ID = re.compile(r"pt_[a-z0-9_]+")

OPPOSITE = {(Direction.increase, Direction.decrease), (Direction.decrease, Direction.increase)}
# An agent never supplies edge numbers; validated edges start from neutral values the engine can widen.
AGENT_EDGE_STRENGTH = 0.5
AGENT_EDGE_SUBSTITUTABILITY = 0.5


@dataclass
class MergeOutcome:
    assessment: AgentAssessment
    validated_edges: list[Edge] = field(default_factory=list)


class _Merger:
    def __init__(self, agent_id: str, context: AgentContext, assessment_id: str, scenario_ids: dict[str, str],
                 origin: Origin, stale: bool) -> None:
        self.agent_id = agent_id
        self.context = context
        self.assessment_id = assessment_id
        self.scenario_ids = scenario_ids
        self.origin = origin
        # A fallback answer was written for another prompt, so none of its claims may change numbers.
        self.stale = stale
        view = context.view
        self.known_ids = {e.id for e in view.entities}
        self.known_evidence = {e.id for e in view.evidence}
        self.edges_by_pair = {frozenset((e.source, e.target)): e for e in view.edges}
        self.existing = {(e.source, e.target, e.relation) for e in view.edges}
        self.report = ValidationReport()
        self.rejected: set[str] = set()
        self.accepted: list[Impact] = []
        self.edges: list[Edge] = []

    def unknown(self, ids: list[str], where: str) -> bool:
        bad = [i for i in ids if i not in self.known_ids or PERSON_ID.fullmatch(i)]
        if bad:
            self.rejected.update(bad)
            self.report.errors.append(f"{where} rejected: unknown entity ids {bad}")
        return bool(bad)

    def clamp(self, value: float, where: str) -> float:
        if 0 <= value <= 1:
            return value
        self.report.clamped_fields.append(where)
        return min(1.0, max(0.0, value))

    def resolves(self, refs: list[str]) -> bool:
        return not self.stale and any(r in self.known_evidence for r in refs)

    def findings(self, items: list[Finding], where: str) -> list[Finding]:
        return [f for n, f in enumerate(items) if not self.unknown(f.entity_ids, f"{where}[{n}]")]

    def edge_path(self, path: list[str]) -> tuple[list[str], list[str]]:
        edges = [self.edges_by_pair.get(frozenset(pair)) for pair in zip(path, path[1:])]
        if all(edges):
            return path, [e.id for e in edges if e]
        return [], []

    def impact(self, proposed: ProposedImpact, where: str, future_key: str) -> ProposedImpact | None:
        confidence = self.clamp(proposed.confidence, f"{where}.confidence")
        if self.unknown([proposed.affected_entity, *proposed.dependency_path], where):
            return None
        effects = self.context.act_now_effects if future_key == "act_now" else self.context.inaction_effects
        for engine_impact in effects:
            same = engine_impact.affected_entity == proposed.affected_entity and engine_impact.metric == proposed.metric
            opposite = (engine_impact.direction, proposed.direction) in OPPOSITE or engine_impact.polarity != proposed.polarity
            if same and opposite:
                self.report.errors.append(f"{where} rejected: contradicts engine impact {engine_impact.impact_id}")
                return None
        status = ClaimStatus.validated if self.resolves(proposed.evidence_refs) else ClaimStatus.hypothesis
        if status is ClaimStatus.hypothesis:
            self.report.downgraded_to_hypothesis.append(where)
        path, edge_path = self.edge_path(proposed.dependency_path)
        index = len(self.accepted)
        # Magnitude, value and timing stay with the engine; the agent contributes the claim, not its numbers.
        self.accepted.append(Impact(
            impact_id=f"imp_{self.assessment_id}_{index}",
            decision_id=self.context.brief.decision_id,
            scenario_id=self.scenario_ids[future_key],
            source_entity=path[0] if path else proposed.affected_entity,
            source_kind="intervention",
            source_ref=self.context.plan.plan_id,
            affected_entity=proposed.affected_entity,
            level=proposed.level,
            category=proposed.category,
            polarity=proposed.polarity,
            direction=proposed.direction,
            metric=proposed.metric,
            magnitude=0.0,
            unit=proposed.unit or "unspecified",
            severity=proposed.severity,
            first_effect_day=0,
            peak_effect_day=0,
            confidence=confidence,
            dependency_path=path,
            edge_path=edge_path,
            evidence_refs=[r for r in proposed.evidence_refs if r in self.known_evidence],
            assumptions=[proposed.rationale],
            origin=self.origin,
            status=status,
        ))
        return proposed.model_copy(update={"confidence": confidence})

    def future_view(self, view: FutureView, name: str, future_key: str) -> FutureView:
        impacts = [self.impact(p, f"{name}.proposed_impacts[{n}]", future_key) for n, p in enumerate(view.proposed_impacts)]
        return view.model_copy(update={
            "failure_modes": self.findings(view.failure_modes, f"{name}.failure_modes"),
            "edge_cases": self.findings(view.edge_cases, f"{name}.edge_cases"),
            "proposed_impacts": [p for p in impacts if p is not None],
        })

    def dependencies(self, items: list[ProposedDependency], where: str) -> list[ProposedDependency]:
        kept = []
        for n, dep in enumerate(items):
            path = f"{where}[{n}]"
            confidence = self.clamp(dep.confidence, f"{path}.confidence")
            if self.unknown([dep.source, dep.target], path):
                continue
            if not self.resolves(dep.evidence_refs):
                self.report.downgraded_to_hypothesis.append(path)
            elif (dep.source, dep.target, dep.relation) not in self.existing:
                self.existing.add((dep.source, dep.target, dep.relation))
                self.edges.append(self.to_edge(dep, confidence))
            kept.append(dep.model_copy(update={"confidence": confidence}))
        return kept

    def to_edge(self, dep: ProposedDependency, confidence: float) -> Edge:
        edge_id = f"e_{dep.source}_{dep.relation.value.lower()}_{dep.target}"
        if len(edge_id) > 80:
            edge_id = "e_agent_" + hashlib.sha256(edge_id.encode()).hexdigest()[:16]
        return Edge(
            id=edge_id,
            source=dep.source,
            target=dep.target,
            relation=dep.relation,
            label=dep.rationale[:120],
            strength=AGENT_EDGE_STRENGTH,
            substitutability=AGENT_EDGE_SUBSTITUTABILITY,
            lag_days=0,
            criticality=Criticality.medium,
            confidence=confidence,
            evidence_refs=[r for r in dep.evidence_refs if r in self.known_evidence],
        )

    def agent_output(self, output: AgentOutput) -> AgentOutput:
        affected = [i for i in output.affected_entities if not self.unknown([i], "affected_entities")]
        questions = [q for n, q in enumerate(output.questions) if not self.unknown(q.entity_ids, f"questions[{n}]")]
        return output.model_copy(update={
            "affected_entities": affected,
            "act_now_view": self.future_view(output.act_now_view, "act_now_view", "act_now"),
            "inaction_view": self.future_view(output.inaction_view, "inaction_view", "inaction"),
            "proposed_dependencies": self.dependencies(output.proposed_dependencies, "proposed_dependencies"),
            "questions": questions,
            "confidence": self.clamp(output.confidence, "confidence"),
        })

    def challenger_output(self, output: ChallengerOutput) -> ChallengerOutput:
        combos = [c for n, c in enumerate(output.overlooked_combinations)
                  if not self.unknown(c, f"overlooked_combinations[{n}]")]
        return output.model_copy(update={
            "unsupported_assumptions": self.findings(output.unsupported_assumptions, "unsupported_assumptions"),
            "circular_logic": self.findings(output.circular_logic, "circular_logic"),
            "overlooked_combinations": combos,
            "missed_dependencies": self.dependencies(output.missed_dependencies, "missed_dependencies"),
            "inaction_underestimated": self.findings(output.inaction_underestimated, "inaction_underestimated"),
            "confidence": self.clamp(output.confidence, "confidence"),
        })


def redact_tree(value: Any) -> tuple[Any, int]:
    if isinstance(value, str):
        text, found = redact_people(value)
        return text, len(found)
    if isinstance(value, dict):
        pairs = [(k, redact_tree(v)) for k, v in value.items()]
        return {k: v for k, (v, _) in pairs}, sum(n for _, (_, n) in pairs)
    if isinstance(value, list):
        items = [redact_tree(v) for v in value]
        return [v for v, _ in items], sum(n for _, n in items)
    return value, 0


def merge(agent_id: str, result: LLMResult, *, context: AgentContext, pass_type: Literal["first_pass", "challenge"],
          scenario_ids: dict[str, str], created_at: datetime) -> MergeOutcome:
    """Applies the section 7 merge rules; scenario_ids maps "act_now" and "inaction" to scenario IDs."""
    assessment_id = f"asm_{context.run_id}_{agent_id}"
    origin = Origin.challenger if pass_type == "challenge" else Origin.agent
    merger = _Merger(agent_id, context, assessment_id, scenario_ids, origin, stale=result.status == "fallback_cached")
    merger.report.errors.extend(result.errors)
    output = challenge = None
    if isinstance(result.output, AgentOutput):
        output = merger.agent_output(result.output)
    elif isinstance(result.output, ChallengerOutput):
        challenge = merger.challenger_output(result.output)
    merger.report.rejected_entity_ids = sorted(merger.rejected)
    merger.report.retries = min(result.retries, 1)
    assessment = AgentAssessment(
        assessment_id=assessment_id,
        run_id=context.run_id,
        plan_id=context.plan.plan_id,
        agent_id=agent_id,
        pass_type=pass_type,
        status=result.status,
        output=output,
        challenge=challenge,
        accepted_impacts=merger.accepted,
        validation=merger.report,
        metrics=result.metrics,
        created_at=created_at,
    )
    # Person tokens were rejected as references above; this removes them from free text and log lines too.
    redacted, count = redact_tree(assessment.model_dump(mode="json"))
    if count:
        log.warning("redacted %d person tokens from the %s assessment", count, agent_id)
        assessment = AgentAssessment.model_validate(redacted)
    return MergeOutcome(assessment, merger.edges)
