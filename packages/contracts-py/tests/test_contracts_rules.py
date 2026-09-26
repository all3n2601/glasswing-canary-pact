from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from contracts_py.agents import AgentOutput, ProposedDependency
from contracts_py.decision import DecisionBrief, Intervention, Scenario
from contracts_py.engine import ValueBreakdown
from contracts_py.enums import Direction, Future, ImpactCategory, ImpactLevel, Polarity, Relation
from contracts_py.events import Event, EventType, PhaseChanged
from contracts_py.package import DecisionPackage, find_person_tokens
from contracts_py.twin import Organization

NOW = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)


def future_view() -> dict:
    return {"summary": "Savings land but billing recon loses its only owner.", "proposed_impacts": []}


def test_person_token_detection() -> None:
    assert find_person_tokens({"headline": "dept_operations and kpt_x are fine"}) == []
    assert find_person_tokens({"ids": ["pt_07"]}) == ["pt_07"]
    assert find_person_tokens({"text": "owned by pt_07 today"}) == ["owned by pt_07 today"]


def package_data(brief: DecisionBrief) -> dict:
    result = {
        "result_id": "res_act_now",
        "run_id": "run_1",
        "scenario_id": "scn_run_1_act_now_plan_naive",
        "future": "act_now",
        "plan_id": "plan_naive",
        "mode": "quick",
        "intervention_ids": ["i_auditlog"],
        "value": breakdown(),
        "goal_met": True,
        "risk": {
            "score": 30,
            "level": "medium",
            "settings_version": 1,
            "components": {
                "financial": 10,
                "capability_workflow": 10,
                "customer_revenue": 5,
                "compliance_control": 5,
                "execution_uncertainty": 0,
            },
        },
        "feasible": True,
        "computed_at": NOW,
    }
    blast = {
        "run_id": "run_1",
        "scenario_id": "scn_run_1_act_now_plan_naive",
        "future": "act_now",
        "root_node_id": "dec_cut_2m",
        "outcome": {"net_value_usd": 2_000_000, "risk_level": "medium", "headline": "Net $2.0M"},
    }
    return {
        "package_id": "pkg_1",
        "run_id": "run_1",
        "decision_id": "dec_cut_2m",
        "versions": {
            "twin_version": "t1",
            "settings_version": 1,
            "prompt_version": "p1",
            "model_id": "mock",
            "engine_version": "e1",
            "created_at": NOW,
            "as_of_date": "2026-09-26",
        },
        "brief": brief.model_dump(),
        "futures": {
            "comparison_id": "cmp_run_1",
            "decision_id": "dec_cut_2m",
            "run_id": "run_1",
            "reference_result_id": "res_inaction",
            "rows": [
                {
                    "future": "act_now",
                    "plan_id": "plan_naive",
                    "result_id": "res_act_now",
                    "label": "Act now",
                    "net_value_p50_usd": 2_000_000,
                    "delta_vs_inaction_p10_usd": 2_300_000,
                    "delta_vs_inaction_p50_usd": 2_300_000,
                    "delta_vs_inaction_p90_usd": 2_300_000,
                    "p_better_than_inaction": 1.0,
                    "feasible": True,
                    "risk_score": 30,
                }
            ],
            "headline": "Acting now is worth $2.3M more than doing nothing; waiting 90 days costs $0.6M.",
        },
        "portfolios": {"evaluated_count": 1, "naive": {"plan_id": "plan_naive", "result": result}},
        "blast_radius_act_now": blast,
        "blast_radius_inaction": blast | {"future": "inaction", "scenario_id": "scn_run_1_inaction_none"},
        "created_at": NOW,
    }


def test_decision_package_validates(brief: DecisionBrief) -> None:
    assert DecisionPackage.model_validate(package_data(brief)).status == "awaiting_approval"


def test_pt_id_in_decision_package_rejected(brief: DecisionBrief) -> None:
    data = package_data(brief)
    data["brief"]["protected_entity_ids"] = ["pt_07"]
    with pytest.raises(ValidationError, match="person tokens"):
        DecisionPackage.model_validate(data)


def test_extra_field_rejected_on_strict(organization: Organization) -> None:
    data = organization.model_dump() | {"nickname": "Nova"}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Organization.model_validate(data)


def test_extra_field_ignored_on_agent_output() -> None:
    output = AgentOutput.model_validate(
        {
            "act_now_view": future_view() | {"mood": "worried"},
            "inaction_view": future_view(),
            "confidence": 1.4,
            "chain_of_thought": "ignored",
        }
    )
    assert not hasattr(output, "chain_of_thought")
    assert output.confidence == 1.4


def breakdown(**overrides: object) -> dict:
    values = {
        "gross_savings_usd": 2_400_000,
        "transition_cost_usd": 220_000,
        "added_cost_usd": 0,
        "rebound_cost_usd": 50_000,
        "expected_business_loss_usd": 100_000,
        "pressure_cost_usd": 30_000,
        "avoided_failure_cost_usd": 0,
        "net_value_usd": 2_000_000,
        "monthly_net_usd": [-220_000, 1_000_000, 2_000_000],
    }
    return values | overrides


