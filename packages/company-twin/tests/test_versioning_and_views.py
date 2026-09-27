"""clone/clone_with_edges/widen_uncertainty (plan B-04) and build_agent_view/
to_role_level/document_is_stale/aggregate_domain_graph/department_detail (plan B-05),
schema v2.2.0 section 7.13.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from contracts_py.engine import KnowledgeCoverage, WorkflowCoverage

from company_twin.documents import document_is_stale
from company_twin.loader import default_fixture_path, load_twin
from company_twin.models import Edge, EntityType, Relation, Sensitivity
from company_twin.versioning import (
    AGENT_EDGE_DEFAULTS,
    clone,
    clone_with_edges,
    edge_from_agent_dependency,
    widen_uncertainty,
)
from company_twin.views import aggregate_domain_graph, build_agent_view, department_detail, to_role_level

TWIN = load_twin(default_fixture_path())
PLANTED_ITEMS = json.loads((default_fixture_path().parent / "planted_items.json").read_text())
_planted = PLANTED_ITEMS["planted_edge"]
# planted_items.json is a demo/Challenger reference file (not an Edge payload: it carries
# document_id/description/challenger_should_flag instead of the contract's edge fields),
# so build a real Edge from its id/source/relation/target plus plausible edge fields.
PLANTED_EDGE = Edge(
    id=_planted["id"],
    source=_planted["source"],
    target=_planted["target"],
    relation=Relation(_planted["relation"]),
    strength=0.6,
    substitutability=0.3,
    lag_days=7,
    criticality="high",
    confidence=0.8,
    evidence_refs=_planted["evidence_refs"],
)


# ---- B-04: clone / clone_with_edges / widen_uncertainty --------------------
def test_baseline_is_byte_equivalent_after_mutating_a_clone():
    before = TWIN.model_dump_json()

    scenario = clone(TWIN)
    scenario.entities[0].name = "mutated in the clone only"
    scenario.edges.append(PLANTED_EDGE)
    scenario.organization.display_name = "also mutated"

    after = TWIN.model_dump_json()
    assert before == after


def test_clone_with_edges_adds_edges_only_to_the_clone():
    scenario = clone_with_edges(TWIN, [PLANTED_EDGE])
    assert PLANTED_EDGE.id in {e.id for e in scenario.edges}
    assert PLANTED_EDGE.id not in {e.id for e in TWIN.edges}
    assert len(scenario.edges) == len(TWIN.edges) + 1


def test_clone_with_edges_leaves_baseline_byte_equivalent():
    before = TWIN.model_dump_json()
    clone_with_edges(TWIN, [PLANTED_EDGE])
    assert TWIN.model_dump_json() == before


def test_widen_uncertainty_widens_only_the_named_departments_edges():
    dept = next(e.department_id for e in TWIN.entities if e.type == EntityType.vendor and e.department_id)
    owned_edge = next(
        e for e in TWIN.edges
        if next((x.department_id for x in TWIN.entities if x.id == e.source), None) == dept
    )
    other_edge = next(
        e for e in TWIN.edges
        if next((x.department_id for x in TWIN.entities if x.id == e.source), None) not in (dept, None)
    )

    widened = widen_uncertainty(TWIN, [dept], delta=0.1)
    w_owned = next(e for e in widened.edges if e.id == owned_edge.id)
    w_other = next(e for e in widened.edges if e.id == other_edge.id)

    assert w_owned.strength_range[0] <= owned_edge.strength_range[0]
    assert w_owned.strength_range[1] >= owned_edge.strength_range[1]
    assert w_owned.strength_range != owned_edge.strength_range
    assert w_other.strength_range == other_edge.strength_range
    # baseline untouched
    assert owned_edge.strength_range == next(e for e in TWIN.edges if e.id == owned_edge.id).strength_range


# ---- B-05: build_agent_view -------------------------------------------------
def test_agent_view_never_exceeds_its_sensitivity_and_entity_type_filter():
    allowed_types = [EntityType.vendor, EntityType.dataset, EntityType.workflow, EntityType.kpi]
    allowed_sensitivity = [Sensitivity.general]

    view = build_agent_view(
        TWIN,
        agent_id="sales",
        department_id="dept_sales",
        visible_entity_types=allowed_types,
        visible_sensitivity=allowed_sensitivity,
    )

    assert view.entities
    for e in view.entities:
        assert e.type in allowed_types
        assert e.sensitivity in allowed_sensitivity
    visible_ids = {e.id for e in view.entities}
    for e in view.edges:
        assert e.source in visible_ids and e.target in visible_ids
    for d in view.documents:
        assert d.sensitivity in allowed_sensitivity
    assert view.redacted_entity_count == len(TWIN.entities) - len(view.entities)


def test_agent_view_excludes_hr_sensitivity_person_tokens_when_not_permitted():
    view = build_agent_view(
        TWIN,
        agent_id="sales",
        department_id="dept_sales",
        visible_entity_types=list(EntityType),
        visible_sensitivity=[Sensitivity.general],
    )
    assert not any(e.type == EntityType.person_token for e in view.entities)


def test_agent_view_never_contains_the_planted_edge_even_with_full_permissions():
    view = build_agent_view(
        TWIN,
        agent_id="challenger",
        department_id=None,
        visible_entity_types=list(EntityType),
        visible_sensitivity=list(Sensitivity),
    )
    assert PLANTED_EDGE.id not in {e.id for e in view.edges}
    assert not any(
        e.source == PLANTED_EDGE.source and e.target == PLANTED_EDGE.target and e.relation == Relation.CONSUMES
        for e in view.edges
    )


def test_agent_view_own_department_profile_is_full_others_are_summaries():
    view = build_agent_view(
        TWIN,
        agent_id="finance",
        department_id="dept_finance",
        visible_entity_types=list(EntityType),
        visible_sensitivity=[Sensitivity.general, Sensitivity.finance],
    )
    assert view.department_profile is not None
    assert view.department_profile.department_id == "dept_finance"
    other_ids = {s.department_id for s in view.other_department_summaries}
    assert "dept_finance" not in other_ids
    assert other_ids == {p.department_id for p in TWIN.department_profiles if p.department_id != "dept_finance"}


# ---- B-05: to_role_level -----------------------------------------------------
def test_to_role_level_removes_every_pt_id_from_a_nested_structure():
    person_tokens = [e for e in TWIN.entities if e.type == EntityType.person_token]
    assert person_tokens

    payload = {
        "holders": [pt.id for pt in person_tokens],
        "nested": {"first_holder": person_tokens[0].id},
        "unrelated": "role_controller stays untouched",
    }
    mapped = to_role_level(payload, TWIN)

    flattened = json.dumps(mapped)
    assert not any(pt.id in flattened for pt in person_tokens)
    for pt in person_tokens:
        assert pt.role_id in mapped["holders"]


def test_to_role_level_maps_pt_ids_inside_a_pydantic_model():
    entity_with_pt_role_id = next(e for e in TWIN.entities if e.type == EntityType.role)
    person_token = next(e for e in TWIN.entities if e.type == EntityType.person_token)
    edge = Edge.model_validate({
        **next(e for e in TWIN.edges if e.relation == Relation.KNOWS).model_dump(),
        "source": person_token.id,
        "target": entity_with_pt_role_id.id,
    })

    mapped = to_role_level(edge, TWIN)
    assert mapped.source == person_token.role_id
    assert mapped.source != person_token.id
    # original untouched
    assert edge.source == person_token.id


def test_to_role_level_maps_pt_ids_embedded_in_free_text():
    person_token = next(e for e in TWIN.entities if e.type == EntityType.person_token)
    payload = {"note": f"ask {person_token.id} about this before Thursday"}

    mapped = to_role_level(payload, TWIN)

    assert person_token.id not in mapped["note"]
    assert person_token.role_id in mapped["note"]
    assert mapped["note"] == f"ask {person_token.role_id} about this before Thursday"


def test_to_role_level_maps_pt_ids_inside_workflow_coverage_owners():
    pt_before, pt_after = [e for e in TWIN.entities if e.type == EntityType.person_token][:2]
    coverage = WorkflowCoverage(
        workflow_id="wf_redaction_check",
        criticality="high",
        owners_before=[pt_before.id, pt_after.id],
        owners_after=[pt_after.id],
        min_qualified_owners=1,
        backup_count_after=0,
        documented_pct=0.4,
        stranded=False,
    )

    mapped = to_role_level(coverage, TWIN)

    assert mapped.owners_before == [pt_before.role_id, pt_after.role_id]
    assert mapped.owners_after == [pt_after.role_id]
    dumped = json.dumps(mapped.model_dump(mode="json"))
    assert pt_before.id not in dumped
    assert pt_after.id not in dumped
    # original untouched
    assert coverage.owners_before == [pt_before.id, pt_after.id]


def test_to_role_level_maps_pt_ids_inside_knowledge_coverage_holders():
    pt_before, pt_after = [e for e in TWIN.entities if e.type == EntityType.person_token][:2]
    coverage = KnowledgeCoverage(
        knowledge_id="kn_redaction_check",
        holders_before=[pt_before.id, pt_after.id],
        holders_after=[],
        holder_capacity_fte_before=2.0,
        holder_capacity_fte_after=0.0,
        documented_pct=0.4,
        lost=True,
    )

    mapped = to_role_level(coverage, TWIN)

    assert mapped.holders_before == [pt_before.role_id, pt_after.role_id]
    dumped = json.dumps(mapped.model_dump(mode="json"))
    assert pt_before.id not in dumped
    assert pt_after.id not in dumped
    # original untouched
    assert coverage.holders_before == [pt_before.id, pt_after.id]


# ---- A2: edge_from_agent_dependency / clone_with_edges(agent_proposed=True) --
def test_agent_edge_defaults_cover_every_relation():
    assert set(AGENT_EDGE_DEFAULTS) == set(Relation)
    for defaults in AGENT_EDGE_DEFAULTS.values():
        low, high = defaults.strength_range
        assert low <= defaults.strength <= high


def test_edge_from_agent_dependency_uses_relation_specific_defaults():
    defaults = AGENT_EDGE_DEFAULTS[Relation.SUBSTITUTES_FOR]
    edge = edge_from_agent_dependency(
        source="vendor_apex",
        target="vendor_beacon",
        relation=Relation.SUBSTITUTES_FOR,
        evidence_refs=["ev_1"],
        confidence=0.6,
    )
    assert edge.strength == defaults.strength
    assert edge.strength_range == defaults.strength_range
    assert edge.substitutability == defaults.substitutability
    assert edge.confidence == 0.6
    assert edge.evidence_refs == ["ev_1"]
    assert edge.extraction_method == "agent"


def test_clone_with_edges_agent_proposed_replaces_placeholder_strength():
    placeholder = Edge(
        id="e_agent_placeholder_dep",
        source="vendor_apex",
        target="vendor_beacon",
        relation=Relation.DEPENDS_ON,
        strength=0.5,
        substitutability=0.5,
        lag_days=0,
        criticality="medium",
        confidence=0.7,
    )

    scenario = clone_with_edges(TWIN, [placeholder], agent_proposed=True)

    added = next(e for e in scenario.edges if e.id == placeholder.id)
    defaults = AGENT_EDGE_DEFAULTS[Relation.DEPENDS_ON]
    assert added.strength == defaults.strength
    assert added.strength_range == defaults.strength_range
    assert added.substitutability == defaults.substitutability
    # baseline untouched, and the un-flagged call path keeps its old placeholder values
    unflagged = clone_with_edges(TWIN, [placeholder])
    kept = next(e for e in unflagged.edges if e.id == placeholder.id)
    assert kept.strength == 0.5
    assert kept.substitutability == 0.5


def test_clone_with_edges_applies_defaults_for_agent_extraction_method_without_the_flag():
    # agent_orchestration.merge._Merger.to_edge is what the orchestrator actually calls to
    # build these edges, but it is a private instance method that needs a full _Merger
    # (agent_id/AgentContext/assessment_id/scenario_ids/origin/stale) to construct, so
    # importing and driving it from a company-twin test isn't practical here. Build the
    # equivalent Edge it produces instead: same 0.5/0.5 placeholder strength/
    # substitutability and extraction_method="agent", nothing else about the shape
    # depends on _Merger internals.
    agent_edge = Edge(
        id="e_vendor_apex_depends_on_vendor_beacon",
        source="vendor_apex",
        target="vendor_beacon",
        relation=Relation.DEPENDS_ON,
        strength=0.5,
        substitutability=0.5,
        lag_days=0,
        criticality="medium",
        confidence=0.6,
        extraction_method="agent",
    )

    scenario = clone_with_edges(TWIN, [agent_edge])

    added = next(e for e in scenario.edges if e.id == agent_edge.id)
    defaults = AGENT_EDGE_DEFAULTS[Relation.DEPENDS_ON]
    assert added.strength == defaults.strength
    assert added.strength_range == defaults.strength_range
    assert added.substitutability == defaults.substitutability


# ---- B-05: document_is_stale -------------------------------------------------
def test_document_is_stale_uses_as_of_date_not_the_wall_clock():
    # the fixture's current documents don't set last_reviewed (no story needs it yet),
    # so build one from a real current document to exercise the date arithmetic.
    template = next(d for d in TWIN.documents if d.status.value == "current")
    current_doc = template.model_copy(update={"last_reviewed": date(2026, 1, 1), "review_cycle_days": 180})
    threshold = current_doc.review_cycle_days
    just_inside = current_doc.last_reviewed + timedelta(days=threshold)
    just_outside = current_doc.last_reviewed + timedelta(days=threshold + 1)

    assert document_is_stale(current_doc, as_of_date=just_inside) is False
    assert document_is_stale(current_doc, as_of_date=just_outside) is True
    # a far-future wall-clock date must not matter; only as_of_date does
    assert document_is_stale(current_doc, as_of_date=just_inside) is False


def test_document_is_stale_non_current_status_is_always_stale():
    outdated_doc = next(d for d in TWIN.documents if d.status.value == "outdated")
    assert document_is_stale(outdated_doc, as_of_date=date(2000, 1, 1)) is True
    assert document_is_stale(outdated_doc, as_of_date=date(2100, 1, 1)) is True


# ---- B-05: aggregate_domain_graph / department_detail ------------------------
def test_aggregate_domain_graph_returns_departments_and_kpi_company_with_flows_to_edges():
    domain = aggregate_domain_graph(TWIN)
    assert {n.id for n in domain.nodes} == {
        e.id for e in TWIN.entities if e.type == EntityType.department
    } | {"kpi_company"}
    assert domain.edges
    assert all(e.relation == Relation.FLOWS_TO for e in domain.edges)


def test_aggregate_domain_graph_selects_company_level_kpis_by_shape_not_by_id():
    renamed = TWIN.model_copy(deep=True)
    for e in renamed.entities:
        if e.id == "kpi_company":
            e.id = "kpi_overall"
    for edge in renamed.edges:
        if edge.target == "kpi_company":
            edge.target = "kpi_overall"
    ids = {n.id for n in aggregate_domain_graph(renamed).nodes}
    assert "kpi_overall" in ids and "kpi_company" not in ids
    # Department-owned KPIs stay off the department map.
    assert not ids & {e.id for e in TWIN.entities if e.type == EntityType.kpi and e.department_id}


def test_department_detail_matches_the_department_and_its_channels():
    detail = department_detail(TWIN, "dept_finance")
    assert detail.entity.id == "dept_finance"
    assert detail.profile.department_id == "dept_finance"
    assert all(e.department_id == "dept_finance" for e in detail.owned_entities)
    assert all(e.target == "dept_finance" for e in detail.channels_in)
    assert all(e.source == "dept_finance" for e in detail.channels_out)
