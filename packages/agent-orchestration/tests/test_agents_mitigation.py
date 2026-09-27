import logging

import pytest
from canary_api.engine_port import EngineNotReady
from canary_api.paths import DATA_DIR
from canary_api.stubs import engine as stub_engine
from canary_api.stubs import results
from contracts_py.decision import CandidatePlan, DecisionBrief, Intervention
from contracts_py.engine import MissingQuestion, MitigationComparison
from contracts_py.enums import Future, Polarity, RunStatus
from contracts_py.events import EventType

from agent_orchestration import run_decision
from agent_orchestration.orchestrator import _Run
from orchestration_helpers import NOW, Recorder, ScriptedLLM, SpyEngine

FEED = Intervention(id="mit_feed", kind="mitigation", type="add_replacement_feed", target_entity_id="ds_account_intel",
                    one_time_cost_usd=30_000, duration_days=60, params={"replacement_vendor_id": "vendor_cinder"},
                    rationale="Replace the unique feed first.")
QUESTION = MissingQuestion(question_id="q_history", text="Does EchoMarket keep our records after termination?",
                           uncertain_input="vendor_echo.retains_history_after_termination",
                           current_assumption="unknown", answer_type="boolean",
                           changes_recommendation_if="it does not", value_gap_usd=1_000_000)


def run(brief, twin, settings, engine, recorder=None):
    recorder = recorder or Recorder()
    package = run_decision(brief, engine=engine, settings=settings, llm=ScriptedLLM(settings, {}), emit=recorder,
                           run_id="run_test", twin=twin, clock=lambda: NOW)
    return package, recorder


class Mitigating(SpyEngine):
    """Stub engine with a one-entry catalog, a scripted mitigation outcome and scripted questions."""

    def __init__(self, *, feasible_after=True, beats_best=True, mitigate_error=None, question_error=None):
        super().__init__()
        self.feasible_after, self.beats_best = feasible_after, beats_best
        self.mitigate_error, self.question_error = mitigate_error, question_error
        self.asked_plans: list[str] = []

    def load_mitigation_catalog(self, path=None, twin=None):
        self.calls.append(("load_mitigation_catalog", (path, twin)))
        return [FEED]

    def simulate(self, twin, brief, scenario, plan, mode, **kwargs):
        self.calls.append(("simulate", (twin, brief, scenario, plan, mode)))
        result = stub_engine.simulate(twin, brief, scenario, plan, mode, **kwargs)
        # Make the act-now result harm the catalog's target so the mitigation applies.
        impacts = [result.impacts[0].model_copy(update={"affected_entity": "ds_account_intel", "polarity": Polarity.harm}),
                   *result.impacts[1:]] if result.impacts and scenario.future is Future.act_now else result.impacts
        return result.model_copy(update={"impacts": impacts})

    def compare_futures(self, twin, brief, plan, **kwargs):
        self.calls.append(("compare_futures", (twin, brief, plan)))
        comparison = stub_engine.compare_futures(twin, brief, plan, **kwargs)
        best = comparison.rows[comparison.best_row_index]
        after = results.act_now_result(kwargs.get("run_id", "run_test"), brief.decision_id).value.net_value_usd
        # The best unmitigated row sits just below (or above) what the mitigated plan will report.
        net = after - 1 if self.beats_best else after + 1
        rows = list(comparison.rows)
        rows[comparison.best_row_index] = best.model_copy(update={"net_value_p50_usd": net})
        return comparison.model_copy(update={"rows": rows})

    def mitigate(self, twin, brief, plan, actions, **kwargs):
        self.calls.append(("mitigate", (twin, brief, plan, actions)))
        if self.mitigate_error:
            raise self.mitigate_error
        before = results.naive_result("run_test", brief.decision_id)
        after = results.act_now_result("run_test", brief.decision_id).model_copy(update={
            "feasible": self.feasible_after, "plan_id": f"{plan.plan_id}_mitigated",
            "assumptions": ["Conditionally feasible: only if mit_feed completes in 60 days"]})
        return MitigationComparison(plan_id_before=plan.plan_id, plan_id_after=f"{plan.plan_id}_mitigated",
                                    actions=actions, before=before, after=after,
                                    restored_entity_ids=["ds_account_intel", "wf_account_planning"],
                                    feasible_before=before.feasible, feasible_after=self.feasible_after)

    def missing_questions(self, twin, brief, plan, **kwargs):
        self.calls.append(("missing_questions", (twin, brief, plan)))
        self.asked_plans.append(plan.plan_id)
        if self.question_error:
            raise self.question_error
        return [QUESTION]


