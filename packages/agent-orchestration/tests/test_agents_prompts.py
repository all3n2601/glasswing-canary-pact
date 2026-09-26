import json
import logging
import shutil

import pytest
from contracts_py.agents import AgentOutput, ChallengerOutput

from agent_orchestration.prompts import (
    MANIFEST_RELATIVE,
    SECTION_TITLES,
    assemble,
    department_knowledge,
    find_repo_root,
    redact_people,
)
from orchestration_helpers import make_context

AGENTS_WITH_SKILLS = ["finance", "engineering", "ai_data", "operations", "product", "marketing", "sales",
                      "customer_success", "compliance", "challenger"]


@pytest.fixture
def context(brief, twin, settings):
    return make_context(brief, twin, settings, agent_id="finance")


def schema_section(text: str) -> dict:
    return json.loads(text.split(SECTION_TITLES["output_schema"] + "\n", 1)[1])


def test_base_first_schema_last(context) -> None:
    prompt = assemble("finance", context)
    text = prompt.text
    assert text.startswith("You are the Finance agent for Canary Pact.")
    assert text.endswith(json.dumps(AgentOutput.model_json_schema(), indent=2, sort_keys=True))
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


def test_skill_files_for_ten_agents_and_fallback_for_people_knowledge() -> None:
    for agent_id in AGENTS_WITH_SKILLS:
        text, source, _ = department_knowledge(agent_id)
        assert source == "skill" and not text.startswith("# "), agent_id
    text, source, _ = department_knowledge("people_knowledge")
    assert source == "fallback" and text.startswith("Role")
