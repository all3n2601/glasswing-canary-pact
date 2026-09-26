"""Tests for the vendor-overlap data (Person 1 output for the vendor-consolidation demo)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("vendor_overlap", _ROOT / "data" / "vendor_overlap.py")
vendor_overlap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vendor_overlap)

DATA = vendor_overlap.compute()


def test_seven_vendors_total_eight_billion():
    assert len(DATA["vendors"]) == 7
    assert DATA["total_annual_spend_usd"] == 8_000_000_000


def test_delta_is_the_only_compliance_critical_vendor():
    critical = [v["id"] for v in DATA["vendors"] if v["critical"]]
    assert critical == ["vendor_delta"]


def test_beacon_is_the_only_fully_dominated_vendor():
    # a clean, safe cut = its fields are a strict subset of another vendor's
    dominated = {v["id"]: v["dominated_by"] for v in DATA["vendors"] if v["dominated_by"]}
    assert dominated == {"vendor_beacon": ["vendor_apex"]}


def test_beacon_is_fully_redundant_and_echo_has_unique_fields():
    beacon = next(v for v in DATA["vendors"] if v["id"] == "vendor_beacon")
    echo = next(v for v in DATA["vendors"] if v["id"] == "vendor_echo")
    assert beacon["unique_field_count"] == 0            # everything Beacon has, Apex has
    assert echo["unique_field_count"] >= 1              # Echo carries unique market intel


def test_recommended_plan_meets_target_and_preserves_compliance():
    rec = DATA["expected_recommended_plan"]
    assert set(rec["removed"]) == {"vendor_beacon", "vendor_echo"}
    assert rec["gross_savings_usd"] == 2_300_000_000
    assert rec["meets_target"] is True
    assert rec["breaks_compliance"] is False
    # feasible once Echo's unique fields are migrated first (the plan's migration step)
    assert rec["fields_to_migrate"]
    assert rec["feasible_after_migration"] is True


def test_naive_plan_loses_unique_coverage():
    naive = DATA["naive_plan"]
    assert naive["lost_fields"]                          # cutting the priciest drops unique data
    assert naive["required_field_coverage_pct"] < 100.0
