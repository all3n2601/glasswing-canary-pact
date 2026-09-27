"""Workforce knowledge risk (plan C-07, sections 4.2, 11.6, 19.3; schema 7.2, 7.15, rule 11; stories W-1 to W-4, W-6)."""

from __future__ import annotations

import json
import re

from contracts_py.decision import CandidatePlan, DecisionBrief
from contracts_py.enums import Criticality, EntityType, Future, ImpactCategory, Relation
from contracts_py.twin import Edge

from company_twin import clone_with_edges, entity_map, load_twin, to_role_level
from company_twin.loader import default_fixture_path
from simulation_engine import check_result, compare_futures, optimize, quick_impact, simulate
from simulation_engine.futures import scenario_for
from simulation_engine.knowledge import knowledge_coverage, workflow_coverage

TWIN = load_twin(default_fixture_path())
DATA = default_fixture_path().parent
VENDOR = DecisionBrief.model_validate(json.loads((DATA / "vendor_scenario.json").read_text()))
WORKFORCE = DecisionBrief.model_validate(json.loads((DATA / "workforce_scenario.json").read_text()))
STORY_WORKFLOWS = {"wf_financial_close", "wf_billing_recon"}
EIGHT_ROLES = {i.target_entity_id for i in WORKFORCE.candidate_interventions}
# A token ID starts a word: "dept_" also contains "pt_".
PERSON_TOKEN = re.compile(r"\bpt_[a-z0-9_]+")


def remove_eight(twin=TWIN):
    return quick_impact(twin, WORKFORCE.candidate_interventions, brief=WORKFORCE)


def backs_up(role_id: str, workflow_id: str) -> Edge:
    return Edge(id=f"e_{role_id.removeprefix('role_')}_backs_{workflow_id.removeprefix('wf_')}", source=role_id,
                target=workflow_id, relation=Relation.BACKS_UP, strength=0.3, strength_range=(0.2, 0.4),
                substitutability=0.3, lag_days=0, criticality=Criticality.high, confidence=0.9,
                evidence_refs=["ev_sop_financial_close_lineage"])


def test_w2_removing_the_eight_roles_strands_exactly_the_two_story_workflows():
    result = remove_eight()
    assert {c.workflow_id for c in result.workflow_coverage if c.stranded} == STORY_WORKFLOWS
    assert not result.feasible
    stranded = next(c for c in result.constraint_results if c.constraint_id == "c_stranded")
    assert stranded.value == 2 and not stranded.passed
    assert any(r.startswith("c_stranded:") for r in result.rejection_reasons)
    for row in result.workflow_coverage:
        if row.workflow_id in STORY_WORKFLOWS:
            assert row.owners_after == [] and set(row.owners_before) <= EIGHT_ROLES
            assert "lost qualified owners" in row.reasons[0]


def test_every_reported_critical_workflow_carries_the_plan_11_6_inputs():
    ents = entity_map(TWIN)
    for row in remove_eight().workflow_coverage:
        wf = ents[row.workflow_id]
        if row.workflow_id not in STORY_WORKFLOWS:
            continue
        assert row.criticality is wf.criticality and row.min_qualified_owners == wf.min_qualified_owners == 2
        assert row.backup_count_after == 0
        assert row.owner_capacity_fte_before > 0 and row.owner_capacity_fte_after == 0
        assert row.documented_pct == wf.documented_pct
        assert row.exception_documented_pct == wf.exception_documented_pct
        assert row.automation_pct == wf.automation_pct
        lost = row.owners_before
        assert row.training_days_required == max(ents[r].time_to_train_days for r in lost)
        assert row.replacement_cost_usd == sum(ents[r].replacement_cost_usd for r in lost)
        text = " ".join(row.reasons)
        for phrase in ("independent backups", "recent execution coverage", "exception path", "automated",
                       "recovery knowledge lost", "to train", f"maximum downtime of {wf.max_downtime_days} days"):
            assert phrase in text, (row.workflow_id, phrase)


