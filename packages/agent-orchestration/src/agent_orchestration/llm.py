import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

from contracts_py.agents import AgentContext, CallMetrics
from contracts_py.twin import OrganizationSettings
from pydantic import BaseModel, ValidationError

from agent_orchestration.mock import mock_output

DEFAULT_BASE_URL = "https://api.sciforium.com/v1"
AssessmentStatus = Literal["ok", "replayed", "fallback_cached", "unavailable", "invalid"]
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
    model_label: str

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


def sciforium_call(model_id: str, messages: Messages, output_model: type[BaseModel], *, timeout: float,
                   temperature: float) -> LiveReply:
    from langchain_openai import ChatOpenAI

    chat = ChatOpenAI(
        model=model_id,
        base_url=resolve_base_url(),
        api_key=os.environ.get("SCIFORIUM_API_KEY"),
        timeout=timeout,
        temperature=temperature,
        max_retries=0,
    )
    structured = chat.with_structured_output(output_model, method="function_calling", include_raw=True)
    reply = structured.invoke([(m["role"], m["content"]) for m in messages])
    if reply["parsing_error"] is not None:
        raise OutputInvalid(str(reply["parsing_error"]))
    usage = getattr(reply["raw"], "usage_metadata", None) or {}
    return LiveReply(reply["parsed"], usage.get("input_tokens", 0), usage.get("output_tokens", 0))


def prompt_hash(model_id: str, prompt_version: str, messages: Messages, output_model: type[BaseModel],
                run_id: str | None = None) -> str:
    rendered = json.dumps(messages, sort_keys=True)
    if run_id:
        # Scenario and result IDs embed the run ID; masking it lets a new run replay an earlier one.
        rendered = rendered.replace(run_id, "run_id")
    payload = json.dumps([model_id, prompt_version, rendered, output_model.model_json_schema()], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def default_cache_dir() -> Path:
    configured = os.environ.get("CANARY_LLM_CACHE_DIR")
    if configured:
        return Path(configured)
    from agent_orchestration.prompts import find_repo_root

    return find_repo_root() / "data" / "artifacts" / "llm_cache"


class AgentLLM:
    def __init__(self, settings: OrganizationSettings, *, cache_dir: Path | None = None,
                 live_call: LiveCall = sciforium_call) -> None:
        self.settings = settings
        self.mode = settings.llm_mode
        self.cache_dir = cache_dir or default_cache_dir()
        self.live_call = live_call

    @property
    def model_label(self) -> str:
        return self.model_id() or self.model_id(fast=True) or self.mode

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
        if self.mode == "mock":
            metrics.model_id = "mock"
            return LLMResult(mock_output(output_model, context), "ok", metrics)
        decision_id = context.brief.decision_id
        if self.mode == "replay":
            result = self._from_cache(agent_id, decision_id, digest, output_model, metrics, [])
        else:
            result = self._live(agent_id, decision_id, model_id, digest, messages, output_model, metrics)
        result.errors = [*notes, *result.errors]
        return result

    def _live(self, agent_id: str, decision_id: str, model_id: str, digest: str, messages: Messages, output_model: type[BaseModel],
              metrics: CallMetrics) -> LLMResult:
        errors: list[str] = []
        attempt_messages = list(messages)
        started = time.monotonic()
        for attempt in range(2):
            try:
                if model_id == "unconfigured":
                    raise RuntimeError("no model id: set model_id_strong/model_id_fast, CANARY_MODEL_STRONG/FAST, "
                                       "MODEL_STRONG/FAST or SCIFORIUM_MODEL")
                reply = self.live_call(model_id, attempt_messages, output_model,
                                       timeout=self.timeout(), temperature=self.temperature())
                output = output_model.model_validate(
                    reply.output.model_dump() if isinstance(reply.output, BaseModel) else reply.output
                )
            except (ValidationError, OutputInvalid) as exc:
                errors.append(f"attempt {attempt + 1}: {exc}")
                attempt_messages = [*messages, {"role": "user", "content":
                                    f"Your previous output failed validation:\n{exc}\nReturn a corrected output."}]
                continue
            except Exception as exc:  # network, auth or timeout: fall back to the cache
                errors.append(f"live call failed: {exc}")
                return self._from_cache(agent_id, decision_id, digest, output_model, metrics, errors, retries=attempt)
            metrics.latency_ms = int((time.monotonic() - started) * 1000)
            metrics.input_tokens, metrics.output_tokens = reply.input_tokens, reply.output_tokens
            self._write_cache(agent_id, decision_id, digest, model_id, metrics.prompt_version, output)
            return LLMResult(output, "ok", metrics, retries=attempt, errors=errors)
        return LLMResult(None, "invalid", metrics, retries=1, errors=errors)

    def _agent_dir(self, agent_id: str) -> Path:
        return self.cache_dir / agent_id

    def _write_cache(self, agent_id: str, decision_id: str, digest: str, model_id: str, prompt_version: str, output: BaseModel) -> None:
        path = self._agent_dir(agent_id) / f"{digest}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"agent_id": agent_id, "decision_id": decision_id, "model_id": model_id, "prompt_version": prompt_version,
                  "prompt_hash": digest, "output": output.model_dump(mode="json")}
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _fallback(self, agent_id: str, decision_id: str) -> Path | None:
        folder = self._agent_dir(agent_id)
        candidates = []
        for path in folder.glob("*.json") if folder.is_dir() else []:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("agent_id") == agent_id and record.get("decision_id") == decision_id:
                candidates.append(path)
        return max(candidates, key=lambda p: p.stat().st_mtime, default=None)

    def _from_cache(self, agent_id: str, decision_id: str, digest: str, output_model: type[BaseModel],
                    metrics: CallMetrics, errors: list[str], retries: int = 0) -> LLMResult:
        exact = self._agent_dir(agent_id) / f"{digest}.json"
        if exact.is_file():
            path, status = exact, "replayed"
        else:
            fallback = self._fallback(agent_id, decision_id)
            if fallback is None:
                return LLMResult(None, "unavailable", metrics, retries,
                                 [*errors, f"no cached answer for {agent_id} on {decision_id}"])
            path, status = fallback, "fallback_cached"
            errors = [*errors, f"cache miss for {digest}; using {path.stem}"]
        record = json.loads(path.read_text(encoding="utf-8"))
        return LLMResult(output_model.model_validate(record["output"]), status, metrics, retries, errors)  # type: ignore[arg-type]
