import json
import os

import pytest
from contracts_py.agents import AgentOutput
from contracts_py.twin import OrganizationSettings

from agent_orchestration.llm import DEFAULT_BASE_URL, AgentLLM, LiveReply, resolve_base_url
from orchestration_helpers import make_context

VALID = {"act_now_view": {"summary": "Billing loses its owner."}, "inaction_view": {"summary": "Hazard stays."},
         "confidence": 0.6}
MESSAGES = [{"role": "system", "content": "sys"}, {"role": "user", "content": "ctx run_test {\"a\": 1}"}]


class FakeLive:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen: list[list[dict]] = []

    def __call__(self, model_id, messages, output_model, *, timeout, temperature):
        self.seen.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return LiveReply(reply, 10, 5)


@pytest.fixture
def live_settings():
    return OrganizationSettings(llm_mode="live", model_id_strong="test-model", agent_timeout_seconds=5)


def call(llm, context, agent_id="operations", messages=MESSAGES):
    return llm.call(agent_id, messages, AgentOutput, prompt_version="p1", context=context)


def test_replay_round_trip(tmp_path, brief, twin, settings, live_settings) -> None:
    context = make_context(brief, twin, settings)
    fake = FakeLive(VALID)
    live = call(AgentLLM(live_settings, cache_dir=tmp_path, live_call=fake), context)
    assert live.status == "ok" and live.metrics.input_tokens == 10
    cached = tmp_path / "operations" / f"{live.metrics.prompt_hash}.json"
    assert json.loads(cached.read_text())["model_id"] == "test-model"

    replay_settings = live_settings.model_copy(update={"llm_mode": "replay"})
    replay = AgentLLM(replay_settings, cache_dir=tmp_path)
    again = call(replay, make_context(brief, twin, settings, run_id="run_other"),
                 messages=[{**m, "content": m["content"].replace("run_test", "run_other")} for m in MESSAGES])
    assert again.status == "replayed" and again.output == live.output

    miss = call(replay, context, messages=[{"role": "user", "content": "different"}])
    assert miss.status == "fallback_cached" and miss.output == live.output
    assert call(replay, context, agent_id="finance").status == "unavailable"


def test_validation_failure_retries_once_with_error(tmp_path, brief, twin, settings, live_settings) -> None:
    fake = FakeLive({"confidence": "high"}, VALID)
    result = call(AgentLLM(live_settings, cache_dir=tmp_path, live_call=fake), make_context(brief, twin, settings))
    assert result.status == "ok" and result.retries == 1
    assert "failed validation" in fake.seen[1][-1]["content"] and len(fake.seen[1]) == len(MESSAGES) + 1


def test_invalid_twice_is_invalid(tmp_path, brief, twin, settings, live_settings) -> None:
    fake = FakeLive({"confidence": "high"}, {})
    result = call(AgentLLM(live_settings, cache_dir=tmp_path, live_call=fake), make_context(brief, twin, settings))
    assert result.status == "invalid" and result.output is None and len(result.errors) == 2


def test_live_error_falls_back_to_cache(tmp_path, brief, twin, settings, live_settings) -> None:
    context = make_context(brief, twin, settings)
    call(AgentLLM(live_settings, cache_dir=tmp_path, live_call=FakeLive(VALID)), context)
    down = AgentLLM(live_settings, cache_dir=tmp_path, live_call=FakeLive(TimeoutError("slow")))
    assert call(down, context, messages=[{"role": "user", "content": "new"}]).status == "fallback_cached"


def test_live_without_model_id_is_unavailable(tmp_path, brief, twin, settings, monkeypatch) -> None:
    monkeypatch.delenv("CANARY_MODEL_STRONG", raising=False)
    llm = AgentLLM(OrganizationSettings(llm_mode="live"), cache_dir=tmp_path, live_call=FakeLive(VALID))
    result = call(llm, make_context(brief, twin, settings))
    assert result.status == "unavailable" and "no model id" in result.errors[0]


def test_mock_is_deterministic_and_cites_only_view_ids(brief, twin, settings) -> None:
    context = make_context(brief, twin, settings)
    llm = AgentLLM(settings)
    first, second = call(llm, context), call(llm, context)
    assert first.output == second.output and first.status == "ok"
    view_ids = {e.id for e in context.view.entities}
    evidence = {e.id for e in context.view.evidence}
    assert set(first.output.affected_entities) <= view_ids
    assert set(first.output.evidence_refs) <= evidence


def test_fallback_uses_same_decision_and_newest_mtime(tmp_path, brief, twin, settings, live_settings) -> None:
    folder = tmp_path / "operations"
    folder.mkdir()

    def record(name: str, decision_id: str, summary: str, mtime: int) -> None:
        output = VALID | {"act_now_view": {"summary": summary}}
        path = folder / f"{name}.json"
        path.write_text(json.dumps({"agent_id": "operations", "decision_id": decision_id, "output": output}))
        os.utime(path, (mtime, mtime))

    record("zzz_old", brief.decision_id, "old answer", 1_000)
    record("aaa_new", brief.decision_id, "new answer", 2_000)
    record("mmm_other", "dec_other", "other decision", 3_000)
    replay = AgentLLM(live_settings.model_copy(update={"llm_mode": "replay"}), cache_dir=tmp_path)
    result = call(replay, make_context(brief, twin, settings))
    assert result.status == "fallback_cached" and result.output.act_now_view.summary == "new answer"
    other = brief.model_copy(update={"decision_id": "dec_unseen"})
    assert call(replay, make_context(other, twin, settings)).status == "unavailable"


