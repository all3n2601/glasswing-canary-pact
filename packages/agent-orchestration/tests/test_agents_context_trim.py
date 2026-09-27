import functools
import os

import pytest
from canary_api import engine_port
from canary_api.paths import DATA_DIR
from contracts_py.decision import DecisionBrief
from contracts_py.twin import OrganizationSettings

from agent_orchestration import AgentLLM, evals, run_decision
from agent_orchestration import orchestrator as orchestrator_module
from agent_orchestration.context import build_context, context_hops

BUDGET = 60_000
BRIEFS = ["vendor_scenario.json", "workforce_scenario.json"]
PLANTED_ENTITIES = {"ds_account_intel", "wf_vendor_reconciliation"}
PLANTED_EVIDENCE = "ev_echo_account_intel_feed"


@pytest.fixture(scope="module", autouse=True)
def real_engine_and_twin():
    saved = {k: os.environ.get(k) for k in ("ENGINE_IMPL", "TWIN_IMPL", "CANARY_AGENT_CONTEXT_HOPS")}
    os.environ.update({"ENGINE_IMPL": "real", "TWIN_IMPL": "real"})
    os.environ.pop("CANARY_AGENT_CONTEXT_HOPS", None)
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(scope="module")
def real_twin(real_engine_and_twin):
    return engine_port.load_twin(DATA_DIR / "synthetic_company.json")


def load_brief(name: str) -> DecisionBrief:
    return DecisionBrief.model_validate_json((DATA_DIR / name).read_text())


class Capture(AgentLLM):
    def __init__(self, settings, store):
        super().__init__(settings, cache_dir=DATA_DIR / "artifacts" / "unused_test_cache")
        self.store = store

    def call(self, agent_id, messages, output_model, *, prompt_version, context, fast=False):
        self.store[agent_id] = (messages, context)
        return super().call(agent_id, messages, output_model, prompt_version=prompt_version, context=context,
                            fast=fast)


@functools.cache
def captured(name: str) -> dict:
    store: dict = {}
    settings = OrganizationSettings(llm_mode="mock")
    twin = engine_port.load_twin(DATA_DIR / "synthetic_company.json")
    run_decision(load_brief(name), engine=engine_port, settings=settings, llm=Capture(settings, store),
                 emit=lambda *a, **k: None, run_id="run_trim_test", twin=twin)
    return store


@pytest.mark.parametrize("name", BRIEFS)
def test_every_agent_prompt_is_under_budget(name) -> None:
    sizes = {agent: sum(len(m["content"]) for m in messages) for agent, (messages, _) in captured(name).items()}
    assert len(sizes) >= 7
    assert {a: n for a, n in sizes.items() if n >= BUDGET} == {}


@pytest.mark.parametrize("agent", ["challenger", "operations"])
def test_planted_path_stays_in_context_on_the_vendor_brief(agent) -> None:
    messages, context = captured("vendor_scenario.json")[agent]
    assert PLANTED_ENTITIES <= {e.id for e in context.view.entities}
    assert PLANTED_EVIDENCE in {e.id for e in context.view.evidence}
    text = "".join(m["content"] for m in messages)
    assert all(item in text for item in [*PLANTED_ENTITIES, PLANTED_EVIDENCE])


@pytest.mark.parametrize("name", BRIEFS)
def test_every_impact_entity_and_its_evidence_is_kept(name) -> None:
    for agent, (_, context) in captured(name).items():
        kept = {e.id for e in context.view.entities}
        evidence = {e.id for e in context.view.evidence}
        visible_evidence = {e.id for e in engine_port.build_agent_view(
            engine_port.load_twin(DATA_DIR / "synthetic_company.json"), agent_id=agent,
            department_id=context.agent.department_id, visible_entity_types=context.agent.visible_entity_types,
            visible_sensitivity=context.agent.visible_sensitivity).evidence}
        for impact in [*context.act_now_effects, *context.inaction_effects]:
            assert {impact.affected_entity, impact.source_entity, *impact.dependency_path} <= kept, agent
            assert set(impact.evidence_refs) & visible_evidence <= evidence, agent


def test_hops_setting_controls_the_neighbourhood(real_twin, monkeypatch) -> None:
    brief = load_brief("vendor_scenario.json")
    settings = OrganizationSettings(llm_mode="mock")
    spec = captured("vendor_scenario.json")["finance"][1].agent
    _, context = captured("vendor_scenario.json")["finance"]

    def entities(hops=None, trim=True):
        return {e.id for e in build_context(spec, run_id="run_x", brief=brief, plan=context.plan, twin=real_twin,
                                            engine=engine_port, act_now=_result(context, "act_now"),
                                            inaction=_result(context, "inaction"), settings=settings, hops=hops,
                                            trim=trim).view.entities}

    assert context_hops() == 2
    narrow, default, full = entities(0), entities(), entities(trim=False)
    assert narrow < default < full
    monkeypatch.setenv("CANARY_AGENT_CONTEXT_HOPS", "0")
    assert entities() == narrow
    monkeypatch.setenv("CANARY_AGENT_CONTEXT_HOPS", "-1")
    with pytest.raises(ValueError, match="CANARY_AGENT_CONTEXT_HOPS"):
        context_hops()


def _result(context, future):
    # The captured context holds the visible impacts; a minimal result carries them back into build_context.
    from contracts_py.engine import SimulationResult

    impacts = context.act_now_effects if future == "act_now" else context.inaction_effects
    return SimulationResult.model_construct(impacts=impacts)


def test_trimming_keeps_resolving_evidence_in_the_mock_eval(real_twin, monkeypatch, tmp_path) -> None:
    brief = load_brief("vendor_scenario.json")
    settings = OrganizationSettings(llm_mode="mock")

    def pct() -> float:
        report = evals.run_eval(engine=engine_port, twin=real_twin, brief=brief, settings=settings, llm_mode="mock",
                                configs=["full"], engine_impl="real", twin_impl="real",
                                cache_dir=tmp_path, planted_path=tmp_path / "absent.json")
        return report.rows[0]["claims_with_resolving_evidence_pct"]

    trimmed = pct()
    monkeypatch.setattr(orchestrator_module, "build_context", functools.partial(build_context, trim=False))
    untrimmed = pct()
    assert trimmed >= untrimmed > 0
