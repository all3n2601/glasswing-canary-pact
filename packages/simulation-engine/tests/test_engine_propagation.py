"""Dependency propagation (plan C-03, sections 11.3 and 19.5) on a toy graph and the full fixture."""

from __future__ import annotations

import pytest
from contracts_py.enums import Criticality, EntityType, ImpactLevel, Polarity, Relation
from contracts_py.twin import Edge, Entity, OrganizationSettings

from company_twin import build_graph, load_twin
from company_twin.loader import default_fixture_path
from simulation_engine import Seed, apply_interventions, impact_ledger, propagate, propagation

TWIN = load_twin(default_fixture_path())


def entity(entity_id: str, kind: EntityType) -> Entity:
    return Entity(id=entity_id, type=kind, name=entity_id)


def edge(source: str, target: str, strength: float, substitutability: float = 0.0, *, lag: int = 0,
         relation: Relation = Relation.DEPENDS_ON) -> Edge:
    return Edge(id=f"e_{source}_{target}", source=source, target=target, relation=relation, strength=strength,
                substitutability=substitutability, lag_days=lag, criticality=Criticality.medium, confidence=0.9)


def toy(entities: list[Entity], edges: list[Edge]):
    return TWIN.model_copy(update={"entities": entities, "edges": edges, "pressures": []})


def seed(entity_id: str, magnitude: float = 1.0, start_day: int = 0) -> dict[str, Seed]:
    return {entity_id: Seed(magnitude, start_day, "act_toy")}


def test_substitutability_scales_the_transfer():
    ents = [entity(n, EntityType.system) for n in ("sys_src", "sys_hard", "sys_soft")]
    twin = toy(ents, [edge("sys_src", "sys_hard", 0.8, 0.0), edge("sys_src", "sys_soft", 0.8, 0.5)])
    effects = propagate(twin, seed("sys_src")).effects
    assert effects["sys_hard"].magnitude == pytest.approx(0.8)
    assert effects["sys_soft"].magnitude == pytest.approx(0.4)


def test_noisy_or_merges_independent_upstream_losses():
    ents = [entity(n, EntityType.system) for n in ("sys_a", "sys_b", "sys_t")]
    twin = toy(ents, [edge("sys_a", "sys_t", 0.5), edge("sys_b", "sys_t", 0.5)])
    effects = propagate(twin, {**seed("sys_a"), **seed("sys_b")}).effects
    assert effects["sys_t"].magnitude == pytest.approx(1 - 0.5 * 0.5)


def test_lag_sets_first_effect_day_and_delayed_level():
    ents = [entity("sys_src", EntityType.system), entity("wf_mid", EntityType.workflow),
            entity("kpi_late", EntityType.kpi)]
    twin = toy(ents, [edge("sys_src", "wf_mid", 0.9, lag=10), edge("wf_mid", "kpi_late", 0.9, lag=45)])
    effects = propagate(twin, seed("sys_src", start_day=60)).effects
    assert effects["wf_mid"].first_effect_day == 70
    assert effects["kpi_late"].first_effect_day == 115
    impacts = {i.affected_entity: i for i in impact_ledger(twin, propagate(twin, seed("sys_src", start_day=60)),
                                                           decision_id="dec_toy", scenario_id="scn_toy",
                                                           polarity=Polarity.harm, constraints=[],
                                                           horizon_days=365)}
    assert impacts["sys_src"].level is ImpactLevel.direct
    assert impacts["wf_mid"].level is ImpactLevel.dependent
    assert impacts["kpi_late"].level is ImpactLevel.delayed


def test_loop_converges_to_the_fixed_point_and_is_labelled_feedback():
    ents = [entity(n, EntityType.department) for n in ("dept_src", "dept_a", "dept_b")]
    edges = [edge("dept_src", "dept_a", 0.5, relation=Relation.FLOWS_TO),
             edge("dept_a", "dept_b", 0.5, relation=Relation.FLOWS_TO),
             edge("dept_b", "dept_a", 0.5, relation=Relation.FLOWS_TO)]
    result = propagate(toy(ents, edges), seed("dept_src"))
    assert result.converged and result.iterations <= 10
    # a = 1 - (1 - 0.5)(1 - 0.5 b), b = 0.5 a  =>  a = 0.5 / 0.875
    a = 0.5 / 0.875
    assert result.effects["dept_a"].magnitude == pytest.approx(a, abs=1e-3)
    assert result.effects["dept_b"].magnitude == pytest.approx(0.5 * a, abs=1e-3)
    assert result.effects["dept_a"].feedback
    assert not result.effects["dept_b"].feedback
    assert result.effects["dept_a"].dependency_path == ["dept_src", "dept_a"]


