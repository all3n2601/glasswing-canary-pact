"""Scenario-only organizational edits and authoritative office projection."""
from contracts_py.decision import DecisionBrief, Intervention
from contracts_py.engine import DepartmentScenarioState
from contracts_py.enums import ActionType, EntityType, Relation
from contracts_py.twin import Twin
from company_twin import edit_department


def prepare_organization(twin: Twin, interventions: list[Intervention], brief: DecisionBrief | None):
    changes = {c.intervention_id: c for c in brief.organization_changes} if brief else {}
    selected = [i for i in interventions if i.id in changes]
    if not selected:
        return twin, interventions
    result = twin.model_copy(deep=True)
    prepared = []
    for intervention in interventions:
        change = changes.get(intervention.id)
        if not change:
            prepared.append(intervention)
            continue
        if intervention.target_entity_id != change.department_id:
            raise ValueError("Organization change and intervention must target the same department")
        if change.operation == "create":
            if any(e.id == change.department_id for e in result.entities):
                raise ValueError("Proposed department ID already exists")
            assert change.new_department is not None
            if not change.new_department.active:
                raise ValueError("A proposed new department must be active")
            result = edit_department(result, change.new_department, actor="scenario")
            prepared.append(intervention.model_copy(update={"type": ActionType.invest, "amount_usd": change.new_department.annual_budget_usd, "amount_pct": None}))
        elif change.operation == "close":
            if not any(p.department_id == change.department_id and p.active for p in result.department_profiles):
                raise ValueError("Closure requires an active department")
            prepared.append(intervention.model_copy(update={"type": ActionType.reduce_capacity, "amount_pct": 100}))
        else:
            profiles = {p.department_id: p for p in result.department_profiles}
            source, destination = profiles.get(change.department_id), profiles.get(change.destination_department_id or "")
            if not source or not destination or not destination.active:
                raise ValueError("Transfer requires an existing source and active destination")
            for workflow_id in change.workflow_ids:
                workflow = next((e for e in result.entities if e.id == workflow_id and e.type is EntityType.workflow and e.department_id == source.department_id), None)
                if workflow is None:
                    raise ValueError("Transfer workflow must belong to the source department")
                workflow.department_id = destination.department_id
                source.owned_entity_ids = [x for x in source.owned_entity_ids if x != workflow_id]
                source.critical_workflow_ids = [x for x in source.critical_workflow_ids if x != workflow_id]
                if workflow_id not in destination.owned_entity_ids:
                    destination.owned_entity_ids.append(workflow_id)
                if workflow.criticality.value in {"high", "critical"}:
                    destination.critical_workflow_ids.append(workflow_id)
                for edge in result.edges:
                    if edge.source == source.department_id and edge.target == workflow_id and edge.relation is Relation.OWNS:
                        edge.source = destination.department_id
            prepared.append(intervention)
    return result, prepared


def department_states(baseline: Twin, prepared: Twin, interventions: list[Intervention], brief: DecisionBrief | None, delay: int = 0):
    before = {p.department_id: p for p in baseline.department_profiles}
    names = {e.id: e.name for e in prepared.entities}
    changes = {c.intervention_id: c for c in brief.organization_changes} if brief else {}
    rows = []
    for profile in prepared.department_profiles:
        old = before.get(profile.department_id)
        fte = old.staffing.actual_fte if old else 0
        budget = old.budget.annual_budget_usd if old else 0
        final_fte, final_budget = profile.staffing.actual_fte, profile.budget.annual_budget_usd
        lifecycle = "active" if old else "added"
        day = 0
        transferred, notes = [], []
        if not old:
            notes.append("Declared staffing and cost only; workflow capability is not verified.")
        for i in interventions:
            change = changes.get(i.id)
            role = next((e for e in baseline.entities if e.id == i.target_entity_id and e.type is EntityType.role
                         and e.department_id == profile.department_id), None)
            if role and i.type in (ActionType.remove_roles, ActionType.reduce_capacity, ActionType.add_capacity):
                capacity = role.capacity_fte or 0
                share = 1 if i.type is ActionType.remove_roles else (i.amount_pct or 0) / 100
                final_fte = max(0, final_fte + capacity * share * (1 if i.type is ActionType.add_capacity else -1))
                day = max(day, (i.start_day or 0) + delay)
                notes.append("Staffing reflects the modeled capacity change of the targeted role.")
            if change and change.operation == "transfer" and profile.department_id in (change.department_id, change.destination_department_id):
                day = max(day, (i.start_day or 0) + delay)
                transferred.extend(change.workflow_ids)
                notes.append("Ownership changes do not establish trained owners or receiver capacity.")
            if i.target_entity_id != profile.department_id:
                continue
            day = max(day, (i.start_day or 0) + delay)
            if i.type in (ActionType.reduce_capacity, ActionType.add_capacity):
                share = (i.amount_pct or 0)/100
                sign = -1 if i.type is ActionType.reduce_capacity else 1
                final_fte *= 1 + sign*share
                notes.append("Budget is the allocated budget; realized savings are reported in the financial result.")
            if change and change.operation == "close":
                lifecycle, final_fte = "closed", 0
                notes.append("Closed in this scenario; outstanding workflow obligations remain visible.")
        rows.append(DepartmentScenarioState(department_id=profile.department_id, name=names[profile.department_id],
            lifecycle=lifecycle, baseline_fte=fte, scenario_fte=final_fte, baseline_budget_usd=budget,
            scenario_budget_usd=final_budget, effective_day=day, transferred_workflow_ids=transferred, modeling_notes=notes))
    return rows
