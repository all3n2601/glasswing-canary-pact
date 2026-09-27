import importlib
import json
import logging
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Literal

from contracts_py.agents import AgentContext, AgentSkillFile
from pydantic import BaseModel

log = logging.getLogger(__name__)

MANIFEST_RELATIVE = Path("packages/agent-orchestration/prompts/manifest.json")
# The lookbehind keeps role and department IDs such as dept_finance intact.
PERSON_TOKEN = re.compile(r"(?<![a-z0-9])pt_[a-z0-9_]+")
SECTION_TITLES = {
    "department_knowledge": "DEPARTMENT KNOWLEDGE",
    "agent_context": "AGENT CONTEXT (JSON; edge and effect table rows follow the listed columns; null means absent)",
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


def prune(value: Any) -> Any:
    """Drops nulls and empty strings, lists and objects so the prompt only carries facts."""
    if isinstance(value, dict):
        pruned = {k: prune(v) for k, v in value.items()}
        return {k: v for k, v in pruned.items() if v not in (None, "", [], {})}
    if isinstance(value, list):
        return [prune(v) for v in value]
    return value


# Fields the agent never reasons over: storage metadata, and values the context already implies.
OMIT_FIELDS = {
    "entities": {"sensitivity"},
    "edges": {"strength_range", "confidence", "coefficient_version", "last_validated", "extraction_method"},
    "documents": {"uri", "mime_type", "uploaded_at", "synthetic", "ingested", "checksum_sha256", "page_count",
                  "version", "sensitivity", "covers_entity_ids"},
    "evidence": {"synthetic"},
    "impacts": {"decision_id", "scenario_id", "origin", "status", "edge_path"},
}


def slim_context(context: dict[str, Any]) -> dict[str, Any]:
    view = dict(context.get("view", {}))
    for part in ("entities", "edges", "documents", "evidence"):
        view[part] = [{k: v for k, v in item.items() if k not in OMIT_FIELDS[part]} for item in view.get(part, [])]
    # Agents propose dependencies by source, relation and target, so an edge id is only noise.
    view["edges"] = [{k: v for k, v in e.items() if k != "id" and not (k == "lag_days" and v == 0)}
                     for e in view["edges"]]
    # A column header avoids repeating edge field names while retaining every value.
    edges = prune(view["edges"])
    if edges:
        columns = sorted({key for edge in edges for key in edge})
        view["edges"] = {"columns": columns, "rows": [[edge.get(key) for key in columns] for edge in edges]}
    slim = {**context, "view": view}
    for key in ("act_now_effects", "inaction_effects"):
        effects = prune([{k: v for k, v in i.items() if k not in OMIT_FIELDS["impacts"]}
                         for i in context.get(key, [])])
        if effects:
            columns = sorted({key for effect in effects for key in effect})
            slim[key] = {"columns": columns, "rows": [[effect.get(key) for key in columns] for effect in effects]}
        else:
            slim[key] = []
    return slim


def strip_schema_titles(schema: Any) -> Any:
    """Pydantic repeats every field name as a title; property names stay, the titles go."""
    if isinstance(schema, list):
        return [strip_schema_titles(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: strip_schema_titles(v) for k, v in schema.items() if k not in ("title", "properties")}
    if "properties" in schema:
        out["properties"] = {name: strip_schema_titles(prop) for name, prop in schema["properties"].items()}
    return out


def compact_json(value: Any) -> str:
    return json.dumps(prune(value), separators=(",", ":"), ensure_ascii=False)


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


def agent_skill_files(root: Path | None = None) -> list[AgentSkillFile]:
    """Return the effective, redacted knowledge file used by every configured agent."""
    root = root or find_repo_root()
    manifest = load_manifest(root)
    from agent_orchestration.roster import ROSTER

    result = []
    for agent_id, entry in manifest["agents"].items():
        content, source, _ = department_knowledge(agent_id, root)
        relative_path = entry["skill"] if source == "skill" else str(Path(manifest["prompts_root"]) / entry["fallback"])
        spec = ROSTER[agent_id]
        result.append(AgentSkillFile(
            agent_id=agent_id,
            display_name=spec.display_name,
            department_id=spec.department_id,
            source=source,
            file_path=relative_path,
            content=content,
        ))
    return result


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
        "agent_context": compact_json(slim_context(context.model_dump(mode="json", exclude_none=True))),
        "output_schema": json.dumps(strip_schema_titles(model.model_json_schema()), separators=(",", ":"),
                                    sort_keys=True),
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