def test_w3_lineage_is_lost_and_the_exception_path_gap_is_reported_separately():
    result = remove_eight()
    knowledge = {k.knowledge_id: k for k in result.knowledge_coverage}
    lineage = knowledge["kn_warehouse_lineage"]
    assert lineage.lost and lineage.holders_before == ["role_data_platform_lead"] and lineage.holders_after == []
    assert lineage.holder_capacity_fte_after == 0 and lineage.documented_pct < 0.5
    assert lineage.dependent_workflow_ids == ["wf_financial_close"]

    exception = knowledge["kn_billing_exception"]
    recon = next(c for c in result.workflow_coverage if c.workflow_id == "wf_billing_recon")
    assert recon.exception_documented_pct < recon.documented_pct
    assert any("exception path is only" in r for r in exception.reasons)
    assert exception.documented_pct == entity_map(TWIN)["kn_billing_exception"].documented_pct

    # A lost asset adds one unpriced ownership impact to each workflow it supports (schema 7.15).
    added = [i for i in result.impacts if i.metric == "knowledge_lost"]
    assert {(i.source_entity, i.affected_entity) for i in added} == {
        ("kn_warehouse_lineage", "wf_financial_close"), ("kn_billing_exception", "wf_billing_recon")}
    assert all(i.category is ImpactCategory.ownership and i.value_usd is None for i in added)


def test_w4_qualified_backups_outside_the_eight_keep_a_workflow_covered():
    # Both story workflows need two qualified owners, so one outside backup is not enough, two are.
    one = remove_eight(clone_with_edges(TWIN, [backs_up("role_controller", "wf_financial_close")]))
    close = next(c for c in one.workflow_coverage if c.workflow_id == "wf_financial_close")
    assert close.owners_after == ["role_controller"] and close.stranded

    two = remove_eight(clone_with_edges(TWIN, [backs_up("role_controller", "wf_financial_close"),
                                               backs_up("role_finance_analyst", "wf_financial_close")]))
    stranded = {c.workflow_id for c in two.workflow_coverage if c.stranded}
    close = next(c for c in two.workflow_coverage if c.workflow_id == "wf_financial_close")
    assert not close.stranded and close.backup_count_after == 2
    assert stranded == {"wf_billing_recon"}

    # With a one-owner minimum, a single qualified backup prevents stranding (plan 19.3).
    relaxed = clone_with_edges(TWIN, [backs_up("role_controller", "wf_financial_close")])
    for e in relaxed.entities:
        if e.id == "wf_financial_close":
            e.min_qualified_owners = 1
    assert not next(c for c in remove_eight(relaxed).workflow_coverage if c.workflow_id == "wf_financial_close").stranded


def test_losing_every_qualified_owner_strands_even_without_a_configured_minimum():
    twin = TWIN.model_copy(deep=True)
    for e in twin.entities:
        if e.id == "wf_financial_close":
            e.min_qualified_owners = None
    close = next(c for c in remove_eight(twin).workflow_coverage if c.workflow_id == "wf_financial_close")
    assert close.stranded and close.min_qualified_owners == 1


def test_rule_11_stranded_and_lost_agree_with_owners_and_holders():
    result = remove_eight()
    for c in result.workflow_coverage:
        assert c.stranded == (len(c.owners_after) < c.min_qualified_owners)
    for k in result.knowledge_coverage:
        assert k.lost == (k.holder_capacity_fte_after == 0 and k.documented_pct < 0.5)
    assert check_result(result, TWIN) == []
    result.workflow_coverage[0].stranded = not result.workflow_coverage[0].stranded
    result.knowledge_coverage[0].lost = not result.knowledge_coverage[0].lost
    issues = [i for i in check_result(result, TWIN) if i.rule == 11]
    assert len(issues) == 2


def test_only_changed_workflows_and_knowledge_are_reported():
    assert workflow_coverage(TWIN, TWIN) == [] and knowledge_coverage(TWIN, TWIN) == []
    vendor = quick_impact(TWIN, [i for i in VENDOR.candidate_interventions if i.id in ("remove_beacon", "remove_echo")],
                          brief=VENDOR)
    assert vendor.workflow_coverage == [] and vendor.knowledge_coverage == []