def test_stub_run_has_a_mitigating_phase_with_nothing_to_mitigate(brief, twin, settings) -> None:
    package, recorder = run(brief, twin, settings, SpyEngine())
    assert "mitigating" in recorder.phases()
    assert recorder.phases().index("mitigating") == recorder.phases().index("comparing_futures") + 1
    assert package.mitigations == [] and package.missing_information == []
    assert not [a for a in package.assumptions if a.startswith("Engine ")]


def test_applicable_mitigations_follow_the_plans_own_harms() -> None:
    result = results.naive_result("run_test", "dec_workforce_knowledge")
    stranded = [w.workflow_id for w in result.workflow_coverage if w.stranded]
    catalog = [FEED.model_copy(update={"id": "mit_a", "target_entity_id": stranded[0]}),
               FEED.model_copy(update={"id": "mit_b", "target_entity_id": "wf_not_harmed"})]
    assert [m.id for m in _Run.applicable_mitigations(catalog, result)] == ["mit_a"]


def test_feasible_mitigated_plan_that_beats_the_best_row_is_recommended(brief, twin, settings) -> None:
    engine = Mitigating()
    package, recorder = run(brief, twin, settings, engine)
    assert len(package.mitigations) >= 1 and recorder.of(EventType.mitigation_applied)
    recommendation = package.recommendation
    assert recommendation.action == "proceed_with_mitigations" and recommendation.future is Future.act_now
    winner = package.mitigations[0]
    assert (recommendation.plan_id, recommendation.result_id) == (winner.plan_id_after, winner.after.result_id)
    # The stub's naive plan is infeasible before mitigation, so the engine's conditional framing is used.
    assert not winner.feasible_before
    assert "conditionally feasible with coverage restored" in recommendation.headline
    assert recommendation.claims[0].text.startswith("Conditionally feasible")
    assert "beats" not in recommendation.headline and "doing nothing" not in recommendation.headline.lower()
    refs = [c.ref for c in recommendation.claims]
    assert "mit_feed" in refs and {"ds_account_intel", "wf_account_planning"} <= set(refs)
    assert all(c.source == "calculation" for c in recommendation.claims)
    assert engine.asked_plans == [winner.plan_id_before]


@pytest.mark.parametrize("kwargs", [{"feasible_after": False}, {"beats_best": False}])
def test_mitigation_that_does_not_win_keeps_the_engine_recommendation(brief, twin, settings, kwargs) -> None:
    package, _ = run(brief, twin, settings, Mitigating(**kwargs))
    assert package.mitigations and package.recommendation.action != "proceed_with_mitigations"
    assert package.recommendation.headline == package.futures.headline


def test_missing_questions_fill_the_package_and_the_first_open_question(brief, twin, settings) -> None:
    package, recorder = run(brief, twin, settings, Mitigating())
    assert package.missing_information == [QUESTION]
    assert package.open_questions[0] == QUESTION.text
    assert [e.payload for e in recorder.of(EventType.question_selected)] == [QUESTION]


@pytest.mark.parametrize(("kwargs", "name"), [
    ({"mitigate_error": EngineNotReady("mitigate does not exist yet")}, "mitigate"),
    ({"question_error": ValueError("no scored inputs")}, "missing_questions"),
])
def test_engine_errors_are_assumptions_not_failures(brief, twin, settings, kwargs, name, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="agent_orchestration.orchestrator"):
        package, recorder = run(brief, twin, settings, Mitigating(**kwargs))
    assert recorder.phases()[-1] == RunStatus.awaiting_approval.value
    assert any(a.startswith(f"Engine {name}:") for a in package.assumptions)
    assert name in caplog.text


def test_catalog_error_is_an_assumption(brief, twin, settings) -> None:
    class BrokenCatalog(SpyEngine):
        def load_mitigation_catalog(self, path=None, twin=None):
            raise FileNotFoundError("data/mitigations.json")

    package, _ = run(brief, twin, settings, BrokenCatalog())
    assert package.mitigations == []
    assert any(a.startswith("Engine load_mitigation_catalog:") for a in package.assumptions)


def test_do_nothing_recommendation_asks_about_the_naive_plan(brief, twin, settings) -> None:
    class DoNothingWins(Mitigating):
        def compare_futures(self, twin, brief, plan, **kwargs):
            comparison = stub_engine.compare_futures(twin, brief, plan, **kwargs)
            inaction = next(i for i, r in enumerate(comparison.rows) if r.future is Future.inaction)
            return comparison.model_copy(update={"best_row_index": inaction})

    engine = DoNothingWins(feasible_after=False)
    package, _ = run(brief, twin, settings, engine)
    assert package.recommendation.action == "do_not_proceed"
    assert engine.asked_plans == [package.portfolios.naive.plan_id]


def _real(name):
    from canary_api import engine_port

    brief = DecisionBrief.model_validate_json((DATA_DIR / name).read_text())
    return brief, engine_port.load_twin(DATA_DIR / "synthetic_company.json"), engine_port


