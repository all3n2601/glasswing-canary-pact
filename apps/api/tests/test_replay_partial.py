import logging
import shutil

import pytest
from real_data import sample_brief
from test_replay_fallback import run

from canary_api import runs


@pytest.mark.parametrize(("configured", "allow", "expected"), [
    ("mock", "true", "mock"),
    ("replay", "true", "replay"),
    ("live", "false", "live"),
    ("REPLAY ", "true", "replay"),
    ("", "true", "live"),
    ("", "false", "replay"),
])
def test_default_mode_prefers_canary_llm_mode(monkeypatch, configured, allow, expected) -> None:
    monkeypatch.setenv("CANARY_LLM_MODE", configured)
    monkeypatch.setenv("CANARY_ALLOW_LIVE", allow)
    assert runs.default_llm_mode() == expected


def test_bad_canary_llm_mode_is_ignored_with_a_warning(monkeypatch, caplog) -> None:
    monkeypatch.setenv("CANARY_LLM_MODE", "chatty")
    monkeypatch.setenv("CANARY_ALLOW_LIVE", "false")
    with caplog.at_level(logging.WARNING, logger="canary_api.runs"):
        assert runs.default_llm_mode() == "replay"
    assert "CANARY_LLM_MODE" in caplog.text


def test_live_env_mode_still_needs_allow_live(client, monkeypatch) -> None:
    from api_auth_helpers import auth_headers

    monkeypatch.setenv("CANARY_LLM_MODE", "live")
    monkeypatch.setenv("CANARY_ALLOW_LIVE", "false")
    response = client.post("/decisions", headers=auth_headers(client), json=sample_brief().model_dump(mode="json"))
    assert response.status_code == 403


def test_replay_mocks_only_the_agents_without_a_cached_answer(client, monkeypatch, tmp_path) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("CANARY_LLM_CACHE_DIR", str(cache))
    brief = sample_brief()
    _, live, _ = run(client, brief, "live")
    agents = {a.agent_id for a in live}
    missing = sorted(a for a in agents if a != "finance")[0]
    shutil.rmtree(cache / missing)

    _, replayed, package = run(client, brief, "replay")
    by_agent = {a.agent_id: a for a in replayed}
    assert set(by_agent) == agents
    mocked = by_agent[missing]
    assert (mocked.status, mocked.metrics.model_id) == ("ok", "mock")
    assert any(e.startswith("mock fallback") for e in mocked.validation.errors)
    others = [a for a in replayed if a.agent_id != missing]
    assert others and all(a.status in ("replayed", "fallback_cached") and a.metrics.model_id != "mock" for a in others)
    assert not [a for a in replayed if a.status == "unavailable"]
    assert runs.mock_fallback_assumption([missing]) in package["assumptions"]
    assert runs.MOCK_FALLBACK_ASSUMPTION not in package["assumptions"]
    assert missing not in package["missing_perspectives"]


def test_every_env_example_variable_is_read() -> None:
    import re

    from canary_api.paths import REPO_ROOT

    names = re.findall(r"^([A-Z][A-Z0-9_]*)=", (REPO_ROOT / ".env.example").read_text(), flags=re.M)
    assert "CANARY_LLM_MODE" in names and "LLM_MODE" not in names
    # The OpenAI client reads this itself when SCIFORIUM_API_KEY is blank.
    implicit = {"OPENAI_API_KEY"}
    sources = [p for root in ("apps", "packages") for p in (REPO_ROOT / root).rglob("*")
               if p.suffix in {".py", ".ts", ".tsx"} and p.is_file()
               and not {"node_modules", ".next", "tests", "__pycache__"} & set(p.parts)]
    code = "\n".join(p.read_text(errors="ignore") for p in sources)
    unread = [n for n in names if n not in implicit and not re.search(rf"\b{n}\b", code)]
    assert unread == []
