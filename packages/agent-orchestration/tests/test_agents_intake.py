from contracts_py.enums import ActionType, EntityType

from agent_orchestration.intake import interpret_decision_prompt


def test_generic_supplier_prompt_selects_highest_spend_vendors(twin) -> None:
    draft = interpret_decision_prompt(
        "Consolidate our largest suppliers without delaying production",
        twin=twin,
        created_by="usr_test",
    )
    ranked = sorted(
        (entity for entity in twin.entities if entity.type is EntityType.vendor),
        key=lambda entity: (entity.annual_cost_usd or 0, entity.id),
        reverse=True,
    )[:7]

    assert draft.matched_entity_ids == [entity.id for entity in ranked]
    assert all(item.type is ActionType.remove_vendor for item in draft.brief.candidate_interventions)
    assert any("highest-spend" in warning for warning in draft.warnings)


def test_department_role_prompt_expands_to_safe_role_assessments(twin) -> None:
    draft = interpret_decision_prompt(
        "Assess removing an Operations role without interrupting billing",
        twin=twin,
        created_by="usr_test",
    )
    expected = sorted(
        entity.id for entity in twin.entities
        if entity.type is EntityType.role and entity.department_id == "dept_operations"
    )

    assert sorted(draft.matched_entity_ids) == expected
    assert all(item.type is ActionType.assess_change for item in draft.brief.candidate_interventions)
    assert any("no specific role" in warning.lower() for warning in draft.warnings)


def test_capacity_percentage_becomes_deterministic_reduction(twin) -> None:
    draft = interpret_decision_prompt(
        "Reduce Operations capacity by 5 percent",
        twin=twin,
        created_by="usr_test",
    )

    assert draft.matched_entity_ids == ["dept_operations"]
    assert len(draft.brief.candidate_interventions) == 1
    assert draft.brief.candidate_interventions[0].type is ActionType.reduce_capacity
    assert draft.brief.candidate_interventions[0].amount_pct == 5
