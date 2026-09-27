from datetime import date

import pytest
from pydantic import ValidationError

from contracts_py.common import SCHEMA_VERSION
from contracts_py.decision import ENGINE_METRICS, Constraint, DecisionBrief
from contracts_py.engine import KnowledgeCoverage, SimulationResult, ValueBreakdown, VendorOverlap, WorkflowCoverage
from contracts_py.enums import MigrationDifficulty, OverlapDimension
from contracts_py.events import RunState
from contracts_py.package import DecisionPackage
from contracts_py.twin import ALWAYS_ENABLED_AGENTS, CORE_AGENT_IDS, Edge, Entity, OrganizationSettings, VersionInfo

from test_contracts_rules import NOW, breakdown, package_data


def overlap() -> VendorOverlap:
    return VendorOverlap(
        vendor_a="vendor_apex",
        vendor_b="vendor_beacon",
        dimensions={dimension: 0.5 for dimension in OverlapDimension},
        overall_overlap=0.62,
        shared_dataset_ids=["ds_firmographics"],
        unique_dataset_ids_a=["ds_intent"],
        unique_dataset_ids_b=[],
        migration_difficulty=MigrationDifficulty.medium,
    )


def edge(**fields: object) -> dict:
    return {
        "id": "e_apex_feeds_scoring",
        "source": "vendor_apex",
        "target": "wf_lead_scoring",
        "relation": "PROVIDES",
        "strength": 0.6,
        "substitutability": 0.3,
        "lag_days": 0,
        "criticality": "medium",
        "confidence": 0.8,
    } | fields


def test_cr1_critical_coverage_metric() -> None:
    assert "critical_coverage_pct" in ENGINE_METRICS
    Constraint(id="c_cov", metric="critical_coverage_pct", operator=">=", threshold=100, unit="pct", hard=True,
               description="Critical coverage stays whole.")


def test_cr2_vendor_overlap_with_all_dimensions() -> None:
    assert len(OverlapDimension) == 11
    again = VendorOverlap.model_validate(overlap().model_dump(mode="json"))
    assert set(again.dimensions) == set(OverlapDimension)
    with pytest.raises(ValidationError):
        VendorOverlap.model_validate(overlap().model_dump(mode="json") | {"dimensions": {"vibes": 0.5}})
    with pytest.raises(ValidationError):
        VendorOverlap.model_validate(overlap().model_dump(mode="json") | {"overall_overlap": 1.2})
    with pytest.raises(ValidationError):
        VendorOverlap.model_validate(overlap().model_dump(mode="json") | {"migration_difficulty": "extreme"})


def test_cr3_cr4_cr9_entity_optional_fields() -> None:
    base = {"id": "vendor_apex", "type": "vendor", "name": "Apex Data", "department_id": "dept_ai_data"}
    plain = Entity.model_validate(base)
    assert plain.geographies == [] and plain.aliases == [] and plain.accuracy is None
    full = Entity.model_validate(base | {
        "geographies": ["US", "EU"],
        "history_years": 7,
        "freshness_days": 1,
        "accuracy": 0.97,
        "permitted_uses": ["scoring"],
        "retains_history_after_termination": False,
        "attribute_group": "firmographics",
        "time_to_train_days": 30,
        "replacement_cost_usd": 250_000,
        "exception_documented_pct": 0.4,
        "automation_pct": 0.6,
        "max_downtime_days": 2,
        "aliases": ["Apex"],
    })
    assert full.aliases == ["Apex"]
    with pytest.raises(ValidationError):
        Entity.model_validate(base | {"accuracy": 1.5})


def test_cr5_knowledge_coverage_on_simulation_result() -> None:
    result = package_data_result()
    result["knowledge_coverage"] = [
        KnowledgeCoverage(
            knowledge_id="kn_billing_recon",
            holders_before=["role_wk_01", "role_wk_02"],
            holders_after=[],
            holder_capacity_fte_before=2.0,
            holder_capacity_fte_after=0.0,
            documented_pct=0.2,
            lost=True,
            dependent_workflow_ids=["wf_billing_recon"],
            reasons=["Both holders are removed."],
        ).model_dump()
    ]
    parsed = SimulationResult.model_validate(result)
    assert parsed.knowledge_coverage[0].lost
    assert SimulationResult.model_validate(package_data_result()).knowledge_coverage == []


def package_data_result() -> dict:
    return {
        "result_id": "res_1",
        "run_id": "run_1",
        "scenario_id": "scn_run_1_inaction_none",
        "future": "inaction",
        "mode": "quick",
        "value": {
            "gross_savings_usd": 0,
            "transition_cost_usd": 0,
            "added_cost_usd": 0,
            "rebound_cost_usd": 0,
            "expected_business_loss_usd": 0,
            "pressure_cost_usd": 0,
            "avoided_failure_cost_usd": 0,
            "net_value_usd": 0,
        },
        "goal_met": False,
        "risk": {
            "score": 0,
            "level": "low",
            "settings_version": 1,
            "components": {
                "financial": 0,
                "capability_workflow": 0,
                "customer_revenue": 0,
                "compliance_control": 0,
                "execution_uncertainty": 0,
            },
        },
        "feasible": True,
        "computed_at": NOW,
    }


def test_cr6_workflow_coverage_optional_fields_keep_stranded_rule() -> None:
    base = {
        "workflow_id": "wf_billing_recon",
        "criticality": "critical",
        "owners_after": [],
        "min_qualified_owners": 1,
        "backup_count_after": 0,
        "documented_pct": 0.2,
        "stranded": True,
        "owner_capacity_fte_before": 2.0,
        "owner_capacity_fte_after": 0.0,
        "exception_documented_pct": 0.3,
        "automation_pct": 0.1,
        "training_days_required": 45,
        "replacement_cost_usd": 180_000,
    }
    assert WorkflowCoverage.model_validate(base).training_days_required == 45
    with pytest.raises(ValidationError):
        WorkflowCoverage.model_validate(base | {"documented_pct": 20})
    with pytest.raises(ValidationError, match="stranded"):
        WorkflowCoverage.model_validate(base | {"stranded": False})


