import importlib
import json
from pathlib import Path
import re

from pydantic import BaseModel

EXPECTED_AGENTS = {
    "finance",
    "engineering",
    "ai_data",
    "operations",
    "product",
    "marketing",
    "sales",
    "customer_success",
    "compliance",
    "people_knowledge",
    "challenger",
}


def get_repo_root() -> Path:
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").is_file() and (current / "packages").is_dir():
            return current
        current = current.parent
    return Path(__file__).resolve().parents[3]


def test_prompt_manifest_structure():
    repo_root = get_repo_root()
    manifest_path = repo_root / "packages/agent-orchestration/prompts/manifest.json"
    assert manifest_path.is_file(), f"Manifest file missing at {manifest_path}"

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. Manifest parses and agent keys are exactly the expected roster
    assert "agents" in manifest, "Manifest missing 'agents' mapping"
    assert set(manifest["agents"].keys()) == EXPECTED_AGENTS, (
        f"Agents mismatch: {set(manifest['agents'].keys())} != {EXPECTED_AGENTS}"
    )

    # Top-level checks
    assert "challenger_base" not in manifest, "Top-level challenger_base should be removed"
    prompts_root = repo_root / manifest.get("prompts_root", "packages/agent-orchestration/prompts")
    assert prompts_root.is_dir(), f"prompts_root {prompts_root} not found"

    # 2. Every base and fallback file exists under prompts_root
    for agent_id, agent_config in manifest["agents"].items():
        assert "base" in agent_config, f"Missing base for {agent_id}"
        base_path = prompts_root / agent_config["base"]
        assert base_path.is_file(), f"Base file for {agent_id} not found: {base_path}"

        assert "fallback" in agent_config, f"Missing fallback for {agent_id}"
        fallback_path = prompts_root / agent_config["fallback"]
        assert fallback_path.is_file(), f"Fallback file for {agent_id} not found: {fallback_path}"

    # 3. Every output_model imports and is a pydantic model
    for agent_id, agent_config in manifest["agents"].items():
        assert "output_model" in agent_config, f"Missing output_model for {agent_id}"
        model_path = agent_config["output_model"]
        module_name, class_name = model_path.rsplit(".", 1)
        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
        assert issubclass(cls, BaseModel), f"{model_path} for {agent_id} is not a Pydantic BaseModel"

    # 4. Check prompt files: no em dash (U+2014) and only {display_name} placeholder
    prompt_files = list(prompts_root.glob("*.txt")) + list((prompts_root / "fallback").glob("*.txt"))
    assert len(prompt_files) == 13, f"Expected 13 prompt files, found {len(prompt_files)}"

    for prompt_file in prompt_files:
        content = prompt_file.read_text(encoding="utf-8")
        assert "\u2014" not in content, f"Em dash found in {prompt_file}"

        placeholders = set(re.findall(r"\{[^{}]*\}", content))
        for p in placeholders:
            assert p == "{display_name}", (
                f"Unexpected placeholder {p} in {prompt_file}; only {{display_name}} is allowed"
            )