def test_value_breakdown_net_mismatch_rejected() -> None:
    assert ValueBreakdown.model_validate(breakdown()).net_value_usd == 2_000_000
    with pytest.raises(ValidationError, match="does not equal components"):
        ValueBreakdown.model_validate(breakdown(net_value_usd=2_100_000, monthly_net_usd=[2_100_000]))
    with pytest.raises(ValidationError, match="last monthly"):
        ValueBreakdown.model_validate(breakdown(monthly_net_usd=[1_900_000]))
    with pytest.raises(ValidationError, match="all set or all null"):
        ValueBreakdown.model_validate(breakdown(p50_net_value_usd=2_000_000))


def test_reduce_capacity_without_amount_pct_rejected() -> None:
    with pytest.raises(ValidationError, match="amount_pct is required"):
        Intervention(
            id="i_ops",
            kind="action",
            type="reduce_capacity",
            target_entity_id="dept_operations",
            rationale="trim",
        )


def test_kind_type_mismatch_rejected() -> None:
    with pytest.raises(ValidationError, match="does not match kind"):
        Intervention(id="i_x", kind="action", type="document_runbook", target_entity_id="wf_billing_recon", rationale="x")


def test_new_owner_id_with_pt_rejected() -> None:
    base = {
        "id": "m_owner",
        "kind": "mitigation",
        "type": "reassign_owner",
        "target_entity_id": "wf_billing_recon",
        "one_time_cost_usd": 5_000,
        "rationale": "Give the workflow a second owner.",
    }
    assert Intervention.model_validate(base | {"new_owner_id": "role_billing_ops_lead"}).new_owner_id
    with pytest.raises(ValidationError, match="new_owner_id"):
        Intervention.model_validate(base | {"new_owner_id": "pt_07"})


def test_brief_without_inaction_gets_inaction_added(brief: DecisionBrief) -> None:
    data = brief.model_dump() | {"futures": ["act_now", "delay"]}
    assert DecisionBrief.model_validate(data).futures == [Future.act_now, Future.delay, Future.inaction]


def test_brief_rejects_protected_target(brief: DecisionBrief) -> None:
    with pytest.raises(ValidationError, match="protected entities"):
        DecisionBrief.model_validate(brief.model_dump() | {"protected_entity_ids": ["vendor_auditlog"]})


def test_only_inaction_scenario_has_no_plan() -> None:
    common = {"run_id": "run_1", "delay_days": 0, "baseline_twin_version": "t1", "created_at": NOW}
    Scenario(scenario_id="scn_run_1_inaction_none", future="inaction", **common)
    with pytest.raises(ValidationError, match="only the inaction"):
        Scenario(scenario_id="scn_run_1_act_now_none", future="act_now", **common)


def test_event_payload_resolved_by_type() -> None:
    event = Event.model_validate(
        {
            "event_id": "evt_1",
            "run_id": "run_1",
            "sequence": 1,
            "type": "phase_changed",
            "actor": "orchestrator",
            "timestamp": NOW,
            "payload": {"from_status": "created", "to_status": "validating"},
        }
    )
    assert event.type is EventType.phase_changed and isinstance(event.payload, PhaseChanged)


def test_future_view_summary_truncated_to_40_words() -> None:
    words = [f"w{i}" for i in range(55)]
    view = AgentOutput.model_validate(
        {"act_now_view": {"summary": " ".join(words)}, "inaction_view": future_view(), "confidence": 0.5}
    ).act_now_view
    assert view.summary.split() == words[:40]


def test_agent_enums_accept_any_casing() -> None:
    output = AgentOutput.model_validate(
        {
            "act_now_view": future_view()
            | {
                "proposed_impacts": [
                    {
                        "affected_entity": "wf_billing_recon",
                        "metric": "owners",
                        "direction": " Increase ",
                        "polarity": "HARM",
                        "category": "Ownership",
                        "level": " DIRECT",
                        "severity": 4,
                        "rationale": "Only owner leaves.",
                        "confidence": 0.7,
                    }
                ]
            },
            "inaction_view": future_view(),
            "proposed_dependencies": [
                {"source": "role_billing_ops_lead", "target": "wf_billing_recon", "relation": "owns",
                 "rationale": "Runbook names the lead.", "confidence": 0.6}
            ],
            "confidence": 0.5,
        }
    )
    impact = output.act_now_view.proposed_impacts[0]
    assert (impact.direction, impact.polarity, impact.category, impact.level) == (
        Direction.increase, Polarity.harm, ImpactCategory.ownership, ImpactLevel.direct
    )
    assert output.proposed_dependencies[0].relation is Relation.OWNS
    with pytest.raises(ValidationError):
        ProposedDependency.model_validate(
            {"source": "a", "target": "b", "relation": " owned by ", "rationale": "x", "confidence": 0.5}
        )


def test_strict_models_keep_exact_enums() -> None:
    with pytest.raises(ValidationError):
        Intervention(id="i_x", kind="ACTION", type="remove_vendor", target_entity_id="vendor_auditlog", rationale="x")
