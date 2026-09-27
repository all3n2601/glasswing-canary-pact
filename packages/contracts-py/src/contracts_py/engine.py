import math
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from contracts_py.common import ID, USD, Day, Ratio, Severity, Strict, prefixed
from contracts_py.decision import EngineMetric, Intervention, Operator
from contracts_py.enums import (
    ClaimStatus,
    Criticality,
    Direction,
    Future,
    ImpactCategory,
    ImpactLevel,
    MigrationDifficulty,
    Origin,
    OverlapDimension,
    Polarity,
    RiskLevel,
)


def _check_percentiles(p10: int | None, p50: int | None, p90: int | None) -> None:
    present = [p is not None for p in (p10, p50, p90)]
    if any(present) and not all(present):
        raise ValueError("p10, p50 and p90 must be all set or all null")
    if all(present) and not p10 <= p50 <= p90:  # type: ignore[operator]
        raise ValueError("expected p10 <= p50 <= p90")


class Impact(Strict):
    impact_id: ID
    decision_id: ID
    scenario_id: ID
    source_entity: ID
    source_kind: Literal["intervention", "pressure"]
    source_ref: ID
    affected_entity: ID
    affected_department: ID | None = None
    level: ImpactLevel
    category: ImpactCategory
    polarity: Polarity
    direction: Direction
    metric: str
    magnitude: float
    unit: str
    value_usd: USD | None = None
    severity: Severity
    first_effect_day: Day
    peak_effect_day: Day
    confidence: Ratio
    dependency_path: list[ID] = Field(default_factory=list)
    edge_path: list[ID] = Field(default_factory=list)
    evidence_refs: list[ID] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    constraint_refs: list[ID] = Field(default_factory=list)
    origin: Origin
    status: ClaimStatus

    @model_validator(mode="after")
    def check_ranges(self) -> "Impact":
        if self.peak_effect_day < self.first_effect_day:
            raise ValueError("peak_effect_day must be >= first_effect_day")
        if len(self.edge_path) != max(len(self.dependency_path) - 1, 0):
            raise ValueError("edge_path must be one shorter than dependency_path")
        return self


class WorkflowCoverage(Strict):
    workflow_id: ID
    criticality: Criticality
    owners_before: list[ID] = Field(default_factory=list)
    owners_after: list[ID] = Field(default_factory=list)
    min_qualified_owners: int = Field(ge=0)
    backup_count_after: int = Field(ge=0)
    documented_pct: Ratio
    stranded: bool
    reasons: list[str] = Field(default_factory=list)
    owner_capacity_fte_before: float | None = None
    owner_capacity_fte_after: float | None = None
    exception_documented_pct: Ratio | None = None
    automation_pct: Ratio | None = None
    training_days_required: int | None = None
    replacement_cost_usd: USD | None = None

    @model_validator(mode="after")
    def check_stranded(self) -> "WorkflowCoverage":
        if self.stranded != (len(self.owners_after) < self.min_qualified_owners):
            raise ValueError("stranded must equal len(owners_after) < min_qualified_owners")
        return self


class KnowledgeCoverage(Strict):
    knowledge_id: ID
    holders_before: list[ID] = Field(default_factory=list)
    holders_after: list[ID] = Field(default_factory=list)
    holder_capacity_fte_before: float = Field(ge=0)
    holder_capacity_fte_after: float = Field(ge=0)
    documented_pct: Ratio
    lost: bool
    dependent_workflow_ids: list[ID] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class VendorOverlap(Strict):
    vendor_a: ID
    vendor_b: ID
    dimensions: dict[OverlapDimension, Ratio]
    overall_overlap: Ratio
    shared_dataset_ids: list[ID] = Field(default_factory=list)
    unique_dataset_ids_a: list[ID] = Field(default_factory=list)
    unique_dataset_ids_b: list[ID] = Field(default_factory=list)
    migration_difficulty: MigrationDifficulty

    @model_validator(mode="after")
    def check_distinct_vendors(self) -> "VendorOverlap":
        if self.vendor_a == self.vendor_b:
            raise ValueError("vendor_a and vendor_b must differ")
        return self


