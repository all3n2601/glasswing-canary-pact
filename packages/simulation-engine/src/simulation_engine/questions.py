"""The missing-fact selector: which unknown is worth asking about (plan sections 11.10, 19.5; E-06).

Every uncertain input is perturbed across its allowed range in expected-value mode (Monte Carlo is
cut, plan E-03), and ranked by::

    score = probability_of_changing_winner * value_gap_between_alternatives - cost_of_getting_answer

- winner: the row ``compare_futures`` picks for ``plan`` against the portfolios the optimizer
  presents, naive, recommended and alternatives, as the orchestrator turns them into plans
  (computed once on the base twin; ``plan`` and duplicate intervention sets excluded), keyed by plan
  (``plan_id`` None is doing nothing, and a plan's act-now and delay rows are the same winner);
- uncertain inputs:
  (a) a null ``retains_history_after_termination`` on each vendor the plan removes, answered True
      and False; null is simulated as True (the optimistic assumption), so True is the base case;
  (b) the ``strength_range`` of each edge on the dependency paths (``edge_path``) of the plan's
      act-now harm impacts, answered at its low and high end, when the range is wider than 0; at
      most ``MAX_EDGE_INPUTS`` distinct edges (the vendor brief's Beacon + Echo plan has 9), those
      on the path of an impact that pushes a hard constraint first, then by the largest impact
      magnitude on them, then by edge ID;
- probability_of_changing_winner: the share of the input's equally weighted answers whose winner
  differs from the base winner;
- value_gap_between_alternatives: the largest net-value difference between the new winner and the
  base winner under an answer that changes the winner; for an input no answer changes, the base
  winner's margin over the runner-up (the best-ranked row of another plan);
- cost_of_getting_answer: ``COST_OF_ANSWER_USD`` by kind: a vendor fact is a contract-clause lookup
  (about a day of procurement and counsel time), an edge strength an SME measurement of the
  dependency (about two weeks of analyst time).

Questions are returned by score, highest first (ties by ``uncertain_input``); the demo asks only
the first. A comparison over every portfolio costs about a second on the vendor brief, so each
answer re-simulates only the plans that could win: every alternative feasible on the base twin, and
a rejected one only when it can turn feasible (``_can_recover``). An answer changes losses only at
the perturbed edge's target or vendor and downstream of it; a missed gross-savings goal never
recovers, and a failed hard constraint only when an impact it names lies downstream. This gives the
same ranking as re-simulating every portfolio at a tenth of the cost (about 2-3 s on the vendor brief).
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
from contracts_py.decision import CandidatePlan, DecisionBrief
from contracts_py.engine import FutureComparison, FutureRow, MissingQuestion, Portfolio, SimulationResult
from contracts_py.enums import ActionType, EntityType, Future, Polarity
from contracts_py.twin import Edge, OrganizationSettings, Twin

from .futures import compare_futures, ranked_rows, scenario_for
from .optimizer import optimize
from .simulate import bounded_id, plan_interventions, simulate

HISTORY_FIELD = "retains_history_after_termination"
MAX_EDGE_INPUTS = 12
COST_OF_ANSWER_USD = {"vendor_fact": 2_000, "edge_strength": 20_000}
NO_CHANGE = "no answer in range changes the winner"
NO_WINNER = "no feasible plan"
# The CandidatePlan source of each portfolio role, as the orchestrator assigns it.
PLAN_SOURCE = {"naive": "naive", "recommended": "optimizer", "alternative": "enumerated"}


@dataclass(frozen=True)
class _Input:
    """One uncertain input: its answers (label, perturbed twin or None for the base twin) and where losses change."""

    question_id: str
    text: str
    uncertain_input: str
    current_assumption: str
    answer_type: str
    cost_usd: int
    answers: list[tuple[str, Twin | None]]
    changes: str


def _plans(entries: list[tuple[str, Portfolio]], plan: CandidatePlan) -> list[CandidatePlan]:
    plans, seen = [], {plan.plan_id, frozenset(plan.intervention_ids)}
    for role, item in entries:
        if item.plan_id in seen or frozenset(item.intervention_ids) in seen:
            continue
        seen |= {item.plan_id, frozenset(item.intervention_ids)}
        plans.append(CandidatePlan(plan_id=item.plan_id, label=f"{role.capitalize()} plan "
                                   f"({', '.join(item.intervention_ids)})", intervention_ids=item.intervention_ids,
                                   source=PLAN_SOURCE[role]))  # type: ignore[arg-type]
    return plans


def _can_recover(result: SimulationResult, brief: DecisionBrief, reach: set[str]) -> bool:
    """Whether a rejected plan could turn feasible when only the losses of the entities in ``reach`` change.

    Gross savings depend on neither kind of input, so a missed gross-savings goal stays missed. A
    failed hard constraint reads the worst harmed entity or every broken one, so it can only pass
    when one of the impacts it names is in reach; a constraint that names none is kept.
    """
    if not result.goal_met and brief.goal.metric == "annual_savings_usd" and brief.goal.basis == "gross":
        return False
    affected = {i.impact_id: i.affected_entity for i in result.impacts}
    return all(not r.impact_ids or any(affected.get(i, "") in reach or i not in affected for i in r.impact_ids)
               for r in result.constraint_results if r.hard and not r.passed)


def _with_entity(twin: Twin, entity_id: str, **update: object) -> Twin:
    return twin.model_copy(update={"entities": [e.model_copy(update=update) if e.id == entity_id else e
                                                for e in twin.entities]})


def _with_edge(twin: Twin, edge_id: str, strength: float) -> Twin:
    return twin.model_copy(update={"edges": [e.model_copy(update={"strength": strength}) if e.id == edge_id else e
                                             for e in twin.edges]})


def _history_inputs(twin: Twin, brief: DecisionBrief, plan: CandidatePlan) -> list[_Input]:
    ents = {e.id: e for e in twin.entities}
    removed = [i.target_entity_id for i in plan_interventions(brief, plan) if i.type is ActionType.remove_vendor]
    inputs = []
    for vendor_id in dict.fromkeys(removed):
        vendor = ents[vendor_id]
        if vendor.type is not EntityType.vendor or getattr(vendor, HISTORY_FIELD) is not None:
            continue
        inputs.append(_Input(
            question_id=bounded_id("q_", f"{vendor_id}_{HISTORY_FIELD}"),
            text=f"Does {vendor.name} keep our historical records after the contract is terminated?",
            uncertain_input=f"{vendor_id}.{HISTORY_FIELD}",
            current_assumption=(f"Unknown (null); the engine assumes {vendor.name} retains history after termination "
                                "(True), the optimistic case"),
            answer_type="boolean", cost_usd=COST_OF_ANSWER_USD["vendor_fact"],
            answers=[("true", None), ("false", _with_entity(twin, vendor_id, **{HISTORY_FIELD: False}))],
            changes=vendor_id,
        ))
    return inputs


def _edge_inputs(twin: Twin, brief: DecisionBrief, plan: CandidatePlan, settings: OrganizationSettings,
                 run_id: str) -> list[_Input]:
    act_now = simulate(twin, brief, scenario_for(twin, brief, run_id, Future.act_now, plan), plan, "full",
                       settings=settings)
    hard = {c.id for c in brief.constraints if c.hard}
    rank: dict[str, tuple[bool, float]] = {}
    for impact in act_now.impacts:
        if impact.polarity is not Polarity.harm:
            continue
        pushes = bool(hard & set(impact.constraint_refs))
        for edge_id in impact.edge_path:
            known = rank.get(edge_id, (False, 0.0))
            rank[edge_id] = (known[0] or pushes, max(known[1], impact.magnitude))
    edges: dict[str, Edge] = {e.id: e for e in twin.edges}
    ents = {e.id: e for e in twin.entities}
    ranged = [edges[e] for e in rank if e in edges and edges[e].strength_range[1] > edges[e].strength_range[0]]
    ranged.sort(key=lambda e: (not rank[e.id][0], -rank[e.id][1], e.id))
    inputs = []
    for edge in ranged[:MAX_EDGE_INPUTS]:
        low, high = edge.strength_range
        source, target = ents[edge.source].name, ents[edge.target].name
        inputs.append(_Input(
            question_id=bounded_id("q_", f"{edge.id}_strength"),
            text=(f"How strongly does {target} depend on {source} ({edge.relation.value} edge {edge.id})? "
                  f"The allowed range is {low:g} to {high:g}."),
            uncertain_input=f"{edge.id}.strength",
            current_assumption=f"Midpoint strength {edge.strength:g} within the range {low:g} to {high:g}",
            answer_type="number", cost_usd=COST_OF_ANSWER_USD["edge_strength"],
            answers=[(f"{low:g}", _with_edge(twin, edge.id, low)), (f"{high:g}", _with_edge(twin, edge.id, high))],
            changes=edge.target,
        ))
    return inputs


def _winner(comparison: FutureComparison) -> FutureRow | None:
    return None if comparison.best_row_index is None else comparison.rows[comparison.best_row_index]


def _key(row: FutureRow | None) -> tuple[bool, str | None]:
    return (False, None) if row is None else (True, row.plan_id)


def _base_winner_row(comparison: FutureComparison, winner: FutureRow | None) -> FutureRow:
    """The base winner's row under a perturbation; inaction (else the first row) when nothing won on the base twin."""
    rows = comparison.rows
    if winner is not None:
        return next(r for r in rows if (r.future, r.plan_id) == (winner.future, winner.plan_id))
    return next((r for r in rows if r.future is Future.inaction), rows[0])


