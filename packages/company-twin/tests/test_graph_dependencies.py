"""list_dependencies (plan B-02; schema v2.2.0 section 7.13)."""

from __future__ import annotations

import pytest

from company_twin.graph import list_dependencies
from company_twin.loader import load_company_twin

TWIN = load_company_twin()


def test_out_direction_returns_only_forward_reachable_edges():
    edges = list_dependencies(TWIN, "vendor_apex", "out", max_depth=1)
    assert edges
    assert all(e.source == "vendor_apex" for e in edges)


def test_in_direction_returns_only_backward_reachable_edges():
    edges = list_dependencies(TWIN, "kpi_gross_margin", "in", max_depth=1)
    assert edges
    assert all(e.target == "kpi_gross_margin" for e in edges)


def test_both_direction_is_the_union_of_in_and_out():
    out_edges = {e.id for e in list_dependencies(TWIN, "wf_billing_recon", "out", max_depth=1)}
    in_edges = {e.id for e in list_dependencies(TWIN, "wf_billing_recon", "in", max_depth=1)}
    both_edges = {e.id for e in list_dependencies(TWIN, "wf_billing_recon", "both", max_depth=1)}
    assert out_edges <= both_edges
    assert in_edges <= both_edges


def test_max_depth_widens_the_result():
    shallow = list_dependencies(TWIN, "vendor_apex", "out", max_depth=1)
    deeper = list_dependencies(TWIN, "vendor_apex", "out", max_depth=3)
    assert len(deeper) >= len(shallow)


def test_unknown_entity_raises_key_error():
    with pytest.raises(KeyError):
        list_dependencies(TWIN, "does_not_exist", "out")
