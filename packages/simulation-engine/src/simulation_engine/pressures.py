"""Baseline pressures in expected-value form (plan section 11.2; schema v2.2.0 sections 5.5, 6.6, 7.6, A12).

A pressure acts on the company in every future, inaction included, unless an intervention in the
plan neutralises it (``neutralised_by``: same intervention type on the same target). A neutralised
pressure stops on the day its neutraliser starts, so in the delay future it runs through the delay.

Each pressure is priced over its active window ``[start_day, min(end_day, horizon, neutralised_day))``
in 30-day months (the last month runs to the horizon):

- ``renewal_step``: ``annual_cost * step_pct / 100 * days / 365`` from the renewal day.
- ``cost_growth``: ``annual_cost * days / 365 * ((1 + rate) ** k - 1)`` in the k-th month since it
  started, so the rate compounds monthly.
- ``hazard``: ``p * days / 30`` expected events at ``cost_per_event_usd`` each. From the day the
  scenario first harms the target, ``p`` becomes
  ``min(1, monthly_probability * (1 + capacity_sensitivity * capacity_loss(target)))``: cuts make
  incidents likelier.
- ``deadline``: ``consequence_cost_usd`` once, if the pressure is still active on ``start_day``.
- ``kpi_drift`` and ``budget_ceiling`` carry no dollar cost in expected-value mode and are reported
  at zero.

Ranges (``rate_range``, ``probability_range``) collapse to their point values; full Monte Carlo
sampling is plan E-03.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import accumulate

from contracts_py.decision import Intervention
from contracts_py.engine import Impact, PressureTrigger
from contracts_py.enums import (
    ClaimStatus,
    Direction,
    EntityType,
    ImpactCategory,
    ImpactLevel,
    Origin,
    Polarity,
    PressureKind,
)
from contracts_py.twin import Pressure, Twin

from .interventions import DAYS_PER_YEAR
from .propagation import DELAYED_AFTER_DAYS, impact_id
from .value import DAYS_PER_MONTH

# How sure the expected cost is, by kind: contracted renewals most, forecast growth less, incidents least.
CONFIDENCE = {PressureKind.renewal_step: 0.9, PressureKind.cost_growth: 0.8, PressureKind.hazard: 0.6,
              PressureKind.deadline: 0.8, PressureKind.kpi_drift: 0.6, PressureKind.budget_ceiling: 0.8}
UNPRICED = {PressureKind.kpi_drift, PressureKind.budget_ceiling}


@dataclass(frozen=True)
class Harm:
    """The scenario's loss at a pressure target and the day it starts."""

    magnitude: float
    first_effect_day: int


@dataclass
class PricedPressures:
    triggers: list[PressureTrigger] = field(default_factory=list)
    impacts: list[Impact] = field(default_factory=list)
    # Cumulative expected pressure cost per month; the last value is ``total_usd`` exactly.
    monthly_usd: list[int] = field(default_factory=list)
    total_usd: int = 0
    assumptions: list[str] = field(default_factory=list)


def active_pressures(twin: Twin, active_ids: list[str] | None) -> list[Pressure]:
    """The brief's active pressures (every twin pressure when the brief names none), in ID order."""
    if active_ids is None:
        return sorted(twin.pressures, key=lambda p: p.id)
    by_id = {p.id: p for p in twin.pressures}
    unknown = sorted(set(active_ids) - set(by_id))
    if unknown:
        raise ValueError(f"brief activates pressures missing from the twin: {unknown}")
    return [by_id[i] for i in sorted(set(active_ids))]


def neutralised_day(pressure: Pressure, interventions: list[Intervention]) -> int | None:
    """The first day an intervention of the plan switches ``pressure`` off, or None."""
    days = [i.start_day for i in interventions for ref in pressure.neutralised_by
            if i.type == ref.intervention_type and i.target_entity_id == ref.target_entity_id]
    return min(days, default=None)


