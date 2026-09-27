import json
import re
import time

from contracts_py.agents import AgentOutput
from contracts_py.twin import OrganizationSettings

from agent_orchestration.llm import AgentLLM, LiveReply, cache_has_decision
from orchestration_helpers import make_context

PERSON_TOKEN = re.compile(r"(?<![a-z0-9])pt_[a-z0-9_]+")
MESSAGES = [{"role": "system", "content": "sys"}, {"role": "user", "content": "ctx"}]
LEAKY = {
    "affected_entities": ["pt_07", "wf_billing_recon"],
    "act_now_view": {"summary": "pt_07 is the only one who reconciles billing; pt_99 helps."},
    "inaction_view": {"summary": "pt_07 burns out."},
    "confidence": 0.6,
}


def people_context(brief, hr_twin):
    context = make_context(brief, hr_twin, OrganizationSettings(llm_mode="live"), agent_id="people_knowledge")
    assert "pt_07" in {e.id for e in context.view.entities}
    return context


def test_cached_answers_carry_roles_not_person_tokens(tmp_path, people_brief, hr_twin) -> None:
    context = people_context(people_brief, hr_twin)
    settings = OrganizationSettings(llm_mode="live", model_id_strong="test-model")
    live = AgentLLM(settings, cache_dir=tmp_path, live_call=lambda *a, **k: LiveReply(LEAKY))
    assert live.call("people_knowledge", MESSAGES, AgentOutput, prompt_version="p1", context=context).status == "ok"

    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1
    text = files[0].read_text()
    assert not PERSON_TOKEN.search(text)
    record = json.loads(text)
    assert record["output"]["affected_entities"] == ["role_billing_ops_lead", "wf_billing_recon"]
    assert "[role] helps" in record["output"]["act_now_view"]["summary"]

    replay = AgentLLM(settings.model_copy(update={"llm_mode": "replay"}), cache_dir=tmp_path)
    replayed = replay.call("people_knowledge", MESSAGES, AgentOutput, prompt_version="p1", context=context)
    assert replayed.status == "replayed"
    assert not PERSON_TOKEN.search(replayed.output.model_dump_json())


def test_hung_live_call_ends_at_the_agent_deadline(tmp_path, brief, twin, monkeypatch) -> None:
    monkeypatch.setenv("CANARY_AGENT_DEADLINE_SECONDS", "0.3")

    def hangs(*args, **kwargs):
        time.sleep(3)
        return LiveReply({"act_now_view": {"summary": "late"}, "inaction_view": {"summary": "late"}, "confidence": 1})

    llm = AgentLLM(OrganizationSettings(llm_mode="live", model_id_strong="test-model"), cache_dir=tmp_path,
                   live_call=hangs)
    context = make_context(brief, twin, OrganizationSettings(llm_mode="live"))
    started = time.monotonic()
    result = llm.call("operations", MESSAGES, AgentOutput, prompt_version="p1", context=context)
    elapsed = time.monotonic() - started
    assert elapsed < 1.5, elapsed
    assert result.status in ("fallback_cached", "unavailable")
    assert any("deadline" in e for e in result.errors)


def test_deadline_defaults_and_overrides(monkeypatch) -> None:
    monkeypatch.delenv("CANARY_AGENT_DEADLINE_SECONDS", raising=False)
    assert AgentLLM(OrganizationSettings()).deadline() == 120
    assert AgentLLM(OrganizationSettings(agent_timeout_seconds=30)).deadline() == 30
    monkeypatch.setenv("CANARY_AGENT_DEADLINE_SECONDS", "7.5")
    assert AgentLLM(OrganizationSettings(agent_timeout_seconds=30)).deadline() == 7.5


def test_cache_has_decision(tmp_path) -> None:
    assert not cache_has_decision(tmp_path / "missing", "dec_a")
    (tmp_path / "finance").mkdir()
    (tmp_path / "finance" / "x.json").write_text(json.dumps({"agent_id": "finance", "decision_id": "dec_a"}))
    (tmp_path / "finance" / "broken.json").write_text("{not json")
    assert cache_has_decision(tmp_path, "dec_a") and not cache_has_decision(tmp_path, "dec_b")
