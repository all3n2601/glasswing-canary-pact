from datetime import date
from typing import Any

from contracts_py.decision import CandidatePlan, DecisionBrief, Intervention, Scenario
from contracts_py.engine import BlastRadius, FutureComparison, PortfolioComparison, SimulationResult
from contracts_py.enums import DocumentStatus, EntityType, Future
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

from canary_api.stubs import results
from canary_api.stubs.twin import stub_twin


def quick_impact(twin: Twin, interventions: list[Intervention], *, brief: DecisionBrief | None = None,
                 settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> SimulationResult:
    decision_id = brief.decision_id if brief else "dec_cut_2m"
    return results.act_now_result(run_id, decision_id, mode="quick")


def simulate(twin: Twin, brief: DecisionBrief, scenario: Scenario, plan: CandidatePlan | None, mode: str, *,
             settings: OrganizationSettings | None = None) -> SimulationResult:
    by_future = {
        Future.inaction: results.inaction_result,
        Future.delay: results.delay_result,
    }
    build = by_future.get(scenario.future, results.act_now_result)
    return build(scenario.run_id, brief.decision_id, mode=mode)


def compare_futures(twin: Twin, brief: DecisionBrief, plan: CandidatePlan, *, alternatives: list[CandidatePlan] | None = None,
                    settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> FutureComparison:
    return results.future_comparison(run_id, brief.decision_id)


def optimize(twin: Twin, brief: DecisionBrief, *, settings: OrganizationSettings | None = None,
             run_id: str = "run_adhoc") -> PortfolioComparison:
    return results.portfolio_comparison(run_id, brief.decision_id)


def blast_radius(result: SimulationResult, twin: Twin) -> BlastRadius:
    decision_id = result.impacts[0].decision_id if result.impacts else "dec_cut_2m"
    if result.future is Future.inaction:
        return results.inaction_blast_radius(result.run_id, decision_id)
    return results.act_now_blast_radius(result.run_id, decision_id)


def check_result(obj: Any, twin: Twin) -> list[ValidationIssue]:
    return []


def load_twin(twin_path: Any, documents_path: Any, snippets_path: Any = None) -> Twin:
    return stub_twin()


def validate_twin(twin: Twin) -> list[ValidationIssue]:
    return []


def build_agent_view(twin: Twin, *, agent_id: str, department_id: str | None, visible_entity_types: list[EntityType],
                     visible_sensitivity: list[Any]) -> AgentView:
    profile = next((p for p in twin.department_profiles if p.department_id == department_id), None)
    return AgentView(
        agent_id=agent_id,
        twin_version=twin.version.twin_version,
        organization=twin.organization,
        department_profile=profile,
        entities=twin.entities,
        edges=twin.edges,
        pressures=twin.pressures,
        documents=twin.documents,
        evidence=twin.evidence,
    )


def reachable_departments(twin: Twin, source_entity_ids: list[str], max_hops: int = 4) -> list[str]:
    return ["dept_compliance", "dept_engineering", "dept_finance", "dept_operations"]


def list_dependencies(twin: Twin, entity_id: str, direction: str = "both", max_depth: int = 1) -> list[Edge]:
    return [e for e in twin.edges if entity_id in (e.source, e.target)]


def to_role_level(obj: Any, twin: Twin) -> Any:
    return obj


def document_is_stale(doc: Document, *, as_of_date: date, settings: OrganizationSettings | None = None) -> bool:
    return doc.status is DocumentStatus.outdated


def aggregate_domain_graph(twin: Twin) -> DomainGraph:
    return DomainGraph(
        nodes=[e for e in twin.entities if e.type is EntityType.department],
        edges=[e for e in twin.edges if e.id.startswith("ch_")],
    )


def department_detail(twin: Twin, department_id: str) -> DepartmentDetail:
    entity = next(e for e in twin.entities if e.id == department_id)
    profile = next(p for p in twin.department_profiles if p.department_id == department_id)
    channels = [e for e in twin.edges if e.id.startswith("ch_")]
    return DepartmentDetail(
        entity=entity,
        profile=profile,
        owned_entities=[e for e in twin.entities if e.department_id == department_id],
        documents=[d for d in twin.documents if d.department_id == department_id],
        channels_in=[e for e in channels if e.target == department_id],
        channels_out=[e for e in channels if e.source == department_id],
    )


def clone_with_edges(twin: Twin, edges: list[Edge]) -> Twin:
    return twin.model_copy(update={"edges": [*twin.edges, *edges]}, deep=True)


def widen_uncertainty(twin: Twin, department_ids: list[str], delta: float = 0.1) -> Twin:
    return twin.model_copy(deep=True)