def month_windows(horizon_days: int) -> list[tuple[int, int]]:
    months = max(1, horizon_days // DAYS_PER_MONTH)
    return [(m * DAYS_PER_MONTH, horizon_days if m == months - 1 else (m + 1) * DAYS_PER_MONTH) for m in range(months)]


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def _monthly_cost(pressure: Pressure, window: tuple[int, int], base_usd: int, harm: Harm | None,
                  horizon_days: int) -> tuple[list[float], float]:
    """Expected cost per month and expected events over ``window``."""
    costs, events = [], 0.0
    for bucket in month_windows(horizon_days):
        days = _overlap(bucket, window)
        cost = 0.0
        if days:
            match pressure.kind:
                case PressureKind.renewal_step:
                    cost = base_usd * (pressure.step_pct or 0) / 100 * days / DAYS_PER_YEAR
                case PressureKind.cost_growth:
                    k = (max(bucket[0], window[0]) - window[0]) // DAYS_PER_MONTH + 1
                    cost = base_usd * days / DAYS_PER_YEAR * ((1 + (pressure.rate or 0)) ** k - 1)
                case PressureKind.hazard:
                    p = pressure.monthly_probability or 0.0
                    boosted = p
                    after = 0
                    if harm is not None:
                        boosted = min(1.0, p * (1 + pressure.capacity_sensitivity * harm.magnitude))
                        after = _overlap(bucket, (max(window[0], harm.first_effect_day), window[1]))
                    n = (p * (days - after) + boosted * after) / DAYS_PER_MONTH
                    events += n
                    cost = n * (pressure.cost_per_event_usd or 0)
                case PressureKind.deadline:
                    if bucket[0] <= pressure.start_day < bucket[1]:
                        events += 1
                        cost = float(pressure.consequence_cost_usd or 0)
        if pressure.kind is PressureKind.renewal_step and days and bucket[0] <= window[0] < bucket[1]:
            events += 1
        costs.append(cost)
    return costs, events


def _severity(cost_usd: int, scale_usd: float) -> int:
    """1-5 from the expected cost as a share of the decision's goal."""
    share = min(1.0, cost_usd / scale_usd) if scale_usd > 0 else 1.0
    return max(1, min(5, 1 + round(4 * share)))


def price_pressures(twin: Twin, pressures: list[Pressure], interventions: list[Intervention], *,
                    harms: dict[str, Harm], horizon_days: int, decision_id: str, scenario_id: str,
                    scale_usd: float) -> PricedPressures:
    """Expected cost, triggers, and one ``pressure`` impact per costed pressure of one future."""
    ents = {e.id: e for e in twin.entities}
    months = len(month_windows(horizon_days))
    totals = [0.0] * months
    out = PricedPressures()
    for pressure in pressures:
        target = ents.get(pressure.target_entity_id)
        if target is None:
            raise ValueError(f"pressure {pressure.id} targets {pressure.target_entity_id}, which is not in the twin")
        off = neutralised_day(pressure, interventions)
        end = min(d for d in (pressure.end_day, horizon_days, off) if d is not None)
        window = (pressure.start_day, max(pressure.start_day, end))
        base = target.annual_cost_usd or 0
        if pressure.kind in (PressureKind.renewal_step, PressureKind.cost_growth) and not base:
            out.assumptions.append(f"{pressure.id}: {target.id} has no annual_cost_usd, so it is priced at $0")
        if pressure.kind in UNPRICED:
            out.assumptions.append(f"{pressure.id}: {pressure.kind.value} has no dollar cost in expected-value mode")
            costs, events = [0.0] * months, 0.0
        else:
            costs, events = _monthly_cost(pressure, window, base, harms.get(target.id), horizon_days)
        cost = round(sum(costs))
        totals = [t + c for t, c in zip(totals, costs)]
        out.triggers.append(PressureTrigger(pressure_id=pressure.id, expected_events=round(events, 6),
                                            expected_cost_usd=cost, neutralised=off is not None))
        if off is not None:
            out.assumptions.append(f"{pressure.id} is neutralised from day {off} by the plan")
        if cost <= 0:
            continue
        department = target.id if target.type is EntityType.department else target.department_id
        out.impacts.append(Impact(
            impact_id=impact_id(pressure.id, "pressure"), decision_id=decision_id, scenario_id=scenario_id,
            source_entity=target.id, source_kind="pressure", source_ref=pressure.id, affected_entity=target.id,
            affected_department=department,
            level=ImpactLevel.delayed if pressure.start_day > DELAYED_AFTER_DAYS else ImpactLevel.direct,
            category=ImpactCategory.financial, polarity=Polarity.harm, direction=Direction.increase,
            metric="expected_cost_usd", magnitude=float(cost), unit="usd", value_usd=cost,
            severity=_severity(cost, scale_usd), first_effect_day=window[0], peak_effect_day=window[1],
            confidence=CONFIDENCE[pressure.kind], dependency_path=[target.id],
            evidence_refs=list(pressure.evidence_refs), origin=Origin.engine, status=ClaimStatus.computed,
            assumptions=[f"{pressure.name}: expected value over days {window[0]}-{window[1]}"],
        ))
    cumulative = [round(c) for c in accumulate(totals)]
    out.total_usd = sum(t.expected_cost_usd for t in out.triggers)
    # Per-pressure rounding can differ from the rounded running sum by a dollar or two; the last month is exact.
    out.monthly_usd = [*cumulative[:-1], out.total_usd]
    return out
