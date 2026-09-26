import json
import os

import pytest
from contracts_py.agents import AgentOutput
from contracts_py.twin import OrganizationSettings

from agent_orchestration.llm import AgentLLM, LiveReply
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
