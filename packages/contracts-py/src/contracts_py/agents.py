from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field

from contracts_py.common import ID, SCHEMA_VERSION, Lenient, SchemaVersion, Severity, Strict, max_words
from contracts_py.decision import CandidatePlan, DecisionBrief
from contracts_py.engine import Impact
from contracts_py.enums import (
    DecisionType,
    Direction,
    EntityType,
    ImpactCategory,
    ImpactLevel,
    Polarity,
    Relation,
    RiskAppetite,
    Sensitivity,
)
from contracts_py.twin import AgentView

# Agent confidences are clamped by the merge step, so the models accept any float.
RawConfidence = float


class AgentSpec(Strict):
    agent_id: ID
    display_name: str
    department_id: ID | None = None
    responsibilities: list[str] = Field(default_factory=list)
    owned_metrics: list[str] = Field(default_factory=list)
    visible_entity_types: list[EntityType] = Field(default_factory=list)
    visible_sensitivity: list[Sensitivity] = Field(default_factory=list)
    routes_for: list[DecisionType | Literal["all"]] = Field(default_factory=list)
    prompt_version: str


class AgentSettingsView(Strict):
    risk_appetite: RiskAppetite
    optimizer_objective: Literal["max_net_value", "min_risk", "balanced"]
    display_currency: str
    money_display_scale: Literal["auto", "K", "M", "B"]


class AgentContext(Strict):
    schema_version: SchemaVersion = SCHEMA_VERSION
    run_id: ID
    agent: AgentSpec
    brief: DecisionBrief
    plan: CandidatePlan
    view: AgentView
    act_now_effects: list[Impact] = Field(default_factory=list)
    inaction_effects: list[Impact] = Field(default_factory=list)
    known_impact_summaries: list[str] = Field(default_factory=list)
    settings: AgentSettingsView
    max_tool_calls: int = Field(default=3, ge=0, le=5)


class Finding(Lenient):
    text: str
    entity_ids: list[str] = Field(default_factory=list)
    severity: Severity
    evidence_refs: list[str] = Field(default_factory=list)


class ProposedImpact(Lenient):
    affected_entity: str
    metric: str
    direction: Direction
    polarity: Polarity
    category: ImpactCategory
    level: ImpactLevel
    estimated_magnitude: float | None = None
    unit: str | None = None
    first_effect_day: int | None = None
    severity: Severity
    rationale: str
    dependency_path: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: RawConfidence


class FutureView(Lenient):
    summary: Annotated[str, max_words(40)]
    failure_modes: list[Finding] = Field(default_factory=list)
    edge_cases: list[Finding] = Field(default_factory=list)
    proposed_impacts: list[ProposedImpact] = Field(default_factory=list)


class ProposedDependency(Lenient):
    source: str
    target: str
    relation: Relation
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: RawConfidence


class AgentQuestion(Lenient):
    text: str
    why_it_matters: str
    entity_ids: list[str] = Field(default_factory=list)


class Objection(Lenient):
    target_ref: str
    text: str
    severity: Severity


class AgentOutput(Lenient):
    affected_entities: list[str] = Field(default_factory=list)
    act_now_view: FutureView
    inaction_view: FutureView
    proposed_dependencies: list[ProposedDependency] = Field(default_factory=list)
    questions: list[AgentQuestion] = Field(default_factory=list)
    objections: list[Objection] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: RawConfidence


class ChallengerOutput(Lenient):
    missing_agents: list[str] = Field(default_factory=list)
    unsupported_assumptions: list[Finding] = Field(default_factory=list)
    circular_logic: list[Finding] = Field(default_factory=list)
    overlooked_combinations: list[list[str]] = Field(default_factory=list)
    missed_dependencies: list[ProposedDependency] = Field(default_factory=list)
    inaction_underestimated: list[Finding] = Field(default_factory=list)
    objections: list[Objection] = Field(default_factory=list)
    confidence: RawConfidence


class ValidationReport(Strict):
    rejected_entity_ids: list[str] = Field(default_factory=list)
    downgraded_to_hypothesis: list[str] = Field(default_factory=list)
    clamped_fields: list[str] = Field(default_factory=list)
    retries: int = Field(default=0, ge=0, le=1)
    errors: list[str] = Field(default_factory=list)


class ToolCall(Strict):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    ok: bool
    result_summary: str


class CallMetrics(Strict):
    model_id: str
    prompt_version: str
    prompt_hash: str
    latency_ms: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    tool_calls: list[ToolCall] = Field(default_factory=list)


class AgentAssessment(Strict):
    assessment_id: ID
    run_id: ID
    plan_id: ID | None = None
    agent_id: ID
    pass_type: Literal["first_pass", "challenge"]
    status: Literal["ok", "replayed", "fallback_cached", "unavailable", "invalid"]
    output: AgentOutput | None = None
    challenge: ChallengerOutput | None = None
    accepted_impacts: list[Impact] = Field(default_factory=list)
    validation: ValidationReport = Field(default_factory=ValidationReport)
    metrics: CallMetrics
    created_at: datetime


class Claim(Strict):
    text: str
    source: Literal["calculation", "evidence", "assumption", "agent_validated"]
    ref: str
