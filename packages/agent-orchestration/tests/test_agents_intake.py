import pytest

from contracts_py.enums import ActionType, DecisionType
from contracts_py.twin import OrganizationSettings

from agent_orchestration.intake import DecisionIntake, IntakeInvalid, IntakeUnavailable
from agent_orchestration.llm import LiveReply
from company_twin import entity_map
from simulation_engine import apply_interventions


PROMPT = (
    "Remove BeaconIQ and EchoMarket to save at least $2 billion annually while preserving compliance and "
    "critical data coverage."
)


def proposal(*, target: str = "vendor_beacon") -> dict:
    return {
        "decision_type": "vendor_consolidation",
        "title": "Remove BeaconIQ and EchoMarket",
        "goal": {
            "metric": "annual_savings_usd",
            "target": 2_000_000_000,
            "unit": "usd",
            "basis": "gross",
            "direction": "at_least",
        },
        "candidate_interventions": [
            {"type": "remove_vendor", "target_entity_id": target, "start_day": 30,
             "rationale": "The user explicitly proposed removing this vendor."},
            {"type": "remove_vendor", "target_entity_id": "vendor_echo", "start_day": 30,
             "rationale": "The user explicitly proposed removing this vendor."},
        ],
        "constraints": [
            {"metric": "compliance_controls_broken", "operator": "==", "threshold": 0, "unit": "count",
             "hard": True, "description": "No mandatory control may break."},
            {"metric": "critical_coverage_pct", "operator": ">=", "threshold": 100, "unit": "percent",
             "hard": True, "description": "Critical data coverage stays complete."},
        ],
        "assumptions": [],
        "warnings": [],
    }


class ScriptedLive:
    def __init__(self, *items):
        self.items = list(items)
        self.messages = []

    def __call__(self, model_id, messages, output_model, *, timeout, temperature, structured_output="auto"):
        self.messages.append(messages)
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return LiveReply(item)


def intake(live) -> DecisionIntake:
    settings = OrganizationSettings(llm_mode="live", model_id_strong="test-model")
    return DecisionIntake(settings, live_call=live)


def test_live_intake_preserves_actions_goal_constraints_and_stable_ids(twin) -> None:
    draft = intake(ScriptedLive(proposal())).draft(PROMPT, twin=twin, created_by="usr_test")

    assert draft.brief.decision_type is DecisionType.vendor_consolidation
    assert draft.brief.goal.metric == "annual_savings_usd"
    assert draft.brief.goal.target == 2_000_000_000
    assert draft.matched_entity_ids == ["vendor_beacon", "vendor_echo"]
    assert [item.type for item in draft.brief.candidate_interventions] == [
        ActionType.remove_vendor,
        ActionType.remove_vendor,
    ]
    assert [item.id for item in draft.brief.candidate_interventions] == ["remove_beacon", "remove_echo"]
    assert all(item.params == {"prompt_generated": True, "intake_source": "live"}
               for item in draft.brief.candidate_interventions)
    assert {item.metric for item in draft.brief.constraints} == {
        "compliance_controls_broken",
        "critical_coverage_pct",
    }


def test_unknown_entity_is_rejected_then_corrected_by_live_intake(twin) -> None:
    live = ScriptedLive(proposal(target="vendor_invented"), proposal())
    draft = intake(live).draft(PROMPT, twin=twin, created_by="usr_test")

    assert draft.matched_entity_ids == ["vendor_beacon", "vendor_echo"]
    assert len(live.messages) == 2
    assert "unknown entity ids" in live.messages[1][-1]["content"]


def test_repeated_unknown_entity_fails_without_rule_based_fallback(twin) -> None:
    live = ScriptedLive(proposal(target="vendor_invented"), proposal(target="vendor_still_invented"))
    with pytest.raises(IntakeInvalid, match="remained invalid"):
        intake(live).draft(PROMPT, twin=twin, created_by="usr_test")


def test_provider_failure_is_unavailable_without_rule_based_fallback(twin) -> None:
    live = ScriptedLive(TimeoutError("provider timed out"))
    with pytest.raises(IntakeUnavailable, match="TimeoutError"):
        intake(live).draft(PROMPT, twin=twin, created_by="usr_test")


def capacity_proposal(**fields) -> dict:
    result = proposal()
    result["decision_type"] = "capacity_change"
    result["candidate_interventions"] = [{
        "type": "reduce_capacity", "target_entity_id": "role_billing_ops_lead",
        "rationale": "Explicit staffing change requested by the user.", **fields,
    }]
    return result


