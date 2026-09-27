from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from contracts_py.common import ID, SCHEMA_VERSION, USD, SchemaVersion, Severity, Strict
from contracts_py.decision import DecisionBrief
from contracts_py.enums import Future
from contracts_py.twin import Organization, OrganizationSettings

GraphLevel = Literal["entity", "domain"]


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
    brief: DecisionBrief
    # None means every candidate intervention in the brief.
    intervention_ids: list[ID] | None = None
    future: Future = Future.act_now


class FuturesRequest(Strict):
    brief: DecisionBrief
    intervention_ids: list[ID] | None = None
    # None means the futures listed on the brief.
    futures: list[Future] | None = None


class OptimizeRequest(Strict):
    brief: DecisionBrief


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


class OrganizationProfileView(Strict):
    schema_version: SchemaVersion = SCHEMA_VERSION
    organization: Organization
    departments: list[OrganizationDepartmentSummary]
    settings: OrganizationSettings


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
