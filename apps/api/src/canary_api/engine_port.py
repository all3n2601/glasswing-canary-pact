"""The only module that reaches the engine and twin. ENGINE_IMPL and TWIN_IMPL (real|stub) pick each side.

Both default to real; stub keeps offline tests and the eval harness working without the real packages.
"""

import importlib
import os
from datetime import date
from pathlib import Path
from typing import Any, Callable, Literal

from contracts_py.decision import CandidatePlan, DecisionBrief, Intervention, Scenario
from contracts_py.engine import (
    BlastRadius,
    FutureComparison,
    MissingQuestion,
    MitigationComparison,
    PortfolioComparison,
    SimulationResult,
    VendorOverlap,
)
from contracts_py.enums import EntityType, Sensitivity
from contracts_py.twin import (
    AgentView,
    DepartmentDetail,
    Document,
    DomainGraph,
    Edge,
    OrganizationSettings,
    Twin,
    ValidationIssue,
)

ENGINE_MODULE = "simulation_engine"
TWIN_MODULE = "company_twin"


class EngineNotReady(RuntimeError):
    pass


def _impl(variable: str, default: str) -> str:
    impl = os.environ.get(variable) or default
    if impl not in ("stub", "real"):
        raise EngineNotReady(f"{variable} must be 'stub' or 'real', got {impl!r}")
    return impl


def engine_impl() -> str:
    return _impl("ENGINE_IMPL", "real")


def twin_impl() -> str:
    # The twin follows the engine unless TWIN_IMPL says otherwise, so a real twin can run with the stub engine.
    return _impl("TWIN_IMPL", engine_impl())


def _resolve(module_name: str, name: str) -> Callable[..., Any]:
    variable, impl = ("TWIN_IMPL", twin_impl()) if module_name == TWIN_MODULE else ("ENGINE_IMPL", engine_impl())
    if impl == "stub":
        from canary_api.stubs import engine as stub_engine

        return getattr(stub_engine, name)
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise EngineNotReady(f"{variable}=real but {module_name} cannot be imported: {exc}") from exc
    function = getattr(module, name, None)
    if not callable(function):
        raise EngineNotReady(f"{variable}=real but {module_name}.{name} does not exist yet")
    return function


def quick_impact(twin: Twin, interventions: list[Intervention], *, brief: DecisionBrief | None = None,
                 settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> SimulationResult:
    return _resolve(ENGINE_MODULE, "quick_impact")(twin, interventions, brief=brief, settings=settings, run_id=run_id)


def simulate(twin: Twin, brief: DecisionBrief, scenario: Scenario, plan: CandidatePlan | None, mode: str, *,
             settings: OrganizationSettings | None = None) -> SimulationResult:
    return _resolve(ENGINE_MODULE, "simulate")(twin, brief, scenario, plan, mode, settings=settings)


def compare_futures(twin: Twin, brief: DecisionBrief, plan: CandidatePlan, *, alternatives: list[CandidatePlan] | None = None,
                    settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> FutureComparison:
    return _resolve(ENGINE_MODULE, "compare_futures")(
        twin, brief, plan, alternatives=alternatives or [], settings=settings, run_id=run_id
    )


def optimize(twin: Twin, brief: DecisionBrief, *, settings: OrganizationSettings | None = None,
             run_id: str = "run_adhoc") -> PortfolioComparison:
    return _resolve(ENGINE_MODULE, "optimize")(twin, brief, settings=settings, run_id=run_id)


def blast_radius(result: SimulationResult, twin: Twin) -> BlastRadius:
    return _resolve(ENGINE_MODULE, "blast_radius")(result, twin)


def vendor_overlap(twin: Twin, vendor_ids: list[str]) -> list[VendorOverlap]:
    return _resolve(ENGINE_MODULE, "vendor_overlap")(twin, vendor_ids)


def mitigate(twin: Twin, brief: DecisionBrief, plan: CandidatePlan, actions: list[Intervention], *,
             settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> MitigationComparison:
    return _resolve(ENGINE_MODULE, "mitigate")(twin, brief, plan, actions, settings=settings, run_id=run_id)


def missing_questions(twin: Twin, brief: DecisionBrief, plan: CandidatePlan, *,
                      settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> list[MissingQuestion]:
    return _resolve(ENGINE_MODULE, "missing_questions")(twin, brief, plan, settings=settings, run_id=run_id)


def check_result(obj: Any, twin: Twin) -> list[ValidationIssue]:
    return _resolve(ENGINE_MODULE, "check_result")(obj, twin)


def load_twin(twin_path: Path, snippets_path: Path | None = None) -> Twin:
    return _resolve(TWIN_MODULE, "load_twin")(twin_path, snippets_path)


def build_twin(data: Twin | dict[str, Any], snippets: dict[str, str] | None = None) -> Twin:
    return _resolve(TWIN_MODULE, "build_twin")(data, snippets)


def load_mitigation_catalog(path: Path | None = None, twin: Twin | None = None) -> list[Intervention]:
    return _resolve(TWIN_MODULE, "load_mitigation_catalog")(path, twin)


def validate_twin(twin: Twin) -> list[ValidationIssue]:
    return _resolve(TWIN_MODULE, "validate_twin")(twin)


def build_agent_view(twin: Twin, *, agent_id: str, department_id: str | None, visible_entity_types: list[EntityType],
                     visible_sensitivity: list[Sensitivity]) -> AgentView:
    return _resolve(TWIN_MODULE, "build_agent_view")(
        twin,
        agent_id=agent_id,
        department_id=department_id,
        visible_entity_types=visible_entity_types,
        visible_sensitivity=visible_sensitivity,
    )


def reachable_departments(twin: Twin, source_entity_ids: list[str], max_hops: int = 4) -> list[str]:
    return _resolve(TWIN_MODULE, "reachable_departments")(twin, source_entity_ids, max_hops)


def list_dependencies(twin: Twin, entity_id: str, direction: Literal["in", "out", "both"], max_depth: int) -> list[Edge]:
    return _resolve(TWIN_MODULE, "list_dependencies")(twin, entity_id, direction, max_depth)


def to_role_level(obj: Any, twin: Twin) -> Any:
    return _resolve(TWIN_MODULE, "to_role_level")(obj, twin)


def document_is_stale(doc: Document, *, as_of_date: date, settings: OrganizationSettings | None = None) -> bool:
    return _resolve(TWIN_MODULE, "document_is_stale")(doc, as_of_date=as_of_date, settings=settings)


def aggregate_domain_graph(twin: Twin) -> DomainGraph:
    return _resolve(TWIN_MODULE, "aggregate_domain_graph")(twin)


def department_detail(twin: Twin, department_id: str) -> DepartmentDetail:
    return _resolve(TWIN_MODULE, "department_detail")(twin, department_id)


def clone_with_edges(twin: Twin, edges: list[Edge]) -> Twin:
    return _resolve(TWIN_MODULE, "clone_with_edges")(twin, edges)


def widen_uncertainty(twin: Twin, department_ids: list[str], delta: float = 0.1) -> Twin:
    return _resolve(TWIN_MODULE, "widen_uncertainty")(twin, department_ids, delta)
