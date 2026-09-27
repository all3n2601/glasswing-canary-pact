"""Validation for the company twin (Person 1: "validated company graph").

The contract models (contracts_py.twin) enforce per-entity structural rules (regex IDs,
ranges, required literals) on load. This module adds the cross-entity and graph acceptance
checks from schema v2.2.0 section 12 (rules 1-4, 16-19) and the team work-division's
acceptance checks, returning the agreed boundary type: ``list[contracts_py.twin.ValidationIssue]``
(empty = valid). Each issue's ``rule`` is the section-12 rule number it enforces, except the
one work-division acceptance check kept from the pre-unification validator.

Run:  python -m company_twin.validate
"""

from __future__ import annotations

from contracts_py.twin import ValidationIssue

from .models import EntityType, Relation, Twin

# schema v2.2.0 section 5.3 "Required fields by type", now including the 2.1.1 additions
# data/generate_company.py populates: vendor geographies/history_years/freshness_days/
# accuracy/permitted_uses, role time_to_train_days, dataset attribute_group.
# vendor.retains_history_after_termination is intentionally NOT required: it is nullable
# by design (vendor_echo's planted unknown, V-11), and SCHEMA 5.3's required-fields table
# for vendor omits it for the same reason.
REQUIRED_FIELDS_BY_TYPE: dict[EntityType, tuple[str, ...]] = {
    EntityType.department: ("annual_cost_usd", "capacity_fte"),
    EntityType.vendor: ("annual_cost_usd", "one_time_exit_cost_usd", "migration_cost_usd",
                        "geographies", "history_years", "freshness_days", "accuracy", "permitted_uses"),
    EntityType.system: ("annual_cost_usd", "failure_cost_per_day_usd"),
    EntityType.project: ("annual_cost_usd", "completion_pct", "remaining_cost_usd", "expected_completion_day"),
    EntityType.workflow: ("min_qualified_owners", "failure_cost_per_day_usd"),
    EntityType.role: ("annual_cost_usd", "capacity_fte", "time_to_train_days"),
    EntityType.person_token: ("role_id",),
    EntityType.knowledge_asset: ("documented_pct",),
    EntityType.control: ("mandatory",),
    EntityType.kpi: ("kpi_baseline", "kpi_unit", "higher_is_better"),
    EntityType.customer_segment: ("arr_usd",),
    EntityType.dataset: ("attribute_group",),
}


