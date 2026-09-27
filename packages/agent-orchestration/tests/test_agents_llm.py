from types import SimpleNamespace

import httpx
import openai
import pytest
from contracts_py.agents import AgentOutput
from contracts_py.twin import OrganizationSettings

from agent_orchestration.llm import DEFAULT_BASE_URL, AgentLLM, LiveReply, OutputInvalid, resolve_base_url, sciforium_call
from orchestration_helpers import make_context

VALID = {"act_now_view": {"summary": "Billing loses its owner."}, "inaction_view": {"summary": "Hazard stays."},
         "confidence": 0.6}
MESSAGES = [{"role": "system", "content": "sys"}, {"role": "user", "content": "ctx run_test {\"a\": 1}"}]


class FakeLive:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen: list[list[dict]] = []

    def __call__(self, model_id, messages, output_model, *, timeout, temperature, structured_output="auto"):
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


def test_live_success_is_not_recorded(tmp_path, brief, twin, settings, live_settings) -> None:
    result = call(AgentLLM(live_settings, live_call=FakeLive(VALID)), make_context(brief, twin, settings))
    assert result.status == "ok" and result.metrics.input_tokens == 10
    assert list(tmp_path.rglob("*.json")) == []


def test_validation_failure_retries_once_with_error(tmp_path, brief, twin, settings, live_settings) -> None:
    fake = FakeLive({"confidence": "high"}, VALID)
    result = call(AgentLLM(live_settings, live_call=fake), make_context(brief, twin, settings))
    assert result.status == "ok" and result.retries == 1
    assert "failed validation" in fake.seen[1][-1]["content"] and len(fake.seen[1]) == len(MESSAGES) + 1


def test_invalid_twice_is_invalid(tmp_path, brief, twin, settings, live_settings) -> None:
    fake = FakeLive({"confidence": "high"}, {})
    result = call(AgentLLM(live_settings, live_call=fake), make_context(brief, twin, settings))
    assert result.status == "invalid" and result.output is None and len(result.errors) == 2


def test_live_error_is_unavailable_without_fallback(brief, twin, settings, live_settings) -> None:
    down = AgentLLM(live_settings, live_call=FakeLive(TimeoutError("slow")))
    result = call(down, make_context(brief, twin, settings))
    assert result.status == "unavailable" and result.output is None


def test_live_without_model_id_is_unavailable(tmp_path, brief, twin, settings, monkeypatch) -> None:
    monkeypatch.delenv("CANARY_MODEL_STRONG", raising=False)
    llm = AgentLLM(OrganizationSettings(llm_mode="live"), live_call=FakeLive(VALID))
    result = call(llm, make_context(brief, twin, settings))
    assert result.status == "unavailable" and "no model id" in result.errors[0]


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

    def live(model_id, messages, output_model, *, timeout, temperature, structured_output="auto"):
        seen.append((model_id, timeout, temperature))
        return LiveReply(VALID)

    context = make_context(brief, twin, settings)
    call(AgentLLM(OrganizationSettings(llm_mode="live"), live_call=live), context)
    explicit = OrganizationSettings(llm_mode="live", temperature=0.9, agent_timeout_seconds=30)
    call(AgentLLM(explicit, live_call=live), context)
    assert seen == [("env-model", 12.0, 0.1), ("env-model", 30.0, 0.9)]
    clean_env.setenv("SCIFORIUM_TEMPERATURE", "warm")
    assert AgentLLM(OrganizationSettings(llm_mode="live")).temperature() == 0.4


def test_api_key_never_appears_in_errors(tmp_path, brief, twin, settings, clean_env, caplog) -> None:
    clean_env.setenv("SCIFORIUM_API_KEY", "sk-secret-value")
    clean_env.setenv("SCIFORIUM_MODEL", "env-model")
    llm = AgentLLM(OrganizationSettings(llm_mode="live"), live_call=FakeLive(ConnectionError("upstream refused")))
    result = call(llm, make_context(brief, twin, settings))
    assert result.status == "unavailable"
    assert "sk-secret-value" not in " ".join(result.errors) + caplog.text


def test_missing_strong_model_falls_back_to_fast(tmp_path, brief, twin, settings, clean_env) -> None:
    clean_env.setenv("CANARY_MODEL_FAST", "fast-model")
    seen = []

    def live(model_id, messages, output_model, *, timeout, temperature, structured_output="auto"):
        seen.append(model_id)
        return LiveReply(VALID)

    llm = AgentLLM(OrganizationSettings(llm_mode="live"), live_call=live)
    result = llm.call("challenger", MESSAGES, AgentOutput, prompt_version="p1",
                      context=make_context(brief, twin, settings), fast=False)
    assert result.status == "ok" and seen == ["fast-model"] and result.metrics.model_id == "fast-model"
    assert result.errors == ["strong model not configured; challenger ran on the fast model fast-model"]
    assert llm.model_label == "fast-model"


class FakeChat:
    """Stands in for langchain_openai.ChatOpenAI; replies come from a shared script."""

    script: list = []
    methods: list[tuple[str, object]] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def with_structured_output(self, schema, *, method, include_raw, strict=None):
        assert include_raw is True
        FakeChat.methods.append((method, strict))
        return SimpleNamespace(invoke=self._invoke)

    def _invoke(self, messages):
        reply = FakeChat.script.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


REQUEST = httpx.Request("POST", "https://llm.example/v1/chat/completions")


