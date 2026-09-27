from datetime import datetime
from typing import Any, Literal, get_args

from pydantic import Field, model_validator

from contracts_py.common import ID, SCHEMA_VERSION, USD, Day, RoleID, SchemaVersion, Strict, prefixed
from contracts_py.enums import ActionType, DecisionType, Future, InterventionKind, MitigationType

EngineMetric = Literal[
    "annual_savings_usd",
    "net_value_usd",
    "revenue_impact_pct",
    "customer_impact_pct",
    "compliance_controls_broken",
    "stranded_workflows",
    "critical_systems_degraded",
    "max_capacity_loss_pct",
    "critical_coverage_pct",
]
ENGINE_METRICS: tuple[str, ...] = get_args(EngineMetric)

Operator = Literal["<=", ">=", "=="]

AMOUNT_PCT_REQUIRED = {ActionType.reduce_capacity, ActionType.add_capacity, MitigationType.retain_capacity_temporarily}
AMOUNT_USD_REQUIRED = {ActionType.invest, ActionType.start_project}


class Goal(Strict):
    metric: str
    target: float
    unit: str = "usd"
    basis: Literal["gross", "net"] = "gross"
    direction: Literal["at_least", "at_most"] = "at_least"


class Constraint(Strict):
    id: ID
    metric: EngineMetric
    operator: Operator
    threshold: float
    unit: str
    hard: bool
    scope_entity_id: ID | None = None
    description: str


class Intervention(Strict):
    id: ID
    kind: InterventionKind
    type: ActionType | MitigationType
    target_entity_id: ID
    amount_pct: float | None = Field(default=None, ge=0, le=100)
    amount_usd: USD | None = None
    start_day: Day = 0
    duration_days: Day | None = None
    one_time_cost_usd: USD = Field(default=0, ge=0)
    new_owner_id: RoleID | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    rationale: str

    @model_validator(mode="after")
    def check_rule_6(self) -> "Intervention":
        expected = ActionType if self.kind is InterventionKind.action else MitigationType
        if not isinstance(self.type, expected):
            raise ValueError(f"type {self.type} does not match kind {self.kind}")
        if self.type in AMOUNT_PCT_REQUIRED and self.amount_pct is None:
            raise ValueError(f"amount_pct is required for {self.type}")
        if self.type in AMOUNT_USD_REQUIRED and self.amount_usd is None:
            raise ValueError(f"amount_usd is required for {self.type}")
        if self.kind is InterventionKind.mitigation and "one_time_cost_usd" not in self.model_fields_set:
            raise ValueError("mitigations must set one_time_cost_usd")
        return self


class DepartmentEdit(Strict):
    department_id: ID
    name: str = Field(min_length=2, max_length=80)
    mission: str = Field(min_length=2, max_length=500)
    actual_fte: float = Field(ge=0)
    annual_budget_usd: USD = Field(ge=0)
    utilisation: float = Field(default=0, ge=0, le=1.5)
    active: bool = True
    agent_id: ID | None = None
    assumption: str = Field(min_length=10, max_length=300)


class OrganizationChange(Strict):
    intervention_id: ID
    operation: Literal["create", "close", "transfer"]
    department_id: ID
    new_department: DepartmentEdit | None = None
    destination_department_id: ID | None = None
    workflow_ids: list[ID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_operation(self) -> "OrganizationChange":
        if self.operation == "create" and (self.new_department is None or self.new_department.department_id != self.department_id):
            raise ValueError("Creation needs a matching department declaration")
        if self.operation == "transfer" and (not self.destination_department_id or not self.workflow_ids):
            raise ValueError("Transfer needs a destination and explicit workflow IDs")
        if self.destination_department_id == self.department_id:
            raise ValueError("Transfer destination must differ from the source")
        return self


class DecisionBrief(Strict):
    schema_version: SchemaVersion = SCHEMA_VERSION
    decision_id: prefixed("dec_")
    decision_type: DecisionType
    title: str
    statement: str
    goal: Goal
    horizon_days: int = Field(default=365, gt=0)
    candidate_interventions: list[Intervention]
    organization_changes: list[OrganizationChange] = Field(default_factory=list)
    protected_entity_ids: list[ID] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    futures: list[Future] = Field(default_factory=lambda: [Future.act_now, Future.inaction, Future.delay])
    delay_days: Day = 90
    # None means every pressure in the twin is active.
    active_pressure_ids: list[ID] | None = None
    seed: int = 42
    mc_samples: int = Field(default=1000, ge=1)
    created_by: str

    @model_validator(mode="after")
    def check_rule_5(self) -> "DecisionBrief":
        intervention_ids = {i.id for i in self.candidate_interventions}
        if any(c.intervention_id not in intervention_ids for c in self.organization_changes):
            raise ValueError("Organization changes must reference candidate interventions")
        if len({c.intervention_id for c in self.organization_changes}) != len(self.organization_changes):
            raise ValueError("Only one organization change is permitted per intervention")
        protected = set(self.protected_entity_ids)
        if any(c.department_id in protected or c.destination_department_id in protected or protected.intersection(c.workflow_ids) for c in self.organization_changes):
            raise ValueError("Organization change targets a protected entity")
        targeted = sorted({i.target_entity_id for i in self.candidate_interventions} & protected)
        if targeted:
            raise ValueError(f"protected entities targeted by interventions: {targeted}")
        constraint_ids = [c.id for c in self.constraints]
        if len(constraint_ids) != len(set(constraint_ids)):
            raise ValueError("constraint ids must be unique")
        if Future.inaction not in self.futures:
            self.futures = [*self.futures, Future.inaction]
        return self


class CandidatePlan(Strict):
    plan_id: ID
    label: str
    intervention_ids: list[ID]
    source: Literal["naive", "enumerated", "optimizer", "agent", "user", "mitigated"]
    parent_plan_id: ID | None = None


class Scenario(Strict):
    scenario_id: ID
    run_id: ID
    future: Future
    plan_id: ID | None = None
    delay_days: Day
    baseline_twin_version: str
    created_at: datetime

    @model_validator(mode="after")
    def check_rule_7(self) -> "Scenario":
        if self.plan_id is None and self.future is not Future.inaction:
            raise ValueError("only the inaction scenario may have no plan")
        return self
