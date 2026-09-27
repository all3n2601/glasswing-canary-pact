"""The twin and engine run on any company twin held in memory, not just Northstar (plan B-01; AGENTS.md sections 5, 8).

Two non-Northstar twins are built in memory, with no file reads: a small hand-built logistics
company made from ``contracts_py`` models and passed through ``company_twin.build_twin``, and the
AdventureWorks importer's output on a handful of inline rows. Every engine entry point runs on
both, every output passes ``check_result``, and repeated runs are identical.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from contracts_py.decision import (
    CandidatePlan,
    Constraint,
    DecisionBrief,
    EngineMetric,
    Goal,
    Intervention,
    Operator,
)
from contracts_py.enums import (
    ActionType,
    BusinessModel,
    ChannelKind,
    Criticality,
    DecisionType,
    DocumentStatus,
    DocumentType,
    EntityType,
    EvidenceSource,
    Future,
    InterventionKind,
    PressureKind,
    Relation,
    Sector,
    SizeBand,
    StrengthCategory,
)
from contracts_py.twin import (
    DepartmentBudget,
    DepartmentProfile,
    DepartmentStrength,
    Document,
    Edge,
    Entity,
    Evidence,
    NeutraliserRef,
    Organization,
    Pressure,
    StaffingStrength,
    Twin,
    VersionInfo,
)

from company_twin import TwinValidationError, build_adventureworks_twin, build_twin
from simulation_engine import (
    blast_radius,
    check_result,
    compare_futures,
    optimize,
    quick_impact,
    simulate,
    vendor_overlap,
)
from simulation_engine.futures import scenario_for

CREATED_AT = datetime(2026, 9, 26, tzinfo=timezone.utc)
FUTURES = (Future.inaction, Future.act_now, Future.delay)

# ---- a small hand-built logistics company ----------------------------------------------------

DEPARTMENTS = {  # id -> (name, annual budget, FTE)
    "dept_dispatch": ("Dispatch", 900_000, 6.0),
    "dept_fleet": ("Fleet", 1_400_000, 9.0),
    "dept_accounts": ("Accounts", 600_000, 4.0),
}


def _edge(edge_id: str, source: str, target: str, relation: Relation, *, strength: float = 0.8,
          substitutability: float = 0.3, criticality: Criticality = Criticality.high,
          channel_kind: ChannelKind | None = None) -> Edge:
    return Edge(id=edge_id, source=source, target=target, relation=relation, strength=strength,
                substitutability=substitutability, criticality=criticality, confidence=0.9, lag_days=0,
                evidence_refs=["ev_ops_map"], channel_kind=channel_kind)


def _profile(dept_id: str, head_role_id: str) -> DepartmentProfile:
    _, budget, fte = DEPARTMENTS[dept_id]
    return DepartmentProfile(
        department_id=dept_id, mission=f"Run {DEPARTMENTS[dept_id][0].lower()}.", head_role_id=head_role_id,
        staffing=StaffingStrength(sanctioned_fte=fte, actual_fte=fte, contractors_fte=0, open_positions=0,
                                  attrition_rate_annual=0.1, avg_time_to_hire_days=40, utilisation=0.9),
        budget=DepartmentBudget(annual_budget_usd=budget, spent_ytd_usd=0, fixed_cost_pct=0.5),
        strengths=[DepartmentStrength(id=f"str_{dept_id.removeprefix('dept_')}", name="Core capability",
                                      category=StrengthCategory.capability, level=3, key_role_ids=[head_role_id],
                                      concentration=0.5)],
        maturity_level=3,
    )


def _vendor(vendor_id: str, name: str, annual_cost: int) -> Entity:
    return Entity(id=vendor_id, type=EntityType.vendor, name=name, department_id="dept_dispatch",
                  annual_cost_usd=annual_cost, one_time_exit_cost_usd=10_000, migration_cost_usd=20_000,
                  geographies=["NA"], history_years=5, freshness_days=1, accuracy=0.95,
                  permitted_uses=["routing"])


def _role(role_id: str, name: str, dept_id: str, cost: int) -> Entity:
    return Entity(id=role_id, type=EntityType.role, name=name, department_id=dept_id, annual_cost_usd=cost,
                  capacity_fte=1.0, time_to_train_days=60)


def logistics_twin_data() -> Twin:
    entities = [
        *(Entity(id=did, type=EntityType.department, name=name, annual_cost_usd=budget, capacity_fte=fte)
          for did, (name, budget, fte) in DEPARTMENTS.items()),
        _role("role_dispatch_lead", "Dispatch lead", "dept_dispatch", 110_000),
        _role("role_route_planner", "Route planner", "dept_dispatch", 90_000),
        _role("role_fleet_manager", "Fleet manager", "dept_fleet", 120_000),
        _role("role_billing_clerk", "Billing clerk", "dept_accounts", 70_000),
        _vendor("vendor_routemap", "RouteMap", 300_000),
        _vendor("vendor_waypoint", "Waypoint", 180_000),
        Entity(id="ds_road_network", type=EntityType.dataset, name="Road network", department_id="dept_dispatch",
               criticality=Criticality.critical, attribute_group="road_network"),
        Entity(id="sys_dispatch_console", type=EntityType.system, name="Dispatch console",
               department_id="dept_dispatch", annual_cost_usd=50_000, failure_cost_per_day_usd=8_000),
        Entity(id="wf_route_dispatch", type=EntityType.workflow, name="Route dispatch", department_id="dept_dispatch",
               criticality=Criticality.critical, min_qualified_owners=1, failure_cost_per_day_usd=12_000,
               customer_facing=True),
        Entity(id="wf_freight_billing", type=EntityType.workflow, name="Freight billing",
               department_id="dept_accounts", criticality=Criticality.high, min_qualified_owners=1,
               failure_cost_per_day_usd=3_000),
        Entity(id="kpi_on_time_delivery", type=EntityType.kpi, name="On-time delivery", department_id="dept_fleet",
               criticality=Criticality.high, kpi_baseline=94.0, kpi_unit="percent", higher_is_better=True),
    ]
    edges = [
        _edge("e_routemap_road_network", "vendor_routemap", "ds_road_network", Relation.PROVIDES,
              substitutability=0.7, criticality=Criticality.medium),
        _edge("e_waypoint_road_network", "vendor_waypoint", "ds_road_network", Relation.PROVIDES,
              substitutability=0.7, criticality=Criticality.medium),
        _edge("e_road_network_dispatch", "ds_road_network", "wf_route_dispatch", Relation.CONSUMES),
        _edge("e_dispatch_console", "wf_route_dispatch", "sys_dispatch_console", Relation.DEPENDS_ON),
        _edge("e_lead_owns_dispatch", "role_dispatch_lead", "wf_route_dispatch", Relation.OWNS),
        _edge("e_planner_backs_dispatch", "role_route_planner", "wf_route_dispatch", Relation.BACKS_UP,
              criticality=Criticality.medium),
        _edge("e_clerk_owns_billing", "role_billing_clerk", "wf_freight_billing", Relation.OWNS),
        _edge("e_dispatch_on_time", "wf_route_dispatch", "kpi_on_time_delivery", Relation.CONTRIBUTES_TO),
        _edge("ch_dispatch_fleet", "dept_dispatch", "dept_fleet", Relation.FLOWS_TO,
              criticality=Criticality.medium, channel_kind=ChannelKind.capability),
        _edge("ch_fleet_accounts", "dept_fleet", "dept_accounts", Relation.FLOWS_TO,
              criticality=Criticality.medium, channel_kind=ChannelKind.signal),
    ]
    return Twin(
        version=VersionInfo(twin_version="twin_harbor_freight_v1", settings_version=1, prompt_version="p1",
                            model_id="none", engine_version="e1", created_at=CREATED_AT, as_of_date=date(2026, 9, 26)),
        organization=Organization(
            id="org_harbor_freight", legal_name="Harbor Freight Lines LLC", display_name="Harbor Freight Lines",
            sector=Sector.logistics_transport, business_model=BusinessModel.b2b, size_band=SizeBand.smb,
            headquarters_country="US", annual_revenue_usd=8_000_000,
            total_annual_budget_usd=sum(b for _, b, _ in DEPARTMENTS.values()),
            total_headcount_fte=sum(f for _, _, f in DEPARTMENTS.values()), fiscal_year_start_month=1,
            description="A regional freight carrier.",
        ),
        department_profiles=[_profile("dept_dispatch", "role_dispatch_lead"),
                             _profile("dept_fleet", "role_fleet_manager"),
                             _profile("dept_accounts", "role_billing_clerk")],
        entities=entities,
        edges=edges,
        pressures=[Pressure(id="pr_routemap_renewal", kind=PressureKind.renewal_step, name="RouteMap renewal uplift",
                            target_entity_id="vendor_routemap", start_day=90, step_pct=10.0,
                            neutralised_by=[NeutraliserRef(intervention_type=ActionType.remove_vendor,
                                                           target_entity_id="vendor_routemap")],
                            evidence_refs=["ev_ops_map"], description="RouteMap renews at +10% on day 90.")],
        documents=[Document(id="doc_dispatch_runbook", title="Dispatch runbook", doc_type=DocumentType.runbook,
                            department_id="dept_dispatch", owner_role_id="role_dispatch_lead",
                            uri="memory://doc_dispatch_runbook", mime_type="text/markdown",
                            status=DocumentStatus.current, covers_entity_ids=["wf_route_dispatch"],
                            summary="How routes are dispatched.", uploaded_at=CREATED_AT)],
        evidence=[Evidence(id="ev_ops_map", source_type=EvidenceSource.workflow_map, document_id="doc_dispatch_runbook",
                           snippet="Dispatch consumes the road network from RouteMap or Waypoint.")],
    )


def _remove(action: ActionType, target: str, cost: int = 0) -> Intervention:
    return Intervention(id=f"remove_{target.split('_', 1)[1]}", kind=InterventionKind.action, type=action,
                        target_entity_id=target, start_day=30, one_time_cost_usd=cost, rationale="Under review")


def _constraint(cid: str, metric: EngineMetric, operator: Operator, threshold: float, *, hard: bool = True) -> Constraint:
    return Constraint(id=cid, metric=metric, operator=operator, threshold=threshold, unit="count", hard=hard,
                      description=cid)


VENDOR_BRIEF = DecisionBrief(
    decision_id="dec_harbor_vendors", decision_type=DecisionType.vendor_consolidation,
    title="Consolidate routing data vendors", statement="Save at least $150k a year on routing data.",
    goal=Goal(metric="annual_savings_usd", target=150_000), created_by="test",
    candidate_interventions=[_remove(ActionType.remove_vendor, "vendor_routemap"),
                             _remove(ActionType.remove_vendor, "vendor_waypoint")],
    constraints=[_constraint("c_compliance", "compliance_controls_broken", "==", 0),
                 _constraint("c_coverage", "critical_coverage_pct", ">=", 100),
                 _constraint("c_stranded", "stranded_workflows", "==", 0, hard=False)],
)
RESTRUCTURE_BRIEF = DecisionBrief(
    decision_id="dec_harbor_billing", decision_type=DecisionType.restructure,
    title="Eliminate the billing clerk role", statement="Evaluate removing the billing clerk role.",
    goal=Goal(metric="annual_savings_usd", target=50_000), created_by="test",
    candidate_interventions=[_remove(ActionType.remove_roles, "role_billing_clerk", 10_000)],
    constraints=[_constraint("c_stranded", "stranded_workflows", "==", 0)],
)


@pytest.fixture(scope="module")
def twin() -> Twin:
    return build_twin(logistics_twin_data())


def plan_of(brief: DecisionBrief, *intervention_ids: str) -> CandidatePlan:
    ids = list(intervention_ids) or [i.id for i in brief.candidate_interventions]
    return CandidatePlan(plan_id="plan_under_test", label="Plan under test", intervention_ids=ids, source="user")


def all_futures(twin: Twin, brief: DecisionBrief, plan: CandidatePlan, mode: str):
    return {future: simulate(twin, brief, scenario_for(twin, brief, "run_generic", future, plan),
                             None if future is Future.inaction else plan, mode)
            for future in FUTURES}


def test_build_twin_accepts_the_hand_built_company_and_derives_its_profiles(twin):
    assert twin.organization.id == "org_harbor_freight"
    dispatch = next(p for p in twin.department_profiles if p.department_id == "dept_dispatch")
    assert dispatch.critical_workflow_ids == ["wf_route_dispatch"] and dispatch.documentation_coverage == 1.0
    accounts = next(p for p in twin.department_profiles if p.department_id == "dept_accounts")
    assert accounts.documentation_coverage == 0.0  # freight billing has no current runbook or SOP


def test_quick_impact_prices_a_vendor_removal(twin):
    result = quick_impact(twin, [VENDOR_BRIEF.candidate_interventions[1]], brief=VENDOR_BRIEF)
    assert result.value.gross_savings_usd == 180_000 and result.goal_met and result.feasible
    assert check_result(result, twin) == []


@pytest.mark.parametrize("mode", ["quick", "full"])
def test_every_future_simulates_cleanly_in_both_modes(twin, mode):
    results = all_futures(twin, VENDOR_BRIEF, plan_of(VENDOR_BRIEF, "remove_routemap"), mode)
    for future, result in results.items():
        assert result.future is future and result.mode == mode
        assert check_result(result, twin) == [], future
    inaction = results[Future.inaction]
    assert inaction.intervention_ids == [] and inaction.value.pressure_cost_usd > 0  # the renewal uplift
    assert results[Future.act_now].value.pressure_cost_usd == 0  # removing RouteMap neutralises it
    assert results[Future.act_now].value.net_value_usd > results[Future.delay].value.net_value_usd


def test_compare_futures_ranks_acting_now_against_inaction(twin):
    comparison = compare_futures(twin, VENDOR_BRIEF, plan_of(VENDOR_BRIEF, "remove_routemap"), run_id="run_generic")
    assert sorted(r.future.value for r in comparison.rows) == ["act_now", "delay", "inaction"]
    assert comparison.best_row_index is not None
    assert comparison.rows[comparison.best_row_index].future is Future.act_now
    assert check_result(comparison, twin) == []


def test_optimize_keeps_one_road_network_provider(twin):
    portfolios = optimize(twin, VENDOR_BRIEF, run_id="run_generic")
    assert portfolios.evaluated_count == 4
    assert portfolios.recommended is not None and portfolios.recommended.intervention_ids == ["remove_routemap"]
    both = next(p for p in portfolios.alternatives if len(p.intervention_ids) == 2)
    assert not both.result.feasible and any(r.startswith("c_coverage:") for r in both.result.rejection_reasons)
    assert check_result(portfolios, twin) == []


def test_a_restructure_brief_is_one_naive_plan_that_strands_billing(twin):
    portfolios = optimize(twin, RESTRUCTURE_BRIEF, run_id="run_generic")
    assert portfolios.evaluated_count == 1 and portfolios.naive.plan_id == "plan_naive"
    assert not portfolios.naive.result.feasible and portfolios.recommended is None
    assert check_result(portfolios, twin) == []
    for mode in ("quick", "full"):
        for result in all_futures(twin, RESTRUCTURE_BRIEF, plan_of(RESTRUCTURE_BRIEF), mode).values():
            assert check_result(result, twin) == []


def test_blast_radius_and_vendor_overlap(twin):
    both = quick_impact(twin, VENDOR_BRIEF.candidate_interventions, brief=VENDOR_BRIEF)
    blast = blast_radius(both, twin)
    assert {"wf_route_dispatch", "ds_road_network"} <= {n.node_id for n in blast.nodes}
    assert check_result(blast, twin) == []
    [pair] = vendor_overlap(twin, ["vendor_waypoint", "vendor_routemap"])
    assert (pair.vendor_a, pair.vendor_b) == ("vendor_routemap", "vendor_waypoint")


def test_engine_outputs_are_deterministic(twin):
    again = build_twin(logistics_twin_data())
    plan = plan_of(VENDOR_BRIEF, "remove_routemap")
    assert (compare_futures(twin, VENDOR_BRIEF, plan, run_id="run_generic").model_dump_json()
            == compare_futures(again, VENDOR_BRIEF, plan, run_id="run_generic").model_dump_json())
    assert (optimize(twin, VENDOR_BRIEF).model_dump_json() == optimize(again, VENDOR_BRIEF).model_dump_json())


# ---- the AdventureWorks importer on inline rows ------------------------------------------------
# build_twin rejects this twin on data rules (see company-twin's test_adventureworks_twin: missing
# required vendor/workflow/system/role fields, documents without checksums), so the engine runs on
# the importer's output directly: no pressures, controls, or datasets, and no derived profile fields.


def _row(width: int, **cols: str) -> list[str]:
    cells = [""] * width
    for key, value in cols.items():
        cells[int(key.removeprefix("c"))] = value
    return cells


def aw_tables() -> dict[str, list[list[str]]]:
    departments = [("3", "Sales"), ("4", "Marketing"), ("5", "Purchasing"), ("7", "Production"),
                   ("8", "Production Control"), ("10", "Finance"), ("11", "Information Services"),
                   ("13", "Quality Assurance"), ("15", "Shipping and Receiving")]
    return {
        "Department.csv": [[d, name, "Operations", "2008-04-30"] for d, name in departments],
        "Employee.csv": [_row(15, c0=d, c5=f"{name} Specialist") for d, name in departments],
        "EmployeeDepartmentHistory.csv": [_row(6, c0=d, c1=d, c3="2019-01-01") for d, _ in departments],
        "EmployeePayHistory.csv": [[d, "2020-01-01", "20.00", "1", "2020-01-01"] for d, _ in departments],
        "Vendor.csv": [_row(8, c0="1492", c2="Australia Bike Retailer", c3="1", c4="1", c5="1"),
                       _row(8, c0="1494", c2="Allenson Cycles", c3="2", c4="0", c5="1")],
        "ProductVendor.csv": [_row(11, c0="1", c1="1492"), _row(11, c0="1", c1="1494")],
        "PurchaseOrderHeader.csv": [_row(13, c0="1", c4="1492", c6="2024-04-16"),
                                    _row(13, c0="2", c4="1494", c6="2024-05-01")],
        "PurchaseOrderDetail.csv": [_row(11, c0="1", c4="1", c7="9000.00"), _row(11, c0="2", c4="1", c7="4000.00")],
        "Product.csv": [_row(25, c0="1", c8="400.00", c18="1")],
        "ProductCategory.csv": [["1", "Bikes", "", "2008-04-30"]],
        "ProductSubcategory.csv": [["1", "1", "Mountain Bikes", "", "2008-04-30"]],
        "Location.csv": [["10", "Frame Forming", "22.50", "96.00", "2008-04-30"]],
        "WorkOrder.csv": [_row(10, c0="1", c1="1", c2="100", c3="98", c4="2")],
        "WorkOrderRouting.csv": [_row(12, c0="1", c1="1", c3="10", c8="6.0")],
        "SalesOrderHeader.csv": [_row(26, c0="43659", c2="2024-05-31", c3="2024-06-12", c4="2024-06-07",
                                      c19="2500.00")],
        "SalesOrderDetail.csv": [_row(11, c0="43659", c3="2", c4="1", c8="1600.00")],
    }


def test_the_engine_runs_on_the_adventureworks_twin():
    twin = build_adventureworks_twin(aw_tables(), created_at=CREATED_AT)
    with pytest.raises(TwinValidationError):
        build_twin(twin)
    assert twin.pressures == [] and not any(e.type in {EntityType.control, EntityType.dataset} for e in twin.entities)
    removals = [_remove(ActionType.remove_vendor, v) for v in ("vendor_aw_1492", "vendor_aw_1494")]
    brief = DecisionBrief(decision_id="dec_aw_vendors", decision_type=DecisionType.vendor_consolidation,
                          title="Consolidate bike suppliers", statement="Drop a supplier.",
                          goal=Goal(metric="annual_savings_usd", target=1_000), candidate_interventions=removals,
                          constraints=[_constraint("c_stranded", "stranded_workflows", "==", 0)],
                          created_by="test")
    plan = plan_of(brief, removals[1].id)

    assert check_result(quick_impact(twin, removals[:1], brief=brief), twin) == []
    for mode in ("quick", "full"):
        results = all_futures(twin, brief, plan, mode)
        assert results[Future.inaction].value.net_value_usd == 0
        for result in results.values():
            assert check_result(result, twin) == []
            assert check_result(blast_radius(result, twin), twin) == []
    comparison = compare_futures(twin, brief, plan, run_id="run_aw")
    portfolios = optimize(twin, brief, run_id="run_aw")
    assert check_result(comparison, twin) == [] and check_result(portfolios, twin) == []
    assert portfolios.evaluated_count == 4
    assert len(vendor_overlap(twin, ["vendor_aw_1492", "vendor_aw_1494"])) == 1
    again = build_adventureworks_twin(aw_tables(), created_at=CREATED_AT)
    assert compare_futures(again, brief, plan, run_id="run_aw").model_dump_json() == comparison.model_dump_json()
