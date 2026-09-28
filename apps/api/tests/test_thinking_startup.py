import logging

from api_auth_helpers import auth_headers
from fastapi.testclient import TestClient
from real_data import sample_brief

from canary_api import runtime


def test_valid_thinking_settings_pass_the_startup_check(monkeypatch) -> None:
    for value in ("", "on", "off", "ON"):
        monkeypatch.setenv("CANARY_LLM_THINKING", value)
        monkeypatch.setenv("CANARY_CHALLENGER_THINKING", value)
        assert runtime.check_thinking() is None


def test_invalid_thinking_fails_at_startup_and_refuses_live_runs(client, monkeypatch, caplog) -> None:
    # Restores the module-level error even if an assertion below fails, so later tests are not refused.
    monkeypatch.setattr(runtime, "thinking_error", None)
    from canary_api.app import app

    monkeypatch.setenv("CANARY_LLM_THINKING", "sometimes")
    with caplog.at_level(logging.ERROR, logger="canary_api.runtime"), TestClient(app):
        pass
    assert "CANARY_LLM_THINKING must be on or off" in caplog.text
    assert runtime.thinking_error and "CANARY_LLM_THINKING" in runtime.thinking_error

    headers = auth_headers(client)
    run = client.post("/decisions", headers=headers, json=sample_brief().model_dump(mode="json"))
    assert run.status_code == 503 and "CANARY_LLM_THINKING" in run.json()["detail"]
    draft = client.post("/decisions/draft", headers=headers, json={"prompt": "Cut two data vendors"})
    assert draft.status_code == 503 and "CANARY_LLM_THINKING" in draft.json()["detail"]

    monkeypatch.setenv("CANARY_LLM_THINKING", "on")
    monkeypatch.setenv("CANARY_CHALLENGER_THINKING", "loud")
    assert "CANARY_CHALLENGER_THINKING" in (runtime.check_thinking() or "")
    monkeypatch.delenv("CANARY_CHALLENGER_THINKING")
    assert runtime.check_thinking() is None


def test_env_example_matches_the_variables_the_code_reads() -> None:
    import re

    from canary_api.paths import REPO_ROOT

    listed = re.findall(r"^([A-Z][A-Z0-9_]*)=", (REPO_ROOT / ".env.example").read_text(), flags=re.M)
    assert len(listed) == len(set(listed))
    sources = [p for root in ("apps", "packages") for p in (REPO_ROOT / root).rglob("*")
               if p.suffix in {".py", ".ts", ".tsx"} and p.is_file()
               and not {"node_modules", ".next", "__pycache__", ".venv"} & set(p.parts)]
    code = "\n".join(p.read_text(errors="ignore") for p in sources)
    # The OpenAI client reads this itself when SCIFORIUM_API_KEY is blank.
    implicit = {"OPENAI_API_KEY"}
    assert [n for n in listed if n not in implicit and not re.search(rf"\b{n}\b", code)] == []

    read = set(re.findall(r'(?:environ(?:\.get)?\(\s*|environ\[|env_first\([^)]*?|_impl\(|_number\("[a-z_]+", |'
                          r'_thinking_setting\()"([A-Z][A-Z0-9_]+)"', code))
    read |= set(re.findall(r"process\.env\.([A-Z][A-Z0-9_]+)", code)) - {"NODE_ENV"}
    read |= {n for n in re.findall(r'"([A-Z][A-Z0-9_]+)"', code) if n.startswith(("CANARY_", "SCIFORIUM_", "MODEL_"))
             and re.search(rf'env_first\([^)]*"{n}"', code)}
    assert sorted(read - set(listed)) == []