@dataclass(frozen=True)
class ScoredQuestion:
    """A question with the terms of its score: ``score = probability * question.value_gap_usd - cost_usd``."""

    question: MissingQuestion
    probability: float
    cost_usd: int
    score: float


def scored_questions(twin: Twin, brief: DecisionBrief, plan: CandidatePlan, *,
                     settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> list[ScoredQuestion]:
    """Every uncertain input of ``plan`` as a scored question, highest score first (ties by ``uncertain_input``)."""
    settings = settings or OrganizationSettings()
    portfolios = optimize(twin, brief, settings=settings, run_id=run_id)
    entries = [("naive", portfolios.naive)]
    if portfolios.recommended:
        entries.append(("recommended", portfolios.recommended))
    entries += [("alternative", p) for p in portfolios.alternatives]
    alternatives = _plans(entries, plan)
    results = {item.plan_id: item.result for _, item in entries}

    def compare(perturbed: Twin, plans: list[CandidatePlan]) -> FutureComparison:
        return compare_futures(perturbed, brief, plan, alternatives=plans, settings=settings, run_id=run_id)

    base = compare(twin, alternatives)
    feasible = {row.plan_id for row in base.rows if row.future is Future.alternative and row.feasible}
    graph = nx.DiGraph([(e.source, e.target) for e in twin.edges])
    winner = _winner(base)
    runner_up = next((base.rows[n] for n in ranked_rows(base.rows) if _key(base.rows[n]) != _key(winner)), None)
    margin = abs(winner.net_value_p50_usd - runner_up.net_value_p50_usd) if winner and runner_up else 0

    scored: list[ScoredQuestion] = []
    for item in [*_history_inputs(twin, brief, plan), *_edge_inputs(twin, brief, plan, settings, run_id)]:
        reach = {item.changes, *(nx.descendants(graph, item.changes) if item.changes in graph else ())}
        plans = [p for p in alternatives if p.plan_id in feasible or _can_recover(results[p.plan_id], brief, reach)]
        changes: list[str] = []
        gap = 0
        for label, perturbed in item.answers:
            result = base if perturbed is None else compare(perturbed, plans)
            new = _winner(result)
            if _key(new) == _key(winner):
                continue
            old = _base_winner_row(result, winner)
            gap = max(gap, abs((new or old).net_value_p50_usd - old.net_value_p50_usd))
            changes.append(f"{label}: the winner becomes {new.label if new else NO_WINNER}")
        probability = len(changes) / len(item.answers)
        value_gap = gap if changes else margin
        scored.append(ScoredQuestion(
            question=MissingQuestion(
                question_id=item.question_id, text=item.text, uncertain_input=item.uncertain_input,
                current_assumption=item.current_assumption, answer_type=item.answer_type,  # type: ignore[arg-type]
                options=[label for label, _ in item.answers],
                changes_recommendation_if="; ".join(changes) if changes else NO_CHANGE, value_gap_usd=value_gap,
            ),
            probability=probability, cost_usd=item.cost_usd, score=probability * value_gap - item.cost_usd,
        ))
    return sorted(scored, key=lambda q: (-q.score, q.question.uncertain_input))


def missing_questions(twin: Twin, brief: DecisionBrief, plan: CandidatePlan, *,
                      settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> list[MissingQuestion]:
    """Every uncertain input of ``plan`` as a question, most valuable first; the demo asks only the first."""
    return [q.question for q in scored_questions(twin, brief, plan, settings=settings, run_id=run_id)]