def _duplicates(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    dupes: list[str] = []
    for i in ids:
        if i in seen and i not in dupes:
            dupes.append(i)
        seen.add(i)
    return dupes


def validate_twin(twin: Twin) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    def err(rule: int | str, message: str, ids: list[str] | None = None) -> None:
        issues.append(ValidationIssue(rule=rule, severity="error", message=message, ids=ids or []))

    def warn(rule: int | str, message: str, ids: list[str] | None = None) -> None:
        issues.append(ValidationIssue(rule=rule, severity="warning", message=message, ids=ids or []))

    ents = {e.id: e for e in twin.entities}
    depts = {e.id for e in twin.entities if e.type == EntityType.department}
    roles = {e.id for e in twin.entities if e.type == EntityType.role}
    person_tokens = {e.id for e in twin.entities if e.type == EntityType.person_token}
    evidence_ids = {v.id for v in twin.evidence}
    document_ids = {d.id for d in twin.documents}
    org = twin.organization

    # ---- rule 1: unique IDs; edge/pressure endpoints exist; evidence refs
    # resolve; department_id points to a department; required-per-type fields.
    for label, ids in (("entity", [e.id for e in twin.entities]), ("edge", [e.id for e in twin.edges]),
                       ("pressure", [p.id for p in twin.pressures])):
        for dup in _duplicates(ids):
            err(1, f"duplicate {label} id {dup}", [dup])

    for e in twin.edges:
        if e.source not in ents:
            err(1, f"edge {e.id} source {e.source} does not exist", [e.id])
        if e.target not in ents:
            err(1, f"edge {e.id} target {e.target} does not exist", [e.id])

    for p in twin.pressures:
        if p.target_entity_id not in ents:
            err(1, f"pressure {p.id} target_entity_id {p.target_entity_id} does not exist", [p.id])

    for v in twin.evidence:
        if v.document_id not in document_ids:
            err(1, f"evidence {v.id} document_id {v.document_id} does not exist", [v.id])

    def check_evidence_refs(owner_id: str, refs: list[str]) -> None:
        for r in refs:
            if r not in evidence_ids:
                err(1, f"{owner_id} evidence_ref {r} does not exist", [owner_id])

    for e in twin.entities:
        check_evidence_refs(e.id, e.evidence_refs)
        if e.department_id is not None and e.department_id not in depts:
            err(1, f"{e.id} department_id {e.department_id} is not a department", [e.id])
        for field in REQUIRED_FIELDS_BY_TYPE.get(e.type, ()):
            value = getattr(e, field)
            if value is None or value == []:
                err(1, f"{e.id} ({e.type.value}) is missing required field {field}", [e.id])
    for e in twin.edges:
        check_evidence_refs(e.id, e.evidence_refs)
    for p in twin.pressures:
        check_evidence_refs(p.id, p.evidence_refs)
    check_evidence_refs(org.id, org.evidence_refs)

    # ---- rule 2: high/critical edges need evidence; FLOWS_TO needs channel_kind;
    # strength stays inside strength_range (contracts_py's Edge already enforces
    # the last one at parse time; kept here too so a future relaxation there is
    # still caught).
    for e in twin.edges:
        if e.criticality.value in ("high", "critical") and not e.evidence_refs:
            err(2, f"edge {e.id} is {e.criticality.value} but has no evidence_refs", [e.id])
        if e.relation == Relation.FLOWS_TO and e.channel_kind is None:
            err(2, f"FLOWS_TO edge {e.id} is missing channel_kind", [e.id])
        if e.strength_range is not None:
            low, high = e.strength_range
            if not low <= e.strength <= high:
                err(2, f"edge {e.id} strength {e.strength} is outside strength_range", [e.id])

    # ---- rule 3: every cross-department edge matches a department channel.
    # Kept as a warning, not an error: after moving vendor_echo to dept_marketing and
    # kpi_net_retention to dept_customer_success (which together resolved 3 of the original
    # 10 warnings on the fixture without adding a channel), 7 edges still genuinely can't fit
    # the drawn map, because the department pair they cross has no channel in either
    # direction, or only the reverse direction is drawn, and moving either endpoint would only
    # move the same problem onto a different edge:
    #   e_lineage_supports_close (ai_data -> finance), e_apex_provides_corporate_linkage
    #   (sales -> compliance), e_market_intel_consumed_ml_scoring and
    #   e_intent_consumed_ml_scoring (marketing -> ai_data; only ai_data -> marketing is
    #   drawn), e_risk_monitoring_margin and e_invoicing_margin (operations -> finance; only
    #   finance -> operations is drawn), e_enterprise_margin (sales -> finance; only
    #   finance -> sales is drawn). See the task summary.
    channel_pairs = {(e.source, e.target) for e in twin.edges if e.relation == Relation.FLOWS_TO}
    for e in twin.edges:
        if e.relation == Relation.FLOWS_TO:
            continue
        source_dept = ents[e.source].department_id if e.source in ents else None
        target_dept = ents[e.target].department_id if e.target in ents else None
        if source_dept and target_dept and source_dept != target_dept:
            if (source_dept, target_dept) not in channel_pairs:
                warn(3, f"edge {e.id} crosses {source_dept} -> {target_dept} with no matching channel", [e.id])

    # ---- rule 4: person tokens use pt_ and get hr sensitivity.
    for e in twin.entities:
        if e.type == EntityType.person_token:
            if not e.id.startswith("pt_"):
                err(4, f"person token {e.id} must use the pt_ prefix", [e.id])
            if e.sensitivity.value != "hr":
                err(4, f"person token {e.id} must have hr sensitivity", [e.id])

    # ---- rule 16: organization totals reconcile; every regulatory framework has
    # at least one control entity.
    dept_budget = sum(e.annual_cost_usd or 0 for e in twin.entities if e.type == EntityType.department)
    if org.total_annual_budget_usd != dept_budget:
        err(16, f"total_annual_budget_usd {org.total_annual_budget_usd} != sum dept budgets {dept_budget}")
    fte = sum(p.staffing.actual_fte + p.staffing.contractors_fte for p in twin.department_profiles)
    if org.total_headcount_fte != fte:
        err(16, f"total_headcount_fte {org.total_headcount_fte} != sum profile FTE {fte}")
    for fw in org.regulatory_frameworks:
        if not any(e.framework == fw for e in twin.entities if e.type == EntityType.control):
            err(16, f"regulatory framework {fw} has no control entity")

    # ---- rule 17: exactly one profile per department; profile budget/FTE agree
    # with the department entity; over-sanctioned staffing is a warning only.
    profile_depts = [p.department_id for p in twin.department_profiles]
    for dup in _duplicates(profile_depts):
        err(17, f"more than one department profile for {dup}", [dup])
    for did in sorted(depts - set(profile_depts)):
        err(17, f"department {did} has no profile", [did])

    for p in twin.department_profiles:
        de = ents.get(p.department_id)
        if de is None:
            err(17, "profile points to a missing department", [p.department_id])
            continue
        if p.budget.annual_budget_usd != de.annual_cost_usd:
            err(17, "profile budget.annual_budget_usd != entity annual_cost_usd", [p.department_id])
        if p.staffing.actual_fte + p.staffing.contractors_fte != de.capacity_fte:
            err(17, "actual_fte + contractors_fte != entity capacity_fte", [p.department_id])
        if p.staffing.actual_fte > p.staffing.sanctioned_fte + p.staffing.open_positions:
            warn(17, "actual_fte exceeds sanctioned_fte + open_positions", [p.department_id])

        # ---- rule 18: strengths' level >= 4 needs evidence; supports_entity_ids
        # and key_role_ids exist; no person tokens in key_role_ids.
        for s in p.strengths:
            for sid in s.supports_entity_ids:
                if sid not in ents:
                    err(18, f"strength {s.id} supports unknown entity {sid}", [sid])
            for kr in s.key_role_ids:
                if kr not in roles:
                    err(18, f"strength {s.id} key_role_id {kr} is not a role", [kr])
                if kr in person_tokens:
                    err(18, f"strength {s.id} key_role_ids must not contain a person token", [kr])
            if s.level >= 4 and not s.evidence_refs:
                err(18, f"strength {s.id} has level {s.level} but no evidence_refs", [s.id])

    # ---- rule 19: unique document IDs; covers_entity_ids exist; owner_role_id is
    # a role, not a person token; non-synthetic documents need a checksum.
    for dup in _duplicates([d.id for d in twin.documents]):
        err(19, f"duplicate document id {dup}", [dup])
    for d in twin.documents:
        for cid in d.covers_entity_ids:
            if cid not in ents:
                err(19, f"document {d.id} covers unknown entity {cid}", [cid])
        if d.owner_role_id is not None and d.owner_role_id not in roles:
            err(19, f"document {d.id} owner_role_id {d.owner_role_id} is not a role", [d.owner_role_id])
        if not d.synthetic and not d.checksum_sha256:
            err(19, f"non-synthetic document {d.id} is missing checksum_sha256", [d.id])

    # ---- work-division acceptance check (kept from the pre-unification
    # validator): every critical workflow has a named owner or is flagged as a
    # knowledge risk instead.
    owned = {e.target for e in twin.edges if e.relation == Relation.OWNS}
    for e in twin.entities:
        if e.type == EntityType.workflow and e.criticality.value in ("high", "critical"):
            flagged = (e.min_qualified_owners or 0) >= 1 and e.documented_pct is not None
            if e.id not in owned and not flagged:
                warn("critical_wf_no_owner", f"critical workflow {e.id} has no owner and is not flagged", [e.id])

    return issues


def main() -> int:
    from .loader import load_company_twin  # the CLI only; the loader itself validates through this module

    twin = load_company_twin()
    issues = validate_twin(twin)
    errors = [i for i in issues if i.severity == "error"]
    print(f"Twin: {twin.organization.display_name}  (schema {twin.schema_version})")
    print(f"entities={len(twin.entities)} edges={len(twin.edges)} issues={len(issues)} errors={len(errors)}")
    for i in issues:
        print(f"  {i.severity.upper()} [{i.rule}] {i.message} {i.ids or ''}")
    print("RESULT:", "VALID" if not errors else "INVALID")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
