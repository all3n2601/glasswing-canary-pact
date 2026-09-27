import pytest
from contracts_py.agents import AgentOutput
from contracts_py.twin import OrganizationSettings

from agent_orchestration.intake import DecisionIntake
from agent_orchestration.llm import AgentLLM, LiveReply, sciforium_call, thinking_enabled
from orchestration_helpers import make_context
from test_agents_intake import PROMPT, proposal

VALID = {"act_now_view": {"summary": "ok"}, "inaction_view": {"summary": "ok"}, "confidence": 0.5}
MESSAGES = [{"role": "system", "content": "sys"}, {"role": "user", "content": "ctx"}]
SETTINGS = OrganizationSettings(llm_mode="live", model_id_strong="test-model")


class RecordingLive:
    def __init__(self, reply=VALID):
        self.reply = reply
        self.kwargs: list[dict] = []

    def __call__(self, model_id, messages, output_model, **kwargs):
        self.kwargs.append(kwargs)
        return LiveReply(self.reply)


@pytest.fixture(autouse=True)
def clean_thinking_env(monkeypatch):
    monkeypatch.delenv("CANARY_LLM_THINKING", raising=False)
    monkeypatch.delenv("CANARY_CHALLENGER_THINKING", raising=False)
    return monkeypatch


def agent_call(agent_id, brief, twin, settings):
    live = RecordingLive()
    result = AgentLLM(SETTINGS, live_call=live).call(agent_id, MESSAGES, AgentOutput, prompt_version="p1",
                                                    context=make_context(brief, twin, settings))
    assert result.status == "ok"
    return live.kwargs[0]


def test_default_is_thinking_on_and_sends_nothing_extra(brief, twin, settings) -> None:
    assert thinking_enabled() and thinking_enabled("challenger")
    assert "thinking" not in agent_call("operations", brief, twin, settings)
    assert "thinking" not in agent_call("challenger", brief, twin, settings)


def test_off_passes_the_thinking_switch(brief, twin, settings, clean_thinking_env) -> None:
    clean_thinking_env.setenv("CANARY_LLM_THINKING", "OFF")
    assert agent_call("operations", brief, twin, settings)["thinking"] is False
    assert agent_call("challenger", brief, twin, settings)["thinking"] is False


def test_challenger_override_either_way(brief, twin, settings, clean_thinking_env) -> None:
    clean_thinking_env.setenv("CANARY_LLM_THINKING", "off")
    clean_thinking_env.setenv("CANARY_CHALLENGER_THINKING", "on")
    assert agent_call("operations", brief, twin, settings)["thinking"] is False
    assert "thinking" not in agent_call("challenger", brief, twin, settings)

    clean_thinking_env.setenv("CANARY_LLM_THINKING", "on")
    clean_thinking_env.setenv("CANARY_CHALLENGER_THINKING", "off")
    assert "thinking" not in agent_call("operations", brief, twin, settings)
    assert agent_call("challenger", brief, twin, settings)["thinking"] is False


def test_intake_follows_the_default_switch(twin, clean_thinking_env) -> None:
    live = RecordingLive(proposal())
    DecisionIntake(SETTINGS, live_call=live).draft(PROMPT, twin=twin, created_by="usr_test")
    assert "thinking" not in live.kwargs[0]
    clean_thinking_env.setenv("CANARY_LLM_THINKING", "off")
    live = RecordingLive(proposal())
    DecisionIntake(SETTINGS, live_call=live).draft(PROMPT, twin=twin, created_by="usr_test")
    assert live.kwargs[0]["thinking"] is False


@pytest.mark.parametrize(("name", "value"), [("CANARY_LLM_THINKING", "maybe"), ("CANARY_CHALLENGER_THINKING", "1")])
def test_invalid_values_are_rejected(clean_thinking_env, name, value) -> None:
    clean_thinking_env.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        thinking_enabled("challenger")


class _Stop(Exception):
    pass


@pytest.mark.parametrize(("thinking", "expected"), [(True, None), (False, {"chat_template_kwargs": {"thinking": False}})])
def test_sciforium_call_sends_extra_body_only_when_thinking_is_off(monkeypatch, thinking, expected) -> None:
    import langchain_openai

    seen: dict = {}

    def fake_chat(**kwargs):
        seen.update(kwargs)
        raise _Stop

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", fake_chat)
    with pytest.raises(_Stop):
        sciforium_call("m", MESSAGES, AgentOutput, timeout=1, temperature=0.1, thinking=thinking)
    assert seen.get("extra_body") == expected
