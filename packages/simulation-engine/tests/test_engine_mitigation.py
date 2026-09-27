"""Mitigation re-simulation (plan E-07, sections 4.2, 11.8, 13.8, 19.3, 19.5; schema rule 12; story W-4)."""

from __future__ import annotations

import json

import networkx as nx
import pytest
from contracts_py.decision import CandidatePlan, Constraint, DecisionBrief, Goal, Intervention
from contracts_py.enums import ActionType, InterventionKind, MitigationType, Polarity, Relation

from company_twin import entity_map, load_twin
from company_twin.loader import default_fixture_path
from simulation_engine import apply_interventions, check_result, mitigate

TWIN = load_twin(default_fixture_path())
WORKFORCE = DecisionBrief.model_validate(
    json.loads((default_fixture_path().parent / "workforce_scenario.json").read_text()))
REMOVALS = {i.id: i for i in WORKFORCE.candidate_interventions}
STRANDED = Constraint(id="c_stranded", metric="stranded_workflows", operator="==", threshold=0, unit="count",
                      hard=True, description="Every critical workflow keeps its minimum qualified owners")
CLOSE_OWNERS = ["remove_close_accountant", "remove_gl_accountant", "remove_reporting_analyst"]


def remove_vendor(vendor_id: str) -> Intervention:
    return Intervention(id=f"remove_{vendor_id.removeprefix('vendor_')}", kind=InterventionKind.action,
                        type=ActionType.remove_vendor, target_entity_id=vendor_id, start_day=30, rationale="test")


def mitigation(mitigation_id: str, kind: MitigationType, target: str, **fields) -> Intervention:
    fields.setdefault("one_time_cost_usd", 15_000)
    return Intervention(id=mitigation_id, kind=InterventionKind.mitigation, type=kind, target_entity_id=target,
                        rationale="test", **fields)


def case(*actions: str | Intervention, constraints: list[Constraint] | None = None,
         ) -> tuple[DecisionBrief, CandidatePlan]:
    """A brief whose only goal is some savings, and the plan that takes every one of its ``actions``."""
    interventions = [REMOVALS[a] if isinstance(a, str) else a for a in actions]
    brief = WORKFORCE.model_copy(update={
        "candidate_interventions": interventions, "constraints": constraints or [],
        "goal": Goal(metric="annual_savings_usd", target=1, unit="usd", basis="gross", direction="at_least"),
    })
    return brief, CandidatePlan(plan_id="plan_cut", label="Cut", intervention_ids=[i.id for i in interventions],
                                source="user")


def close_backup(**fields) -> Intervention:
    fields.setdefault("duration_days", 20)
    fields.setdefault("new_owner_id", "role_controller")
    return mitigation("mit_close_backup", MitigationType.reassign_owner, "wf_financial_close", **fields)


def test_reassign_owner_restores_a_stranded_workflow_and_makes_the_plan_conditionally_feasible():
    brief, plan = case(*CLOSE_OWNERS, constraints=[STRANDED])
    comparison = mitigate(TWIN, brief, plan, [close_backup()])
    assert check_result(comparison, TWIN) == []
    assert not comparison.feasible_before and comparison.feasible_after
    assert (comparison.plan_id_before, comparison.plan_id_after) == ("plan_cut", "plan_cut_mitigated")
    assert comparison.after.intervention_ids == [*CLOSE_OWNERS, "mit_close_backup"]

    before = {c.workflow_id: c for c in comparison.before.workflow_coverage}["wf_financial_close"]
    after = {c.workflow_id: c for c in comparison.after.workflow_coverage}["wf_financial_close"]
    assert before.stranded and before.owners_after == []
    assert not after.stranded and after.owners_after == ["role_controller"]
    assert "wf_financial_close" in comparison.restored_entity_ids
    assert "stranded_workflows" in comparison.changed_metrics

    conditional = [a for a in comparison.after.assumptions if a.startswith("Conditionally feasible")]
    assert len(conditional) == 1 and "20 days for $15,000" in conditional[0] and "readiness gate" in conditional[0]
    assert "Mitigations take 20 days (day 0 to day 20) and cost $15,000 one-time" in comparison.after.assumptions
    assert comparison.after.value.transition_cost_usd == comparison.before.value.transition_cost_usd + 15_000
    assert not any(a.startswith("Conditionally feasible") for a in comparison.before.assumptions)


