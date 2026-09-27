"""Deterministic acceptance-check fixtures for both demo briefs (S3 handover; plan 19.2, 19.5).

``tests/fixtures/<decision_id>.expected.json`` holds, for a fixed run ID, the output of every
engine function that exists: ``quick_impact`` on the chosen plan, ``optimize`` (naive and
recommended in full, every other portfolio summarised), ``simulate`` in full mode for inaction,
act_now and delay, ``compare_futures``, ``blast_radius`` for act_now and inaction,
``vendor_overlap`` for the brief's vendors, ``mitigate`` on the chosen plan with the brief's
mitigations from ``data/mitigations.json`` (plan E-07; Gates 4 and 5), ``missing_questions`` for the
vendor brief (plan E-06; Gate 4), and ``check_result`` on each output. The twin is built with
``company_twin.build_twin``, so it is validated first.

A task is complete only when its acceptance check passes: the engine output must equal the
fixture, pass ``check_result`` and repeat byte for byte. An intended engine or data change
regenerates the fixtures:

    UPDATE_ACCEPTANCE_FIXTURES=1 uv run pytest packages/simulation-engine/tests/test_engine_acceptance_fixtures.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from contracts_py.decision import CandidatePlan, DecisionBrief
from contracts_py.enums import ActionType, Future

from company_twin import build_twin, load_mitigation_catalog
from company_twin.loader import default_fixture_path
from simulation_engine import (
    blast_radius,
    check_result,
    compare_futures,
    missing_questions,
    mitigate,
    optimize,
    quick_impact,
    simulate,
    vendor_overlap,
)
from simulation_engine.futures import scenario_for
from simulation_engine.simulate import plan_interventions

TWIN = build_twin(json.loads(default_fixture_path().read_text(encoding="utf-8")))
DATA = default_fixture_path().parent
FIXTURES = Path(__file__).parent / "fixtures"
RUN_ID = "run_acceptance"
BRIEFS = ["vendor_scenario.json", "workforce_scenario.json"]
REGENERATE = "UPDATE_ACCEPTANCE_FIXTURES"
CATALOG = {m.id: m for m in load_mitigation_catalog(twin=TWIN)}
# Each story's mitigations: migrate Echo's unique account intel first; back up and document the two workflows.
MITIGATIONS = {
    "dec_vendor_reduction": ["mit_replacement_feed_account_intel"],
    "dec_workforce_knowledge": ["mit_reassign_financial_close", "mit_reassign_billing_recon",
                                "mit_runbook_billing_recon", "mit_runbook_warehouse_lineage"],
}
QUESTION_BRIEFS = {"dec_vendor_reduction"}


def dump(model: Any) -> Any:
    return model.model_dump(mode="json")


def issues(obj: Any) -> list[dict]:
    return [dump(i) for i in check_result(obj, TWIN)]


def engine_outputs(brief: DecisionBrief) -> dict[str, Any]:
    portfolio = optimize(TWIN, brief, run_id=RUN_ID)
    chosen = portfolio.recommended or portfolio.naive
    plan = CandidatePlan(plan_id=chosen.plan_id, label="Recommended plan" if portfolio.recommended else "Naive plan",
                         intervention_ids=chosen.intervention_ids, source="optimizer")
    quick = quick_impact(TWIN, plan_interventions(brief, plan), brief=brief, run_id=RUN_ID)
    futures = {f: simulate(TWIN, brief, scenario_for(TWIN, brief, RUN_ID, f, plan),
                           None if f is Future.inaction else plan, "full")
               for f in (Future.inaction, Future.act_now, Future.delay)}
    comparison = compare_futures(TWIN, brief, plan, alternatives=[], run_id=RUN_ID)
    blasts = {f: blast_radius(futures[f], TWIN) for f in (Future.act_now, Future.inaction)}
    vendors = sorted({i.target_entity_id for i in brief.candidate_interventions if i.type is ActionType.remove_vendor})
    overlaps = vendor_overlap(TWIN, vendors) if vendors else []
    mitigation = mitigate(TWIN, brief, plan, [CATALOG[m] for m in MITIGATIONS[brief.decision_id]], run_id=RUN_ID)
    questions = (missing_questions(TWIN, brief, plan, run_id=RUN_ID) if brief.decision_id in QUESTION_BRIEFS
                 else [])
    shown = {portfolio.naive.plan_id, *([portfolio.recommended.plan_id] if portfolio.recommended else [])}
    return {
        "decision_id": brief.decision_id,
        "run_id": RUN_ID,
        "twin_version": TWIN.version.twin_version,
        "as_of_date": str(TWIN.version.as_of_date),
        "chosen_plan": dump(plan),
        "quick_impact": dump(quick),
        "optimize": {
            "evaluated_count": portfolio.evaluated_count,
            "naive": dump(portfolio.naive),
            "recommended": dump(portfolio.recommended) if portfolio.recommended else None,
            "alternatives": [{
                "plan_id": p.plan_id, "intervention_ids": p.intervention_ids, "rank": p.rank,
                "feasible": p.result.feasible, "gross_savings_usd": p.result.value.gross_savings_usd,
                "net_value_usd": p.result.value.net_value_usd, "risk_score": p.result.risk.score,
                "rejection_reasons": p.result.rejection_reasons,
            } for p in portfolio.alternatives if p.plan_id not in shown],
        },
        "simulate": {f.value: dump(r) for f, r in futures.items()},
        "compare_futures": dump(comparison),
        "blast_radius": {f.value: dump(b) for f, b in blasts.items()},
        "vendor_overlap": [dump(o) for o in overlaps],
        "mitigate": dump(mitigation),
        "missing_questions": [dump(q) for q in questions],
        "check_result": {
            "quick_impact": issues(quick),
            "optimize": issues(portfolio),
            **{f"simulate.{f.value}": issues(r) for f, r in futures.items()},
            "compare_futures": issues(comparison),
            **{f"blast_radius.{f.value}": issues(b) for f, b in blasts.items()},
            "mitigate": issues(mitigation),
        },
    }


def render(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=1, sort_keys=True) + "\n"


def load_brief(name: str) -> DecisionBrief:
    return DecisionBrief.model_validate(json.loads((DATA / name).read_text(encoding="utf-8")))


@pytest.mark.parametrize("name", BRIEFS)
def test_engine_outputs_match_the_acceptance_fixture(name):
    brief = load_brief(name)
    path = FIXTURES / f"{brief.decision_id}.expected.json"
    actual = render(engine_outputs(brief))
    if os.environ.get(REGENERATE) == "1":
        FIXTURES.mkdir(exist_ok=True)
        path.write_text(actual, encoding="utf-8", newline="\n")
    assert path.exists(), f"missing {path.name}; regenerate with {REGENERATE}=1"
    expected = path.read_text(encoding="utf-8")
    assert json.loads(actual) == json.loads(expected), (
        f"{path.name} differs from the engine output; if the change is intended, regenerate with {REGENERATE}=1")


@pytest.mark.parametrize("name", BRIEFS)
def test_acceptance_outputs_pass_check_result_and_repeat_byte_for_byte(name):
    brief = load_brief(name)
    first = engine_outputs(brief)
    assert all(found == [] for found in first["check_result"].values()), first["check_result"]
    assert render(engine_outputs(brief)) == render(first)
