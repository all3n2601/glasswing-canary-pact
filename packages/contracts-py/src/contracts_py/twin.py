from datetime import date, datetime, timezone
from typing import Annotated, Literal

from pydantic import Field, model_validator

from contracts_py.common import (
    ID,
    SCHEMA_VERSION,
    USD,
    Day,
    Ratio,
    RoleID,
    SchemaVersion,
    Severity,
    Strict,
    max_words,
    prefixed,
)
from contracts_py.decision import Constraint, DepartmentEdit
from contracts_py.enums import (
    ActionType,
    BusinessModel,
    ChannelKind,
    Criticality,
    DocumentStatus,
    DocumentType,
    EntityType,
    EvidenceSource,
    Future,
    MitigationType,
    PressureKind,
    Relation,
    RiskAppetite,
    Sector,
    Sensitivity,
    SizeBand,
    StrengthCategory,
)

NonNegFloat = Annotated[float, Field(ge=0)]


class Evidence(Strict):
    id: prefixed("ev_")
    source_type: EvidenceSource
    document_id: ID
    location: str | None = None
    snippet: str = Field(max_length=300)
    synthetic: bool = True


class VersionInfo(Strict):
    twin_version: str
    settings_version: int = Field(ge=1)
    prompt_version: str
    model_id: str
    engine_version: str
    created_at: datetime
    as_of_date: date
    data_snapshot_id: str | None = None
    policy_version: str | None = None
    coefficient_version: str | None = None
    created_by: str | None = None


class Entity(Strict):
    id: ID
    type: EntityType
    name: str
    department_id: ID | None = None
    criticality: Criticality = Criticality.medium
    sensitivity: Sensitivity = Sensitivity.general
    annual_cost_usd: USD | None = None
    one_time_exit_cost_usd: USD | None = None
    migration_cost_usd: USD | None = None
    capacity_fte: NonNegFloat | None = None
    min_qualified_owners: int | None = Field(default=None, ge=0)
    documented_pct: Ratio | None = None
    failure_cost_per_day_usd: USD | None = None
    customer_facing: bool | None = None
    completion_pct: Ratio | None = None
    remaining_cost_usd: USD | None = None
    expected_completion_day: Day | None = None
    retires_entity_ids: list[ID] = Field(default_factory=list)
    role_id: RoleID | None = None
    kpi_baseline: float | None = None
    kpi_unit: str | None = None
    higher_is_better: bool | None = None
    mandatory: bool | None = None
    framework: str | None = None
    arr_usd: USD | None = None
    tags: list[str] = Field(default_factory=list)
    evidence_refs: list[ID] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)
    history_years: int | None = None
    freshness_days: int | None = None
    accuracy: Ratio | None = None
    permitted_uses: list[str] = Field(default_factory=list)
    retains_history_after_termination: bool | None = None
    attribute_group: str | None = None
    time_to_train_days: int | None = None
    replacement_cost_usd: USD | None = None
    exception_documented_pct: Ratio | None = None
    automation_pct: Ratio | None = None
    max_downtime_days: int | None = None
    aliases: list[str] = Field(default_factory=list)


class Edge(Strict):
    id: prefixed("ch_", "e_")
    source: ID
    target: ID
    relation: Relation
    label: str | None = None
    channel_kind: ChannelKind | None = None
    strength: Ratio
    # Filled with [s*0.7, min(1, s*1.3)] when omitted.
    strength_range: tuple[Ratio, Ratio] | None = None
    substitutability: Ratio
    lag_days: Day
    criticality: Criticality
    confidence: Ratio
    evidence_refs: list[ID] = Field(default_factory=list)
    extraction_method: Literal["seeded", "keyword", "zero_shot", "canary", "agent"] | None = None
    last_validated: date | None = None

    @model_validator(mode="after")
    def fill_strength_range(self) -> "Edge":
        if self.strength_range is None:
            self.strength_range = (self.strength * 0.7, min(1.0, self.strength * 1.3))
        low, high = self.strength_range
        if not low <= self.strength <= high:
            raise ValueError("strength_range must contain strength")
        return self


class NeutraliserRef(Strict):
    intervention_type: ActionType | MitigationType
    target_entity_id: ID


class Pressure(Strict):
    id: prefixed("pr_")
    kind: PressureKind
    name: str
    target_entity_id: ID
    start_day: Day = 0
    end_day: Day | None = None
    rate: float | None = None
    rate_range: tuple[float, float] | None = None
    step_pct: float | None = None
    monthly_probability: Ratio | None = None
    probability_range: tuple[Ratio, Ratio] | None = None
    cost_per_event_usd: USD | None = None
    capacity_sensitivity: NonNegFloat = 0.0
    threshold: float | None = None
    consequence_cost_usd: USD | None = None
    neutralised_by: list[NeutraliserRef] = Field(default_factory=list)
    evidence_refs: list[ID] = Field(default_factory=list)
    description: str


