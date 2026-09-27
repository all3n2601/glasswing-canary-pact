"""Mitigation re-simulation (plan E-07, sections 4.2, 11.8, 13.8, 19.3, 19.5; schema rule 12; story W-4)."""

from __future__ import annotations

import json
import re

import networkx as nx
import pytest
from contracts_py.decision import CandidatePlan, Constraint, DecisionBrief, Goal, Intervention
from contracts_py.enums import ActionType, InterventionKind, MitigationType, Polarity, Relation

from company_twin import clone_with_edges, edge_from_agent_dependency, entity_map, load_mitigation_catalog, load_twin
from company_twin.loader import default_fixture_path
from simulation_engine import apply_interventions, check_result, mitigate, optimize

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


# ---- the two demo stories with the real catalog (data/mitigations.json) -------------------------------------------
CATALOG = {m.id: m for m in load_mitigation_catalog(twin=TWIN)}
WORKFORCE_MITIGATIONS = ["mit_reassign_financial_close", "mit_reassign_billing_recon", "mit_runbook_billing_recon",
                         "mit_runbook_warehouse_lineage"]
VENDOR = DecisionBrief.model_validate(json.loads((default_fixture_path().parent / "vendor_scenario.json").read_text()))
BEACON_ECHO = CandidatePlan(plan_id="plan_beacon_echo", label="Beacon + Echo",
                            intervention_ids=["remove_beacon", "remove_echo"], source="optimizer")
PLANTED = json.loads((default_fixture_path().parent / "planted_items.json").read_text())["planted_edge"]
RECONCILIATION = ("wf_vendor_reconciliation", "ctl_sox_reconciliation")


def eight_roles() -> CandidatePlan:
    return CandidatePlan(plan_id="plan_naive", label="Remove the eight roles", source="naive",
                         intervention_ids=[i.id for i in WORKFORCE.candidate_interventions])


def planted_twin():
    # The Challenger's validated edge, built exactly as the orchestrator builds agent edges (agent defaults).
    edge = edge_from_agent_dependency(PLANTED["source"], PLANTED["target"], Relation.CONSUMES,
                                      PLANTED["evidence_refs"], 0.8, edge_id=PLANTED["id"])
    return clone_with_edges(TWIN, [edge])


def reconciliation_harms(result) -> dict[str, tuple[float, int]]:
    return {i.affected_entity: (i.magnitude, i.severity) for i in result.impacts
            if i.polarity is Polarity.harm and i.unit == "ratio" and i.affected_entity in RECONCILIATION}


def test_role_level_mitigation_restores_both_stranded_workflows_and_makes_the_plan_conditionally_feasible():
    comparison = mitigate(TWIN, WORKFORCE, eight_roles(), [CATALOG[m] for m in WORKFORCE_MITIGATIONS])
    assert check_result(comparison, TWIN) == []
    before, after = comparison.before, comparison.after
    # Removing all eight roles strands exactly the two workflows and is infeasible (plan 19.3, C-07).
    assert sorted(c.workflow_id for c in before.workflow_coverage if c.stranded) == ["wf_billing_recon",
                                                                                     "wf_financial_close"]
    assert not comparison.feasible_before and any(r.startswith("c_stranded:") for r in before.rejection_reasons)
    # Backup owners and documented exception handling restore minimum coverage (Gate 5) ...
    assert not any(c.stranded for c in after.workflow_coverage)
    assert {"wf_billing_recon", "wf_financial_close"} <= set(comparison.restored_entity_ids)
    # ... so the scenario moves from infeasible to conditionally feasible (plan 13.8).
    assert comparison.feasible_after
    assert any(a.startswith("Conditionally feasible: only if mit_reassign_financial_close") for a in after.assumptions)
    # Knowledge transfer changes the risk result, and the mitigation reports its time and cost (plan 19.3).
    assert [k.knowledge_id for k in before.knowledge_coverage if k.lost] == ["kn_billing_exception",
                                                                             "kn_warehouse_lineage"]
    assert not any(k.lost for k in after.knowledge_coverage)
    assert after.risk.score < before.risk.score and "risk_score" in comparison.changed_metrics
    assert "Mitigations take 25 days (day 0 to day 25) and cost $115,000 one-time" in after.assumptions
    # No output names a person (plan 19.3, Gate 5).
    assert not re.search(r"pt_\d", comparison.model_dump_json())


def test_the_planted_dependency_is_a_compliance_risk_on_beacon_and_echo_that_stays_feasible_and_recommended():
    twin = planted_twin()
    edge = next(e for e in twin.edges if e.id == PLANTED["id"])
    assert edge.extraction_method == "agent" and (edge.strength, edge.substitutability) == (0.6, 0.4)
    base = mitigate(TWIN, VENDOR, BEACON_ECHO, [CATALOG["mit_replacement_feed_account_intel"]]).before
    planted = mitigate(twin, VENDOR, BEACON_ECHO, [CATALOG["mit_replacement_feed_account_intel"]]).before
    assert reconciliation_harms(base) == {}
    # ds_account_intel now feeds vendor reconciliation and the mandatory SOX control: a compliance risk.
    harms = reconciliation_harms(planted)
    assert set(harms) == set(RECONCILIATION) and all(severity >= 2 for _, severity in harms.values())
    assert entity_map(twin)["ctl_sox_reconciliation"].mandatory
    sox = next(i for i in planted.impacts if i.affected_entity == "ctl_sox_reconciliation")
    assert sox.dependency_path[-3:] == ["ds_account_intel", *RECONCILIATION] and PLANTED["id"] in sox.edge_path
    assert planted.risk.components.compliance_control > base.risk.components.compliance_control == 0
    assert planted.risk.score > base.risk.score
    # Beacon + Echo is still feasible and still the recommended portfolio (plan 4.1).
    assert planted.feasible
    assert optimize(twin, VENDOR).recommended.intervention_ids == ["remove_beacon", "remove_echo"]


def test_migrating_the_unique_echo_attributes_clears_the_planted_exposure():
    twin = planted_twin()
    comparison = mitigate(twin, VENDOR, BEACON_ECHO, [CATALOG["mit_replacement_feed_account_intel"]])
    assert check_result(comparison, twin) == []
    before, after = comparison.before, comparison.after
    assert comparison.feasible_before and comparison.feasible_after
    # The account-intel migration runs first: Echo and Beacon are removed once it completes (plan 4.1).
    assert any(a.startswith("Readiness gate: the plan's actions remove_beacon, remove_echo move to day 60")
               for a in after.assumptions)
    assert after.value.migration_cost_usd - before.value.migration_cost_usd == 30_000_000
    # No critical exposure remains: the reconciliation workflow and SOX control fall to the lowest severity.
    assert set(RECONCILIATION) <= set(comparison.restored_entity_ids)
    assert all(severity == 1 for _, severity in reconciliation_harms(after).values())
    assert after.risk.components.compliance_control < before.risk.components.compliance_control / 10
    assert after.risk.score < before.risk.score and after.risk.level.value == "low"
