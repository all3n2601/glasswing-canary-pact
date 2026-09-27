"""Multi-dimensional vendor overlap (plan C-02, section 4.1; story V-8)."""

from __future__ import annotations

import pytest
from contracts_py.enums import EntityType, OverlapDimension

from company_twin import load_twin
from company_twin.loader import default_fixture_path
from simulation_engine import OVERLAP_WEIGHTS, unique_contribution, vendor_overlap

TWIN = load_twin(default_fixture_path())
VENDORS = sorted(e.id for e in TWIN.entities if e.type is EntityType.vendor)


def test_v8_21_pairs_each_with_all_11_dimensions_in_range():
    pairs = vendor_overlap(TWIN, VENDORS)
    assert len(VENDORS) == 7 and len(pairs) == 21
    assert len({(p.vendor_a, p.vendor_b) for p in pairs}) == 21
    for p in pairs:
        assert p.vendor_a < p.vendor_b
        assert set(p.dimensions) == set(OverlapDimension) and len(p.dimensions) == 11
        assert all(0 <= v <= 1 for v in p.dimensions.values())
        assert 0 <= p.overall_overlap <= 1


def test_v8_echo_unique_datasets_are_exactly_account_intel():
    for p in vendor_overlap(TWIN, VENDORS):
        if p.vendor_a == "vendor_echo":
            assert p.unique_dataset_ids_a == ["ds_account_intel"]
        if p.vendor_b == "vendor_echo":
            assert p.unique_dataset_ids_b == ["ds_account_intel"]


def test_granite_unique_datasets_are_exactly_the_emerging_market_slice():
    for p in vendor_overlap(TWIN, VENDORS):
        if "vendor_granite" in (p.vendor_a, p.vendor_b):
            unique = p.unique_dataset_ids_b if p.vendor_b == "vendor_granite" else p.unique_dataset_ids_a
            assert unique == ["ds_geo_risk_emerging"]
        if {p.vendor_a, p.vendor_b} == {"vendor_delta", "vendor_granite"}:
            assert p.shared_dataset_ids == ["ds_geo_risk"] and p.unique_dataset_ids_a == ["ds_identity_verification"]


def test_v8_apex_has_the_highest_unique_contribution():
    contributions = {v: unique_contribution(TWIN, v) for v in VENDORS}
    assert max(contributions, key=contributions.get) == "vendor_apex"


def test_shared_datasets_and_weights():
    pair = next(p for p in vendor_overlap(TWIN, VENDORS) if (p.vendor_a, p.vendor_b) == ("vendor_apex", "vendor_beacon"))
    assert pair.shared_dataset_ids == ["ds_contact_data", "ds_firmographics"]
    assert pair.dimensions[OverlapDimension.record_coverage] > 0
    assert set(OVERLAP_WEIGHTS) == set(OverlapDimension)
    assert sum(OVERLAP_WEIGHTS.values()) == pytest.approx(1)


def test_overlap_is_deterministic_and_order_independent():
    first = [p.model_dump_json() for p in vendor_overlap(TWIN, VENDORS)]
    second = [p.model_dump_json() for p in vendor_overlap(TWIN, list(reversed(VENDORS)))]
    assert first == second


def test_non_vendor_ids_are_rejected():
    with pytest.raises(ValueError):
        vendor_overlap(TWIN, ["vendor_apex", "ds_usage"])