def test_w1_workforce_inaction_loses_money_and_pressure_is_its_largest_line():
    result = simulate(TWIN, WORKFORCE, scenario_for(TWIN, WORKFORCE, "run_kn", Future.inaction, None), None, "full")
    v = result.value
    assert v.net_value_usd < 0 and v.net_value_usd == -v.pressure_cost_usd
    assert all(v.pressure_cost_usd > line for line in (v.gross_savings_usd, v.transition_cost_usd, v.added_cost_usd,
                                                        v.rebound_cost_usd, v.expected_business_loss_usd))
    assert result.feasible and result.workflow_coverage == [] and result.knowledge_coverage == []


def test_cuts_make_the_workforce_hazards_likelier():
    plan = optimize(TWIN, WORKFORCE, run_id="run_kn").naive
    candidate = CandidatePlan(plan_id=plan.plan_id, label="Eight roles", intervention_ids=plan.intervention_ids,
                              source="optimizer")
    rows = {f: simulate(TWIN, WORKFORCE, scenario_for(TWIN, WORKFORCE, "run_kn", f, candidate),
                        None if f is Future.inaction else candidate, "full")
            for f in (Future.inaction, Future.act_now)}
    for pressure_id in ("pr_billing_recon_hazard", "pr_lineage_holder_attrition"):
        cost = {f: next(t for t in r.pressures_triggered if t.pressure_id == pressure_id).expected_cost_usd
                for f, r in rows.items()}
        assert cost[Future.act_now] > cost[Future.inaction]


def test_w6_no_output_names_or_ranks_person_tokens():
    tokens = {e.id for e in TWIN.entities if e.type is EntityType.person_token}
    assert tokens
    plan = optimize(TWIN, WORKFORCE, run_id="run_kn")
    candidate = CandidatePlan(plan_id=plan.naive.plan_id, label="Eight roles",
                              intervention_ids=plan.naive.intervention_ids, source="optimizer")
    outputs = [remove_eight(), plan, compare_futures(TWIN, WORKFORCE, candidate, run_id="run_kn")]
    for output in outputs:
        raw = output.model_dump_json()
        assert not any(t in raw for t in tokens) and not PERSON_TOKEN.search(raw)
        assert not PERSON_TOKEN.search(to_role_level(output, TWIN).model_dump_json())
    result = remove_eight()
    for c in result.workflow_coverage:
        assert all(o.startswith("role_") for o in [*c.owners_before, *c.owners_after])
    for k in result.knowledge_coverage:
        assert all(h.startswith("role_") for h in [*k.holders_before, *k.holders_after])


def test_knowledge_risk_is_deterministic_and_leaves_the_baseline_alone():
    before = TWIN.model_dump_json()
    assert remove_eight().model_dump_json() == remove_eight().model_dump_json()
    assert TWIN.model_dump_json() == before


def test_a_workflow_hazard_follows_its_largest_loss_not_the_knowledge_impact():
    plan = CandidatePlan(plan_id="plan_naive", label="Eight roles",
                         intervention_ids=[i.id for i in WORKFORCE.candidate_interventions], source="optimizer")
    result = simulate(TWIN, WORKFORCE, scenario_for(TWIN, WORKFORCE, "run_kn", Future.act_now, plan), plan, "full")
    loss = max(i.magnitude for i in result.impacts if i.affected_entity == "wf_billing_recon" and i.unit == "ratio")
    hazard = next(p for p in TWIN.pressures if p.id == "pr_billing_recon_hazard")
    boosted = min(1.0, hazard.monthly_probability * (1 + hazard.capacity_sensitivity * loss))
    events = (hazard.monthly_probability * 30 + boosted * 335) / 30
    trigger = next(t for t in result.pressures_triggered if t.pressure_id == hazard.id)
    assert trigger.expected_events == round(events, 6)
