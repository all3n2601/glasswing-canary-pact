"""Ablation evals: run the full decision pipeline per configuration and measure every number from the runs.

The engine, twin and brief are injected so this package never imports canary_api; the runnable entry point is
`uv run python -m canary_api.eval_cli`.
"""

import argparse
import csv
import json
import os
import statistics
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from contracts_py.agents import AgentAssessment, AgentOutput, ChallengerOutput
from contracts_py.decision import DecisionBrief
from contracts_py.enums import Future
from contracts_py.events import EventType
from contracts_py.package import DecisionPackage
from contracts_py.twin import OrganizationSettings, Twin
from pydantic import BaseModel

from agent_orchestration.llm import AgentLLM, LLMClient
from agent_orchestration.merge import REJECTED_MARKER
from agent_orchestration.orchestrator import run_decision
from agent_orchestration.ports import EnginePort
from agent_orchestration.prompts import PERSON_TOKEN, find_repo_root

CONFIGS: dict[str, dict[str, bool]] = {
    "full": {},
    "no_challenger": {"challenger": False},
    "no_evidence": {"agent_evidence": False},
    # Validated edges are still reported, but never fed back into the engine for a second simulation pass.
    "single_pass": {"feedback": False},
}
METRIC_KEYS = [
    "planted_edge_found",
    "planted_unknown_asked",
    "planted_unknown_rank",
    "planted_unknown_in_agent_questions",
    "perspectives_ok",
    "missing_perspectives",
    "claims_total",
    "claims_with_resolving_evidence_pct",
    "rejected_items",
    "pt_token_leaks",
    "wall_seconds",
    "agent_latency_ms_p50",
    "input_tokens_total",
    "output_tokens_total",
]
TABLE_KEYS = ["planted_edge_found", "planted_unknown_asked", "planted_unknown_in_agent_questions", "perspectives_ok", "missing_perspectives",
              "claims_total", "claims_with_resolving_evidence_pct", "rejected_items", "pt_token_leaks",
              "wall_seconds", "agent_latency_ms_p50", "input_tokens_total", "output_tokens_total"]
OK_STATUSES = {"ok", "replayed"}


@dataclass
class EvalReport:
    rows: list[dict[str, Any]]
    aggregates: list[dict[str, Any]]
    planted_keys: list[str] = field(default_factory=list)


class _Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[EventType, BaseModel]] = []
        self.lock = threading.Lock()

    def __call__(self, type: EventType, payload: BaseModel, *, actor: str, scenario_id: str | None = None,
                 future: Future | None = None) -> None:
        with self.lock:
            self.events.append((type, payload))

    def of(self, kind: EventType) -> list[Any]:
        return [payload for event_type, payload in self.events if event_type is kind]


def default_planted_path() -> Path:
    return find_repo_root() / "data" / "planted_items.json"


def default_out_dir() -> Path:
    return find_repo_root() / "data" / "artifacts" / "eval"


def load_planted(path: Path | None) -> dict[str, Any]:
    path = path or default_planted_path()
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _claim_evidence(assessment: AgentAssessment) -> list[list[str]]:
    """Evidence refs of every agent claim that can carry evidence: findings, impacts and dependencies."""
    claims: list[list[str]] = []
    output = assessment.output
    if isinstance(output, AgentOutput):
        for view in (output.act_now_view, output.inaction_view):
            claims += [f.evidence_refs for f in [*view.failure_modes, *view.edge_cases]]
            claims += [p.evidence_refs for p in view.proposed_impacts]
        claims += [d.evidence_refs for d in output.proposed_dependencies]
    challenge = assessment.challenge
    if isinstance(challenge, ChallengerOutput):
        findings = [*challenge.unsupported_assumptions, *challenge.circular_logic, *challenge.inaction_underestimated]
        claims += [f.evidence_refs for f in findings]
        claims += [d.evidence_refs for d in challenge.missed_dependencies]
    return claims


