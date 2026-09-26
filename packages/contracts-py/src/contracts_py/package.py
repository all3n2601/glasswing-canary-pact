import re
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from contracts_py.agents import Claim
from contracts_py.common import ID, SCHEMA_VERSION, Day, SchemaVersion, Strict
from contracts_py.decision import DecisionBrief, Operator
from contracts_py.engine import (
    BlastRadius,
    DepartmentImpactSummary,
    FutureComparison,
    Impact,
    ItemCounterfactual,
    MissingQuestion,
    MitigationComparison,
    PortfolioComparison,
)
from contracts_py.enums import Future
from contracts_py.twin import VersionInfo

# The lookbehind keeps ids such as dept_ops from matching; e_pt_07 still matches.
PERSON_TOKEN = re.compile(r"(?<![a-z0-9])pt_[a-z0-9]")


def find_person_tokens(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        if PERSON_TOKEN.search(value):
            found.append(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            found += find_person_tokens(key) + find_person_tokens(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            found += find_person_tokens(item)
    return found


class Recommendation(Strict):
    plan_id: ID
    future: Future
    result_id: ID
    headline: str
    claims: list[Claim] = Field(default_factory=list)


class ImplementationStep(Strict):
    order: int = Field(ge=1)
    day: Day
    action: str
    intervention_id: ID | None = None
    gate: str | None = None


class MonitorRule(Strict):
    metric: str
    entity_id: ID | None = None
    operator: Operator
    threshold: float
    action: Literal["watch", "pause", "rollback", "escalate"]
    description: str


class DecisionPackage(Strict):
    schema_version: SchemaVersion = SCHEMA_VERSION
    package_id: ID
    run_id: ID
    decision_id: ID
    versions: VersionInfo
    brief: DecisionBrief
    recommendation: Recommendation | None = None
    futures: FutureComparison
    portfolios: PortfolioComparison
    blast_radius_act_now: BlastRadius
    blast_radius_inaction: BlastRadius
    department_impacts: list[DepartmentImpactSummary] = Field(default_factory=list)
    critical_risks: list[Impact] = Field(default_factory=list)
    mitigations: list[MitigationComparison] = Field(default_factory=list)
    counterfactuals: list[ItemCounterfactual] = Field(default_factory=list)
    missing_information: list[MissingQuestion] = Field(default_factory=list)
    implementation: list[ImplementationStep] = Field(default_factory=list)
    monitoring: list[MonitorRule] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    missing_perspectives: list[ID] = Field(default_factory=list)
    status: Literal["awaiting_approval", "approved", "rejected", "another_scenario_requested"] = "awaiting_approval"
    created_at: datetime

    @model_validator(mode="after")
    def ethics_guard(self) -> "DecisionPackage":
        leaks = find_person_tokens(self.model_dump(mode="json"))
        if leaks:
            raise ValueError(f"person tokens must not appear in a decision package: {leaks[:5]}")
        return self


class HumanDecision(Strict):
    run_id: ID
    package_id: ID
    decision: Literal["approve", "reject", "request_scenario"]
    decided_by: str
    decided_at: datetime
    notes: str = ""
    package_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
