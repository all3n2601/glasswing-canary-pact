"""Company-twin domain models — Merged Schema v2.0.0.

Pydantic v2 is the source of truth; JSON Schema and TS types are generated from these.
See docs/CANARY_PACT_SCHEMA_v2_merged for the full spec. Owner: A (Twin/data).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --------------------------------------------------------------------------- enums


class EntityType(StrEnum):
    DEPARTMENT = "department"
    PERSON_TOKEN = "person_token"
    ROLE = "role"
    KNOWLEDGE_ASSET = "knowledge_asset"
    SYSTEM = "system"
    VENDOR = "vendor"
    PROJECT = "project"
    WORKFLOW = "workflow"
    CONTROL = "control"
    KPI = "kpi"
    CUSTOMER_SEGMENT = "customer_segment"
    DATASET = "dataset"


class Relation(StrEnum):
    OWNS = "OWNS"
    BACKS_UP = "BACKS_UP"
    KNOWS = "KNOWS"
    MAINTAINS = "MAINTAINS"
    RUNS = "RUNS"
    PROVIDES = "PROVIDES"
    CONSUMES = "CONSUMES"
    DEPENDS_ON = "DEPENDS_ON"
    SUPPORTS = "SUPPORTS"
    FUNDS = "FUNDS"
    CONTROLS = "CONTROLS"
    CONTRIBUTES_TO = "CONTRIBUTES_TO"
    SUBSTITUTES_FOR = "SUBSTITUTES_FOR"
    FLOWS_TO = "FLOWS_TO"


class ChannelKind(StrEnum):
    CONSTRAINT = "constraint"
    BUDGET = "budget"
    CAPABILITY = "capability"
    SIGNAL = "signal"
    VALUE = "value"


class Criticality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Sensitivity(StrEnum):
    GENERAL = "general"
    FINANCE = "finance"
    HR = "hr"
    CUSTOMER = "customer"
    SECURITY = "security"


class PressureKind(StrEnum):
    COST_GROWTH = "cost_growth"
    RENEWAL_STEP = "renewal_step"
    HAZARD = "hazard"
    KPI_DRIFT = "kpi_drift"
    BUDGET_CEILING = "budget_ceiling"
    DEADLINE = "deadline"


# --------------------------------------------------------------------------- twin models


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source_type: str
    document_id: str
    location: str | None = None
    snippet: str = Field(max_length=300)
    synthetic: bool = True


class VersionInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    twin_version: str
    settings_version: int
    prompt_version: str
    model_id: str
    engine_version: str
    created_at: str


class Entity(BaseModel):
    """Flat entity; the validator enforces required fields per type."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: EntityType
    name: str
    department_id: str | None = None
    criticality: Criticality = Criticality.MEDIUM
    sensitivity: Sensitivity = Sensitivity.GENERAL
    annual_cost_usd: int | None = Field(default=None, ge=0)
    one_time_exit_cost_usd: int | None = Field(default=None, ge=0)
    migration_cost_usd: int | None = Field(default=None, ge=0)
    capacity_fte: float | None = Field(default=None, ge=0)
    min_qualified_owners: int | None = Field(default=None, ge=0)
    documented_pct: float | None = Field(default=None, ge=0, le=1)
    failure_cost_per_day_usd: int | None = Field(default=None, ge=0)
    customer_facing: bool | None = None
    completion_pct: float | None = Field(default=None, ge=0, le=1)
    retires_entity_ids: list[str] = Field(default_factory=list)
    role_id: str | None = None
    kpi_baseline: float | None = None
    kpi_unit: str | None = None
    higher_is_better: bool | None = None
    mandatory: bool | None = None
    framework: str | None = None
    arr_usd: int | None = Field(default=None, ge=0)
    tags: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)

    _REQUIRED: dict[str, tuple[str, ...]] = {
        "department": ("annual_cost_usd", "capacity_fte"),
        "vendor": ("annual_cost_usd", "one_time_exit_cost_usd"),
        "system": ("annual_cost_usd", "failure_cost_per_day_usd"),
        "project": ("annual_cost_usd", "completion_pct"),
        "workflow": ("min_qualified_owners", "failure_cost_per_day_usd"),
        "role": ("annual_cost_usd", "capacity_fte"),
        "person_token": ("role_id",),
        "knowledge_asset": ("documented_pct",),
        "control": ("mandatory",),
        "kpi": ("kpi_baseline", "kpi_unit", "higher_is_better"),
        "customer_segment": ("arr_usd",),
    }

    @model_validator(mode="after")
    def _check_required(self) -> "Entity":
        for field in self._REQUIRED.get(self.type.value, ()):
            if getattr(self, field) is None:
                raise ValueError(f"{self.id} ({self.type}) missing required field {field}")
        if self.type not in (EntityType.DEPARTMENT,) and self.id != "kpi_company":
            if self.department_id is None:
                raise ValueError(f"{self.id} missing department_id")
        if self.type == EntityType.PERSON_TOKEN:
            if not self.id.startswith("pt_"):
                raise ValueError(f"person token {self.id} must use pt_ prefix")
            if self.sensitivity != Sensitivity.HR:
                raise ValueError(f"person token {self.id} must have hr sensitivity")
        return self