def _planted_edge_found(planted: dict[str, Any], edges: list[Any]) -> int | None:
    target = planted.get("planted_edge")
    if target is None:
        return None
    relation = str(target["relation"]).upper()
    return int(any(e.source == target["source"] and e.relation.value == relation and e.target == target["target"]
                   for e in edges))


def _planted_unknown(planted: dict[str, Any], package: DecisionPackage) -> tuple[int | None, int | None]:
    target = planted.get("planted_unknown")
    if target is None:
        return None, None
    entity_id = target["entity_id"]
    asked = [*package.open_questions, *(q.model_dump_json() for q in package.missing_information)]
    rank = next((index for index, text in enumerate(asked, start=1) if entity_id in text), None)
    return int(rank is not None), rank


def _planted_unknown_in_agent_questions(planted: dict[str, Any], assessments: list[AgentAssessment]) -> int | None:
    target = planted.get("planted_unknown")
    if target is None:
        return None
    entity_id = target["entity_id"]
    questions = [q for a in assessments if isinstance(a.output, AgentOutput) for q in a.output.questions]
    return int(any(entity_id in q.entity_ids or entity_id in q.text for q in questions))


def compute_metrics(package: DecisionPackage, assessments: list[AgentAssessment], validated_edges: list[Any],
                    twin: Twin, planted: dict[str, Any]) -> dict[str, Any]:
    evidence_ids = {e.id for e in twin.evidence}
    claims = [refs for a in assessments for refs in _claim_evidence(a)]
    resolving = sum(1 for refs in claims if any(r in evidence_ids for r in refs))
    latencies = [a.metrics.latency_ms for a in assessments]
    asked, rank = _planted_unknown(planted, package)
    return {
        "planted_edge_found": _planted_edge_found(planted, validated_edges),
        "planted_unknown_asked": asked,
        "planted_unknown_rank": rank,
        "planted_unknown_in_agent_questions": _planted_unknown_in_agent_questions(planted, assessments),
        "perspectives_ok": sum(1 for a in assessments if a.status in OK_STATUSES),
        "missing_perspectives": len(package.missing_perspectives),
        "claims_total": len(claims),
        "claims_with_resolving_evidence_pct": round(100 * resolving / len(claims), 1) if claims else None,
        # Only rejected claims; cache-miss, retry and model-fallback notes are not rejections.
        "rejected_items": sum(1 for a in assessments for e in a.validation.errors if REJECTED_MARKER in e),
        "pt_token_leaks": len(PERSON_TOKEN.findall(package.model_dump_json())),
        "agent_latency_ms_p50": statistics.median(latencies) if latencies else None,
        "input_tokens_total": sum(a.metrics.input_tokens for a in assessments),
        "output_tokens_total": sum(a.metrics.output_tokens for a in assessments),
    }


def _mean(values: list[Any]) -> float | None:
    present = [v for v in values if v is not None]
    return round(statistics.fmean(present), 3) if present else None


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregates = []
    for config in dict.fromkeys(row["config"] for row in rows):
        group = [row for row in rows if row["config"] == config]
        aggregates.append({
            "config": config,
            "runs": len(group),
            "failed_runs": sum(1 for row in group if row.get("error")),
            "engine_impl": group[0]["engine_impl"],
            "twin_impl": group[0]["twin_impl"],
            "llm_mode": group[0]["llm_mode"],
            **{key: _mean([row.get(key) for row in group]) for key in METRIC_KEYS},
        })
    return aggregates


