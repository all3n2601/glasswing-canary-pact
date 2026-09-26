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


def interpret_decision_prompt(prompt: str, *, twin: Twin, created_by: str, horizon_days: int = 365) -> DecisionDraft:
    """Create a reviewable brief without inventing entities or quantified effects."""
    prompt = " ".join(prompt.split())
    digest = hashlib.sha256(prompt.encode()).hexdigest()[:12]
    matched = _matching_entities(prompt, twin)
    departments = [entity.id for entity in twin.entities if entity.type is EntityType.department]
    targets = matched or departments
    warnings = []
    if not matched:
        warnings.append(
            "No company entity was named clearly enough to resolve. The draft uses every department as an "
            "assessment scope; confirm specific systems, projects, vendors, roles or workflows before approval."
        )

    interventions = [
        Intervention(
            id=f"assess_{target.removeprefix('dept_').removeprefix('vendor_').removeprefix('role_')}",
            kind=InterventionKind.action,
            type=ActionType.assess_change,
            target_entity_id=target,
            start_day=0,
            rationale="Assess the user-proposed change without assuming an unsupported quantitative effect.",
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
        decision_type=_decision_type(prompt.casefold()),
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
        matched_entity_ids=matched,
        assumptions=[
            "The prompt expresses a proposal for assessment, not an approved action.",
            "Unquantified effects remain unknown until deterministic rules or user-supplied values support them.",
        ],
        warnings=warnings,
        assessing_department_ids=departments,
    )
