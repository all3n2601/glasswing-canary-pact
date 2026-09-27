"""Blast radius for the act-now future (plan section 13.4; schema v2.2.0 section 7.10, rule 14)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from contracts_py.decision import CandidatePlan, DecisionBrief, Scenario
from contracts_py.enums import Future, Polarity

from company_twin import load_twin
from company_twin.loader import default_fixture_path
from simulation_engine import blast_radius, check_result, quick_impact, simulate
from simulation_engine.blast import OUTCOME_NODE_ID, money

TWIN = load_twin(default_fixture_path())
DATA = default_fixture_path().parent
VENDOR = DecisionBrief.model_validate(json.loads((DATA / "vendor_scenario.json").read_text()))
AT = datetime(2026, 9, 26, tzinfo=timezone.utc)


def act_now(plan_id: str, *names: str):
    plan = CandidatePlan(plan_id=plan_id, label=plan_id, intervention_ids=[f"remove_{n}" for n in names],
                         source="user")
    scenario = Scenario(scenario_id=f"scn_run_blast_act_now_{plan_id}", run_id="run_blast", future=Future.act_now,
                        plan_id=plan_id, delay_days=0, baseline_twin_version=TWIN.version.twin_version, created_at=AT)
    return simulate(TWIN, VENDOR, scenario, plan, "quick")


def test_rule_14_every_edge_references_existing_nodes():
    for result in (act_now("plan_beacon_echo", "beacon", "echo"), act_now("plan_naive", "apex", "cinder")):
        blast = blast_radius(result, TWIN)
        ids = {n.node_id for n in blast.nodes}
        assert len(ids) == len(blast.nodes)
        assert blast.root_node_id in ids and OUTCOME_NODE_ID in ids
        assert all(e.source in ids and e.target in ids for e in blast.edges)
        assert check_result(blast, TWIN) == []


def test_every_impact_is_drawn_and_tied_to_its_run():
    result = act_now("plan_beacon_echo", "beacon", "echo")
    blast = blast_radius(result, TWIN)
    assert (blast.run_id, blast.scenario_id, blast.future, blast.plan_id) == (
        "run_blast", result.scenario_id, Future.act_now, "plan_beacon_echo")
    drawn = {i for n in blast.nodes for i in n.impact_ids}
    assert drawn == {i.impact_id for i in result.impacts}
    targets = {e.target for e in blast.edges}
    assert {i.affected_entity for i in result.impacts} <= targets
    assert blast.outcome.net_value_usd == result.value.net_value_usd
    assert blast.outcome.risk_level is result.risk.level


def test_failed_hard_constraints_are_marked_critical():
    blast = blast_radius(act_now("plan_naive", "apex", "cinder"), TWIN)
    critical = {e.target for e in blast.edges if e.critical_constraint}
    assert {"ctl_kyc_screening", "ds_corporate_linkage", "kpi_pipeline"} <= critical
    assert all(e.label == "Critical constraint" for e in blast.edges if e.critical_constraint)
    safe = blast_radius(act_now("plan_beacon_echo", "beacon", "echo"), TWIN)
    assert not any(e.critical_constraint for e in safe.edges)


def test_department_summaries_cover_every_affected_department():
    result = act_now("plan_beacon_echo", "beacon", "echo")
    blast = blast_radius(result, TWIN)
    assert [d.department_id for d in blast.departments] == sorted(result.affected_department_ids)
    sales = next(d for d in blast.departments if d.department_id == "dept_sales")
    assert sales.polarity is Polarity.harm


def test_blast_radius_is_deterministic_and_works_without_a_plan():
    result = act_now("plan_beacon_echo", "beacon", "echo")
    assert blast_radius(result, TWIN).model_dump_json() == blast_radius(result, TWIN).model_dump_json()
    adhoc = blast_radius(quick_impact(TWIN, []), TWIN)
    assert adhoc.root_node_id == adhoc.scenario_id and check_result(adhoc, TWIN) == []


def test_money_is_formatted_at_the_right_scale():
    assert money(2_300_000_000) == "$2.3B"
    assert money(-120_000_000) == "-$120M"
    assert money(1_961_000) == "$1.96M"
    assert money(12) == "$12"