LLM_ENV = ["SCIFORIUM_API_URL", "SCIFORIUM_BASE_URL", "SCIFORIUM_MODEL", "SCIFORIUM_TEMPERATURE",
           "SCIFORIUM_TIMEOUT_SECONDS", "CANARY_MODEL_STRONG", "CANARY_MODEL_FAST", "MODEL_STRONG", "MODEL_FAST"]


@pytest.fixture
def clean_env(monkeypatch):
    for name in LLM_ENV:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.mark.parametrize("url, expected", [
    ("https://llm.example/v1/chat/completions", "https://llm.example/v1"),
    ("https://llm.example/v1/chat/completions/", "https://llm.example/v1"),
    ("https://llm.example/v1", "https://llm.example/v1"),
])
def test_api_url_trims_chat_completions(clean_env, url, expected) -> None:
    clean_env.setenv("SCIFORIUM_API_URL", url)
    clean_env.setenv("SCIFORIUM_BASE_URL", "https://ignored.example/v1")
    assert resolve_base_url() == expected


def test_base_url_fallbacks(clean_env) -> None:
    assert resolve_base_url() == DEFAULT_BASE_URL
    clean_env.setenv("SCIFORIUM_BASE_URL", "https://base.example/v1")
    assert resolve_base_url() == "https://base.example/v1"


@pytest.mark.parametrize("fast, chain", [
    (False, ["CANARY_MODEL_STRONG", "MODEL_STRONG", "SCIFORIUM_MODEL"]),
    (True, ["CANARY_MODEL_FAST", "MODEL_FAST", "SCIFORIUM_MODEL"]),
])
def test_model_resolution_order(clean_env, fast, chain) -> None:
    llm = AgentLLM(OrganizationSettings(llm_mode="live"))
    assert llm.model_id(fast) is None
    for name in reversed(chain):
        clean_env.setenv(name, f"model-from-{name.lower()}")
        assert llm.model_id(fast) == f"model-from-{name.lower()}"
    field = "model_id_fast" if fast else "model_id_strong"
    assert AgentLLM(OrganizationSettings(llm_mode="live", **{field: "from-settings"})).model_id(fast) == "from-settings"


def test_temperature_and_timeout_from_env_unless_settings_set(tmp_path, brief, twin, settings, clean_env) -> None:
    clean_env.setenv("SCIFORIUM_MODEL", "env-model")
    clean_env.setenv("SCIFORIUM_TEMPERATURE", "0.1")
    clean_env.setenv("SCIFORIUM_TIMEOUT_SECONDS", "12")
    seen = []

    def live(model_id, messages, output_model, *, timeout, temperature):
        seen.append((model_id, timeout, temperature))
        return LiveReply(VALID)

    context = make_context(brief, twin, settings)
    call(AgentLLM(OrganizationSettings(llm_mode="live"), cache_dir=tmp_path, live_call=live), context)
    explicit = OrganizationSettings(llm_mode="live", temperature=0.9, agent_timeout_seconds=30)
    call(AgentLLM(explicit, cache_dir=tmp_path, live_call=live), context)
    assert seen == [("env-model", 12.0, 0.1), ("env-model", 30.0, 0.9)]
    clean_env.setenv("SCIFORIUM_TEMPERATURE", "warm")
    assert AgentLLM(OrganizationSettings(llm_mode="live")).temperature() == 0.4


def test_api_key_never_appears_in_errors(tmp_path, brief, twin, settings, clean_env, caplog) -> None:
    clean_env.setenv("SCIFORIUM_API_KEY", "sk-secret-value")
    clean_env.setenv("SCIFORIUM_MODEL", "env-model")
    llm = AgentLLM(OrganizationSettings(llm_mode="live"), cache_dir=tmp_path,
                   live_call=FakeLive(ConnectionError("upstream refused")))
    result = call(llm, make_context(brief, twin, settings))
    assert result.status == "unavailable"
    assert "sk-secret-value" not in " ".join(result.errors) + caplog.text


def test_missing_strong_model_falls_back_to_fast(tmp_path, brief, twin, settings, clean_env) -> None:
    clean_env.setenv("CANARY_MODEL_FAST", "fast-model")
    seen = []

    def live(model_id, messages, output_model, *, timeout, temperature):
        seen.append(model_id)
        return LiveReply(VALID)

    llm = AgentLLM(OrganizationSettings(llm_mode="live"), cache_dir=tmp_path, live_call=live)
    result = llm.call("challenger", MESSAGES, AgentOutput, prompt_version="p1",
                      context=make_context(brief, twin, settings), fast=False)
    assert result.status == "ok" and seen == ["fast-model"] and result.metrics.model_id == "fast-model"
    assert result.errors == ["strong model not configured; challenger ran on the fast model fast-model"]
    assert llm.model_label == "fast-model"
