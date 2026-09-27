from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, RootModel, model_validator

from contracts_py.agents import AgentAssessment, ReviewIssue
from contracts_py.common import ID, SCHEMA_VERSION, USD, SchemaVersion, Strict
from contracts_py.decision import CandidatePlan, DecisionBrief, Scenario
from contracts_py.engine import (
    BlastRadius,
    ConstraintResult,
    FutureComparison,
    Impact,
    MissingQuestion,
    MitigationComparison,
    PortfolioComparison,
    SimulationResult,
    UserAnswer,
)
from contracts_py.enums import Future, RunStatus
from contracts_py.package import DecisionPackage, HumanDecision
from contracts_py.twin import Document, Edge


class EventType(StrEnum):
    run_created = "run_created"
    phase_changed = "phase_changed"
    scenario_created = "scenario_created"
    pressure_activated = "pressure_activated"
    candidate_generated = "candidate_generated"
    candidate_rejected = "candidate_rejected"
    agent_started = "agent_started"
    agent_completed = "agent_completed"
    agent_failed = "agent_failed"
    dependency_validated = "dependency_validated"
    impact_computed = "impact_computed"
    constraint_violated = "constraint_violated"
    challenge_raised = "challenge_raised"
    simulation_completed = "simulation_completed"
    futures_compared = "futures_compared"
    portfolio_ranked = "portfolio_ranked"
    blast_radius_ready = "blast_radius_ready"
    mitigation_applied = "mitigation_applied"
    package_ready = "package_ready"
    human_decision_recorded = "human_decision_recorded"
    question_selected = "question_selected"
    answer_received = "answer_received"
    settings_updated = "settings_updated"
    document_registered = "document_registered"
    run_failed = "run_failed"


class PhaseChanged(Strict):
    from_status: RunStatus
    to_status: RunStatus


class PressureActivated(Strict):
    pressure_id: ID
    future: Future
    expected_cost_usd: USD


class CandidateRejected(Strict):
    plan_id: ID
    reasons: list[str]


class AgentStarted(Strict):
    agent_id: ID
    plan_id: ID | None = None
    pass_type: Literal["first_pass", "challenge", "response"] = "first_pass"
    review_issues: list[ReviewIssue] = Field(default_factory=list)


class AgentFailed(Strict):
    agent_id: ID
    reason: str
    fallback_used: bool
    plan_id: ID | None = None
    pass_type: Literal["first_pass", "challenge", "response"] = "first_pass"


class DependencyValidated(Strict):
    assessment_id: ID
    edge: Edge


class SettingsUpdated(Strict):
    settings_version: int = Field(ge=1)
    changed_fields: list[str]


class RunFailed(Strict):
    reason: str


EVENT_PAYLOADS: dict[EventType, type[Strict]] = {
    EventType.run_created: DecisionBrief,
    EventType.phase_changed: PhaseChanged,
    EventType.scenario_created: Scenario,
    EventType.pressure_activated: PressureActivated,
    EventType.candidate_generated: CandidatePlan,
    EventType.candidate_rejected: CandidateRejected,
    EventType.agent_started: AgentStarted,
    EventType.agent_completed: AgentAssessment,
    EventType.agent_failed: AgentFailed,
    EventType.dependency_validated: DependencyValidated,
    EventType.impact_computed: Impact,
    EventType.constraint_violated: ConstraintResult,
    EventType.challenge_raised: AgentAssessment,
    EventType.simulation_completed: SimulationResult,
    EventType.futures_compared: FutureComparison,
    EventType.portfolio_ranked: PortfolioComparison,
    EventType.blast_radius_ready: BlastRadius,
    EventType.mitigation_applied: MitigationComparison,
    EventType.package_ready: DecisionPackage,
    EventType.human_decision_recorded: HumanDecision,
    EventType.question_selected: MissingQuestion,
    EventType.answer_received: UserAnswer,
    EventType.settings_updated: SettingsUpdated,
    EventType.document_registered: Document,
    EventType.run_failed: RunFailed,
}

EventPayload = (
    DecisionBrief
    | PhaseChanged
    | Scenario
    | PressureActivated
    | CandidatePlan
    | CandidateRejected
    | AgentStarted
    | AgentAssessment
    | AgentFailed
    | DependencyValidated
    | Impact
    | ConstraintResult
    | SimulationResult
    | FutureComparison
    | PortfolioComparison
    | BlastRadius
    | MitigationComparison
    | DecisionPackage
    | HumanDecision
    | MissingQuestion
    | UserAnswer
    | SettingsUpdated
    | Document
    | RunFailed
)


class Event(Strict):
    schema_version: SchemaVersion = SCHEMA_VERSION
    event_id: ID
    run_id: ID
    sequence: int = Field(ge=0)
    type: EventType
    actor: str
    scenario_id: ID | None = None
    future: Future | None = None
    timestamp: datetime
    payload: EventPayload

    # Payload models overlap structurally, so the type field picks the model before union validation.
    @model_validator(mode="before")
    @classmethod
    def resolve_payload(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("payload"), dict) and data.get("type") in EVENT_PAYLOADS:
            model = EVENT_PAYLOADS[EventType(data["type"])]
            data = {**data, "payload": model.model_validate(data["payload"])}
        return data

    @model_validator(mode="after")
    def check_payload_type(self) -> "Event":
        expected = EVENT_PAYLOADS[self.type]
        if type(self.payload) is not expected:
            raise ValueError(f"{self.type} expects a {expected.__name__} payload")
        return self


class EventLog(RootModel[list[Event]]):
    @model_validator(mode="after")
    def check_sequence(self) -> "EventLog":
        last: dict[str, int] = {}
        for event in self.root:
            if event.run_id in last and event.sequence <= last[event.run_id]:
                raise ValueError(f"sequence must strictly increase per run ({event.event_id})")
            last[event.run_id] = event.sequence
        return self


class RunState(Strict):
    schema_version: SchemaVersion = SCHEMA_VERSION
    run_id: ID
    decision_id: ID
    baseline_twin_version: str
    status: RunStatus
    scenario_ids: list[ID] = Field(default_factory=list)
    candidate_plan_ids: list[ID] = Field(default_factory=list)
    assessment_ids: list[ID] = Field(default_factory=list)
    result_ids: list[ID] = Field(default_factory=list)
    comparison_id: ID | None = None
    package_id: ID | None = None
    last_sequence: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
