from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EntityKind(StrEnum):
    DEPARTMENT = "department"
    VENDOR = "vendor"
    DATASET = "dataset"
    WORKFLOW = "workflow"
    EMPLOYEE = "employee"
    SYSTEM = "system"
    KPI = "kpi"


class Entity(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    kind: EntityKind
    name: str
    department_id: str | None = None
    annual_cost: float | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Dependency(BaseModel):
    source: str
    target: str
    relationship: str
    importance: float = Field(ge=0, le=1)
    substitutability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    evidence: str


class CompanyTwin(BaseModel):
    id: str
    name: str
    version: str
    entities: list[Entity]
    dependencies: list[Dependency]

    def entity_map(self) -> dict[str, Entity]:
        return {entity.id: entity for entity in self.entities}

