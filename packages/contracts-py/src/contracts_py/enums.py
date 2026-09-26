from enum import StrEnum


class EntityType(StrEnum):
    department = "department"
    person_token = "person_token"
    role = "role"
    knowledge_asset = "knowledge_asset"
    system = "system"
    vendor = "vendor"
    project = "project"
    workflow = "workflow"
    control = "control"
    kpi = "kpi"
    customer_segment = "customer_segment"
    dataset = "dataset"


class Layer(StrEnum):
    people = "people"
    knowledge = "knowledge"
    system = "system"
    workflow = "workflow"
    control = "control"
    outcome = "outcome"
    org = "org"


LAYER_OF: dict[EntityType, Layer] = {
    EntityType.person_token: Layer.people,
    EntityType.role: Layer.people,
    EntityType.knowledge_asset: Layer.knowledge,
    EntityType.system: Layer.system,
    EntityType.vendor: Layer.system,
    EntityType.dataset: Layer.system,
    EntityType.workflow: Layer.workflow,
    EntityType.project: Layer.workflow,
    EntityType.control: Layer.control,
    EntityType.kpi: Layer.outcome,
    EntityType.customer_segment: Layer.outcome,
    EntityType.department: Layer.org,
}


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
    constraint = "constraint"
    budget = "budget"
    capability = "capability"
    signal = "signal"
    value = "value"


class Criticality(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Sensitivity(StrEnum):
    general = "general"
    finance = "finance"
    hr = "hr"
    customer = "customer"
    security = "security"


class EvidenceSource(StrEnum):
    contract = "contract"
    workflow_map = "workflow_map"
    system_ownership = "system_ownership"
    kpi_definition = "kpi_definition"
    runbook = "runbook"
    architecture_note = "architecture_note"
    activity_log = "activity_log"
    knowledge_matrix = "knowledge_matrix"
    policy = "policy"
    incident = "incident"
    finance_forecast = "finance_forecast"


class DecisionType(StrEnum):
    cost_reduction = "cost_reduction"
    vendor_consolidation = "vendor_consolidation"
    capacity_change = "capacity_change"
    project_decision = "project_decision"
    investment = "investment"
    restructure = "restructure"
    mixed = "mixed"


class InterventionKind(StrEnum):
    action = "action"
    mitigation = "mitigation"


class ActionType(StrEnum):
    assess_change = "assess_change"
    remove_vendor = "remove_vendor"
    reduce_capacity = "reduce_capacity"
    add_capacity = "add_capacity"
    remove_roles = "remove_roles"
    stop_project = "stop_project"
    start_project = "start_project"
    delay_project = "delay_project"
    invest = "invest"


class MitigationType(StrEnum):
    reassign_owner = "reassign_owner"
    document_runbook = "document_runbook"
    reassign_on_call = "reassign_on_call"
    add_replacement_feed = "add_replacement_feed"
    resequence_project = "resequence_project"
    retain_capacity_temporarily = "retain_capacity_temporarily"


class Future(StrEnum):
    act_now = "act_now"
    inaction = "inaction"
    delay = "delay"
    alternative = "alternative"


class PressureKind(StrEnum):
    cost_growth = "cost_growth"
    renewal_step = "renewal_step"
    hazard = "hazard"
    kpi_drift = "kpi_drift"
    budget_ceiling = "budget_ceiling"
    deadline = "deadline"


class ImpactLevel(StrEnum):
    direct = "direct"
    dependent = "dependent"
    second_order = "second_order"
    delayed = "delayed"
    feedback = "feedback"


class ImpactCategory(StrEnum):
    ownership = "ownership"
    technical = "technical"
    operational = "operational"
    business = "business"
    compliance = "compliance"
    financial = "financial"


class Polarity(StrEnum):
    benefit = "benefit"
    harm = "harm"


class Direction(StrEnum):
    increase = "increase"
    decrease = "decrease"
    no_change = "no_change"


class ClaimStatus(StrEnum):
    computed = "computed"
    validated = "validated"
    hypothesis = "hypothesis"
    rejected = "rejected"


class Origin(StrEnum):
    engine = "engine"
    agent = "agent"
    challenger = "challenger"
    user = "user"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Sector(StrEnum):
    technology_saas = "technology_saas"
    financial_services = "financial_services"
    banking = "banking"
    insurance = "insurance"
    healthcare = "healthcare"
    pharma_life_sciences = "pharma_life_sciences"
    manufacturing = "manufacturing"
    retail_ecommerce = "retail_ecommerce"
    telecom = "telecom"
    energy_utilities = "energy_utilities"
    logistics_transport = "logistics_transport"
    media_entertainment = "media_entertainment"
    professional_services = "professional_services"
    education = "education"
    public_sector = "public_sector"
    nonprofit = "nonprofit"
    other = "other"


class BusinessModel(StrEnum):
    b2b = "b2b"
    b2c = "b2c"
    b2b2c = "b2b2c"
    marketplace = "marketplace"
    public_service = "public_service"
    mixed = "mixed"


class SizeBand(StrEnum):
    startup = "startup"
    smb = "smb"
    mid_market = "mid_market"
    enterprise = "enterprise"
    large_enterprise = "large_enterprise"


class StrengthCategory(StrEnum):
    capability = "capability"
    expertise = "expertise"
    process = "process"
    asset = "asset"
    relationship = "relationship"
    data = "data"


class DocumentType(StrEnum):
    contract = "contract"
    policy = "policy"
    runbook = "runbook"
    sop = "sop"
    architecture_note = "architecture_note"
    org_chart = "org_chart"
    budget_report = "budget_report"
    financial_forecast = "financial_forecast"
    kpi_report = "kpi_report"
    incident_report = "incident_report"
    audit_report = "audit_report"
    workflow_map = "workflow_map"
    knowledge_matrix = "knowledge_matrix"
    meeting_minutes = "meeting_minutes"
    strategy_memo = "strategy_memo"
    other = "other"


class DocumentStatus(StrEnum):
    current = "current"
    outdated = "outdated"
    draft = "draft"
    archived = "archived"


class RiskAppetite(StrEnum):
    conservative = "conservative"
    balanced = "balanced"
    aggressive = "aggressive"


class OverlapDimension(StrEnum):
    record_coverage = "record_coverage"
    attribute_coverage = "attribute_coverage"
    geography = "geography"
    history_depth = "history_depth"
    freshness = "freshness"
    accuracy = "accuracy"
    permitted_use = "permitted_use"
    consumer_teams = "consumer_teams"
    downstream_workflows = "downstream_workflows"
    model_features = "model_features"
    substitutability = "substitutability"


class MigrationDifficulty(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class RunStatus(StrEnum):
    created = "created"
    validating = "validating"
    building_futures = "building_futures"
    running_agents = "running_agents"
    propagating = "propagating"
    challenging = "challenging"
    optimizing = "optimizing"
    comparing_futures = "comparing_futures"
    mitigating = "mitigating"
    generating_package = "generating_package"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"