def test_depth_cap_and_minimum_threshold():
    chain = [f"sys_n{i}" for i in range(7)]
    ents = [entity(n, EntityType.system) for n in chain] + [entity("sys_faint", EntityType.system)]
    edges = [edge(a, b, 1.0) for a, b in zip(chain, chain[1:])] + [edge("sys_n0", "sys_faint", 0.01)]
    twin = toy(ents, edges)
    effects = propagate(twin, seed("sys_n0"), settings=OrganizationSettings(propagation_max_hops=4)).effects
    assert "sys_n4" in effects and "sys_n5" not in effects
    assert "sys_faint" not in effects
    assert all(0 <= e.magnitude <= 1 for e in effects.values())
    assert max(e.hops for e in effects.values()) == 4


def test_a_dataset_loses_only_the_share_no_remaining_provider_supplies():
    ents = [entity("vendor_x", EntityType.vendor), entity("vendor_y", EntityType.vendor),
            entity("ds_shared", EntityType.dataset)]
    edges = [edge("vendor_x", "ds_shared", 0.8, 0.5, relation=Relation.PROVIDES),
             edge("vendor_y", "ds_shared", 0.6, 0.5, relation=Relation.PROVIDES)]
    twin = toy(ents, edges)
    one = propagate(twin, seed("vendor_x")).effects["ds_shared"].magnitude
    before = 1 - 0.2 * 0.4
    after = 1 - (1 - 0.8 * 0.5) * 0.4
    assert one == pytest.approx(1 - after / before)
    both = propagate(twin, {**seed("vendor_x"), **seed("vendor_y")}).effects["ds_shared"].magnitude
    assert both > one


def test_removing_vendor_delta_reaches_ctl_kyc_screening():
    remove_delta = next(i for i in _vendor_brief().candidate_interventions if i.id == "remove_delta")
    applied = apply_interventions(TWIN, [remove_delta])
    effects = propagate(applied.twin, applied.losses).effects
    kyc = effects["ctl_kyc_screening"]
    assert kyc.dependency_path == ["vendor_delta", "ds_identity_verification", "wf_kyc_screening",
                                   "ctl_kyc_screening"]
    assert kyc.edge_path == ["e_delta_provides_identity", "e_identity_consumed_kyc", "e_kyc_supports_control"]
    assert kyc.magnitude > 0.5
    assert kyc.confidence == pytest.approx(0.9 ** 3)
    assert kyc.first_effect_day == remove_delta.start_day
    assert kyc.source_ref == "remove_delta"
    assert kyc.evidence_refs


def test_empty_seeds_produce_no_effects():
    assert propagate(TWIN, {}).effects == {}


def test_the_shared_graph_gives_the_same_effects_as_a_freshly_built_one(monkeypatch):
    brief = _vendor_brief()
    scenarios = [apply_interventions(TWIN, [i]) for i in brief.candidate_interventions]
    scenarios.append(apply_interventions(TWIN, list(brief.candidate_interventions)))
    shared = [propagate(s.twin, s.losses) for s in scenarios]
    monkeypatch.setattr(propagation, "_graph", build_graph)
    assert shared == [propagate(s.twin, s.losses) for s in scenarios]


def test_clones_with_the_same_structure_share_a_graph_and_any_edit_gets_its_own():
    first, second = (apply_interventions(TWIN, []).twin for _ in range(2))
    assert propagation._graph(first) is propagation._graph(second)

    weaker = [e.model_copy(update={"strength": e.strength / 2}) if n == 0 else e for n, e in enumerate(TWIN.edges)]
    assert propagation._graph(TWIN.model_copy(update={"edges": weaker})) is not propagation._graph(first)
    first.entities[0].evidence_refs = [*first.entities[0].evidence_refs, "ev_new"]
    assert propagation._graph(first) is not propagation._graph(second)
    assert propagation._graph(first).nodes[first.entities[0].id]["evidence_refs"][-1] == "ev_new"


def test_an_edge_to_an_unknown_entity_is_still_rejected():
    broken = edge("sys_src", "sys_missing", 0.5)
    with pytest.raises(ValueError, match="unknown entity"):
        propagate(toy([entity("sys_src", EntityType.system)], [broken]), seed("sys_src"))


def _vendor_brief():
    import json

    from contracts_py.decision import DecisionBrief

    path = default_fixture_path().parent / "vendor_scenario.json"
    return DecisionBrief.model_validate(json.loads(path.read_text()))