def test_real_engine_workforce_mitigations_beat_doing_nothing(settings, monkeypatch) -> None:
    monkeypatch.setenv("ENGINE_IMPL", "real")
    monkeypatch.setenv("TWIN_IMPL", "real")
    brief, twin, engine = _real("workforce_scenario.json")
    package, _ = run(brief, twin, settings, engine)
    inaction = next(r for r in package.futures.rows if r.future is Future.inaction)
    winner = next(m for m in package.mitigations if m.feasible_after)
    assert not winner.feasible_before and winner.after.value.net_value_usd > inaction.net_value_p50_usd
    assert package.recommendation.action == "proceed_with_mitigations"
    assert package.recommendation.plan_id == winner.plan_id_after


def test_real_engine_vendor_top_question_is_echo_history(settings, monkeypatch) -> None:
    monkeypatch.setenv("ENGINE_IMPL", "real")
    monkeypatch.setenv("TWIN_IMPL", "real")
    brief, twin, engine = _real("vendor_scenario.json")
    package, _ = run(brief, twin, settings, engine)
    top = package.missing_information[0]
    assert top.uncertain_input == "vendor_echo.retains_history_after_termination"
    assert package.open_questions[0] == top.text


def test_already_feasible_plan_leads_with_the_mitigation_and_engine_risk(brief, twin, settings) -> None:
    class FeasibleBefore(Mitigating):
        def mitigate(self, twin, brief, plan, actions, **kwargs):
            comparison = super().mitigate(twin, brief, plan, actions, **kwargs)
            before = comparison.before.model_copy(update={"feasible": True})
            return comparison.model_copy(update={"before": before, "feasible_before": True})

    package, _ = run(brief, twin, settings, FeasibleBefore())
    recommendation, winner = package.recommendation, package.mitigations[0]
    assert recommendation.action == "proceed_with_mitigations"
    assert recommendation.headline.startswith("Proceed with 1 mitigation first: migrate Account intelligence")
    assert "Restores" not in recommendation.headline and recommendation.headline.count(". ") == 1
    assert any(c.text.startswith("Restores ") for c in recommendation.claims)
    assert f"{winner.before.risk.score:.1f} ({winner.before.risk.level.value}) before" in recommendation.headline
    assert f"{winner.after.risk.score:.1f} ({winner.after.risk.level.value}) after" in recommendation.headline


def test_compare_futures_gets_feasible_alternatives_or_the_first_one() -> None:
    portfolio = results.portfolio_comparison("run_test", "dec_vendor_reduction")
    naive = portfolio.naive
    feasible = naive.model_copy(update={"plan_id": "plan_alt_ok", "result": naive.result.model_copy(
        update={"feasible": True})})
    blocked = naive.model_copy(update={"plan_id": "plan_alt_blocked", "result": naive.result.model_copy(
        update={"feasible": False})})
    runner = _Run.__new__(_Run)
    plan = CandidatePlan(plan_id="plan_under_review", label="x", intervention_ids=[], source="optimizer")
    both = portfolio.model_copy(update={"alternatives": [blocked, feasible]})
    assert [p.plan_id for p in runner.compare_alternatives(both, plan)] == ["plan_alt_ok"]
    only_blocked = portfolio.model_copy(update={"alternatives": [blocked]})
    assert [p.plan_id for p in runner.compare_alternatives(only_blocked, plan)] == ["plan_alt_blocked"]
    assert runner.compare_alternatives(portfolio.model_copy(update={"alternatives": []}), plan) == []


def test_real_engine_vendor_passes_its_feasible_alternative_and_migrates_first(settings, monkeypatch) -> None:
    monkeypatch.setenv("ENGINE_IMPL", "real")
    monkeypatch.setenv("TWIN_IMPL", "real")
    brief, twin, engine = _real("vendor_scenario.json")
    spy = SpyEngine()
    spy.__class__ = type("RealSpy", (SpyEngine,), {"__getattr__": lambda self, name: _spy(self, engine, name)})
    package, _ = run(brief, twin, settings, spy)
    compared = [kwargs for name, kwargs in spy.kwargs if name == "compare_futures"]
    feasible = [a.plan_id for a in package.portfolios.alternatives if a.result.feasible]
    assert feasible and [p.plan_id for p in compared[-1]["alternatives"]] == feasible
    assert any(r.future is Future.alternative for r in package.futures.rows)
    recommendation = package.recommendation
    assert recommendation.action == "proceed_with_mitigations"
    assert recommendation.headline.startswith(
        "Proceed with 1 mitigation first: migrate Account intelligence from EchoMarket to ")


def _spy(self, engine, name):
    function = getattr(engine, name)

    def wrapper(*args, **kwargs):
        self.calls.append((name, args))
        self.__dict__.setdefault("kwargs", []).append((name, kwargs))
        return function(*args, **kwargs)

    return wrapper