class ValueBreakdown(Strict):
    gross_savings_usd: USD
    transition_cost_usd: USD
    added_cost_usd: USD
    rebound_cost_usd: USD
    expected_business_loss_usd: USD
    pressure_cost_usd: USD
    avoided_failure_cost_usd: USD
    net_value_usd: USD
    monthly_net_usd: list[USD] = Field(default_factory=list)
    p10_net_value_usd: USD | None = None
    p50_net_value_usd: USD | None = None
    p90_net_value_usd: USD | None = None
    # Optional detail the engine may report; not terms of the net value formula below.
    termination_cost_usd: USD | None = Field(
        default=None, ge=0, description="Contract termination fees paid to exit vendors or projects.")
    migration_cost_usd: USD | None = Field(
        default=None, ge=0, description="One-time cost of moving work or data onto a replacement.")
    displaced_work_cost_usd: USD | None = Field(
        default=None, ge=0, description="Cost of work pushed onto remaining teams by the change.")

    @model_validator(mode="after")
    def check_sums(self) -> "ValueBreakdown":
        expected = (
            self.gross_savings_usd
            - self.transition_cost_usd
            - self.added_cost_usd
            - self.rebound_cost_usd
            - self.expected_business_loss_usd
            - self.pressure_cost_usd
            + self.avoided_failure_cost_usd
        )
        if self.net_value_usd != expected:
            raise ValueError(f"net_value_usd {self.net_value_usd} does not equal components {expected}")
        if self.monthly_net_usd and self.monthly_net_usd[-1] != self.net_value_usd:
            raise ValueError("last monthly_net_usd value must equal net_value_usd")
        _check_percentiles(self.p10_net_value_usd, self.p50_net_value_usd, self.p90_net_value_usd)
        return self


class ConstraintResult(Strict):
    constraint_id: ID
    metric: EngineMetric
    operator: Operator
    threshold: float
    value: float
    hard: bool
    passed: bool
    explanation: str
    impact_ids: list[ID] = Field(default_factory=list)


class RiskComponents(Strict):
    financial: float = Field(ge=0)
    capability_workflow: float = Field(ge=0)
    customer_revenue: float = Field(ge=0)
    compliance_control: float = Field(ge=0)
    execution_uncertainty: float = Field(ge=0)


class RiskScore(Strict):
    score: float = Field(ge=0, le=100)
    level: RiskLevel
    settings_version: int = Field(ge=1)
    components: RiskComponents

    @model_validator(mode="after")
    def check_sum(self) -> "RiskScore":
        c = self.components
        total = c.financial + c.capability_workflow + c.customer_revenue + c.compliance_control + c.execution_uncertainty
        if not math.isclose(self.score, total, abs_tol=1e-6):
            raise ValueError(f"score {self.score} does not equal sum of components {total}")
        return self


class PressureTrigger(Strict):
    pressure_id: ID
    expected_events: float = Field(ge=0)
    expected_cost_usd: USD
    neutralised: bool


class SimulationResult(Strict):
    result_id: ID
    run_id: ID
    scenario_id: ID
    future: Future
    plan_id: ID | None = None
    mode: Literal["quick", "full"]
    seed: int | None = None
    intervention_ids: list[ID] = Field(default_factory=list)
    value: ValueBreakdown
    goal_met: bool
    constraint_results: list[ConstraintResult] = Field(default_factory=list)
    impacts: list[Impact] = Field(default_factory=list)
    workflow_coverage: list[WorkflowCoverage] = Field(default_factory=list)
    knowledge_coverage: list[KnowledgeCoverage] = Field(default_factory=list)
    pressures_triggered: list[PressureTrigger] = Field(default_factory=list)
    risk: RiskScore
    affected_department_ids: list[ID] = Field(default_factory=list)
    feasible: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    computed_at: datetime