def test_reassign_owner_hands_the_removed_roles_edges_to_the_new_owner():
    brief, plan = case(*CLOSE_OWNERS)
    applied = apply_interventions(TWIN, [*brief.candidate_interventions, close_backup()])
    into_close = [e for e in applied.twin.edges if e.target == "wf_financial_close" and e.relation is not
                  Relation.SUPPORTS]
    assert [(e.id, e.source, e.relation) for e in into_close] == [
        ("e_mit_close_backup_1", "role_controller", Relation.OWNS)]
    strongest = next(e for e in TWIN.edges if e.id == "e_close_accountant_owns_close")
    handed = into_close[0]
    assert (handed.strength, handed.substitutability, handed.lag_days) == (
        strongest.strength, strongest.substitutability, strongest.lag_days)
    assert handed.extraction_method is None
    assert any(a.startswith("mit_close_backup: reassign_owner trains role_controller") for a in applied.assumptions)


def test_knowledge_transfer_keeps_the_asset_and_lowers_the_risk():
    brief, plan = case("remove_data_platform_lead")
    comparison = mitigate(TWIN, brief, plan, [close_backup()])
    assert check_result(comparison, TWIN) == []
    lineage_before = {k.knowledge_id: k for k in comparison.before.knowledge_coverage}["kn_warehouse_lineage"]
    lineage_after = {k.knowledge_id: k for k in comparison.after.knowledge_coverage}["kn_warehouse_lineage"]
    assert lineage_before.lost and not lineage_after.lost
    assert lineage_after.holders_after == ["role_controller"]
    assert comparison.after.risk.score < comparison.before.risk.score
    assert "kn_warehouse_lineage" in comparison.restored_entity_ids
    assert {"risk_score", "lost_knowledge_assets"} <= set(comparison.changed_metrics)
    # Nothing to hand over for ownership, so the controller is trained in as a new owner.
    new_owner = {c.workflow_id: c for c in comparison.after.workflow_coverage}["wf_financial_close"]
    assert "role_controller" in new_owner.owners_after


def test_document_runbook_on_a_knowledge_asset_keeps_it_and_neutralises_its_pressure():
    brief, plan = case("remove_data_platform_lead")
    runbook = mitigation("mit_lineage_runbook", MitigationType.document_runbook, "kn_warehouse_lineage",
                         duration_days=10)
    comparison = mitigate(TWIN, brief, plan, [runbook])
    assert check_result(comparison, TWIN) == []
    lineage = {k.knowledge_id: k for k in comparison.after.knowledge_coverage}["kn_warehouse_lineage"]
    assert not lineage.lost and lineage.documented_pct == 0.8 and lineage.holders_after == []
    assert any("(the default level)" in a for a in comparison.after.assumptions)
    neutralised = [{t.pressure_id: t.neutralised for t in r.pressures_triggered}["pr_lineage_holder_attrition"]
                   for r in (comparison.before, comparison.after)]
    assert neutralised == [False, True]


def test_document_runbook_on_a_workflow_raises_its_documentation_and_neutralises_its_hazard():
    runbook = mitigation("mit_recon_runbook", MitigationType.document_runbook, "wf_billing_recon",
                         params={"documented_pct": 0.9})
    brief, plan = case("remove_billing_ops_lead")
    applied = apply_interventions(TWIN, [*brief.candidate_interventions, runbook])
    recon = entity_map(applied.twin)["wf_billing_recon"]
    assert recon.documented_pct == 0.9 and recon.exception_documented_pct == 0.9
    edges = {e.id: e for e in applied.twin.edges}
    assert edges["e_kn_billing_supports_recon"].substitutability == 0.9
    # Only knowledge assets become substitutable; the billing platform's edge is untouched.
    assert edges["e_billing_platform_recon"].substitutability == 0.25

    comparison = mitigate(TWIN, brief, plan, [runbook])
    assert check_result(comparison, TWIN) == []
    before = {t.pressure_id: t for t in comparison.before.pressures_triggered}["pr_billing_recon_hazard"]
    after = {t.pressure_id: t for t in comparison.after.pressures_triggered}["pr_billing_recon_hazard"]
    assert not before.neutralised and after.neutralised
    assert after.expected_cost_usd < before.expected_cost_usd
    assert "pressure_cost_usd" in comparison.changed_metrics


