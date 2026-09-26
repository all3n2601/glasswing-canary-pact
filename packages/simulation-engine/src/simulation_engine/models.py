from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ImpactLevel(StrEnum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    SECOND_ORDER = "second_order"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScenarioRequest(BaseModel):
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    remove_entity_ids: list[str] = Field(default_factory=list)
    savings_target: float = Field(default=0, ge=0)
    constraints: dict[str, Any] = Field(default_factory=dict)


class Impact(BaseModel):
    entity_id: str
    department: str
    description: str
    level: ImpactLevel
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    path: list[str]


class ScenarioResult(BaseModel):
    scenario_id: str
    status: str
    gross_savings: float
    transition_cost: float
    net_savings: float
    impacts: list[Impact]
    violations: list[str]
    recommendation: str

