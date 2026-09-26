import asyncio
import json
import logging
from datetime import datetime, timezone

import pytest
from api_auth_helpers import auth_headers

from canary_api import engine_port, eval_cli, paths, runtime, storage
from canary_api.app import app, lifespan
from canary_api.stubs import engine as stub_engine
from canary_api.stubs.results import STORY_VALUES
from canary_api.stubs.twin import sample_brief, stub_twin, workforce_brief
from contracts_py.decision import CandidatePlan, DecisionBrief, Scenario
from contracts_py.enums import Future


@pytest.fixture
def restore_structured_output(monkeypatch):
    yield
    monkeypatch.delenv("CANARY_STRUCTURED_OUTPUT", raising=False)
    runtime.check_structured_output()


def test_invalid_structured_output_blocks_live_runs_at_startup(client, brief_json, monkeypatch, caplog,
                                                               restore_structured_output) -> None:
    monkeypatch.setenv("CANARY_STRUCTURED_OUTPUT", "xml")
    monkeypatch.setattr(storage, "close", lambda: None)

    async def start_and_stop() -> None:
        async with lifespan(app):
            pass

    with caplog.at_level(logging.ERROR, logger="canary_api.runtime"):
        asyncio.run(start_and_stop())
    assert "live runs disabled" in caplog.text and "CANARY_STRUCTURED_OUTPUT" in caplog.text
    monkeypatch.setenv("CANARY_ALLOW_LIVE", "true")
    denied = client.post("/decisions?llm_mode=live", headers=auth_headers(client), json=brief_json)
    assert denied.status_code == 503
    assert "CANARY_STRUCTURED_OUTPUT must be one of auto, json_schema, function_calling" in denied.json()["detail"]
    assert client.post("/decisions?llm_mode=mock", headers=auth_headers(client), json=brief_json).status_code == 200


def test_valid_structured_output_clears_the_startup_error(monkeypatch, restore_structured_output) -> None:
    monkeypatch.setenv("CANARY_STRUCTURED_OUTPUT", "json_schema")
    assert runtime.check_structured_output() is None and runtime.structured_output_error is None


def _values(node, key: str) -> set[str]:
    if isinstance(node, dict):
        found = set()
        for k, v in node.items():
            if k == key and isinstance(v, str):
                found.add(v)
            elif k == key and isinstance(v, list):
                found |= {x for x in v if isinstance(x, str)}
            else:
                found |= _values(v, key)
        return found
    if isinstance(node, list):
        return set().union(*(_values(v, key) for v in node)) if node else set()
    return set()


def _stub_constraint_ids(brief: DecisionBrief) -> set[str]:
    twin = stub_twin()
    portfolio = stub_engine.optimize(twin, brief, run_id="run_check")
    chosen = portfolio.recommended or portfolio.naive
    plan = CandidatePlan(plan_id=chosen.plan_id, label="check", intervention_ids=chosen.intervention_ids,
                         source="optimizer")
    results = [p.result for p in [portfolio.naive, portfolio.recommended, *portfolio.alternatives] if p]
    for future in (Future.act_now, Future.inaction, Future.delay):
        acting = future is not Future.inaction
        scenario = Scenario(scenario_id="scn_check", run_id="run_check", future=future,
                            plan_id=plan.plan_id if acting else None, delay_days=0, baseline_twin_version="v",
                            created_at=datetime.now(timezone.utc))
        results.append(stub_engine.simulate(twin, brief, scenario, plan if acting else None, "full"))
    results.append(stub_engine.quick_impact(twin, brief.candidate_interventions, brief=brief))
    dumped = [r.model_dump(mode="json") for r in results]
    return _values(dumped, "constraint_id") | _values(dumped, "constraint_refs")


@pytest.mark.parametrize("loader", [sample_brief, workforce_brief])
def test_stub_constraint_ids_exist_in_the_brief(loader) -> None:
    brief = loader()
    known = {c.id for c in brief.constraints}
    story = STORY_VALUES[brief.decision_id]
    from_story = _values(story, "constraint_id") | _values(story, "constraint_refs")
    from_engine = _stub_constraint_ids(brief)
    assert from_story and from_engine
    assert from_story - known == set() and from_engine - known == set()


@pytest.mark.parametrize("filename", ["vendor_scenario.json", "workforce_scenario.json"])
def test_data_briefs_match_the_real_twin(filename, monkeypatch) -> None:
    brief = DecisionBrief.model_validate_json((paths.DATA_DIR / filename).read_text())
    monkeypatch.setenv("TWIN_IMPL", "real")
    twin = engine_port.load_twin(paths.DATA_DIR / "synthetic_company.json", None)
    entities, pressures = {e.id for e in twin.entities}, {p.id for p in twin.pressures}
    assert [i.target_entity_id for i in brief.candidate_interventions if i.target_entity_id not in entities] == []
    assert [p for p in brief.active_pressure_ids or [] if p not in pressures] == []
    assert [p for p in brief.protected_entity_ids if p not in entities] == []


def test_eval_cli_live_needs_opt_in(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("CANARY_ALLOW_LIVE", raising=False)
    with pytest.raises(SystemExit, match="CANARY_ALLOW_LIVE=true"):
        eval_cli.main(["--mode", "live", "--out", str(tmp_path)])
    assert not (tmp_path / "ablation.json").exists()


def test_eval_cli_records_twin_impl(tmp_path) -> None:
    assert eval_cli.main(["--mode", "mock", "--out", str(tmp_path)]) == 0
    rows = json.loads((tmp_path / "eval_runs.json").read_text())["rows"]
    assert {row["twin_impl"] for row in rows} == {engine_port.twin_impl()}