def test_cr7_package_with_vendor_overlaps(brief: DecisionBrief) -> None:
    data = package_data(brief)
    assert DecisionPackage.model_validate(data).vendor_overlaps == []
    package = DecisionPackage.model_validate(data | {"vendor_overlaps": [overlap().model_dump(mode="json")]})
    assert package.vendor_overlaps[0].vendor_b == "vendor_beacon"


def test_cr8_version_info_optional_fields() -> None:
    base = {
        "twin_version": "t1",
        "settings_version": 1,
        "prompt_version": "p1",
        "model_id": "mock",
        "engine_version": "e1",
        "created_at": NOW,
        "as_of_date": "2026-09-26",
    }
    assert VersionInfo.model_validate(base).data_snapshot_id is None
    full = VersionInfo.model_validate(base | {
        "data_snapshot_id": "snap_1",
        "policy_version": "pol_1",
        "coefficient_version": "coef_1",
        "created_by": "engine",
    })
    assert full.coefficient_version == "coef_1"


def test_cr9_edge_extraction_method_and_last_validated() -> None:
    parsed = Edge.model_validate(edge(extraction_method="zero_shot", last_validated="2026-09-01"))
    assert parsed.last_validated == date(2026, 9, 1)
    assert Edge.model_validate(edge()).extraction_method is None
    assert Edge.model_validate(edge(extraction_method="agent")).extraction_method == "agent"
    with pytest.raises(ValidationError):
        Edge.model_validate(edge(extraction_method="guess"))


def test_cr10_people_knowledge_in_roster() -> None:
    assert "people_knowledge" in CORE_AGENT_IDS
    assert set(ALWAYS_ENABLED_AGENTS) <= set(CORE_AGENT_IDS)
    assert "people_knowledge" in OrganizationSettings().enabled_agent_ids


@pytest.mark.parametrize("version", ["2.1.0", "2.1.1"])
def test_cr11_both_schema_versions_accepted(brief: DecisionBrief, version: str) -> None:
    assert DecisionBrief.model_validate(brief.model_dump() | {"schema_version": version}).schema_version == version
    state = {"run_id": "run_1", "decision_id": brief.decision_id, "baseline_twin_version": "t1", "status": "created",
             "created_at": NOW, "updated_at": NOW, "schema_version": version}
    assert RunState.model_validate(state).schema_version == version


def test_cr11_default_and_rejected_versions(brief: DecisionBrief) -> None:
    assert SCHEMA_VERSION == "2.1.1"
    assert brief.schema_version == "2.1.1"
    with pytest.raises(ValidationError):
        DecisionBrief.model_validate(brief.model_dump() | {"schema_version": "2.0.0"})


def test_fraction_fields_share_the_ratio_scale() -> None:
    knowledge = Entity.model_validate(
        {"id": "kn_billing_recon", "type": "knowledge_asset", "name": "Billing recon know-how",
         "department_id": "dept_operations", "documented_pct": 0.35}
    )
    coverage = KnowledgeCoverage(
        knowledge_id=knowledge.id,
        holders_before=["role_billing_ops_lead"],
        holder_capacity_fte_before=1.0,
        holder_capacity_fte_after=1.0,
        documented_pct=knowledge.documented_pct,  # type: ignore[arg-type]
        lost=False,
    )
    assert KnowledgeCoverage.model_validate(coverage.model_dump()).documented_pct == 0.35
    base = {"id": "proj_x", "type": "project", "name": "X", "department_id": "dept_engineering"}
    for field in ("documented_pct", "completion_pct"):
        assert getattr(Entity.model_validate(base | {field: 1.0}), field) == 1.0
        with pytest.raises(ValidationError):
            Entity.model_validate(base | {field: 35})


def test_vendor_overlap_rejects_same_vendor() -> None:
    with pytest.raises(ValidationError, match="must differ"):
        VendorOverlap.model_validate(overlap().model_dump(mode="json") | {"vendor_b": "vendor_apex"})


def test_knowledge_coverage_rejects_negative_capacity() -> None:
    base = {"knowledge_id": "kn_x", "holder_capacity_fte_before": 1.0, "holder_capacity_fte_after": 0.0,
            "documented_pct": 0.5, "lost": True}
    KnowledgeCoverage.model_validate(base)
    for field in ("holder_capacity_fte_before", "holder_capacity_fte_after"):
        with pytest.raises(ValidationError):
            KnowledgeCoverage.model_validate(base | {field: -0.5})


def test_value_breakdown_optional_cost_split() -> None:
    plain = ValueBreakdown.model_validate(breakdown())
    assert (plain.termination_cost_usd, plain.migration_cost_usd, plain.displaced_work_cost_usd) == (None, None, None)
    split = ValueBreakdown.model_validate(breakdown(termination_cost_usd=50_000, migration_cost_usd=120_000,
                                                   displaced_work_cost_usd=0))
    assert split.net_value_usd == plain.net_value_usd and split.migration_cost_usd == 120_000
    for bad in ({"termination_cost_usd": -1}, {"migration_cost_usd": 120_000.5}):
        with pytest.raises(ValidationError):
            ValueBreakdown.model_validate(breakdown(**bad))
    with pytest.raises(ValidationError, match="does not equal components"):
        ValueBreakdown.model_validate(breakdown(net_value_usd=1, monthly_net_usd=[1], migration_cost_usd=10))