@pytest.mark.parametrize("action_type", ["reduce_capacity", "add_capacity"])
@pytest.mark.parametrize("unit", ["dollars", "fte", "percent"])
def test_capacity_units_normalize_and_simulate_without_model_arithmetic(twin, action_type, unit) -> None:
    role = entity_map(twin)["role_billing_ops_lead"]
    role.capacity_fte = 10
    role.annual_cost_usd = 1_000_000
    quantities = {
        "dollars": {"amount_usd": 200_000, "dollar_basis": "annual_staffing_cost"},
        "fte": {"amount_fte": 2},
        "percent": {"amount_pct": 20},
    }
    prompt = f"{action_type} for Billing Operations by {quantities[unit]}"
    live = ScriptedLive(capacity_proposal(type=action_type, **quantities[unit]))
    draft = intake(live).draft(prompt, twin=twin, created_by="usr_test")
    action = draft.brief.candidate_interventions[0]
    assert action.type.value == action_type and action.amount_pct == 20
    assert draft.brief.statement == prompt
    assert not draft.warnings and len(live.messages) == 1
    applied = apply_interventions(twin, [action])
    assert entity_map(applied.twin)[role.id].capacity_fte == (8 if action_type == "reduce_capacity" else 12)
    assert (applied.gross_savings_usd if action_type == "reduce_capacity" else applied.added_cost_usd) == 200_000
    assert role.capacity_fte == 10
    if unit != "percent":
        assert "20%" in draft.assumptions[-1]
        assert draft.assumptions[-1] in applied.assumptions


@pytest.mark.parametrize(("fields", "message"), [
    ({}, "Specify one capacity change"),
    ({"amount_usd": 500_000}, "budget cut is not assumed"),
    ({"amount_usd": 500_000, "dollar_basis": "budget"}, "budget cut is not assumed"),
    ({"amount_fte": 100_000}, "exceeds"),
    ({"amount_fte": 1, "amount_pct": 10}, "Specify one capacity change"),
    ({"type": "invest"}, "investment amount"),
    ({"type": "assess_change"}, "resources changing"),
])
def test_unquantified_requests_produce_reviewable_assessments(twin, fields, message) -> None:
    live = ScriptedLive(capacity_proposal(**fields))
    draft = intake(live).draft("Evaluate the proposed company change", twin=twin, created_by="usr_test")
    action = draft.brief.candidate_interventions[0]
    assert action.type is ActionType.assess_change
    assert action.amount_pct is None and action.amount_usd is None
    assert message in draft.warnings[-1]
    assert action.params["requested_action"]["type"] == fields.get("type", "reduce_capacity")
    assert len(live.messages) == 1  # Missing business facts should not cause model retries.
    applied = apply_interventions(twin, [action])
    assert applied.twin.model_dump_json() == twin.model_dump_json()
    assert not applied.losses and not applied.gains and not applied.gross_savings_usd


def test_missing_capacity_baseline_is_an_assessment_not_a_guessed_percentage(twin) -> None:
    entity_map(twin)["role_billing_ops_lead"].annual_cost_usd = None
    draft = intake(ScriptedLive(capacity_proposal(amount_usd=10, dollar_basis="annual_staffing_cost"))).draft(
        "Reduce annual Billing Operations staffing costs by $10", twin=twin, created_by="usr_test",
    )
    assert draft.brief.candidate_interventions[0].type is ActionType.assess_change
    assert "complete annual staffing cost baseline" in draft.warnings[-1]


def test_partial_role_removal_does_not_remove_the_entire_role_group(twin) -> None:
    role = entity_map(twin)["role_billing_ops_lead"]
    role.capacity_fte = 10
    draft = intake(ScriptedLive(capacity_proposal(type="remove_roles", amount_fte=2))).draft(
        "Remove two full-time Billing Operations positions", twin=twin, created_by="usr_test",
    )
    action = draft.brief.candidate_interventions[0]
    assert action.type is ActionType.reduce_capacity
    applied = apply_interventions(twin, [action])
    assert entity_map(applied.twin)[role.id].capacity_fte == 8


def test_constraints_that_demand_harm_are_dropped_with_a_warning(twin) -> None:
    bad = proposal()
    bad["constraints"] += [
        {"metric": "max_capacity_loss_pct", "operator": "==", "threshold": 100, "unit": "percent", "hard": True,
         "scope_entity_id": "vendor_beacon", "description": "Exit the vendor completely."},
        {"metric": "customer_impact_pct", "operator": ">=", "threshold": 5, "unit": "percent", "hard": True,
         "description": "Move every customer."},
        {"metric": "max_capacity_loss_pct", "operator": "<=", "threshold": 20, "unit": "percent", "hard": True,
         "description": "Keep capacity loss within 20%."},
    ]
    draft = intake(ScriptedLive(bad)).draft(PROMPT, twin=twin, created_by="usr_test")

    kept = {(c.metric, c.operator, c.threshold) for c in draft.brief.constraints}
    assert kept == {("compliance_controls_broken", "==", 0), ("critical_coverage_pct", ">=", 100),
                    ("max_capacity_loss_pct", "<=", 20)}
    assert sum("Ignored a constraint" in w for w in draft.warnings) == 2


def test_protective_constraints_are_kept_unchanged(twin) -> None:
    draft = intake(ScriptedLive(proposal())).draft(PROMPT, twin=twin, created_by="usr_test")

    assert len(draft.brief.constraints) == 2
    assert not any("Ignored a constraint" in w for w in draft.warnings)