def reply(parsed=None, parsing_error=None) -> dict:
    return {"raw": SimpleNamespace(usage_metadata={"input_tokens": 3, "output_tokens": 2}), "parsed": parsed,
            "parsing_error": parsing_error}


def rejected() -> openai.BadRequestError:
    return openai.BadRequestError("response_format is not supported", response=httpx.Response(400, request=REQUEST),
                                  body=None)


@pytest.fixture
def fake_chat(monkeypatch):
    import langchain_openai

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeChat)
    monkeypatch.delenv("CANARY_STRUCTURED_OUTPUT", raising=False)
    FakeChat.script, FakeChat.methods = [], []
    return FakeChat


def live(mode=None):
    kwargs = {} if mode is None else {"structured_output": mode}
    return sciforium_call("m", MESSAGES, AgentOutput, timeout=5, temperature=0.1, **kwargs)


def parsed_output() -> AgentOutput:
    return AgentOutput.model_validate(VALID)


def test_default_is_auto_and_tries_json_schema_first(fake_chat) -> None:
    fake_chat.script = [reply(parsed_output())]
    result = live()
    assert fake_chat.methods == [("json_schema", False)]
    assert result.output == parsed_output() and (result.input_tokens, result.output_tokens) == (3, 2)
    assert AgentLLM(OrganizationSettings(llm_mode="live")).structured_output() == "auto"


def test_auto_falls_back_when_json_schema_returns_nothing(fake_chat) -> None:
    fake_chat.script = [reply(None), reply(parsed_output())]
    assert live("auto").output == parsed_output()
    assert [m for m, _ in fake_chat.methods] == ["json_schema", "function_calling"]


def test_auto_falls_back_on_response_format_rejection(fake_chat) -> None:
    fake_chat.script = [rejected(), reply(parsed_output())]
    assert live("auto").output == parsed_output()
    assert [m for m, _ in fake_chat.methods] == ["json_schema", "function_calling"]


def test_auto_does_not_retry_timeouts(fake_chat) -> None:
    fake_chat.script = [openai.APITimeoutError(request=REQUEST)]
    with pytest.raises(openai.APITimeoutError):
        live("auto")
    assert [m for m, _ in fake_chat.methods] == ["json_schema"]


@pytest.mark.parametrize("mode", ["json_schema", "function_calling"])
def test_forced_mode_makes_exactly_one_call(fake_chat, mode) -> None:
    fake_chat.script = [reply(None)]
    assert live(mode).output is None
    assert [m for m, _ in fake_chat.methods] == [mode]


def test_forced_json_schema_does_not_fall_back_on_rejection(fake_chat) -> None:
    fake_chat.script = [rejected()]
    with pytest.raises(openai.BadRequestError):
        live("json_schema")
    assert len(fake_chat.methods) == 1


@pytest.mark.parametrize("mode", ["auto", "json_schema", "function_calling"])
def test_parsing_error_raises_output_invalid(fake_chat, mode) -> None:
    fake_chat.script = [reply(None, parsing_error=ValueError("bad json"))]
    with pytest.raises(OutputInvalid, match="bad json"):
        live(mode)
    assert len(fake_chat.methods) == 1


def test_client_passes_env_mode_to_the_call(fake_chat, monkeypatch, tmp_path, brief, twin, settings) -> None:
    monkeypatch.setenv("CANARY_STRUCTURED_OUTPUT", "function_calling")
    fake_chat.script = [reply(parsed_output())]
    llm = AgentLLM(OrganizationSettings(llm_mode="live", model_id_strong="m"))
    result = call(llm, make_context(brief, twin, settings))
    assert result.status == "ok" and [m for m, _ in fake_chat.methods] == ["function_calling"]


def test_invalid_structured_output_env_raises(fake_chat, monkeypatch, tmp_path, brief, twin, settings) -> None:
    monkeypatch.setenv("CANARY_STRUCTURED_OUTPUT", "xml")
    llm = AgentLLM(OrganizationSettings(llm_mode="live", model_id_strong="m"))
    with pytest.raises(ValueError, match="auto, json_schema, function_calling"):
        llm.structured_output()
    with pytest.raises(ValueError, match="CANARY_STRUCTURED_OUTPUT"):
        call(llm, make_context(brief, twin, settings))
    assert fake_chat.methods == []


def bad_request(message: str, body=None) -> openai.BadRequestError:
    return openai.BadRequestError(message, response=httpx.Response(400, request=REQUEST), body=body)


@pytest.mark.parametrize("error", [
    bad_request("Unknown model: /deployments/x/typo"),
    bad_request("This model's maximum context length is 32768 tokens"),
])
def test_auto_does_not_retry_unrelated_400s(fake_chat, error) -> None:
    fake_chat.script = [error]
    with pytest.raises(openai.BadRequestError):
        live("auto")
    assert [m for m, _ in fake_chat.methods] == ["json_schema"]


@pytest.mark.parametrize("error", [
    bad_request("Invalid request", body={"error": {"message": "json_schema is not supported by this model"}}),
    bad_request("Structured output is not available for this deployment"),
])
def test_auto_retries_400s_that_name_the_response_format(fake_chat, error) -> None:
    fake_chat.script = [error, reply(parsed_output())]
    assert live("auto").output == parsed_output()
    assert [m for m, _ in fake_chat.methods] == ["json_schema", "function_calling"]