def test_add_replacement_feed_restores_dataset_coverage_and_refuses_a_removed_vendor():
    brief, plan = case(remove_vendor("vendor_echo"))
    feed = mitigation("mit_account_feed", MitigationType.add_replacement_feed, "ds_account_intel",
                      duration_days=60, one_time_cost_usd=250_000, params={"replacement_vendor_id": "vendor_apex"})
    comparison = mitigate(TWIN, brief, plan, [feed])
    assert check_result(comparison, TWIN) == []

    def loss(result) -> float:
        return max((i.magnitude for i in result.impacts if i.affected_entity == "ds_account_intel"
                    and i.polarity is Polarity.harm and i.unit == "ratio"), default=0.0)

    assert loss(comparison.after) < loss(comparison.before)
    assert "ds_account_intel" in comparison.restored_entity_ids
    assert comparison.after.value.migration_cost_usd == comparison.before.value.migration_cost_usd + 250_000

    removed = feed.model_copy(update={"params": {"replacement_vendor_id": "vendor_echo"}})
    with pytest.raises(ValueError, match="itself removed"):
        mitigate(TWIN, brief, plan, [removed])


def test_a_mitigation_changes_only_what_its_target_reaches():
    # Plan 19.5: the eight removals strand both story workflows; a backup for the close leaves billing untouched.
    brief, plan = case(*REMOVALS, constraints=[STRANDED])
    comparison = mitigate(TWIN, brief, plan, [close_backup()])
    graph = nx.DiGraph([(e.source, e.target) for e in TWIN.edges])
    touched = {"wf_financial_close", "kn_warehouse_lineage"}
    reachable = touched.union(*(nx.descendants(graph, n) for n in touched))

    def outside(result) -> dict[str, dict]:
        return {i.impact_id: i.model_dump(exclude={"scenario_id"}) for i in result.impacts
                if i.affected_entity not in reachable}

    assert outside(comparison.before) and outside(comparison.before) == outside(comparison.after)
    assert set(comparison.restored_entity_ids) <= reachable
    rows = [{c.workflow_id: c for c in r.workflow_coverage}["wf_billing_recon"]
            for r in (comparison.before, comparison.after)]
    assert rows[0] == rows[1] and rows[1].stranded
    assert not comparison.feasible_after


def test_the_readiness_gate_moves_actions_that_would_start_before_the_mitigations_are_ready():
    brief, plan = case(*CLOSE_OWNERS, constraints=[STRANDED])
    comparison = mitigate(TWIN, brief, plan, [close_backup(start_day=5, duration_days=40)])

    def savings_days(result) -> set[int]:
        return {i.first_effect_day for i in result.impacts if i.metric == "annual_cost_usd"}

    assert savings_days(comparison.before) == {30}
    assert savings_days(comparison.after) == {45}
    gate = next(a for a in comparison.after.assumptions if a.startswith("Readiness gate"))
    assert "remove_close_accountant, remove_gl_accountant, remove_reporting_analyst move to day 45" in gate
    assert "Mitigations take 40 days (day 5 to day 45) and cost $15,000 one-time" in comparison.after.assumptions
    assert check_result(comparison, TWIN) == []

    on_time = mitigate(TWIN, brief, plan, [close_backup()])
    assert any("complete by day 20, before the plan's first action on day 30" in a
               for a in on_time.after.assumptions)


def test_invalid_mitigations_are_rejected():
    brief, plan = case(*CLOSE_OWNERS)
    on_call = mitigation("mit_on_call", MitigationType.reassign_on_call, "wf_financial_close",
                         new_owner_id="role_controller")
    with pytest.raises(ValueError, match="reassign_on_call is not modelled yet"):
        mitigate(TWIN, brief, plan, [on_call])
    with pytest.raises(ValueError, match="only mitigations"):
        mitigate(TWIN, brief, plan, [REMOVALS["remove_ar_specialist"]])
    with pytest.raises(ValueError, match="at least one"):
        mitigate(TWIN, brief, plan, [])
    with pytest.raises(ValueError, match="no capacity left"):
        mitigate(TWIN, brief, plan, [close_backup(new_owner_id="role_gl_accountant")])
    with pytest.raises(ValueError, match="needs a workflow"):
        mitigate(TWIN, brief, plan, [mitigation("mit_bad", MitigationType.reassign_owner, "kn_warehouse_lineage",
                                                new_owner_id="role_controller")])
