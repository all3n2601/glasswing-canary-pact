from typing import Any, Literal, Protocol

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
from contracts_py.twin import AgentView, Edge, OrganizationSettings, Twin, ValidationIssue


class EnginePort(Protocol):
    """Mirrors apps/api/src/canary_api/engine_port.py; that module (or the stub engine) is passed in as-is."""

    def quick_impact(self, twin: Twin, interventions: list[Intervention], *, brief: DecisionBrief | None = None,
                     settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> SimulationResult: ...

    def simulate(self, twin: Twin, brief: DecisionBrief, scenario: Scenario, plan: CandidatePlan | None, mode: str, *,
                 settings: OrganizationSettings | None = None) -> SimulationResult: ...

    def compare_futures(self, twin: Twin, brief: DecisionBrief, plan: CandidatePlan, *,
                        alternatives: list[CandidatePlan] | None = None, settings: OrganizationSettings | None = None,
                        run_id: str = "run_adhoc") -> FutureComparison: ...

    def optimize(self, twin: Twin, brief: DecisionBrief, *, settings: OrganizationSettings | None = None,
                 run_id: str = "run_adhoc") -> PortfolioComparison: ...

    def blast_radius(self, result: SimulationResult, twin: Twin) -> BlastRadius: ...

    def vendor_overlap(self, twin: Twin, vendor_ids: list[str]) -> list[VendorOverlap]: ...

    def mitigate(self, twin: Twin, brief: DecisionBrief, plan: CandidatePlan, actions: list[Intervention], *,
                 settings: OrganizationSettings | None = None, run_id: str = "run_adhoc") -> MitigationComparison: ...

    def missing_questions(self, twin: Twin, brief: DecisionBrief, plan: CandidatePlan, *,
                          settings: OrganizationSettings | None = None,
                          run_id: str = "run_adhoc") -> list[MissingQuestion]: ...

    def load_mitigation_catalog(self, path: Any = None, twin: Twin | None = None) -> list[Intervention]: ...

    def check_result(self, obj: Any, twin: Twin) -> list[ValidationIssue]: ...

    def build_agent_view(self, twin: Twin, *, agent_id: str, department_id: str | None,
                         visible_entity_types: list[EntityType], visible_sensitivity: list[Sensitivity]) -> AgentView: ...

    def reachable_departments(self, twin: Twin, source_entity_ids: list[str], max_hops: int = 4) -> list[str]: ...

    def list_dependencies(
        self,
        twin: Twin,
        entity_id: str,
        direction: Literal["in", "out", "both"],
        max_depth: int,
    ) -> list[Edge]: ...

    def to_role_level(self, obj: Any, twin: Twin) -> Any: ...

    def clone_with_edges(self, twin: Twin, edges: list[Edge]) -> Twin: ...

    def widen_uncertainty(self, twin: Twin, department_ids: list[str], delta: float = 0.1) -> Twin: ...
