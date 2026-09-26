import importlib
import json
import logging
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Literal

from contracts_py.agents import AgentContext
from pydantic import BaseModel

log = logging.getLogger(__name__)

MANIFEST_RELATIVE = Path("packages/agent-orchestration/prompts/manifest.json")
# The lookbehind keeps role and department IDs such as dept_finance intact.
PERSON_TOKEN = re.compile(r"(?<![a-z0-9])pt_[a-z0-9_]+")
SECTION_TITLES = {
    "department_knowledge": "DEPARTMENT KNOWLEDGE",
    "agent_context": "AGENT CONTEXT (JSON)",
    "output_schema": "OUTPUT SCHEMA (JSON Schema)",
}


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / MANIFEST_RELATIVE).is_file():
            return candidate
    raise FileNotFoundError(f"cannot find {MANIFEST_RELATIVE} above {current}")


@cache
def _load_manifest(root: Path) -> dict[str, Any]:
    return json.loads((root / MANIFEST_RELATIVE).read_text(encoding="utf-8"))


def load_manifest(root: Path | None = None) -> dict[str, Any]:
    return _load_manifest(root or find_repo_root())


def redact_people(text: str) -> tuple[str, list[str]]:
    found = PERSON_TOKEN.findall(text)
    return PERSON_TOKEN.sub("[role]", text), found


def strip_title(markdown: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def output_model(agent_id: str, root: Path | None = None) -> type[BaseModel]:
    module_name, class_name = load_manifest(root)["agents"][agent_id]["output_model"].rsplit(".", 1)
    return getattr(importlib.import_module(module_name), class_name)


def department_knowledge(agent_id: str, root: Path | None = None) -> tuple[str, Literal["skill", "fallback"], list[str]]:
    root = root or find_repo_root()
    manifest = load_manifest(root)
    entry = manifest["agents"][agent_id]
    skill = root / entry["skill"]
    if skill.is_file():
        text, source = strip_title(skill.read_text(encoding="utf-8")), "skill"
    else:
        text, source = (root / manifest["prompts_root"] / entry["fallback"]).read_text(encoding="utf-8").strip(), "fallback"
    text, redacted = redact_people(text)
    if redacted:
        log.warning("redacted %d person tokens from the %s %s text", len(redacted), agent_id, source)
    return text, source, redacted  # type: ignore[return-value]


@dataclass
class AssembledPrompt:
    agent_id: str
    messages: list[dict[str, str]]
    output_model: type[BaseModel]
    knowledge_source: str
    redactions: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(m["content"] for m in self.messages)


def assemble(agent_id: str, context: AgentContext, root: Path | None = None) -> AssembledPrompt:
    """Sections follow manifest.assembly_order; only the base template is filled, never the joined prompt."""
    root = root or find_repo_root()
    manifest = load_manifest(root)
    entry = manifest["agents"][agent_id]
    model = output_model(agent_id, root)
    knowledge, source, redacted = department_knowledge(agent_id, root)
    base = (root / manifest["prompts_root"] / entry["base"]).read_text(encoding="utf-8").strip()
    sections = {
        "base": base.replace("{display_name}", entry["display_name"]),
        "department_knowledge": knowledge,
        "agent_context": context.model_dump_json(indent=2),
        "output_schema": json.dumps(model.model_json_schema(), indent=2, sort_keys=True),
    }
    rendered = [
        sections[name] if name == "base" else f"{SECTION_TITLES[name]}\n{sections[name]}"
        for name in manifest["assembly_order"]
    ]
    # Instructions go in the system message; the per-run data and schema go in the user message.
    split = manifest["assembly_order"].index("agent_context")
    messages = [
        {"role": "system", "content": "\n\n".join(rendered[:split])},
        {"role": "user", "content": "\n\n".join(rendered[split:])},
    ]
    return AssembledPrompt(agent_id, messages, model, source, redacted)
