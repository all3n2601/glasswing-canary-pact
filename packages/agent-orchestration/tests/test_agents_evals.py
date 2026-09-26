import ast
import csv
import json
import subprocess
import sys
from pathlib import Path

from canary_api.stubs import engine as stub_engine
from contracts_py.agents import AgentContext, AgentOutput, ChallengerOutput, ProposedDependency
from contracts_py.events import EventType

from agent_orchestration import evals, run_decision
from agent_orchestration.llm import LLMResult
from orchestration_helpers import NOW, ScriptedLLM, metrics

PLANTED_EDGE = {"source": "wf_vendor_reconciliation", "relation": "consumes", "target": "ds_account_intel"}
PLANTED_UNKNOWN = {"entity_id": "ds_account_intel"}


def challenger_finds_planted_edge(context: AgentContext) -> LLMResult:
    dependency = ProposedDependency(source="wf_vendor_reconciliation", target="ds_account_intel", relation="consumes",
                                    rationale="The workflow map says account intel feeds it.",
                                    evidence_refs=["ev_echo_account_intel_feed"], confidence=0.8)
    return LLMResult(ChallengerOutput(missed_dependencies=[dependency], confidence=0.6), "ok", metrics("challenger"))


def operations_asks_about_unknown(context: AgentContext) -> LLMResult:
    output = AgentOutput.model_validate({
        "act_now_view": {"summary": "Reconciliation depends on a feed nobody owns."},
        "inaction_view": {"summary": "Nothing changes."},
        "questions": [{"text": "Who refreshes ds_account_intel?", "why_it_matters": "It feeds reconciliation.",
                       "entity_ids": ["ds_account_intel"]}],
        "confidence": 0.6,
    })
    return LLMResult(output, "ok", metrics("operations"))


def planted_file(tmp_path: Path, **keys) -> Path:
    path = tmp_path / "planted_items.json"
    path.write_text(json.dumps({"note": "test", **keys}))
    return path


def scripted(settings):
    return ScriptedLLM(settings, {"challenger": challenger_finds_planted_edge,
                                  "operations": operations_asks_about_unknown})


def run(brief, twin, settings, tmp_path, **kwargs):
    return evals.run_eval(engine=stub_engine, twin=twin, brief=brief, settings=settings, engine_impl="stub",
                          planted_path=kwargs.pop("planted_path", tmp_path / "absent.json"), **kwargs)


def test_every_config_runs_to_a_package_with_all_metrics(brief, twin, settings, tmp_path) -> None:
    report = run(brief, twin, settings, tmp_path)
    assert [row["config"] for row in report.rows] == list(evals.CONFIGS)
    for row in report.rows:
        assert "error" not in row, row.get("error")
        assert set(evals.METRIC_KEYS) <= set(row)
        assert (row["engine_impl"], row["llm_mode"]) == ("stub", "mock")
        assert row["pt_token_leaks"] == 0
    assert [a["config"] for a in report.aggregates] == list(evals.CONFIGS)


def test_no_challenger_has_no_challenger_perspective(brief, twin, settings, tmp_path) -> None:
    rows = {row["config"]: row for row in run(brief, twin, settings, tmp_path).rows}
    assert "challenger" in rows["full"]["agents"] and "challenger" not in rows["no_challenger"]["agents"]
    assert rows["no_challenger"]["perspectives_ok"] == rows["full"]["perspectives_ok"] - 1


def test_no_evidence_removes_resolving_evidence(brief, twin, settings, tmp_path) -> None:
    rows = {row["config"]: row for row in run(brief, twin, settings, tmp_path).rows}
    assert rows["full"]["claims_with_resolving_evidence_pct"] > 0
    assert rows["no_evidence"]["claims_with_resolving_evidence_pct"] == 0


def test_planted_keys_absent_report_null(brief, twin, settings, tmp_path) -> None:
    for path in (tmp_path / "absent.json", planted_file(tmp_path)):
        row = run(brief, twin, settings, tmp_path, planted_path=path, configs=["full"]).rows[0]
        assert row["planted_edge_found"] is None and row["planted_unknown_asked"] is None
        assert row["planted_unknown_rank"] is None


def test_planted_items_are_measured_from_the_run(brief, twin, settings, tmp_path) -> None:
    path = planted_file(tmp_path, planted_edge=PLANTED_EDGE, planted_unknown=PLANTED_UNKNOWN)
    rows = {row["config"]: row for row in run(brief, twin, settings, tmp_path, planted_path=path,
                                              llm_factory=scripted).rows}
    assert rows["full"]["planted_edge_found"] == 1 and rows["single_pass"]["planted_edge_found"] == 1
    assert rows["no_challenger"]["planted_edge_found"] == 0
    assert rows["full"]["planted_unknown_asked"] == 1 and rows["full"]["planted_unknown_rank"] == 1
    plain = run(brief, twin, settings, tmp_path, planted_path=path, configs=["full"]).rows[0]
    assert (plain["planted_edge_found"], plain["planted_unknown_asked"], plain["planted_unknown_rank"]) == (0, 0, None)


def test_corrupting_an_evidence_ref_lowers_resolving_pct(brief, twin, settings) -> None:
    recorder = evals._Recorder()
    package = run_decision(brief, engine=stub_engine, settings=settings, llm=evals.AgentLLM(settings), emit=recorder,
                           run_id="run_eval_probe", twin=twin, clock=lambda: NOW)
    assessments = recorder.of(EventType.agent_completed)
    before = evals.compute_metrics(package, assessments, [], twin, {})
    cited = {r for a in assessments for refs in evals._claim_evidence(a) for r in refs}
    victim = sorted(cited)[0]
    corrupted = twin.model_copy(update={"evidence": [
        e.model_copy(update={"id": "ev_corrupted"}) if e.id == victim else e for e in twin.evidence
    ]})
    after = evals.compute_metrics(package, assessments, [], corrupted, {})
    assert after["claims_total"] == before["claims_total"]
    assert after["claims_with_resolving_evidence_pct"] < before["claims_with_resolving_evidence_pct"]


def test_outputs_and_table(brief, twin, settings, tmp_path) -> None:
    report = run(brief, twin, settings, tmp_path, runs=2)
    paths = evals.write_outputs(report, tmp_path / "out")
    assert [p.name for p in paths] == ["eval_runs.json", "ablation.json", "ablation.csv"]
    assert len(json.loads(paths[0].read_text())["rows"]) == 2 * len(evals.CONFIGS)
    ablation = json.loads(paths[1].read_text())
    assert [c["runs"] for c in ablation["configs"]] == [2] * len(evals.CONFIGS)
    with paths[2].open() as handle:
        assert [row["config"] for row in csv.DictReader(handle)] == list(evals.CONFIGS)
    table = evals.format_table(report.aggregates).splitlines()
    assert table[0].split()[:4] == ["config", "runs", "engine_impl", "llm_mode"] and len(table) == 5


def test_evals_does_not_import_canary_api() -> None:
    tree = ast.parse(Path(evals.__file__).read_text())
    modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    modules += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not [m for m in modules if m and m.startswith("canary_api")]


def test_module_entry_points_to_api_cli() -> None:
    result = subprocess.run([sys.executable, "-m", "agent_orchestration.evals"], capture_output=True, text=True)
    assert result.returncode == 2 and "canary_api.eval_cli" in result.stderr
