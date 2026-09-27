"""Intervention operators (plan C-01; schema v2.2.0 section 6.4): every ActionType edits only the clone."""

from __future__ import annotations

import pytest
from contracts_py.decision import Intervention
from contracts_py.enums import ActionType, Criticality, EntityType, InterventionKind, MitigationType, Relation
from contracts_py.twin import Edge

from company_twin import clone_with_edges, entity_map, load_twin
from company_twin.loader import default_fixture_path
from simulation_engine import apply_interventions, capacity_percentage

TWIN = load_twin(default_fixture_path())


def action(action_type: ActionType, target: str, **fields) -> Intervention:
    return Intervention(id=f"act_{action_type.value}", kind=InterventionKind.action, type=action_type,
                        target_entity_id=target, rationale="test", **fields)


ALL_ACTIONS = [
    action(ActionType.assess_change, "vendor_apex"),
    action(ActionType.remove_vendor, "vendor_echo", start_day=30),
    action(ActionType.reduce_capacity, "dept_marketing", amount_pct=10),
    action(ActionType.add_capacity, "role_sre", amount_pct=50),
    action(ActionType.remove_roles, "role_billing_ops_lead"),
    action(ActionType.stop_project, "proj_billing_modernization"),
    action(ActionType.start_project, "proj_soc2_type2", amount_usd=1_000_000),
    action(ActionType.invest, "sys_data_pipeline", amount_usd=2_000_000, amount_pct=20),
    action(ActionType.delay_project, "proj_soc2_type2", duration_days=60),
]


def test_every_action_type_is_covered():
    assert {a.type for a in ALL_ACTIONS} == set(ActionType)


def test_baseline_is_unchanged_by_every_operator():
    before = TWIN.model_dump_json()
    applied = apply_interventions(TWIN, ALL_ACTIONS)
    assert TWIN.model_dump_json() == before
    assert applied.twin is not TWIN
    assert applied.twin.model_dump_json() != before


def test_remove_vendor_saves_its_cost_and_charges_exit_and_migration():
    echo = entity_map(TWIN)["vendor_echo"]
    applied = apply_interventions(TWIN, [action(ActionType.remove_vendor, "vendor_echo", start_day=30)])
    assert applied.gross_savings_usd == echo.annual_cost_usd == 1_100_000_000
    assert applied.transition_cost_usd == echo.one_time_exit_cost_usd + echo.migration_cost_usd
    assert entity_map(applied.twin)["vendor_echo"].annual_cost_usd == 0
    assert applied.losses["vendor_echo"].magnitude == 1.0
    assert applied.losses["vendor_echo"].start_day == 30


def test_remove_roles_sets_fte_to_zero_and_drops_person_token_edges():
    role_id = "role_billing_ops_lead"
    token = next(e for e in TWIN.entities if e.type is EntityType.person_token and e.role_id == role_id)
    token_edge = Edge(id="e_pt_owns_billing_recon", source=token.id, target="wf_billing_recon", relation=Relation.OWNS,
                      strength=0.5, substitutability=0.2, lag_days=0, criticality=Criticality.medium, confidence=0.9)
    twin = clone_with_edges(TWIN, [token_edge])
    applied = apply_interventions(twin, [action(ActionType.remove_roles, role_id)])
    role = entity_map(applied.twin)[role_id]
    assert role.capacity_fte == 0
    assert applied.gross_savings_usd == entity_map(TWIN)[role_id].annual_cost_usd
    assert all(e.id != "e_pt_owns_billing_recon" for e in applied.twin.edges)
    assert any(e.id == "e_pt_owns_billing_recon" for e in twin.edges)


def test_reduce_capacity_cuts_every_role_in_a_department_by_the_same_share():
    applied = apply_interventions(TWIN, [action(ActionType.reduce_capacity, "dept_marketing", amount_pct=10)])
    before, after = entity_map(TWIN), entity_map(applied.twin)
    roles = [e for e in TWIN.entities if e.type is EntityType.role and e.department_id == "dept_marketing"]
    assert roles
    for role in roles:
        assert after[role.id].capacity_fte == pytest.approx(before[role.id].capacity_fte * 0.9)
        assert applied.losses[role.id].magnitude == pytest.approx(0.1)
    assert applied.gross_savings_usd == round(sum(r.annual_cost_usd for r in roles) * 0.1)


def test_department_fte_normalization_uses_the_roles_scaled_by_the_engine():
    roles = [e for e in TWIN.entities if e.type is EntityType.role and e.department_id == "dept_marketing"]
    baseline = sum(r.capacity_fte for r in roles)
    percentage, assumption = capacity_percentage(TWIN, "dept_marketing", amount_fte=baseline / 4)
    assert percentage == 25
    assert "uniformly" in assumption
    applied = apply_interventions(TWIN, [action(ActionType.reduce_capacity, "dept_marketing", amount_pct=percentage)])
    remaining = sum(e.capacity_fte for e in applied.twin.entities
                    if e.type is EntityType.role and e.department_id == "dept_marketing")
    assert remaining == pytest.approx(baseline * .75)


@pytest.mark.parametrize("amount", [-1, float("nan"), float("inf"), 1_000_000])
def test_capacity_normalization_rejects_invalid_or_unsupported_amounts(amount):
    with pytest.raises(ValueError):
        capacity_percentage(TWIN, "role_sre", amount_fte=amount)


