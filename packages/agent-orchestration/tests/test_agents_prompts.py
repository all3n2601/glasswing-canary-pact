import json
import logging
import shutil

import pytest
from contracts_py.agents import AgentOutput, ChallengerOutput

from agent_orchestration.prompts import (
    MANIFEST_RELATIVE,
    SECTION_TITLES,
    assemble,
    find_repo_root,
    load_manifest,
    redact_people,
    strip_schema_titles,
    strip_title,
)
from orchestration_helpers import make_context

@pytest.fixture
def context(brief, twin, settings):
    return make_context(brief, twin, settings, agent_id="finance")


def schema_section(text: str) -> dict:
    return json.loads(text.split(SECTION_TITLES["output_schema"] + "\n", 1)[1])


def test_base_first_schema_last(context) -> None:
    prompt = assemble("finance", context)
    text = prompt.text
    assert text.startswith("You are the Finance agent for Canary Pact.")
    compact_schema = json.dumps(strip_schema_titles(AgentOutput.model_json_schema()), separators=(",", ":"),
                                sort_keys=True)
    assert text.endswith(compact_schema) and '"title"' not in compact_schema
    positions = [text.index(SECTION_TITLES[k]) for k in ("department_knowledge", "agent_context", "output_schema")]
    assert positions == sorted(positions)
    assert [m["role"] for m in prompt.messages] == ["system", "user"]
    assert set(schema_section(text)["$defs"]) >= {"Finding", "ProposedImpact", "FutureView"}


def test_challenger_uses_its_base_and_schema(brief, twin, settings) -> None:
    prompt = assemble("challenger", make_context(brief, twin, settings, agent_id="challenger"))
    assert prompt.output_model is ChallengerOutput
    assert "ChallengerOutput record" in prompt.messages[0]["content"]
    assert "Finding" in schema_section(prompt.text)["$defs"]


def test_json_braces_in_context_do_not_break_assembly(context) -> None:
    odd = context.model_copy(update={"known_impact_summaries": ["{display_name} {agent} }{ {{x}}"]})
    text = assemble("finance", odd).text
    assert '"{display_name} {agent} }{ {{x}}"' in text
    assert "{display_name}" not in text.split(SECTION_TITLES["agent_context"])[0]


def test_person_tokens_redacted_in_skill_text(tmp_path, context, caplog) -> None:
    root = find_repo_root()
    prompts = MANIFEST_RELATIVE.parent
    shutil.copytree(root / prompts, tmp_path / prompts)
    skills = tmp_path / "docs" / "skillfiles"
    skills.mkdir(parents=True)
    (skills / "finance.md").write_text("# Finance\nAsk pt_07 and pt_ops_lead; dept_finance owns close.\n")
    with caplog.at_level(logging.WARNING):
        prompt = assemble("finance", context, root=tmp_path)
    knowledge = prompt.messages[0]["content"]
    assert "Ask [role] and [role]; dept_finance owns close." in knowledge
    assert "# Finance" not in knowledge and prompt.redactions == ["pt_07", "pt_ops_lead"]
    assert "redacted 2 person tokens" in caplog.text


def test_redact_keeps_department_ids() -> None:
    assert redact_people("dept_ops, kept_x, pt_1") == ("dept_ops, kept_x, [role]", ["pt_1"])


def knowledge_texts(root, agent_id: str) -> tuple[str, str]:
    manifest = load_manifest(root)
    entry = manifest["agents"][agent_id]
    skill = root / entry["skill"]
    fallback = (root / manifest["prompts_root"] / entry["fallback"]).read_text(encoding="utf-8").strip()
    skill_text = redact_people(strip_title(skill.read_text(encoding="utf-8")))[0] if skill.is_file() else ""
    return skill_text, fallback


# Agents allowed to run on their fallback text; empty now that every agent has a skill file.
FALLBACK_ALLOWED: set[str] = set()


@pytest.mark.parametrize("agent_id", sorted(load_manifest()["agents"]))
def test_every_agent_uses_its_skill_file(agent_id, brief, twin, settings) -> None:
    root = find_repo_root()
    skill = root / load_manifest(root)["agents"][agent_id]["skill"]
    skill_text, fallback = knowledge_texts(root, agent_id)
    prompt = assemble(agent_id, make_context(brief, twin, settings, agent_id=agent_id))
    system = prompt.messages[0]["content"]
    if agent_id in FALLBACK_ALLOWED and not skill.is_file():
        assert fallback in system
        return
    assert skill.is_file(), f"{agent_id} has no skill file at {skill}"
    assert prompt.knowledge_source == "skill"
    assert skill_text in system and fallback not in system


def test_missing_skill_file_falls_back(tmp_path, brief, twin, settings) -> None:
    root = find_repo_root()
    shutil.copytree(root / MANIFEST_RELATIVE.parent, tmp_path / MANIFEST_RELATIVE.parent)
    skill_text, fallback = knowledge_texts(root, "finance")
    assert skill_text, "finance must have a skill file in the repo for this test to mean anything"
    prompt = assemble("finance", make_context(brief, twin, settings, agent_id="finance"), root=tmp_path)
    system = prompt.messages[0]["content"]
    assert prompt.knowledge_source == "fallback"
    assert fallback in system and skill_text not in system
