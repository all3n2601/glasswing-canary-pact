from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from contracts_py.common import ID, SCHEMA_VERSION, USD, Ratio, SchemaVersion, Severity, Strict
from contracts_py.decision import DecisionBrief
from contracts_py.enums import Criticality, EvidenceSource, Future
from contracts_py.twin import Organization, OrganizationSettings, DepartmentProfile, DepartmentEdit
from contracts_py.events import Event
from contracts_py.engine import SimulationResult, BlastRadius

GraphLevel = Literal["entity", "domain"]
ReplaySpeed = Literal[1, 2, 4]


class HealthResponse(Strict):
    status: Literal["ok", "degraded"] = "ok"
    schema_version: SchemaVersion = SCHEMA_VERSION
    storage: Literal["file", "postgres"] = "file"
    storage_write_failures: int = Field(default=0, ge=0)
    engine_impl: Literal["stub", "real"] = "stub"
    twin_impl: Literal["stub", "real"] = "stub"


class DecisionCreated(Strict):
    run_id: ID


class DecisionPromptRequest(Strict):
    prompt: str = Field(min_length=10, max_length=4000)
    horizon_days: int = Field(default=365, gt=0, le=3650)


class DecisionDraft(Strict):
    brief: DecisionBrief
    matched_entity_ids: list[ID] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    assessing_department_ids: list[ID] = Field(default_factory=list)


class HumanDecisionRequest(Strict):
    decision: Literal["approve", "reject", "request_scenario"]
    # Ignored when sent: the server records the logged-in user.
    decided_by: str | None = None
    notes: str = ""
    package_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class QuickSimulateRequest(Strict):
    expected_twin_version: str | None = None
    brief: DecisionBrief
    # None means every candidate intervention in the brief.
    intervention_ids: list[ID] | None = None
    future: Future = Future.act_now


class QuickOfficePreview(Strict):
    baseline_twin_version: str
    result: SimulationResult
    blast_radius: BlastRadius


class FuturesRequest(Strict):
    brief: DecisionBrief
    intervention_ids: list[ID] | None = None
    # None means the futures listed on the brief.
    futures: list[Future] | None = None


class OptimizeRequest(Strict):
    brief: DecisionBrief


class ReplayInfo(Strict):
    name: str
    decision_id: ID | None = None
    event_count: int = Field(ge=0)


class ReplayStarted(Strict):
    run_id: ID
    name: str
    speed: ReplaySpeed


# Named apart from twin.DepartmentSummary so the generated schema and TypeScript names stay unqualified.
class OrganizationDepartmentSummary(Strict):
    department_id: ID
    name: str
    mission: str
    actual_fte: float = Field(ge=0)
    annual_budget_usd: USD = Field(ge=0)
    utilisation: float = Field(ge=0, le=1.5)
    maturity_level: Severity
    enabled: bool
    active: bool = True
    agent_id: ID | None = None


class OrganizationProfileView(Strict):
    twin_version: str | None = None
    schema_version: SchemaVersion = SCHEMA_VERSION
    organization: Organization
    departments: list[OrganizationDepartmentSummary]
    settings: OrganizationSettings


class DepartmentContextItemCreate(Strict):
    entity_type: Literal[
        "role", "knowledge_asset", "system", "project", "workflow", "kpi",
    ]
    name: str = Field(min_length=2, max_length=120)
    criticality: Criticality = Criticality.medium
    evidence_title: str = Field(min_length=2, max_length=160)
    evidence_source: EvidenceSource
    evidence_snippet: str = Field(min_length=10, max_length=300)
    annual_cost_usd: USD | None = Field(default=None, ge=0)
    capacity_fte: float | None = Field(default=None, ge=0)
    min_qualified_owners: int | None = Field(default=None, ge=0)
    documented_pct: Ratio | None = None
    failure_cost_per_day_usd: USD | None = Field(default=None, ge=0)
    completion_pct: Ratio | None = None
    remaining_cost_usd: USD | None = Field(default=None, ge=0)
    expected_completion_day: int | None = Field(default=None, ge=0)
    time_to_train_days: int | None = Field(default=None, ge=0)
    kpi_baseline: float | None = None
    kpi_unit: str | None = Field(default=None, max_length=40)
    higher_is_better: bool | None = None


EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class UserRole(StrEnum):
    viewer = "viewer"
    approver = "approver"


class SignupRequest(Strict):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(Strict):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(max_length=256)


class UserPublic(Strict):
    user_id: ID
    email: str
    display_name: str
    role: UserRole
    created_at: datetime


class AuthToken(Strict):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserPublic




class DepartmentSave(Strict):
    expected_twin_version: str
    department: DepartmentEdit


class RunEventPage(Strict):
    events: list[Event]
    next_sequence: int = Field(ge=0)
    has_more: bool
    terminal: bool


class OrganizationSave(Strict):
    expected_twin_version: str
    organization: Organization
    departments: list[DepartmentEdit]
    settings: OrganizationSettings