class Edge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source: str
    target: str
    relation: Relation
    label: str | None = None
    channel_kind: ChannelKind | None = None
    strength: float = Field(ge=0, le=1)
    strength_range: list[float]
    substitutability: float = Field(ge=0, le=1)
    lag_days: int = Field(default=0, ge=0)
    criticality: Criticality = Criticality.MEDIUM
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _checks(self) -> "Edge":
        lo, hi = self.strength_range
        if not (lo <= self.strength <= hi):
            raise ValueError(f"edge {self.id}: strength {self.strength} not in {self.strength_range}")
        if self.relation == Relation.FLOWS_TO and self.channel_kind is None:
            raise ValueError(f"FLOWS_TO edge {self.id} requires channel_kind")
        if self.criticality in (Criticality.HIGH, Criticality.CRITICAL) and not self.evidence_refs:
            raise ValueError(f"critical edge {self.id} requires evidence_refs")
        return self


class NeutraliserRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intervention_type: str
    target_entity_id: str


class Pressure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: PressureKind
    name: str
    target_entity_id: str
    start_day: int = Field(ge=0)
    end_day: int | None = None
    rate: float | None = None
    rate_range: list[float] | None = None
    step_pct: float | None = None
    monthly_probability: float | None = None
    probability_range: list[float] | None = None
    cost_per_event_usd: int | None = None
    capacity_sensitivity: float = Field(default=0.0, ge=0)
    threshold: float | None = None
    consequence_cost_usd: int | None = None
    neutralised_by: list[NeutraliserRef] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    description: str = ""


class DepartmentStrength(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    category: str
    level: int = Field(ge=1, le=5)
    supports_entity_ids: list[str] = Field(default_factory=list)
    key_role_ids: list[str] = Field(default_factory=list)
    concentration: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ev(self) -> "DepartmentStrength":
        if self.level >= 4 and not self.evidence_refs:
            raise ValueError(f"strength {self.id} level>=4 requires evidence_refs")
        return self


class StaffingStrength(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sanctioned_fte: float
    actual_fte: float
    contractors_fte: float
    open_positions: int
    attrition_rate_annual: float = Field(ge=0, le=1)
    avg_time_to_hire_days: int
    utilisation: float = Field(ge=0, le=1.5)


class DepartmentBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    annual_budget_usd: int
    spent_ytd_usd: int
    fixed_cost_pct: float = Field(ge=0, le=1)
    budget_owner_role_id: str | None = None


class DepartmentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department_id: str
    mission: str
    head_role_id: str | None = None
    agent_id: str | None = None
    staffing: StaffingStrength
    budget: DepartmentBudget
    strengths: list[DepartmentStrength] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    maturity_level: int = Field(ge=1, le=5)


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    doc_type: str
    department_id: str | None = None
    owner_role_id: str | None = None
    uri: str
    mime_type: str
    status: str
    sensitivity: Sensitivity = Sensitivity.GENERAL
    covers_entity_ids: list[str] = Field(default_factory=list)
    framework_refs: list[str] = Field(default_factory=list)
    summary: str
    synthetic: bool = True
    ingested: bool = False
    uploaded_at: str


class StrategicPriority(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    text: str
    rank: int
    kpi_ids: list[str] = Field(default_factory=list)


class Organization(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    legal_name: str
    display_name: str
    sector: str
    sub_sector: str | None = None
    secondary_sectors: list[str] = Field(default_factory=list)
    business_model: str
    size_band: str
    headquarters_country: str
    operating_regions: list[str] = Field(default_factory=list)
    annual_revenue_usd: int
    total_annual_budget_usd: int
    total_headcount_fte: float
    fiscal_year_start_month: int = Field(ge=1, le=12)
    regulatory_frameworks: list[str] = Field(default_factory=list)
    strategic_priorities: list[StrategicPriority] = Field(default_factory=list)
    description: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class Twin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str
    version: VersionInfo
    organization: Organization
    department_profiles: list[DepartmentProfile] = Field(default_factory=list)
    entities: list[Entity]
    edges: list[Edge]
    pressures: list[Pressure] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)

    def entity_map(self) -> dict[str, Entity]:
        return {e.id: e for e in self.entities}

    @model_validator(mode="after")
    def _integrity(self) -> "Twin":
        ids = {e.id for e in self.entities}
        if len(ids) != len(self.entities):
            raise ValueError("duplicate entity ids")
        doc_ids = {d.id for d in self.documents}
        ev_ids = {v.id for v in self.evidence}
        for ed in self.edges:
            if ed.source not in ids or ed.target not in ids:
                raise ValueError(f"edge {ed.id} references unknown entity")
            for r in ed.evidence_refs:
                if r not in ev_ids:
                    raise ValueError(f"edge {ed.id} references unknown evidence {r}")
        for v in self.evidence:
            if v.document_id not in doc_ids:
                raise ValueError(f"evidence {v.id} references unknown document")
        for pr in self.pressures:
            if pr.target_entity_id not in ids:
                raise ValueError(f"pressure {pr.id} references unknown entity")
        depts = {e.id for e in self.entities if e.type == EntityType.DEPARTMENT}
        prof = {p.department_id for p in self.department_profiles}
        if depts != prof:
            raise ValueError(f"department/profile mismatch: {depts ^ prof}")
        return self


# Backwards-compatible alias (loader/graph import this name)
CompanyTwin = Twin
