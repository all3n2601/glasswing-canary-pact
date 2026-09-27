from canary_api.stubs import engine as stub_engine
from contracts_py.enums import DecisionType
from contracts_py.twin import CORE_AGENT_IDS, OrganizationSettings

from agent_orchestration.roster import ROSTER
from agent_orchestration.router import route_agents, routing_sources


def test_roster_follows_contract_agent_ids() -> None:
    assert tuple(ROSTER) == CORE_AGENT_IDS
    assert ROSTER["people_knowledge"].routes_for == ["capacity_change", "restructure", "cost_reduction"]
    assert ROSTER["people_knowledge"].visible_sensitivity == ["general", "hr"]
    assert ROSTER["operations"].routes_for == [t for t in DecisionType if t is not DecisionType.investment]
    assert "person_token" not in ROSTER["finance"].visible_entity_types


def test_routing_sources_are_intervention_and_pressure_targets(brief, twin) -> None:
    sources = routing_sources(brief, twin)
    targets = [i.target_entity_id for i in brief.candidate_interventions]
    active = [p.target_entity_id for p in twin.pressures if p.id in (brief.active_pressure_ids or [])]
    inactive = {p.target_entity_id for p in twin.pressures if p.id not in (brief.active_pressure_ids or [])}
    assert sources[:len(targets)] == targets
    assert set(sources) == set(targets) | set(active)
    assert inactive - set(targets) - set(active) and not (inactive - set(targets) - set(active)) & set(sources)


def test_route_uses_reachability_and_types(brief, people_brief, twin, settings) -> None:
    reachable = set(stub_engine.reachable_departments(twin, routing_sources(brief, twin)))
    routed = route_agents(brief, twin=twin, engine=stub_engine, settings=settings)
    # Vendor brief. Challenger runs later; product and people_knowledge do not route for vendor consolidation.
    assert routed == ["finance", "engineering", "ai_data", "operations", "sales", "compliance"]
    # marketing and customer_success match the decision type but their departments are not reachable.
    assert {"dept_marketing", "dept_customer_success"}.isdisjoint(reachable)
    assert "vendor_consolidation" in ROSTER["marketing"].routes_for and "marketing" not in routed
    assert "vendor_consolidation" not in ROSTER["product"].routes_for and "product" not in routed

    restructure = route_agents(people_brief, twin=twin, engine=stub_engine, settings=settings)
    assert "people_knowledge" in restructure and "marketing" not in restructure


def test_route_respects_enabled_agents_but_keeps_mandatory(brief, twin) -> None:
    settings = OrganizationSettings(llm_mode="mock", enabled_agent_ids=["engineering"])
    routed = route_agents(brief, twin=twin, engine=stub_engine, settings=settings)
    assert routed == ["finance", "engineering", "compliance"]


def test_route_skips_type_mismatch(brief, twin, settings) -> None:
    investment = brief.model_copy(update={"decision_type": DecisionType.investment, "candidate_interventions": []})
    routed = route_agents(investment, twin=twin, engine=stub_engine, settings=settings)
    assert "operations" not in routed and "engineering" in routed
