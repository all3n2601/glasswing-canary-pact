from canary_api.stubs import engine as stub_engine
from contracts_py.enums import DecisionType
from contracts_py.twin import OrganizationSettings

from agent_orchestration.roster import ROSTER
from agent_orchestration.router import route_agents, routing_sources


def test_roster_has_eleven_specs() -> None:
    assert len(ROSTER) == 11
    assert ROSTER["people_knowledge"].visible_sensitivity == ["general", "hr"]
    assert ROSTER["operations"].routes_for == [t for t in DecisionType if t is not DecisionType.investment]
    assert "person_token" not in ROSTER["finance"].visible_entity_types


def test_routing_sources_are_intervention_and_pressure_targets(brief, twin) -> None:
    sources = routing_sources(brief, twin)
    assert {"dept_operations", "vendor_auditlog", "sys_cloud_platform", "wf_billing_recon"} <= set(sources)


def test_route_uses_reachability_and_types(brief, twin, settings) -> None:
    routed = route_agents(brief, twin=twin, engine=stub_engine, settings=settings)
    # Stub reachability: compliance, engineering, finance, operations. Challenger runs later.
    assert routed == ["finance", "engineering", "operations", "compliance"]


def test_route_respects_enabled_agents_but_keeps_mandatory(brief, twin) -> None:
    settings = OrganizationSettings(llm_mode="mock", enabled_agent_ids=["engineering"])
    routed = route_agents(brief, twin=twin, engine=stub_engine, settings=settings)
    assert routed == ["finance", "engineering", "compliance"]


def test_route_skips_type_mismatch(brief, twin, settings) -> None:
    investment = brief.model_copy(update={"decision_type": DecisionType.investment, "candidate_interventions": []})
    routed = route_agents(investment, twin=twin, engine=stub_engine, settings=settings)
    assert "operations" not in routed and "engineering" in routed
