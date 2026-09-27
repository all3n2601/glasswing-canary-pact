import json
import logging

import pytest

import company_twin
from canary_api import engine_port, paths
from canary_api.stubs import engine as stub_engine
from canary_api.stubs import twin as stub_twin_module
from contracts_py.decision import DecisionBrief

TWIN_FUNCTIONS = ["load_twin", "validate_twin", "build_agent_view", "reachable_departments", "list_dependencies",
                  "to_role_level", "document_is_stale", "aggregate_domain_graph", "department_detail",
                  "clone_with_edges", "widen_uncertainty"]
ENGINE_FUNCTIONS = ["quick_impact", "simulate", "compare_futures", "optimize", "blast_radius", "check_result"]


@pytest.mark.parametrize(("loader", "filename"), [
    (stub_twin_module.sample_brief, "vendor_scenario.json"),
    (stub_twin_module.workforce_brief, "workforce_scenario.json"),
])
def test_briefs_come_from_the_data_files(loader, filename) -> None:
    on_disk = DecisionBrief.model_validate_json((paths.DATA_DIR / filename).read_text())
    assert loader() == on_disk
    assert loader().decision_id in ("dec_vendor_reduction", "dec_workforce_knowledge")


def test_vendor_brief_matches_the_data_team_file() -> None:
    raw = json.loads((paths.DATA_DIR / "vendor_scenario.json").read_text())
    brief = stub_twin_module.sample_brief()
    assert [c.id for c in brief.constraints] == [c["id"] for c in raw["constraints"]]
    assert brief.active_pressure_ids == raw["active_pressure_ids"]


@pytest.mark.parametrize(("loader", "fallback"), [
    (stub_twin_module.sample_brief, stub_twin_module.fallback_vendor_brief),
    (stub_twin_module.workforce_brief, stub_twin_module.fallback_workforce_brief),
])
def test_missing_brief_file_falls_back_with_a_warning(loader, fallback, tmp_path, monkeypatch, caplog) -> None:
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    with caplog.at_level(logging.WARNING, logger="canary_api.stubs.twin"):
        brief = loader()
    assert brief == fallback()
    assert "not found" in caplog.text and brief.decision_id in caplog.text


def test_both_switches_default_to_real(monkeypatch) -> None:
    monkeypatch.delenv("ENGINE_IMPL", raising=False)
    monkeypatch.delenv("TWIN_IMPL", raising=False)
    assert (engine_port.engine_impl(), engine_port.twin_impl()) == ("real", "real")


def test_twin_defaults_to_the_engine_setting(monkeypatch) -> None:
    monkeypatch.delenv("TWIN_IMPL", raising=False)
    monkeypatch.setenv("ENGINE_IMPL", "real")
    assert engine_port.twin_impl() == "real"
    monkeypatch.setenv("ENGINE_IMPL", "stub")
    assert engine_port.twin_impl() == "stub"
    monkeypatch.setenv("TWIN_IMPL", "bogus")
    with pytest.raises(engine_port.EngineNotReady, match="TWIN_IMPL"):
        engine_port.twin_impl()


def test_real_twin_with_stub_engine_resolves_each_side(monkeypatch) -> None:
    monkeypatch.setenv("ENGINE_IMPL", "stub")
    monkeypatch.setenv("TWIN_IMPL", "real")
    for name in TWIN_FUNCTIONS:
        assert engine_port._resolve(engine_port.TWIN_MODULE, name) is getattr(company_twin, name), name
    for name in ENGINE_FUNCTIONS:
        assert engine_port._resolve(engine_port.ENGINE_MODULE, name) is getattr(stub_engine, name), name


def test_stub_twin_with_real_engine_names_the_engine_variable(monkeypatch) -> None:
    import sys
    import types

    monkeypatch.setitem(sys.modules, "simulation_engine", types.ModuleType("simulation_engine"))
    monkeypatch.setenv("ENGINE_IMPL", "real")
    monkeypatch.setenv("TWIN_IMPL", "stub")
    for name in TWIN_FUNCTIONS:
        assert engine_port._resolve(engine_port.TWIN_MODULE, name) is getattr(stub_engine, name), name
    with pytest.raises(engine_port.EngineNotReady, match=r"ENGINE_IMPL=real but simulation_engine\.optimize"):
        engine_port._resolve(engine_port.ENGINE_MODULE, "optimize")


def test_health_reports_both_implementations(client, monkeypatch) -> None:
    body = client.get("/health").json()
    assert (body["engine_impl"], body["twin_impl"]) == ("real", "real")
    monkeypatch.setenv("ENGINE_IMPL", "stub")
    monkeypatch.setenv("TWIN_IMPL", "real")
    body = client.get("/health").json()
    assert (body["engine_impl"], body["twin_impl"]) == ("stub", "real")


def test_stub_twin_never_reads_storage(monkeypatch) -> None:
    from canary_api import runtime, storage

    monkeypatch.setenv("TWIN_IMPL", "stub")
    monkeypatch.setattr(runtime, "_stub_twin", None)
    monkeypatch.setattr(storage.current(), "load_active_twin", lambda: pytest.fail("stub twin read storage"))
    assert runtime.twin() == stub_engine.load_twin(paths.DATA_DIR / "synthetic_company.json")


def test_real_twin_loads_the_fixture(monkeypatch) -> None:
    from canary_api import runtime

    monkeypatch.setenv("TWIN_IMPL", "real")
    twin = runtime.twin()
    assert twin.organization.id == "org_northstar"
    brief = stub_twin_module.sample_brief()
    ids = {e.id for e in twin.entities}
    assert {i.target_entity_id for i in brief.candidate_interventions} <= ids
    assert set(brief.active_pressure_ids or []) <= {p.id for p in twin.pressures}
