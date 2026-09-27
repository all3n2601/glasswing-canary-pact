import hashlib
import re

from contracts_py.api import DecisionDraft
from contracts_py.decision import Constraint, DecisionBrief, Goal, Intervention
from contracts_py.enums import ActionType, DecisionType, EntityType, InterventionKind
from contracts_py.twin import Twin


def _decision_type(text: str) -> DecisionType:
    if any(word in text for word in ("restructure", "layoff", "role", "headcount", "workforce")):
        return DecisionType.restructure
    if any(word in text for word in ("vendor", "supplier", "provider", "contract")):
        return DecisionType.vendor_consolidation
    if any(word in text for word in ("project", "launch", "roadmap", "initiative")):
        return DecisionType.project_decision
    if any(word in text for word in ("invest", "buy", "build", "expand", "acquire")):
        return DecisionType.investment
    if any(word in text for word in ("capacity", "hire", "staff", "team")):
        return DecisionType.capacity_change
    if any(word in text for word in ("save", "cut", "reduce cost", "cost reduction")):
        return DecisionType.cost_reduction
    return DecisionType.mixed


def _title(prompt: str) -> str:
    first = re.split(r"[.!?\n]", prompt.strip(), maxsplit=1)[0].strip()
    return (first or "Assess proposed company decision")[:120]


def _matching_entities(prompt: str, twin: Twin) -> list[str]:
    lowered = prompt.casefold()
    matches = []
    for entity in twin.entities:
        name = entity.name.casefold().strip()
        if entity.id.casefold() in lowered or (len(name) >= 4 and name in lowered):
            matches.append(entity.id)
    return list(dict.fromkeys(matches))


def _percentage(prompt: str) -> float | None:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:%|percent)\b", prompt, re.IGNORECASE)
    return min(100.0, float(match.group(1))) if match else None


def _resolve_targets(prompt: str, twin: Twin, matched: list[str], decision_type: DecisionType
                     ) -> tuple[list[str], ActionType, float | None, list[str]]:
    entities = {entity.id: entity for entity in twin.entities}
    matched_entities = [entities[entity_id] for entity_id in matched]
    warnings: list[str] = []

    if decision_type is DecisionType.vendor_consolidation:
        named = [entity.id for entity in matched_entities if entity.type is EntityType.vendor]
        if named:
            return named, ActionType.remove_vendor, None, warnings
        ranked = sorted(
            (entity for entity in twin.entities
             if entity.type is EntityType.vendor and (entity.annual_cost_usd or 0) > 0),
            key=lambda entity: (entity.annual_cost_usd or 0, entity.id),
            reverse=True,
        )[:7]
        if ranked:
            warnings.append(
                "No supplier was named explicitly. The draft uses the seven highest-spend modeled suppliers as "
                "reviewable consolidation candidates; confirm the shortlist before running the decision."
            )
            return [entity.id for entity in ranked], ActionType.remove_vendor, None, warnings

    if decision_type is DecisionType.restructure and any(word in prompt.casefold() for word in ("role", "roles")):
        named_roles = [entity.id for entity in matched_entities if entity.type is EntityType.role]
        if named_roles:
            return named_roles, ActionType.remove_roles, None, warnings
        department_ids = {entity.id for entity in matched_entities if entity.type is EntityType.department}
        scoped_roles = sorted(
            (entity for entity in twin.entities
             if entity.type is EntityType.role and entity.department_id in department_ids),
            key=lambda entity: entity.name,
        )
        if scoped_roles:
            warnings.append(
                "A department was named but no specific role was. Its modeled roles are included as non-destructive "
                "assessment candidates; select an exact role before proposing removal."
            )
            return [entity.id for entity in scoped_roles], ActionType.assess_change, None, warnings

    if decision_type is DecisionType.capacity_change:
        department_ids = [entity.id for entity in matched_entities if entity.type is EntityType.department]
        amount = _percentage(prompt)
        if department_ids and amount is not None:
            action = ActionType.reduce_capacity if any(
                word in prompt.casefold() for word in ("reduce", "cut", "decrease")
            ) else ActionType.add_capacity
            return department_ids, action, amount, warnings

    return matched, ActionType.assess_change, None, warnings


def interpret_decision_prompt(prompt: str, *, twin: Twin, created_by: str, horizon_days: int = 365) -> DecisionDraft:
    """Create a reviewable brief without inventing entities or quantified effects."""
    prompt = " ".join(prompt.split())
    digest = hashlib.sha256(prompt.encode()).hexdigest()[:12]
    matched = _matching_entities(prompt, twin)
    departments = [entity.id for entity in twin.entities if entity.type is EntityType.department]
    decision_type = _decision_type(prompt.casefold())
    targets, action, amount_pct, warnings = _resolve_targets(prompt, twin, matched, decision_type)
    targets = targets or departments
    if not matched and action is ActionType.assess_change:
        warnings.append(
            "No company entity was named clearly enough to resolve. The draft uses every department as an "
            "assessment scope; confirm specific systems, projects, vendors, roles or workflows before approval."
        )

    interventions = [
        Intervention(
            id=f"assess_{target.removeprefix('dept_').removeprefix('vendor_').removeprefix('role_')}",
            kind=InterventionKind.action,
            type=action,
            target_entity_id=target,
            amount_pct=amount_pct,
            start_day=0,
            rationale=(
                "Evaluate this candidate using the modeled company graph and deterministic calculations."
                if action is not ActionType.assess_change
                else "Assess the user-proposed change without assuming an unsupported quantitative effect."
            ),
            params={"prompt_generated": True},
        )
        for target in targets
    ]
    constraints = [
        Constraint(id="c_compliance", metric="compliance_controls_broken", operator="==", threshold=0,
                   unit="count", hard=True, description="No mandatory compliance control may break"),
        Constraint(id="c_revenue", metric="revenue_impact_pct", operator="<=", threshold=3,
                   unit="percent", hard=True, description="Revenue impact must remain within 3%"),
        Constraint(id="c_customer", metric="customer_impact_pct", operator="<=", threshold=2,
                   unit="percent", hard=True, description="Customer impact must remain within 2%"),
    ]
    brief = DecisionBrief(
        decision_id=f"dec_prompt_{digest}",
        decision_type=decision_type,
        title=_title(prompt),
        statement=prompt,
        goal=Goal(metric="net_value_usd", target=0, unit="usd", basis="net", direction="at_least"),
        horizon_days=horizon_days,
        candidate_interventions=interventions,
        constraints=constraints,
        created_by=created_by,
    )
    return DecisionDraft(
        brief=brief,
        matched_entity_ids=targets if targets != departments or matched else [],
        assumptions=[
            "The prompt expresses a proposal for assessment, not an approved action.",
            "Unquantified effects remain unknown until deterministic rules or user-supplied values support them.",
        ],
        warnings=warnings,
        assessing_department_ids=departments,
    )
