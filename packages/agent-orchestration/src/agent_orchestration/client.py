from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError


StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


class SciforiumError(RuntimeError):
    """Raised when SciForium cannot return a valid structured response."""


@dataclass(frozen=True)
class SciforiumConfig:
    api_key: str | None
    api_url: str = "https://api.sciforium.com/v1/chat/completions"
    model: str = "/deployments/506a9a37/deepseek-ai/DeepSeek-V4.1-Flash"
    temperature: float = 0.7
    timeout_seconds: float = 30.0
    max_retries: int = 1

    @classmethod
    def from_env(cls) -> "SciforiumConfig":
        return cls(
            api_key=os.getenv("SCIFORIUM_API_KEY"),
            api_url=os.getenv(
                "SCIFORIUM_API_URL",
                "https://api.sciforium.com/v1/chat/completions",
            ),
            model=os.getenv(
                "SCIFORIUM_MODEL",
                "/deployments/506a9a37/deepseek-ai/DeepSeek-V4.1-Flash",
            ),
            temperature=float(os.getenv("SCIFORIUM_TEMPERATURE", "0.7")),
            timeout_seconds=float(os.getenv("SCIFORIUM_TIMEOUT_SECONDS", "30")),
        )


class SciforiumClient:
    """Thin OpenAI-compatible client used by every department agent."""

    def __init__(
        self,
        config: SciforiumConfig | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.config = config or SciforiumConfig.from_env()
        self._http_client = http_client or httpx.Client(
            timeout=self.config.timeout_seconds
        )
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client:
            self._http_client.close()

    def __enter__(self) -> "SciforiumClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[StructuredOutput],
    ) -> StructuredOutput:
        if not self.config.api_key:
            raise SciforiumError("SCIFORIUM_API_KEY is not configured")

        schema_instruction = (
            "Return only one valid JSON object. Do not include Markdown or chain of "
            "thought. The object must satisfy this JSON Schema:\n"
            + json.dumps(response_model.model_json_schema(), separators=(",", ":"))
        )
        request_messages = [message.copy() for message in messages]
        if request_messages and request_messages[0]["role"] == "system":
            request_messages[0]["content"] += f"\n\n{schema_instruction}"
        else:
            request_messages.insert(
                0, {"role": "system", "content": schema_instruction}
            )
        payload = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "messages": request_messages,
        }

        last_error: Exception | None = None
        for _ in range(self.config.max_retries + 1):
            try:
                response = self._http_client.post(
                    self.config.api_url,
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                content = self._extract_content(response.json())
                return response_model.model_validate_json(self._strip_code_fence(content))
            except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError) as exc:
                last_error = exc

        raise SciforiumError(
            "SciForium did not return a valid structured response"
        ) from last_error

    @staticmethod
    def _extract_content(response: dict[str, Any]) -> str:
        content = response["choices"][0]["message"]["content"]
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            if text_parts:
                return "".join(text_parts)
        raise TypeError("SciForium response content is not text")

    @staticmethod
    def _strip_code_fence(content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            lines = stripped.splitlines()
            return "\n".join(lines[1:-1]).strip()
        return stripped
