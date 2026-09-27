import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Protocol

from contracts_py.agents import AgentContext, CallMetrics
from contracts_py.twin import OrganizationSettings
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.sciforium.com/v1"
StructuredOutput = Literal["auto", "json_schema", "function_calling"]
STRUCTURED_OUTPUT_MODES: tuple[str, ...] = ("auto", "json_schema", "function_calling")
AssessmentStatus = Literal["ok", "unavailable", "invalid"]
Messages = list[dict[str, str]]


class OutputInvalid(ValueError):
    pass


@dataclass
class LiveReply:
    output: Any
    input_tokens: int = 0
    output_tokens: int = 0


LiveCall = Callable[..., LiveReply]


@dataclass
class LLMResult:
    output: BaseModel | None
    status: AssessmentStatus
    metrics: CallMetrics
    retries: int = 0
    errors: list[str] = field(default_factory=list)


class LLMClient(Protocol):
    @property
    def model_label(self) -> str: ...

    def call(self, agent_id: str, messages: Messages, output_model: type[BaseModel], *, prompt_version: str,
             context: AgentContext, fast: bool = False) -> LLMResult: ...


def env_first(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def resolve_base_url() -> str:
    """SCIFORIUM_API_URL is the full completions endpoint; the OpenAI client wants the base before it."""
    url = os.environ.get("SCIFORIUM_API_URL")
    if url:
        url = url.rstrip("/")
        return url.removesuffix("/chat/completions")
    return os.environ.get("SCIFORIUM_BASE_URL") or DEFAULT_BASE_URL


def structured_output_mode() -> StructuredOutput:
    mode = os.environ.get("CANARY_STRUCTURED_OUTPUT", "auto").strip() or "auto"
    if mode not in STRUCTURED_OUTPUT_MODES:
        raise ValueError(f"CANARY_STRUCTURED_OUTPUT must be one of {', '.join(STRUCTURED_OUTPUT_MODES)}, got {mode!r}")
    return mode  # type: ignore[return-value]


RESPONSE_FORMAT_HINTS = ("response_format", "json_schema", "structured output")


def _rejects_response_format(exc: Exception) -> bool:
    """Only a 400 that names the response format; other 400s (bad model, context too long) are real errors."""
    import openai

    if not isinstance(exc, openai.APIStatusError) or exc.status_code != 400:
        return False
    text = f"{exc.message} {exc.body}".lower().replace("_", " ")
    return any(hint.replace("_", " ") in text for hint in RESPONSE_FORMAT_HINTS)


def _structured_invoke(chat: Any, output_model: type[BaseModel], messages: Messages, method: str) -> dict[str, Any]:
    if method == "json_schema":
        structured = chat.with_structured_output(output_model, method="json_schema", include_raw=True, strict=False)
    else:
        structured = chat.with_structured_output(output_model, method="function_calling", include_raw=True)
    return structured.invoke([(m["role"], m["content"]) for m in messages])


THINKING_VALUES = ("on", "off")
# Sciforium's DeepSeek honours only this switch; reasoning_effort and reasoning.enabled are ignored.
THINKING_OFF_BODY = {"chat_template_kwargs": {"thinking": False}}


def _thinking_setting(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip().lower() or default
    if value not in THINKING_VALUES:
        raise ValueError(f"{name} must be on or off, got {value!r}")
    return value


def thinking_enabled(agent_id: str | None = None) -> bool:
    """CANARY_LLM_THINKING (on by default); the challenger may override it with CANARY_CHALLENGER_THINKING."""
    default = _thinking_setting("CANARY_LLM_THINKING", "on")
    if agent_id == "challenger":
        return _thinking_setting("CANARY_CHALLENGER_THINKING", default) == "on"
    return default == "on"


def thinking_kwargs(agent_id: str | None = None) -> dict[str, Any]:
    # Thinking on sends nothing extra, so live calls are unchanged unless someone turns it off.
    return {} if thinking_enabled(agent_id) else {"thinking": False}


def sciforium_call(model_id: str, messages: Messages, output_model: type[BaseModel], *, timeout: float,
                   temperature: float, structured_output: StructuredOutput = "auto",
                   thinking: bool = True) -> LiveReply:
    from langchain_openai import ChatOpenAI

    chat = ChatOpenAI(
        model=model_id,
        base_url=resolve_base_url(),
        api_key=os.environ.get("SCIFORIUM_API_KEY"),
        timeout=timeout,
        temperature=temperature,
        max_retries=0,
        **({} if thinking else {"extra_body": THINKING_OFF_BODY}),
    )
    method = "json_schema" if structured_output == "auto" else structured_output
    try:
        reply = _structured_invoke(chat, output_model, messages, method)
    except Exception as exc:
        if structured_output != "auto" or not _rejects_response_format(exc):
            raise
        # Some OpenAI-compatible servers reject response_format; function calling is the other supported path.
        log.debug("json_schema rejected for %s (HTTP 400); retrying with function_calling", model_id)
        method = "function_calling"
        reply = _structured_invoke(chat, output_model, messages, method)
    if structured_output == "auto" and method == "json_schema" and reply["parsed"] is None \
            and reply["parsing_error"] is None:
        log.debug("json_schema returned nothing for %s; retrying with function_calling", model_id)
        method = "function_calling"
        reply = _structured_invoke(chat, output_model, messages, method)
    if reply["parsing_error"] is not None:
        raise OutputInvalid(str(reply["parsing_error"]))
    log.debug("structured output for %s produced by %s", model_id, method)
    usage = getattr(reply["raw"], "usage_metadata", None) or {}
    return LiveReply(reply["parsed"], usage.get("input_tokens", 0), usage.get("output_tokens", 0))


def prompt_hash(model_id: str, prompt_version: str, messages: Messages, output_model: type[BaseModel],
                run_id: str | None = None) -> str:
    rendered = json.dumps(messages, sort_keys=True)
    if run_id:
        # Scenario and result IDs embed the run ID; masking it keeps equivalent prompts comparable.
        rendered = rendered.replace(run_id, "run_id")
    payload = json.dumps([model_id, prompt_version, rendered, output_model.model_json_schema()], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


class AgentLLM:
    def __init__(self, settings: OrganizationSettings, *, live_call: LiveCall = sciforium_call) -> None:
        self.settings = settings
        self.live_call = live_call

    @property
    def model_label(self) -> str:
        return self.model_id() or self.model_id(fast=True) or "live"

    def model_id(self, fast: bool = False) -> str | None:
        if fast:
            return self.settings.model_id_fast or env_first("CANARY_MODEL_FAST", "MODEL_FAST", "SCIFORIUM_MODEL")
        return self.settings.model_id_strong or env_first("CANARY_MODEL_STRONG", "MODEL_STRONG", "SCIFORIUM_MODEL")

    def _number(self, field: str, env_name: str) -> float:
        # Settings always carry a default, so only an explicitly set value beats the team .env.
        if field not in self.settings.model_fields_set and os.environ.get(env_name):
            try:
                return float(os.environ[env_name])
            except ValueError:
                pass
        return float(getattr(self.settings, field))

    def temperature(self) -> float:
        return self._number("temperature", "SCIFORIUM_TEMPERATURE")

    def structured_output(self) -> StructuredOutput:
        return structured_output_mode()

    def timeout(self) -> float:
        return self._number("agent_timeout_seconds", "SCIFORIUM_TIMEOUT_SECONDS")

    def call(self, agent_id: str, messages: Messages, output_model: type[BaseModel], *, prompt_version: str,
             context: AgentContext, fast: bool = False) -> LLMResult:
        notes: list[str] = []
        model_id = self.model_id(fast)
        if model_id is None and not fast and self.model_id(fast=True):
            model_id = self.model_id(fast=True)
            notes.append(f"strong model not configured; {agent_id} ran on the fast model {model_id}")
        model_id = model_id or "unconfigured"
        digest = prompt_hash(model_id, prompt_version, messages, output_model, context.run_id)
        metrics = CallMetrics(model_id=model_id, prompt_version=prompt_version, prompt_hash=digest, latency_ms=0,
                              input_tokens=0, output_tokens=0)
        result = self._live(agent_id, model_id, messages, output_model, metrics)
        result.errors = [*notes, *result.errors]
        return result

    def _live(self, agent_id: str, model_id: str, messages: Messages, output_model: type[BaseModel],
              metrics: CallMetrics) -> LLMResult:
        # Resolved before the attempts so a misconfigured mode fails loudly instead of looking like an outage.
        structured_output = self.structured_output()
        thinking = thinking_kwargs(agent_id)
        errors: list[str] = []
        attempt_messages = list(messages)
        started = time.monotonic()
        for attempt in range(2):
            try:
                if model_id == "unconfigured":
                    raise RuntimeError("no model id: set model_id_strong/model_id_fast, CANARY_MODEL_STRONG/FAST, "
                                       "MODEL_STRONG/FAST or SCIFORIUM_MODEL")
                reply = self.live_call(model_id, attempt_messages, output_model,
                                       timeout=self.timeout(), temperature=self.temperature(),
                                       structured_output=structured_output, **thinking)
                output = output_model.model_validate(
                    reply.output.model_dump() if isinstance(reply.output, BaseModel) else reply.output
                )
            except (ValidationError, OutputInvalid) as exc:
                errors.append(f"attempt {attempt + 1}: {exc}")
                attempt_messages = [*messages, {"role": "user", "content":
                                    f"Your previous output failed validation:\n{exc}\nReturn a corrected output."}]
                continue
            except Exception as exc:  # network, auth, configuration, or timeout
                errors.append(f"live call failed: {exc}")
                metrics.latency_ms = int((time.monotonic() - started) * 1000)
                return LLMResult(None, "unavailable", metrics, retries=attempt, errors=errors)
            metrics.latency_ms = int((time.monotonic() - started) * 1000)
            metrics.input_tokens, metrics.output_tokens = reply.input_tokens, reply.output_tokens
            return LLMResult(output, "ok", metrics, retries=attempt, errors=errors)
        return LLMResult(None, "invalid", metrics, retries=1, errors=errors)