def run_eval(*, engine: EnginePort, twin: Twin, brief: DecisionBrief, settings: OrganizationSettings,
             llm_mode: str = "mock", runs: int = 1, engine_impl: str = "unknown", twin_impl: str = "unknown",
             cache_dir: Path | None = None,
             planted_path: Path | None = None, configs: list[str] | None = None,
             llm_factory: Callable[[OrganizationSettings], LLMClient] | None = None) -> EvalReport:
    planted = load_planted(planted_path)
    run_settings = settings.model_copy(update={"llm_mode": llm_mode})
    rows: list[dict[str, Any]] = []
    for config in configs or list(CONFIGS):
        for index in range(1, runs + 1):
            llm = llm_factory(run_settings) if llm_factory else AgentLLM(run_settings, cache_dir=cache_dir)
            recorder = _Recorder()
            row: dict[str, Any] = {"config": config, "run": index, "engine_impl": engine_impl, "twin_impl": twin_impl,
                                   "llm_mode": llm_mode}
            started = time.perf_counter()
            try:
                package = run_decision(brief, engine=engine, settings=run_settings, llm=llm, emit=recorder,
                                       run_id=f"run_eval_{config}_{index}", twin=twin, **CONFIGS[config])
            except Exception as exc:
                row.update({key: None for key in METRIC_KEYS}, error=str(exc))
                row["wall_seconds"] = round(time.perf_counter() - started, 3)
                rows.append(row)
                continue
            row["wall_seconds"] = round(time.perf_counter() - started, 3)
            assessments = recorder.of(EventType.agent_completed)
            edges = [event.edge for event in recorder.of(EventType.dependency_validated)]
            row.update(compute_metrics(package, assessments, edges, twin, planted))
            row["agents"] = sorted({a.agent_id for a in assessments})
            rows.append(row)
    keys = [k for k in ("planted_edge", "planted_unknown") if k in planted]
    return EvalReport(rows, aggregate(rows), keys)


def write_outputs(report: EvalReport, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    runs_path, json_path, csv_path = out_dir / "eval_runs.json", out_dir / "ablation.json", out_dir / "ablation.csv"
    runs_path.write_text(json.dumps({"generated_at": generated_at, "rows": report.rows}, indent=2) + "\n")
    json_path.write_text(json.dumps({"generated_at": generated_at, "planted_keys_present": report.planted_keys,
                                     "metrics": METRIC_KEYS, "configs": report.aggregates}, indent=2) + "\n")
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report.aggregates[0]) if report.aggregates else ["config"])
        writer.writeheader()
        writer.writerows(report.aggregates)
    return [runs_path, json_path, csv_path]


def format_table(aggregates: list[dict[str, Any]]) -> str:
    columns = ["config", "runs", "engine_impl", "twin_impl", "llm_mode", *TABLE_KEYS]
    cells = [[("null" if row.get(c) is None else str(row.get(c))) for c in columns] for row in aggregates]
    widths = [max(len(c), *(len(r[i]) for r in cells)) for i, c in enumerate(columns)]
    lines = ["  ".join(c.ljust(w) for c, w in zip(columns, widths))]
    lines += ["  ".join(v.ljust(w) for v, w in zip(row, widths)) for row in cells]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the decision pipeline ablations and write measured metrics.")
    parser.add_argument("--mode", choices=["mock", "replay", "live"], default="mock")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--out", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None, *, engine: EnginePort, twin: Twin, brief: DecisionBrief,
         settings: OrganizationSettings, engine_impl: str, twin_impl: str = "unknown",
         cache_dir: Path | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.mode == "live" and os.environ.get("CANARY_ALLOW_LIVE", "").strip().lower() != "true":
        raise SystemExit("--mode live is disabled; set CANARY_ALLOW_LIVE=true to allow paid model calls")
    report = run_eval(engine=engine, twin=twin, brief=brief, settings=settings, llm_mode=args.mode, runs=args.runs,
                      engine_impl=engine_impl, twin_impl=twin_impl, cache_dir=cache_dir)
    paths = write_outputs(report, args.out or default_out_dir())
    print(format_table(report.aggregates))
    if not report.planted_keys:
        print("planted_edge / planted_unknown missing from data/planted_items.json: those metrics are null")
    print("wrote " + ", ".join(str(p) for p in paths))
    return 1 if any(row.get("error") for row in report.rows) else 0


if __name__ == "__main__":
    print("evals needs an injected engine and twin; run: uv run python -m canary_api.eval_cli --mode mock",
          file=sys.stderr)
    raise SystemExit(2)
