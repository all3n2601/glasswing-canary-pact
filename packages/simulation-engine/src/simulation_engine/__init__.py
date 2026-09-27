from .blast import blast_radius
from .checks import check_result
from .constraints import ScenarioMetrics, evaluate_constraints
from .interventions import AppliedScenario, Seed, apply_interventions
from .knowledge import workflow_coverage
from .optimizer import optimize as _vendor_optimize
from .overlap import OVERLAP_WEIGHTS, unique_contribution, vendor_overlap
from .propagation import Effect, Propagation, impact_ledger, propagate
from .quick import quick_impact
from .simulate import simulate as _quick_simulate
from .simulator import compare_futures, simulate as _full_simulate


def simulate(twin, brief, scenario, plan, mode, *, settings=None):
    """Use the modular engine for quick act-now evaluation and the full engine for other futures."""
    if mode == "quick" and scenario.future.value == "act_now":
        return _quick_simulate(twin, brief, scenario, plan, mode, settings=settings)
    return _full_simulate(twin, brief, scenario, plan, mode, settings=settings)


def optimize(twin, brief, *, settings=None, run_id="run_adhoc"):
    """Search vendor portfolios or evaluate the single proposed non-vendor plan."""
    return _vendor_optimize(twin, brief, settings=settings, run_id=run_id)


__all__ = [
    "check_result",
    "quick_impact",
    "simulate",
    "compare_futures",
    "optimize",
    "blast_radius",
    "vendor_overlap",
    "unique_contribution",
    "OVERLAP_WEIGHTS",
    "apply_interventions",
    "AppliedScenario",
    "Seed",
    "propagate",
    "Propagation",
    "Effect",
    "impact_ledger",
    "ScenarioMetrics",
    "evaluate_constraints",
    "workflow_coverage",
]