class StrategicPriority(Strict):
    id: ID
    text: str
    rank: int = Field(ge=1)
    kpi_ids: list[ID] = Field(default_factory=list)


class Organization(Strict):
    id: prefixed("org_")
    legal_name: str
    display_name: str
    sector: Sector
    sub_sector: str | None = None
    secondary_sectors: list[Sector] = Field(default_factory=list)
    business_model: BusinessModel
    size_band: SizeBand
    headquarters_country: str
    operating_regions: list[str] = Field(default_factory=list)
    annual_revenue_usd: USD = Field(ge=0)
    total_annual_budget_usd: USD = Field(ge=0)
    total_headcount_fte: NonNegFloat
    fiscal_year_start_month: int = Field(ge=1, le=12)
    regulatory_frameworks: list[str] = Field(default_factory=list)
    strategic_priorities: list[StrategicPriority] = Field(default_factory=list)
    description: str
    evidence_refs: list[ID] = Field(default_factory=list)


class StaffingStrength(Strict):
    sanctioned_fte: NonNegFloat
    actual_fte: NonNegFloat
    contractors_fte: NonNegFloat
    open_positions: int = Field(ge=0)
    attrition_rate_annual: Ratio
    avg_time_to_hire_days: Day
    utilisation: float = Field(ge=0, le=1.5)


class DepartmentBudget(Strict):
    annual_budget_usd: USD = Field(ge=0)
    spent_ytd_usd: USD = Field(ge=0)
    fixed_cost_pct: Ratio
    budget_owner_role_id: RoleID | None = None


class DepartmentStrength(Strict):
    id: prefixed("str_")
    name: str
    category: StrengthCategory
    level: Severity
    supports_entity_ids: list[ID] = Field(default_factory=list)
    key_role_ids: list[RoleID] = Field(default_factory=list)
    concentration: Ratio
    evidence_refs: list[ID] = Field(default_factory=list)


class DepartmentGap(Strict):
    id: prefixed("gap_")
    name: str
    category: StrengthCategory
    severity: Severity
    affected_entity_ids: list[ID] = Field(default_factory=list)
    evidence_refs: list[ID] = Field(default_factory=list)


class DepartmentProfile(Strict):
    active: bool = True
    department_id: ID
    mission: str
    head_role_id: RoleID | None = None
    agent_id: ID | None = None
    staffing: StaffingStrength
    budget: DepartmentBudget
    strengths: list[DepartmentStrength] = Field(min_length=1)
    gaps: list[DepartmentGap] = Field(default_factory=list)
    maturity_level: Severity
    owned_entity_ids: list[ID] = Field(default_factory=list)
    critical_workflow_ids: list[ID] = Field(default_factory=list)
    kpi_ids: list[ID] = Field(default_factory=list)
    document_ids: list[ID] = Field(default_factory=list)
    documentation_coverage: Ratio = 0.0


class Document(Strict):
    id: prefixed("doc_")
    title: str
    doc_type: DocumentType
    department_id: ID | None = None
    owner_role_id: RoleID | None = None
    uri: str
    mime_type: str
    status: DocumentStatus
    version: str | None = None
    last_reviewed: date | None = None
    review_cycle_days: int | None = Field(default=None, gt=0)
    sensitivity: Sensitivity = Sensitivity.general
    covers_entity_ids: list[ID] = Field(default_factory=list)
    framework_refs: list[str] = Field(default_factory=list)
    summary: Annotated[str, max_words(60)]
    page_count: int | None = Field(default=None, ge=0)
    checksum_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    synthetic: bool = True
    ingested: bool = False
    uploaded_at: datetime


class Twin(Strict):
    organization_settings: "OrganizationSettings | None" = None
    schema_version: SchemaVersion = SCHEMA_VERSION
    version: VersionInfo
    organization: Organization
    department_profiles: list[DepartmentProfile] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    pressures: list[Pressure] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class DepartmentSummary(Strict):
    department_id: ID
    mission: str
    strength_names: list[str] = Field(default_factory=list)
    staffing: StaffingStrength


class AgentView(Strict):
    agent_id: ID
    twin_version: str
    organization: Organization
    department_profile: DepartmentProfile | None = None
    other_department_summaries: list[DepartmentSummary] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    pressures: list[Pressure] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    redacted_entity_count: int = Field(default=0, ge=0)


