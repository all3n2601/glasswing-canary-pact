"""The API boundary for the real company twin and deterministic engine."""

from datetime import date
from pathlib import Path
from typing import Any, Literal

import company_twin
import simulation_engine

from contracts_py.decision import CandidatePlan, DecisionBrief, Intervention, Scenario
from contracts_py.engine import BlastRadius, FutureComparison, PortfolioComparison, SimulationResult, VendorOverlap
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


class EngineNotReady(RuntimeError):
    pass


def engine_impl() -> Literal["real"]:
    return "real"


def twin_impl() -> Literal["real"]:
    return "real"


def quick_impact(twin: Twin, interventions: list[Intervention], *, brief: DecisionBrief | None = None,
                 settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> SimulationResult:
    return simulation_engine.quick_impact(
        twin, interventions, brief=brief, settings=settings, run_id=run_id
    )


def simulate(twin: Twin, brief: DecisionBrief, scenario: Scenario, plan: CandidatePlan | None, mode: str, *,
             settings: OrganizationSettings | None = None) -> SimulationResult:
    return simulation_engine.simulate(twin, brief, scenario, plan, mode, settings=settings)


def compare_futures(twin: Twin, brief: DecisionBrief, plan: CandidatePlan, *, alternatives: list[CandidatePlan] | None = None,
                    settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> FutureComparison:
    return simulation_engine.compare_futures(
        twin, brief, plan, alternatives=alternatives or [], settings=settings, run_id=run_id
    )


def optimize(twin: Twin, brief: DecisionBrief, *, settings: OrganizationSettings | None = None,
             run_id: str = "run_adhoc") -> PortfolioComparison:
    return simulation_engine.optimize(twin, brief, settings=settings, run_id=run_id)


def blast_radius(result: SimulationResult, twin: Twin) -> BlastRadius:
    return simulation_engine.blast_radius(result, twin)


def vendor_overlap(twin: Twin, vendor_ids: list[str]) -> list[VendorOverlap]:
    return simulation_engine.vendor_overlap(twin, vendor_ids)


def check_result(obj: Any, twin: Twin) -> list[ValidationIssue]:
    return simulation_engine.check_result(obj, twin)


def load_twin(twin_path: Path, snippets_path: Path | None = None) -> Twin:
    return company_twin.load_twin(twin_path, snippets_path)


def validate_twin(twin: Twin) -> list[ValidationIssue]:
    return company_twin.validate_twin(twin)


def build_agent_view(twin: Twin, *, agent_id: str, department_id: str | None, visible_entity_types: list[EntityType],
                     visible_sensitivity: list[Sensitivity]) -> AgentView:
    return company_twin.build_agent_view(
        twin,
        agent_id=agent_id,
        department_id=department_id,
        visible_entity_types=visible_entity_types,
        visible_sensitivity=visible_sensitivity,
    )


def reachable_departments(twin: Twin, source_entity_ids: list[str], max_hops: int = 4) -> list[str]:
    return company_twin.reachable_departments(twin, source_entity_ids, max_hops)


def list_dependencies(
    twin: Twin,
    entity_id: str,
    direction: Literal["in", "out", "both"],
    max_depth: int,
) -> list[Edge]:
    return company_twin.list_dependencies(twin, entity_id, direction, max_depth)


def to_role_level(obj: Any, twin: Twin) -> Any:
    return company_twin.to_role_level(obj, twin)


def document_is_stale(doc: Document, *, as_of_date: date, settings: OrganizationSettings | None = None) -> bool:
    return company_twin.document_is_stale(doc, as_of_date=as_of_date, settings=settings)


def aggregate_domain_graph(twin: Twin) -> DomainGraph:
    return company_twin.aggregate_domain_graph(twin)


def department_detail(twin: Twin, department_id: str) -> DepartmentDetail:
    return company_twin.department_detail(twin, department_id)


def clone_with_edges(twin: Twin, edges: list[Edge]) -> Twin:
    return company_twin.clone_with_edges(twin, edges)


def widen_uncertainty(twin: Twin, department_ids: list[str], delta: float = 0.1) -> Twin:
    return company_twin.widen_uncertainty(twin, department_ids, delta)
