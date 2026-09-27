from canary_api.paths import DATA_DIR
from canary_api.stubs import engine as stub_engine
from contracts_py.decision import DecisionBrief
from contracts_py.enums import Future

from agent_orchestration import run_decision
from orchestration_helpers import NOW, Recorder, ScriptedLLM, SpyEngine


def run(brief, twin, settings, engine):
    return run_decision(brief, engine=engine, settings=settings, llm=ScriptedLLM(settings, {}), emit=Recorder(),
                        run_id="run_test", twin=twin, clock=lambda: NOW)


def test_vendor_brief_keeps_a_proceed_recommendation(brief, twin, settings) -> None:
    package = run(brief, twin, settings, SpyEngine())
    best = package.futures.rows[package.futures.best_row_index]
    recommendation = package.recommendation
    assert recommendation is not None and best.future is Future.act_now
    assert (recommendation.action, recommendation.plan_id) == ("proceed", best.plan_id)
    assert recommendation.plan_id is not None


VIOLATED = {"c_compliance": "A mandatory control loses its only supplier.",
            "c_stranded": "Two workflows fall below their qualified owners."}


class InactionWins(SpyEngine):
    def simulate(self, twin, brief, scenario, plan, mode, **kwargs):
        self.calls.append(("simulate", (twin, brief, scenario, plan, mode)))
        result = stub_engine.simulate(twin, brief, scenario, plan, mode, **kwargs)
        if scenario.future is not Future.act_now:
            return result
        constraints = [c.model_copy(update={"passed": False, "explanation": VIOLATED[c.constraint_id]})
                       if c.constraint_id in VIOLATED else c.model_copy(update={"passed": True})
                       for c in result.constraint_results]
        return result.model_copy(update={"constraint_results": constraints})

    def compare_futures(self, twin, brief, plan, **kwargs):
        self.calls.append(("compare_futures", (twin, brief, plan)))
        comparison = stub_engine.compare_futures(twin, brief, plan, **kwargs)
        inaction = next(i for i, row in enumerate(comparison.rows) if row.future is Future.inaction)
        return comparison.model_copy(update={"best_row_index": inaction,
                                             "headline": "Doing nothing beats acting now on this plan."})


def test_inaction_best_recommends_not_proceeding_with_reasons(brief, twin, settings) -> None:
    package = run(brief, twin, settings, InactionWins())
    inaction_row = next(r for r in package.futures.rows if r.future is Future.inaction)
    recommendation = package.recommendation
    assert recommendation is not None
    assert (recommendation.action, recommendation.plan_id, recommendation.future) == (
        "do_not_proceed", None, Future.inaction)
    assert recommendation.result_id == inaction_row.result_id
    assert recommendation.headline == "Doing nothing beats acting now on this plan."
    assert recommendation.claims[0].text == recommendation.headline
    reasons = [(c.ref, c.text, c.source) for c in recommendation.claims[1:]]
    assert sorted(reasons) == sorted((ref, text, "calculation") for ref, text in VIOLATED.items())


def test_real_engine_workforce_brief_gets_a_recommendation(settings) -> None:
    from canary_api import engine_port

    brief = DecisionBrief.model_validate_json((DATA_DIR / "workforce_scenario.json").read_text())
    twin = engine_port.load_twin(DATA_DIR / "synthetic_company.json")
    package = run(brief, twin, settings, engine_port)
    best = package.futures.rows[package.futures.best_row_index]
    recommendation = package.recommendation
    assert recommendation is not None and recommendation.headline == package.futures.headline
    assert recommendation.future is best.future and recommendation.result_id == best.result_id
    if best.future is Future.inaction:
        assert (recommendation.action, recommendation.plan_id) == ("do_not_proceed", None)