class RiskLevelThresholds(Strict):
    medium: float = 25
    high: float = 50
    critical: float = 75

    @model_validator(mode="after")
    def check_increasing(self) -> "RiskLevelThresholds":
        if not 0 < self.medium < self.high < self.critical <= 100:
            raise ValueError("risk level thresholds must be strictly increasing within 0-100")
        return self


class RiskWeights(Strict):
    financial: float = Field(default=25, ge=0)
    capability_workflow: float = Field(default=25, ge=0)
    customer_revenue: float = Field(default=20, ge=0)
    compliance_control: float = Field(default=20, ge=0)
    execution_uncertainty: float = Field(default=10, ge=0)

    @model_validator(mode="after")
    def check_sum(self) -> "RiskWeights":
        total = (
            self.financial
            + self.capability_workflow
            + self.customer_revenue
            + self.compliance_control
            + self.execution_uncertainty
        )
        if abs(total - 100) > 1e-6:
            raise ValueError(f"risk weights must sum to 100, got {total}")
        return self


ALWAYS_ENABLED_AGENTS = ("finance", "compliance", "challenger")
CORE_AGENT_IDS = (
    "finance",
    "engineering",
    "ai_data",
    "operations",
    "product",
    "marketing",
    "sales",
    "customer_success",
    "compliance",
    "challenger",
    "people_knowledge",
)


class OrganizationSettings(Strict):
    settings_id: ID = "set_default"
    organization_id: ID | None = None
    settings_version: int = Field(default=1, ge=1)
    updated_by: str = "system"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    display_currency: str = "USD"
    money_display_scale: Literal["auto", "K", "M", "B"] = "auto"
    timezone: str = "UTC"
    locale: str = "en-US"
    default_horizon_days: int = Field(default=365, gt=0)
    default_futures: list[Future] = Field(default_factory=lambda: [Future.act_now, Future.inaction, Future.delay])
    default_delay_days: Day = 90
    mc_samples: int = Field(default=1000, ge=200, le=5000)
    default_seed: int = 42
    propagation_max_hops: int = Field(default=4, ge=1, le=6)
    min_impact_threshold: Ratio = 0.02
    risk_appetite: RiskAppetite = RiskAppetite.balanced
    risk_level_thresholds: RiskLevelThresholds = Field(default_factory=RiskLevelThresholds)
    risk_weights: RiskWeights = Field(default_factory=RiskWeights)
    optimizer_objective: Literal["max_net_value", "min_risk", "balanced"] = "max_net_value"
    default_constraints: list[Constraint] = Field(default_factory=list)
    always_protected_entity_ids: list[ID] = Field(default_factory=list)
    require_human_approval: Literal[True] = True
    anonymize_people: Literal[True] = True
    enabled_agent_ids: list[ID] = Field(default_factory=lambda: list(CORE_AGENT_IDS))
    llm_mode: Literal["live"] = "live"
    model_id_strong: str | None = None
    model_id_fast: str | None = None
    max_tool_calls: int = Field(default=3, ge=0, le=5)
    temperature: float = Field(default=0.4, ge=0, le=2)
    agent_timeout_seconds: int = Field(default=45, gt=0)
    doc_staleness_days: int = Field(default=365, gt=0)
    required_doc_types_per_workflow: list[DocumentType] = Field(
        default_factory=lambda: [DocumentType.runbook, DocumentType.sop]
    )
    sector_preset_id: ID | None = None

    @model_validator(mode="after")
    def keep_required_agents(self) -> "OrganizationSettings":
        missing = [a for a in ALWAYS_ENABLED_AGENTS if a not in self.enabled_agent_ids]
        if missing:
            self.enabled_agent_ids = [*self.enabled_agent_ids, *missing]
        return self


class SectorPreset(Strict):
    id: prefixed("preset_")
    sector: Sector
    mandatory_frameworks: list[str] = Field(default_factory=list)
    default_constraints: list[Constraint] = Field(default_factory=list)
    risk_weights: RiskWeights | None = None
    pressure_templates: list[Pressure] = Field(default_factory=list)
    typical_departments: list[str] = Field(default_factory=list)


class ValidationIssue(Strict):
    rule: int | str
    severity: Literal["error", "warning"]
    message: str
    ids: list[ID] = Field(default_factory=list)


class DomainGraph(Strict):
    nodes: list[Entity] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)


class DepartmentDetail(Strict):
    entity: Entity
    profile: DepartmentProfile
    owned_entities: list[Entity] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)
    channels_in: list[Edge] = Field(default_factory=list)
    channels_out: list[Edge] = Field(default_factory=list)


Twin.model_rebuild()
