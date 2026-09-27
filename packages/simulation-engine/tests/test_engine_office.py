"""Department edits must remain scenario-isolated and deterministic."""
from company_twin import load_company_twin, edit_department
from contracts_py.decision import DecisionBrief, DepartmentEdit
from contracts_py.twin import OrganizationSettings
from simulation_engine import quick_impact


def declaration():
    return DepartmentEdit(department_id="dept_research", name="Research", mission="Test new capabilities",
                          actual_fte=4, annual_budget_usd=400000, assumption="Declared capacity; workflow capabilities have not been verified.")


def brief_for(department_id, operation="create", **extra):
    return DecisionBrief.model_validate(dict(decision_id="dec_office", decision_type="restructure",
        title="Office change", statement="Test department change", goal=dict(metric="net_value_usd", target=0),
        candidate_interventions=[dict(id="change_office",kind="action",type="assess_change",target_entity_id=department_id,rationale="User scenario")],
        organization_changes=[dict(intervention_id="change_office",operation=operation,department_id=department_id,**extra)],created_by="user_test"))


def test_create_department_isolated_repeatable_and_charged():
    twin=load_company_twin(); original=twin.model_dump_json()
    brief=brief_for("dept_research",new_department=declaration().model_dump())
    a=quick_impact(twin,brief.candidate_interventions,brief=brief)
    b=quick_impact(twin,brief.candidate_interventions,brief=brief)
    assert a.model_dump_json()==b.model_dump_json()
    assert twin.model_dump_json()==original
    assert a.value.added_cost_usd==400000
    row=next(d for d in a.department_states if d.department_id=="dept_research")
    assert row.lifecycle=="added" and row.scenario_fte==4 and row.baseline_fte==0
    assert row.modeling_notes


def test_closure_preserves_obligations_and_baseline():
    twin=load_company_twin(); original=twin.model_dump_json()
    brief=brief_for("dept_operations","close")
    result=quick_impact(twin,brief.candidate_interventions,brief=brief)
    row=next(d for d in result.department_states if d.department_id=="dept_operations")
    assert row.lifecycle=="closed" and row.scenario_fte==0
    assert result.impacts and result.workflow_coverage
    assert twin.model_dump_json()==original


def test_baseline_archive_rejects_unresolved_work():
    import pytest
    twin=load_company_twin()
    edit=declaration().model_copy(update={"department_id":"dept_operations","active":False,"actual_fte":0,"annual_budget_usd":0})
    with pytest.raises(ValueError,match="still owns work"):
        edit_department(twin,edit,actor="user_test")


def test_transfer_never_invents_qualified_owners():
    twin=load_company_twin()
    workflow=next(e for e in twin.entities if e.type.value=="workflow" and e.department_id=="dept_operations")
    brief=brief_for("dept_operations","transfer",destination_department_id="dept_engineering",workflow_ids=[workflow.id])
    result=quick_impact(twin,brief.candidate_interventions,brief=brief)
    row=next(d for d in result.department_states if d.department_id=="dept_engineering")
    assert workflow.id in row.transferred_workflow_ids
    assert any("trained owners" in note for note in row.modeling_notes)
    assert next(e for e in twin.entities if e.id==workflow.id).department_id=="dept_operations"
