import json

from canary_api import eval_cli


def test_eval_cli_live_writes_measured_outputs(tmp_path, capsys) -> None:
    assert eval_cli.main(["--mode", "live", "--out", str(tmp_path)]) == 0
    ablation = json.loads((tmp_path / "ablation.json").read_text())
    assert [c["config"] for c in ablation["configs"]] == ["full", "no_challenger", "no_evidence", "single_pass"]
    assert all(c["engine_impl"] == "real" and c["llm_mode"] == "live" for c in ablation["configs"])
    assert (tmp_path / "ablation.csv").is_file() and (tmp_path / "eval_runs.json").is_file()
    assert "no_challenger" in capsys.readouterr().out


def test_eval_cli_mock_writes_measured_outputs(tmp_path, capsys) -> None:
    assert eval_cli.main(["--mode", "mock", "--out", str(tmp_path)]) == 0
    ablation = json.loads((tmp_path / "ablation.json").read_text())
    assert [c["config"] for c in ablation["configs"]] == ["full", "no_challenger", "no_evidence", "single_pass"]
    assert all(c["llm_mode"] == "mock" and c["failed_runs"] == 0 for c in ablation["configs"])
    assert "no_challenger" in capsys.readouterr().out


def test_eval_cli_mock_runs_offline_on_the_stub_engine(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ENGINE_IMPL", "stub")
    monkeypatch.setenv("TWIN_IMPL", "stub")
    assert eval_cli.main(["--mode", "mock", "--out", str(tmp_path)]) == 0
    ablation = json.loads((tmp_path / "ablation.json").read_text())
    assert all(c["engine_impl"] == "stub" and c["twin_impl"] == "stub" for c in ablation["configs"])