class FutureRow(Strict):
    future: Future
    plan_id: ID | None = None
    result_id: ID
    label: str
    net_value_p50_usd: USD
    delta_vs_inaction_p10_usd: USD
    delta_vs_inaction_p50_usd: USD
    delta_vs_inaction_p90_usd: USD
    p_better_than_inaction: Ratio
    breakeven_day: Day | None = None
    cost_of_delay_usd: USD | None = None
    feasible: bool
    risk_score: float = Field(ge=0, le=100)
    monthly_delta_usd: list[USD] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_percentiles(self) -> "FutureRow":
        _check_percentiles(self.delta_vs_inaction_p10_usd, self.delta_vs_inaction_p50_usd, self.delta_vs_inaction_p90_usd)
        return self


class FutureComparison(Strict):
    comparison_id: prefixed("cmp_")
    decision_id: ID
    run_id: ID
    reference_result_id: ID
    rows: list[FutureRow]
    best_row_index: int | None = Field(default=None, ge=0)
    headline: str


class Portfolio(Strict):
    plan_id: ID
    intervention_ids: list[ID] = Field(default_factory=list)
    rank: int | None = Field(default=None, ge=1)
    result: SimulationResult


class PortfolioComparison(Strict):
    evaluated_count: int = Field(ge=0)
    naive: Portfolio
    recommended: Portfolio | None = None
    alternatives: list[Portfolio] = Field(default_factory=list)


class MitigationComparison(Strict):
    plan_id_before: ID
    plan_id_after: ID
    actions: list[Intervention]
    before: SimulationResult
    after: SimulationResult
    restored_entity_ids: list[ID] = Field(default_factory=list)
    changed_metrics: list[str] = Field(default_factory=list)
    feasible_before: bool
    feasible_after: bool


class BlastNode(Strict):
    node_id: ID
    kind: Literal["decision", "department", "entity", "pressure", "outcome"]
    department_id: ID | None = None
    entity_id: ID | None = None
    pressure_id: ID | None = None
    headline: str
    level: ImpactLevel | None = None
    category: ImpactCategory | None = None
    polarity: Polarity | None = None
    severity: Severity | None = None
    value_usd: USD | None = None
    first_effect_day: Day | None = None
    impact_ids: list[ID] = Field(default_factory=list)


class BlastEdge(Strict):
    source: ID
    target: ID
    label: str
    level: ImpactLevel | None = None
    critical_constraint: bool
    channel_id: ID | None = None


class DepartmentImpactSummary(Strict):
    department_id: ID
    headline: str
    polarity: Polarity
    severity: Severity
    impact_ids: list[ID] = Field(default_factory=list)


class CompanyOutcome(Strict):
    net_value_usd: USD
    risk_level: RiskLevel
    headline: str


class BlastRadius(Strict):
    run_id: ID
    scenario_id: ID
    future: Future
    plan_id: ID | None = None
    root_node_id: ID
    nodes: list[BlastNode] = Field(default_factory=list)
    edges: list[BlastEdge] = Field(default_factory=list)
    departments: list[DepartmentImpactSummary] = Field(default_factory=list)
    outcome: CompanyOutcome


class ItemCounterfactual(Strict):
    intervention_id: ID
    contribution_usd: USD
    net_value_without_usd: USD
    goal_still_met: bool
    verdict: Literal["keep", "drop", "borderline"]
    explanation: str


class MissingQuestion(Strict):
    question_id: ID
    text: str
    uncertain_input: str
    current_assumption: str
    answer_type: Literal["boolean", "number", "choice"]
    options: list[str] = Field(default_factory=list)
    changes_recommendation_if: str
    value_gap_usd: USD


class UserAnswer(Strict):
    question_id: ID
    value: bool | float | str
    answered_by: str
    answered_at: datetime
