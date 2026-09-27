"""Cost accounting (plan section 11.4; schema v2.2.0 section 7.3, rule 9).

Every line of ``ValueBreakdown`` is priced separately and the net is their exact sum::

    net = gross_savings - transition - added - rebound - expected_business_loss - pressure + avoided_failure

- gross_savings: recurring cost the interventions stop (a removed vendor's ``annual_cost_usd``).
- transition: one-off costs: a vendor's ``one_time_exit_cost_usd`` (termination) plus its
  ``migration_cost_usd``, project cancellation fees, and each intervention's ``one_time_cost_usd``.
- added: investments and added capacity, plus **displaced work**: while a workflow or system
  runs at a loss ``L``, the company covers that share by other means at the entity's
  ``failure_cost_per_day_usd``, so it costs ``L * failure_cost_per_day_usd * days`` from the
  impact's first effect day to the horizon.
- rebound: run cost that continues because a project that would retire it stopped or slipped.
- expected_business_loss: revenue at risk, ``L * arr_usd * days / 365`` for each harmed customer
  segment.
- pressure and avoided_failure: priced by the futures comparison and mitigation (plan E-02,
  E-07); zero for a single act-now evaluation.

``monthly_net_usd`` is cumulative: one-off costs land in the month the first intervention
starts, recurring lines accrue evenly after it, and the last month equals the net exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

from contracts_py.engine import Impact, ValueBreakdown
from contracts_py.enums import EntityType, Polarity
from contracts_py.twin import Twin

from .interventions import DAYS_PER_YEAR, AppliedScenario

DAYS_PER_MONTH = 30
DISPLACED_TYPES = {EntityType.workflow, EntityType.system}


@dataclass(frozen=True)
class PricedLines:
    displaced_work_usd: int
    business_loss_usd: int
    displaced_by_impact: dict[str, int]
    loss_by_impact: dict[str, int]


def price_harms(twin: Twin, impacts: list[Impact], horizon_days: int) -> PricedLines:
    """Displaced work and business loss from the harm impacts, each traceable to its impact."""
    ents = {e.id: e for e in twin.entities}
    displaced: dict[str, int] = {}
    lost: dict[str, int] = {}
    for impact in impacts:
        if impact.polarity is not Polarity.harm:
            continue
        entity = ents[impact.affected_entity]
        days = max(0, horizon_days - impact.first_effect_day)
        if entity.type in DISPLACED_TYPES and entity.failure_cost_per_day_usd:
            displaced[impact.impact_id] = round(impact.magnitude * entity.failure_cost_per_day_usd * days)
        elif entity.type is EntityType.customer_segment and entity.arr_usd:
            lost[impact.impact_id] = round(impact.magnitude * entity.arr_usd * days / DAYS_PER_YEAR)
    return PricedLines(sum(displaced.values()), sum(lost.values()), displaced, lost)


def monthly_net(recurring_net: int, one_off: int, start_day: int, horizon_days: int) -> list[int]:
    """Cumulative net per month; ``recurring_net - one_off`` is the last value exactly."""
    months = max(1, horizon_days // DAYS_PER_MONTH)
    accrual_days = max(1, months * DAYS_PER_MONTH - start_day)
    series = []
    for m in range(1, months):
        day = m * DAYS_PER_MONTH
        elapsed = min(1.0, max(0, day - start_day) / accrual_days)
        series.append(round(recurring_net * elapsed) - (one_off if day > start_day else 0))
    return [*series, recurring_net - one_off]


def value_breakdown(applied: AppliedScenario, priced: PricedLines, *, start_day: int, horizon_days: int,
                    ) -> ValueBreakdown:
    """The act-now value lines in quick mode: point values, so every percentile is null."""
    gross = applied.gross_savings_usd
    added = applied.added_cost_usd + priced.displaced_work_usd
    recurring = gross - added - applied.rebound_cost_usd - priced.business_loss_usd
    net = recurring - applied.transition_cost_usd
    return ValueBreakdown(
        gross_savings_usd=gross, transition_cost_usd=applied.transition_cost_usd, added_cost_usd=added,
        rebound_cost_usd=applied.rebound_cost_usd, expected_business_loss_usd=priced.business_loss_usd,
        pressure_cost_usd=0, avoided_failure_cost_usd=0, net_value_usd=net,
        monthly_net_usd=monthly_net(recurring, applied.transition_cost_usd, start_day, horizon_days),
    )
