from contracts_py.agents import AgentSpec
from contracts_py.enums import DecisionType, EntityType, Sensitivity
from contracts_py.twin import ALWAYS_ENABLED_AGENTS, CORE_AGENT_IDS

PROMPT_VERSION = "p1"
CHALLENGER = "challenger"
ALWAYS_RUN = ALWAYS_ENABLED_AGENTS

ALL = "all"
VENDOR = DecisionType.vendor_consolidation
CAPACITY = DecisionType.capacity_change
PROJECT = DecisionType.project_decision
INVESTMENT = DecisionType.investment

G, F, HR, C, S = Sensitivity.general, Sensitivity.finance, Sensitivity.hr, Sensitivity.customer, Sensitivity.security
NON_PERSON_TYPES = [t for t in EntityType if t is not EntityType.person_token]

# Which agents exist comes from contracts_py.CORE_AGENT_IDS; this table only adds each agent's details.
# agent_id: display name, department, sensitivity, routes, responsibilities
_DETAILS = {
    "finance": ("Finance", "dept_finance", [G, F], [ALL], "Savings, cash, margin and vendor contracts."),
    "engineering": ("Engineering", "dept_engineering", [G, S], [VENDOR, CAPACITY, PROJECT, INVESTMENT],
        "Platform reliability, security and delivery capacity."),
    "ai_data": ("AI and Data", "dept_ai_data", [G], [VENDOR, CAPACITY, PROJECT], "Data pipelines, models and feeds."),
    "operations": ("Operations", "dept_operations", [G], [t for t in DecisionType if t is not INVESTMENT],
        "Platform operations, billing and on-call."),
    "product": ("Product", "dept_product", [G], [CAPACITY, PROJECT, INVESTMENT], "Roadmap and customer-facing scope."),
    "marketing": ("Marketing", "dept_marketing", [G, C], [VENDOR, CAPACITY, INVESTMENT], "Demand and brand."),
    "sales": ("Sales", "dept_sales", [G, C], [VENDOR, CAPACITY, PROJECT], "Pipeline and customer contracts."),
    "customer_success": ("Customer Success", "dept_customer_success", [G, C], [VENDOR, CAPACITY, PROJECT],
        "Retention, support and onboarding."),
    "compliance": ("Compliance", "dept_compliance", [G, S], [ALL], "Controls, audits and regulatory frameworks."),
    "challenger": ("Challenger", None, [G], [ALL], "Challenges every assessment and the inaction future."),
    "people_knowledge": ("People and Knowledge", None, [G, HR],
        [CAPACITY, DecisionType.restructure, DecisionType.cost_reduction], "Knowledge concentration and succession."),
}

if set(_DETAILS) != set(CORE_AGENT_IDS):
    raise RuntimeError(f"roster details do not match CORE_AGENT_IDS: {sorted(set(_DETAILS) ^ set(CORE_AGENT_IDS))}")

ROSTER: dict[str, AgentSpec] = {
    agent_id: AgentSpec(
        agent_id=agent_id,
        display_name=name,
        department_id=department,
        responsibilities=[responsibilities],
        visible_entity_types=list(EntityType) if HR in sensitivity else NON_PERSON_TYPES,
        visible_sensitivity=sensitivity,
        routes_for=routes,
        prompt_version=PROMPT_VERSION,
    )
    for agent_id in CORE_AGENT_IDS
    for name, department, sensitivity, routes, responsibilities in [_DETAILS[agent_id]]
}
