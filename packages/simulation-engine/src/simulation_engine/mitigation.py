"""Mitigation re-simulation (plan E-07, sections 4.2, 11.8, 13.8, 19.3, 19.5; schema v2.2.0 section 7.10, rule 12).

``mitigate`` runs a plan's act-now future twice, as planned (``before``) and with the mitigation
actions added (``after``), and reports what the mitigations restore. The mitigations are graph
edits on the post-action scenario (``interventions.py``), so a mitigation changes only what can be
reached from its target (plan 19.5).

**Readiness gate.** The change is staged after the readiness gates pass (plan 4.2): the
mitigations are ready on ``ready_day = max(start_day + duration_days)``, and every plan action
that would start earlier moves to ``ready_day``.

**Mitigated plan.** ``plan_{parent}_mitigated``, labelled "<label> with mitigations", source
``mitigated``, with the parent's interventions then the mitigations. Contracts carry feasibility
only as booleans, so when the mitigations turn an infeasible plan feasible, ``after.assumptions``
says it is conditionally feasible and names the conditions (each mitigation's duration and cost and
the readiness gate), followed by the total mitigation time and one-time cost.

**Restored entities.** Every entity with a ratio harm in ``before`` whose largest ratio harm in
``after`` is gone or smaller, and every workflow stranded in ``before`` and not in ``after``.

**Changed metrics.** A name is listed, once, when its value differs between ``before`` and
``after``: the metric of every constraint result (compared per constraint ID), and the result
measures in ``RESULT_METRICS``.
"""

from __future__ import annotations

from collections.abc import Callable

from contracts_py.decision import CandidatePlan, DecisionBrief, Intervention
from contracts_py.engine import MitigationComparison, SimulationResult
from contracts_py.enums import Future, InterventionKind, Polarity
from contracts_py.twin import OrganizationSettings, Twin

from .futures import scenario_for
from .simulate import bounded_id, plan_interventions, simulate

MODE = "full"
RESULT_METRICS: dict[str, Callable[[SimulationResult], float]] = {
    "net_value_usd": lambda r: r.value.net_value_usd,
    "transition_cost_usd": lambda r: r.value.transition_cost_usd,
    "added_cost_usd": lambda r: r.value.added_cost_usd,
    "expected_business_loss_usd": lambda r: r.value.expected_business_loss_usd,
    "pressure_cost_usd": lambda r: r.value.pressure_cost_usd,
    "risk_score": lambda r: r.risk.score,
    "stranded_workflows": lambda r: sum(c.stranded for c in r.workflow_coverage),
    "lost_knowledge_assets": lambda r: sum(k.lost for k in r.knowledge_coverage),
}


def _ratio_harms(result: SimulationResult) -> dict[str, float]:
    """Entity ID -> its largest ratio harm."""
    harms: dict[str, float] = {}
    for i in result.impacts:
        if i.polarity is Polarity.harm and i.unit == "ratio":
            harms[i.affected_entity] = max(harms.get(i.affected_entity, 0.0), i.magnitude)
    return harms


def _restored(before: SimulationResult, after: SimulationResult) -> list[str]:
    harms_after = _ratio_harms(after)
    restored = {e for e, m in _ratio_harms(before).items() if harms_after.get(e, 0.0) < m}
    stranded_after = {c.workflow_id for c in after.workflow_coverage if c.stranded}
    restored |= {c.workflow_id for c in before.workflow_coverage if c.stranded and c.workflow_id not in stranded_after}
    return sorted(restored)


def _changed_metrics(before: SimulationResult, after: SimulationResult) -> list[str]:
    after_values = {c.constraint_id: c.value for c in after.constraint_results}
    changed = {c.metric for c in before.constraint_results if after_values.get(c.constraint_id) != c.value}
    changed |= {name for name, read in RESULT_METRICS.items() if read(before) != read(after)}
    return sorted(changed)


def mitigate(twin: Twin, brief: DecisionBrief, plan: CandidatePlan, actions: list[Intervention], *,
             settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> MitigationComparison:
    """``plan``'s act-now future before and after adding the mitigation ``actions``; the baseline is never changed."""
    if not actions:
        raise ValueError("mitigate needs at least one mitigation")
    not_mitigations = [a.id for a in actions if a.kind is not InterventionKind.mitigation]
    if not_mitigations:
        raise ValueError(f"mitigate takes only mitigations; these are actions: {not_mitigations}")
    planned = plan_interventions(brief, plan)
    clashes = sorted({a.id for a in actions} & {i.id for i in planned})
    if clashes:
        raise ValueError(f"mitigation IDs clash with the plan's interventions: {clashes}")

    before = simulate(twin, brief, scenario_for(twin, brief, run_id, Future.act_now, plan), plan, MODE,
                      settings=settings)

    ready_day = max(a.start_day + (a.duration_days or 0) for a in actions)
    first_start = min(a.start_day for a in actions)
    early = {i.id for i in planned if i.start_day < ready_day}
    if early:
        gate = (f"Readiness gate: the plan's actions {', '.join(sorted(early))} move to day {ready_day}, when the "
                "mitigations are complete (plan 4.2)")
    else:
        gate = (f"Readiness gate: the mitigations complete by day {ready_day}, before the plan's first action on day "
                f"{min(i.start_day for i in planned)}")
    mitigation_ids = {a.id for a in actions}
    kept = [i.model_copy(update={"start_day": ready_day}) if i.id in early else i
            for i in brief.candidate_interventions if i.id not in mitigation_ids]
    # model_copy, not a re-validated brief: a mitigation may document or back up a protected entity (rule 5).
    brief_after = brief.model_copy(update={"candidate_interventions": [*kept, *actions]})
    mitigated = CandidatePlan(
        plan_id=bounded_id("plan_", f"{plan.plan_id.removeprefix('plan_')}_mitigated"),
        label=f"{plan.label} with mitigations", intervention_ids=[*plan.intervention_ids, *(a.id for a in actions)],
        source="mitigated", parent_plan_id=plan.plan_id,
    )
    after = simulate(twin, brief_after, scenario_for(twin, brief_after, run_id, Future.act_now, mitigated), mitigated,
                     MODE, settings=settings)

    cost = sum(a.one_time_cost_usd for a in actions)
    notes = [gate]
    if after.feasible and not before.feasible:
        conditions = [f"{a.id} ({a.type} on {a.target_entity_id}) completes in {a.duration_days or 0} days for "
                      f"${a.one_time_cost_usd:,}" for a in actions]
        notes.append(f"Conditionally feasible: only if {'; '.join(conditions)}; and the plan's actions start no "
                     f"earlier than day {ready_day} (readiness gate)")
    notes.append(f"Mitigations take {ready_day - first_start} days (day {first_start} to day {ready_day}) and cost "
                 f"${cost:,} one-time")
    after = after.model_copy(update={"assumptions": [*after.assumptions, *notes]})

    return MitigationComparison(
        plan_id_before=plan.plan_id, plan_id_after=mitigated.plan_id, actions=list(actions), before=before,
        after=after, restored_entity_ids=_restored(before, after), changed_metrics=_changed_metrics(before, after),
        feasible_before=before.feasible, feasible_after=after.feasible,
    )
