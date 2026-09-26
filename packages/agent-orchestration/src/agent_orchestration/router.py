from contracts_py.decision import DecisionBrief
from contracts_py.enums import ActionType, DecisionType
from contracts_py.twin import OrganizationSettings, Twin

from agent_orchestration.ports import EnginePort
from agent_orchestration.roster import ALL, ALWAYS_RUN, CHALLENGER, ROSTER

ROUTING_HOPS = 4

# A cost_reduction brief made of vendor, capacity and project cuts also concerns the agents routed for those types.
ACTION_DECISION_TYPE = {
    ActionType.remove_vendor: DecisionType.vendor_consolidation,
    ActionType.reduce_capacity: DecisionType.capacity_change,
    ActionType.add_capacity: DecisionType.capacity_change,
    ActionType.remove_roles: DecisionType.capacity_change,
    ActionType.stop_project: DecisionType.project_decision,
    ActionType.start_project: DecisionType.project_decision,
    ActionType.delay_project: DecisionType.project_decision,
    ActionType.invest: DecisionType.investment,
}


def decision_types(brief: DecisionBrief) -> set[DecisionType]:
    types = {brief.decision_type}
    types |= {ACTION_DECISION_TYPE[i.type] for i in brief.candidate_interventions if i.type in ACTION_DECISION_TYPE}
    return types


def routing_sources(brief: DecisionBrief, twin: Twin) -> list[str]:
    active = brief.active_pressure_ids
    pressures = [p for p in twin.pressures if active is None or p.id in active]
    sources = [i.target_entity_id for i in brief.candidate_interventions] + [p.target_entity_id for p in pressures]
    return list(dict.fromkeys(sources))


def route_agents(brief: DecisionBrief, *, twin: Twin, engine: EnginePort, settings: OrganizationSettings) -> list[str]:
    """First-pass agents in roster order; the challenger runs later in its own phase."""
    reachable = set(engine.reachable_departments(twin, routing_sources(brief, twin), ROUTING_HOPS))
    types = decision_types(brief)
    enabled = set(settings.enabled_agent_ids) | set(ALWAYS_RUN)
    routed = []
    for agent_id, spec in ROSTER.items():
        if agent_id == CHALLENGER or agent_id not in enabled:
            continue
        if agent_id in ALWAYS_RUN:
            routed.append(agent_id)
            continue
        type_match = ALL in spec.routes_for or bool(types & set(spec.routes_for))
        department_match = spec.department_id in reachable if spec.department_id else bool(reachable)
        if type_match and department_match:
            routed.append(agent_id)
    return routed
