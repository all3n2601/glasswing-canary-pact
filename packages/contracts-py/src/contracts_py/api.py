from typing import Literal

from pydantic import Field

from contracts_py.common import ID, SCHEMA_VERSION, USD, SchemaVersion, Severity, Strict
from contracts_py.decision import DecisionBrief
from contracts_py.enums import Future
from contracts_py.twin import Organization, OrganizationSettings

GraphLevel = Literal["entity", "domain"]
ReplaySpeed = Literal[1, 2, 4]


class HealthResponse(Strict):
    status: Literal["ok"] = "ok"
    schema_version: SchemaVersion = SCHEMA_VERSION


class DecisionCreated(Strict):
    run_id: ID


class HumanDecisionRequest(Strict):
    decision: Literal["approve", "reject", "request_scenario"]
    decided_by: str
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


class OrganizationProfileView(Strict):
    schema_version: SchemaVersion = SCHEMA_VERSION
    organization: Organization
    departments: list[OrganizationDepartmentSummary]
    settings: OrganizationSettings