@pytest.mark.parametrize("cost", [None, 0])
def test_capacity_normalization_requires_a_cost_baseline(cost):
    twin = TWIN.model_copy(deep=True)
    entity_map(twin)["role_sre"].annual_cost_usd = cost
    with pytest.raises(ValueError, match="baseline"):
        capacity_percentage(twin, "role_sre", amount_usd=10)


def test_dollar_capacity_cut_respects_fixed_cost_limit():
    twin = TWIN.model_copy(deep=True)
    profile = next(p for p in twin.department_profiles if p.department_id == "dept_marketing")
    profile.budget.fixed_cost_pct = 1
    with pytest.raises(ValueError, match="reducible annual budget"):
        capacity_percentage(twin, "dept_marketing", amount_usd=10)


def test_department_dollars_normalize_to_the_requested_savings():
    percentage, _ = capacity_percentage(TWIN, "dept_marketing", amount_usd=10_000)
    applied = apply_interventions(TWIN, [action(ActionType.reduce_capacity, "dept_marketing", amount_pct=percentage)])
    assert applied.gross_savings_usd == 10_000


def test_add_capacity_adds_cost_and_a_gain():
    sre = entity_map(TWIN)["role_sre"]
    applied = apply_interventions(TWIN, [action(ActionType.add_capacity, "role_sre", amount_pct=50)])
    assert applied.added_cost_usd == round(sre.annual_cost_usd * 0.5)
    assert entity_map(applied.twin)["role_sre"].capacity_fte == pytest.approx(sre.capacity_fte * 1.5)
    assert applied.gains["role_sre"].magnitude == pytest.approx(0.5)


def test_stop_project_saves_remaining_cost_and_retired_entities_rebound():
    project = entity_map(TWIN)["proj_billing_modernization"]
    twin = TWIN.model_copy(deep=True)
    entity_map(twin)["proj_billing_modernization"].retires_entity_ids = ["sys_billing_platform"]
    applied = apply_interventions(twin, [action(ActionType.stop_project, "proj_billing_modernization")])
    assert applied.gross_savings_usd == project.remaining_cost_usd
    assert applied.transition_cost_usd == project.one_time_exit_cost_usd
    platform = entity_map(TWIN)["sys_billing_platform"].annual_cost_usd
    assert applied.rebound_cost_usd == round(platform * (365 - project.expected_completion_day) / 365)


def test_start_project_invest_and_delay_project():
    start = apply_interventions(TWIN, [action(ActionType.start_project, "proj_soc2_type2", amount_usd=1_000_000,
                                              start_day=10)])
    assert start.added_cost_usd == 1_000_000
    assert start.gains["proj_soc2_type2"].start_day == 10 + entity_map(TWIN)["proj_soc2_type2"].expected_completion_day
    invest = apply_interventions(TWIN, [action(ActionType.invest, "sys_data_pipeline", amount_usd=5)])
    assert invest.added_cost_usd == 5 and not invest.gains and invest.assumptions
    delay = apply_interventions(TWIN, [action(ActionType.delay_project, "proj_soc2_type2", duration_days=60)])
    assert entity_map(delay.twin)["proj_soc2_type2"].expected_completion_day == (
        entity_map(TWIN)["proj_soc2_type2"].expected_completion_day + 60)


def test_assess_change_makes_no_graph_edit():
    applied = apply_interventions(TWIN, [action(ActionType.assess_change, "vendor_apex")])
    assert applied.twin.model_dump_json() == TWIN.model_dump_json()
    assert not applied.losses and not applied.gains


def test_invalid_interventions_are_rejected():
    with pytest.raises(ValueError, match="unknown target"):
        apply_interventions(TWIN, [action(ActionType.remove_vendor, "vendor_missing")])
    with pytest.raises(ValueError, match="needs a vendor"):
        apply_interventions(TWIN, [action(ActionType.remove_vendor, "role_sre")])
    mitigation = Intervention(id="mit_feed", kind=InterventionKind.mitigation, type=MitigationType.add_replacement_feed,
                              target_entity_id="ds_account_intel", one_time_cost_usd=0, rationale="test")
    with pytest.raises(ValueError, match="replacement_vendor_id"):
        apply_interventions(TWIN, [mitigation])


def test_mitigations_apply_after_every_action_and_cost_transition():
    # Listed first, the replacement feed still sees vendor_echo's removal, so it refuses vendor_echo itself.
    feed = Intervention(id="mit_feed", kind=InterventionKind.mitigation, type=MitigationType.add_replacement_feed,
                        target_entity_id="ds_account_intel", one_time_cost_usd=25_000,
                        params={"replacement_vendor_id": "vendor_apex"}, rationale="test")
    remove_echo = action(ActionType.remove_vendor, "vendor_echo")
    applied = apply_interventions(TWIN, [feed, remove_echo])
    echo = entity_map(TWIN)["vendor_echo"]
    assert applied.transition_cost_usd == echo.one_time_exit_cost_usd + echo.migration_cost_usd + 25_000
    assert applied.migration_cost_usd == echo.migration_cost_usd + 25_000
    added = [e for e in applied.twin.edges if e.id == "e_mit_feed_1"]
    assert [(e.source, e.target, e.relation) for e in added] == [("vendor_apex", "ds_account_intel", Relation.PROVIDES)]
    assert added[0].extraction_method is None
    with pytest.raises(ValueError, match="itself removed"):
        apply_interventions(TWIN, [feed.model_copy(update={"params": {"replacement_vendor_id": "vendor_echo"}}),
                                   remove_echo])
