"""Build a Canary Pact twin from Microsoft's public AdventureWorks OLTP tables.

This module is a pure transformation: it performs no network access, file
reads, environment lookups, or clock reads.  An outer adapter fetches the
tables named in ``ADVENTUREWORKS_TABLES`` (tab-delimited, UTF-8 with BOM) and
passes the parsed rows in together with an explicit ``created_at``.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from contracts_py.enums import (
    BusinessModel,
    ChannelKind,
    Criticality,
    DocumentStatus,
    DocumentType,
    EntityType,
    EvidenceSource,
    Relation,
    Sector,
    Sensitivity,
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
    Organization,
    StaffingStrength,
    StrategicPriority,
    Twin,
    VersionInfo,
)


# Provenance recorded on the twin's documents; this module never fetches it.
_PROVENANCE_BASE = (
    "https://raw.githubusercontent.com/microsoft/sql-server-samples/master/"
    "samples/databases/adventure-works/oltp-install-script"
)
ADVENTUREWORKS_TABLES: tuple[str, ...] = (
    "Department.csv",
    "Employee.csv",
    "EmployeeDepartmentHistory.csv",
    "EmployeePayHistory.csv",
    "Vendor.csv",
    "ProductVendor.csv",
    "PurchaseOrderHeader.csv",
    "PurchaseOrderDetail.csv",
    "Product.csv",
    "ProductCategory.csv",
    "ProductSubcategory.csv",
    "Location.csv",
    "WorkOrder.csv",
    "WorkOrderRouting.csv",
    "SalesOrderHeader.csv",
    "SalesOrderDetail.csv",
)

AdventureWorksTables = Mapping[str, Sequence[Sequence[str]]]


def _slug(value: str, limit: int = 52) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return value[:limit].rstrip("_") or "unknown"


def _money(value: Decimal | float | int) -> int:
    return max(0, round(Decimal(str(value))))


def _year(value: str) -> int:
    return int(value[:4])


def _years(rows: Sequence[Sequence[str]], index: int) -> int:
    return max(1, len({_year(row[index]) for row in rows if row[index]}))


def _edge(
    edge_id: str,
    source: str,
    target: str,
    relation: Relation,
    *,
    strength: float,
    substitutability: float,
    criticality: Criticality = Criticality.medium,
    confidence: float = 0.95,
    lag_days: int = 0,
    evidence_refs: list[str] | None = None,
    label: str | None = None,
    channel_kind: ChannelKind | None = None,
) -> Edge:
    return Edge(
        id=edge_id,
        source=source,
        target=target,
        relation=relation,
        strength=max(0.0, min(1.0, strength)),
        substitutability=max(0.0, min(1.0, substitutability)),
        lag_days=lag_days,
        criticality=criticality,
        confidence=confidence,
        evidence_refs=evidence_refs or [],
        label=label,
        channel_kind=channel_kind,
        extraction_method="seeded",
    )


AGENT_BY_DEPARTMENT = {
    "Engineering": "engineering",
    "Tool Design": "engineering",
    "Sales": "sales",
    "Marketing": "marketing",
    "Purchasing": "finance",
    "Research and Development": "product",
    "Production": "operations",
    "Production Control": "operations",
    "Human Resources": "people_knowledge",
    "Finance": "finance",
    "Information Services": "ai_data",
    "Document Control": "compliance",
    "Quality Assurance": "compliance",
    "Facilities and Maintenance": "operations",
    "Shipping and Receiving": "customer_success",
}


def build_adventureworks_twin(
    tables: AdventureWorksTables,
    *,
    created_at: datetime,
    twin_version: str | None = None,
) -> Twin:
    """Transform AdventureWorks OLTP rows into the current Twin contract.

    ``tables`` maps every name in ``ADVENTUREWORKS_TABLES`` to its parsed rows
    (header-less, as in Microsoft's install script).  The result depends only on
    the arguments: ``twin_version`` defaults to ``adventureworks-<created_at date>``.
    Derived DepartmentProfile fields are left for ``company_twin.build_twin`` to compute.
    """
    missing = [name for name in ADVENTUREWORKS_TABLES if name not in tables]
    if missing:
        raise ValueError(f"missing AdventureWorks tables: {', '.join(missing)}")
    data = tables
    as_of = created_at.date()

    department_rows = data["Department.csv"]
    employee_rows = data["Employee.csv"]
    current_assignments = [row for row in data["EmployeeDepartmentHistory.csv"] if not row[4]]
    pay_rows = data["EmployeePayHistory.csv"]
    vendor_rows = data["Vendor.csv"]
    product_vendor_rows = data["ProductVendor.csv"]
    purchase_headers = data["PurchaseOrderHeader.csv"]
    purchase_details = data["PurchaseOrderDetail.csv"]
    product_rows = data["Product.csv"]
    category_rows = data["ProductCategory.csv"]
    subcategory_rows = data["ProductSubcategory.csv"]
    location_rows = data["Location.csv"]
    work_order_rows = data["WorkOrder.csv"]
    routing_rows = data["WorkOrderRouting.csv"]
    sales_headers = data["SalesOrderHeader.csv"]
    sales_details = data["SalesOrderDetail.csv"]

    dept_name = {row[0]: row[1] for row in department_rows}
    dept_id = {raw: f"dept_{_slug(name)}" for raw, name in dept_name.items()}
    employee_title = {row[0]: row[5] for row in employee_rows}
    employee_dept = {row[0]: row[1] for row in current_assignments}
    latest_rate: dict[str, tuple[str, Decimal]] = {}
    for employee_id, changed_at, rate, *_ in pay_rows:
        if employee_id not in latest_rate or changed_at > latest_rate[employee_id][0]:
            latest_rate[employee_id] = (changed_at, Decimal(rate))

    employees_by_dept: dict[str, list[str]] = defaultdict(list)
    roles_by_dept: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    annual_pay: dict[str, int] = {}
    for employee_id, raw_dept in employee_dept.items():
        employees_by_dept[raw_dept].append(employee_id)
        roles_by_dept[raw_dept][employee_title[employee_id]].append(employee_id)
        annual_pay[employee_id] = _money(latest_rate[employee_id][1] * Decimal(2080))

    entities: list[Entity] = []
    edges: list[Edge] = []
    profiles: list[DepartmentProfile] = []

    role_id_by_dept_title: dict[tuple[str, str], str] = {}
    head_role_by_dept: dict[str, str] = {}
    total_budget = 0
    for raw_id, name, group_name, _ in department_rows:
        did = dept_id[raw_id]
        employees = employees_by_dept[raw_id]
        budget = sum(annual_pay[eid] for eid in employees)
        total_budget += budget
        entities.append(Entity(
            id=did,
            type=EntityType.department,
            name=name,
            criticality=Criticality.high if name in {"Production", "Sales", "Purchasing"} else Criticality.medium,
            annual_cost_usd=budget,
            capacity_fte=float(len(employees)),
            tags=["adventureworks", _slug(group_name)],
            evidence_refs=["ev_aw_departments", "ev_aw_employee_assignments"],
        ))
        role_costs: list[tuple[int, str]] = []
        for title, members in sorted(roles_by_dept[raw_id].items()):
            rid = f"role_aw_{raw_id}_{_slug(title, 45)}"
            cost = sum(annual_pay[eid] for eid in members)
            role_id_by_dept_title[(raw_id, title)] = rid
            role_costs.append((cost, rid))
            entities.append(Entity(
                id=rid,
                type=EntityType.role,
                name=title,
                department_id=did,
                criticality=Criticality.medium,
                annual_cost_usd=cost,
                capacity_fte=float(len(members)),
                time_to_train_days=60,
                replacement_cost_usd=_money(cost * Decimal("0.20")),
                sensitivity=Sensitivity.hr,
                tags=["adventureworks_derived", "training_cost_assumption"],
                evidence_refs=["ev_aw_employees", "ev_aw_pay_history"],
            ))
        head_role = max(role_costs)[1] if role_costs else None
        if head_role:
            head_role_by_dept[raw_id] = head_role
        profiles.append(DepartmentProfile(
            department_id=did,
            mission=f"Deliver {name.lower()} capabilities within the {group_name} business group.",
            head_role_id=head_role,
            agent_id=AGENT_BY_DEPARTMENT.get(name),
            staffing=StaffingStrength(
                sanctioned_fte=float(len(employees)),
                actual_fte=float(len(employees)),
                contractors_fte=0,
                open_positions=0,
                attrition_rate_annual=0,
                avg_time_to_hire_days=45,
                utilisation=1,
            ),
            budget=DepartmentBudget(
                annual_budget_usd=budget,
                spent_ytd_usd=0,
                fixed_cost_pct=0.8,
                budget_owner_role_id=head_role,
            ),
            strengths=[DepartmentStrength(
                id=f"str_aw_{raw_id}_core",
                name=f"{name} operating capability",
                category=StrengthCategory.capability,
                level=3,
                key_role_ids=[head_role] if head_role else [],
                concentration=1 / max(1, len(roles_by_dept[raw_id])),
                evidence_refs=["ev_aw_employee_assignments"],
            )],
            maturity_level=3,
        ))

    products = {row[0]: row for row in product_rows}
    subcategory_to_category = {row[0]: row[1] for row in subcategory_rows}
    category_name = {row[0]: row[1] for row in category_rows}
    product_category: dict[str, str] = {}
    for product_id, row in products.items():
        subcategory_id = row[18]
        if subcategory_id and subcategory_id in subcategory_to_category:
            product_category[product_id] = subcategory_to_category[subcategory_id]

    purchase_years = _years(purchase_headers, 6)
    po_vendor = {row[0]: row[4] for row in purchase_headers}
    vendor_spend: dict[str, Decimal] = defaultdict(Decimal)
    vendor_category_spend: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for row in purchase_details:
        vendor_id = po_vendor[row[0]]
        amount = Decimal(row[7])
        vendor_spend[vendor_id] += amount
        category_id = product_category.get(row[4])
        if category_id:
            vendor_category_spend[(vendor_id, category_id)] += amount

    vendors_by_category: dict[str, set[str]] = defaultdict(set)
    for product_id, vendor_id, *_ in product_vendor_rows:
        category_id = product_category.get(product_id)
        if category_id:
            vendors_by_category[category_id].add(vendor_id)

    purchasing_dept = dept_id["5"]
    total_vendor_spend = sum(vendor_spend.values(), Decimal(0))
    for raw_id, _, name, credit_rating, preferred, active, *_ in vendor_rows:
        annual_cost = _money(vendor_spend[raw_id] / purchase_years)
        entities.append(Entity(
            id=f"vendor_aw_{raw_id}",
            type=EntityType.vendor,
            name=name,
            department_id=purchasing_dept,
            criticality=Criticality.high if preferred == "1" else Criticality.medium,
            annual_cost_usd=annual_cost,
            one_time_exit_cost_usd=_money(annual_cost * Decimal("0.05")),
            migration_cost_usd=_money(annual_cost * Decimal("0.10")),
            geographies=["unknown"],
            history_years=purchase_years,
            freshness_days=30,
            accuracy=0.8,
            permitted_uses=["procurement", "manufacturing"],
            retains_history_after_termination=True,
            tags=[
                "adventureworks",
                "active" if active == "1" else "inactive",
                "preferred" if preferred == "1" else "standard",
                f"credit_rating_{credit_rating}",
                "exit_cost_is_assumption",
                "substitution_fields_are_assumptions",
            ],
            evidence_refs=["ev_aw_vendors", "ev_aw_purchase_orders"],
        ))
        edges.append(_edge(
            f"e_aw_vendor_{raw_id}_procurement",
            f"vendor_aw_{raw_id}",
            "wf_aw_procurement",
            Relation.PROVIDES,
            strength=max(0.01, float(vendor_spend[raw_id] / total_vendor_spend)) if total_vendor_spend else 0.01,
            substitutability=0.5,
            criticality=Criticality.high if preferred == "1" else Criticality.medium,
            confidence=0.98,
            lag_days=7,
            evidence_refs=["ev_aw_vendors", "ev_aw_purchase_orders"],
        ))

    production_dept = dept_id["7"]
    workflow_by_category: dict[str, str] = {}
    for category_id, name in category_name.items():
        wid = f"wf_aw_make_{_slug(name)}"
        workflow_by_category[category_id] = wid
        category_sales = Decimal(0)
        entities.append(Entity(
            id=wid,
            type=EntityType.workflow,
            name=f"Manufacture {name}",
            department_id=production_dept,
            criticality=Criticality.critical if name in {"Bikes", "Components"} else Criticality.high,
            min_qualified_owners=1,
            documented_pct=0.75,
            failure_cost_per_day_usd=max(1_000, _money(category_sales) // 365),
            customer_facing=True,
            tags=["adventureworks_derived", f"product_category_{category_id}"],
            evidence_refs=["ev_aw_products", "ev_aw_work_orders"],
        ))

    for (raw_vendor, category_id), spend in vendor_category_spend.items():
        if category_id not in workflow_by_category:
            continue
        alternatives = len(vendors_by_category[category_id])
        substitution = 0.85 if alternatives >= 4 else 0.6 if alternatives >= 2 else 0.1
        category_total = sum(value for (vendor, cat), value in vendor_category_spend.items() if cat == category_id)
        strength = float(spend / category_total) if category_total else 0.1
        edges.append(_edge(
            f"e_aw_vendor_{raw_vendor}_category_{category_id}",
            f"vendor_aw_{raw_vendor}",
            workflow_by_category[category_id],
            Relation.PROVIDES,
            strength=max(0.05, strength),
            substitutability=substitution,
            criticality=Criticality.high,
            confidence=0.98,
            lag_days=14,
            evidence_refs=["ev_aw_product_vendor", "ev_aw_purchase_orders"],
        ))

    location_name = {row[0]: row[1] for row in location_rows}
    for raw_id, name, cost_rate, availability, _ in location_rows:
        entities.append(Entity(
            id=f"sys_aw_location_{raw_id}",
            type=EntityType.system,
            name=f"{name} work center",
            department_id=production_dept,
            criticality=Criticality.high,
            annual_cost_usd=_money(Decimal(cost_rate) * Decimal(2080)),
            failure_cost_per_day_usd=max(1_000, _money(Decimal(cost_rate) * Decimal(8))),
            capacity_fte=float(Decimal(availability or "0")),
            tags=["physical_work_center", "adventureworks"],
            evidence_refs=["ev_aw_locations"],
        ))

    category_location_hours: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for row in routing_rows:
        category_id = product_category.get(row[1])
        if category_id:
            category_location_hours[(category_id, row[3])] += Decimal(row[8] or "0")
    for (category_id, location_id), hours in category_location_hours.items():
        total = sum(value for (cat, _), value in category_location_hours.items() if cat == category_id)
        edges.append(_edge(
            f"e_aw_location_{location_id}_category_{category_id}",
            f"sys_aw_location_{location_id}",
            workflow_by_category[category_id],
            Relation.SUPPORTS,
            strength=float(hours / total) if total else 0.1,
            substitutability=0.3,
            criticality=Criticality.high,
            evidence_refs=["ev_aw_work_order_routing"],
        ))

    supporting_workflows = [
        ("wf_aw_procurement", "Supplier procurement", "5", Criticality.high, "ev_aw_purchase_orders"),
        ("wf_aw_sales_fulfillment", "Sales order fulfillment", "3", Criticality.critical, "ev_aw_sales_orders"),
        ("wf_aw_shipping", "Shipping and receiving", "15", Criticality.high, "ev_aw_sales_orders"),
        ("wf_aw_quality", "Production quality assurance", "13", Criticality.high, "ev_aw_work_orders"),
    ]
    for wid, name, raw_dept, criticality, evidence_ref in supporting_workflows:
        entities.append(Entity(
            id=wid,
            type=EntityType.workflow,
            name=name,
            department_id=dept_id[raw_dept],
            criticality=criticality,
            min_qualified_owners=1,
            documented_pct=0.7,
            failure_cost_per_day_usd=max(
                1_000,
                sum(annual_pay[employee_id] for employee_id in employees_by_dept[raw_dept]) // 260,
            ),
            customer_facing=wid in {"wf_aw_sales_fulfillment", "wf_aw_shipping"},
            evidence_refs=[evidence_ref],
            tags=["adventureworks_derived"],
        ))
        owner = head_role_by_dept.get(raw_dept)
        if owner:
            edges.append(_edge(
                f"e_aw_owner_{raw_dept}_{wid.removeprefix('wf_aw_')}", owner, wid, Relation.OWNS,
                strength=0.9, substitutability=0.4, confidence=0.8, evidence_refs=["ev_aw_employee_assignments"],
            ))

    production_owner = head_role_by_dept.get("7")
    if production_owner:
        for category_id, wid in workflow_by_category.items():
            edges.append(_edge(
                f"e_aw_owner_production_{category_id}", production_owner, wid, Relation.OWNS,
                strength=0.9, substitutability=0.35, confidence=0.75, evidence_refs=["ev_aw_employee_assignments"],
            ))

    sales_years = _years(sales_headers, 2)
    sales_revenue = sum((Decimal(row[19]) for row in sales_headers), Decimal(0)) / sales_years
    on_time_rows = [row for row in sales_headers if row[4]]
    on_time = sum(1 for row in on_time_rows if row[4] <= row[3]) / max(1, len(on_time_rows))
    detail_cost = Decimal(0)
    detail_sales = Decimal(0)
    for row in sales_details:
        product = products[row[4]]
        qty = Decimal(row[3])
        detail_cost += Decimal(product[8] or "0") * qty
        detail_sales += Decimal(row[8])
    gross_margin = float((detail_sales - detail_cost) / detail_sales * 100) if detail_sales else 0
    ordered = sum(int(row[2]) for row in work_order_rows)
    scrapped = sum(int(row[4]) for row in work_order_rows)
    scrap_rate = scrapped / max(1, ordered) * 100
    annual_purchase_spend = _money(sum(vendor_spend.values(), Decimal(0)) / purchase_years)

    kpis = [
        Entity(id="kpi_company", type=EntityType.kpi, name="Company performance", criticality=Criticality.high,
               kpi_baseline=100, kpi_unit="index", higher_is_better=True),
        Entity(id="kpi_aw_sales", type=EntityType.kpi, name="Annual sales revenue", department_id=dept_id["3"],
               criticality=Criticality.critical, kpi_baseline=float(_money(sales_revenue)), kpi_unit="usd",
               higher_is_better=True, evidence_refs=["ev_aw_sales_orders"]),
        Entity(id="kpi_aw_gross_margin", type=EntityType.kpi, name="Gross margin", department_id=dept_id["10"],
               criticality=Criticality.high, kpi_baseline=round(gross_margin, 2), kpi_unit="percent",
               higher_is_better=True, evidence_refs=["ev_aw_sales_orders", "ev_aw_products"]),
        Entity(id="kpi_aw_on_time_delivery", type=EntityType.kpi, name="On-time delivery",
               department_id=dept_id["15"], criticality=Criticality.high,
               kpi_baseline=round(on_time * 100, 2), kpi_unit="percent", higher_is_better=True,
               evidence_refs=["ev_aw_sales_orders"]),
        Entity(id="kpi_aw_purchase_spend", type=EntityType.kpi, name="Annual supplier spend",
               department_id=dept_id["5"], criticality=Criticality.high,
               kpi_baseline=float(annual_purchase_spend), kpi_unit="usd", higher_is_better=False,
               evidence_refs=["ev_aw_purchase_orders"]),
        Entity(id="kpi_aw_scrap_rate", type=EntityType.kpi, name="Production scrap rate",
               department_id=dept_id["13"], criticality=Criticality.high,
               kpi_baseline=round(scrap_rate, 3), kpi_unit="percent", higher_is_better=False,
               evidence_refs=["ev_aw_work_orders"]),
    ]
    entities.extend(kpis)

    for wid in workflow_by_category.values():
        edges.extend([
            _edge(f"e_{wid}_sales", wid, "kpi_aw_sales", Relation.CONTRIBUTES_TO,
                  strength=0.7, substitutability=0.2, criticality=Criticality.high,
                  evidence_refs=["ev_aw_sales_orders"]),
            _edge(f"e_{wid}_margin", wid, "kpi_aw_gross_margin", Relation.CONTRIBUTES_TO,
                  strength=0.6, substitutability=0.3, criticality=Criticality.high,
                  evidence_refs=["ev_aw_products", "ev_aw_sales_orders"]),
        ])
    edges.extend([
        _edge("e_aw_procurement_spend", "wf_aw_procurement", "kpi_aw_purchase_spend", Relation.CONTRIBUTES_TO,
              strength=0.95, substitutability=0.1, criticality=Criticality.high,
              evidence_refs=["ev_aw_purchase_orders"]),
        _edge("e_aw_fulfillment_shipping", "wf_aw_sales_fulfillment", "wf_aw_shipping", Relation.DEPENDS_ON,
              strength=0.9, substitutability=0.2, criticality=Criticality.critical, lag_days=2,
              evidence_refs=["ev_aw_sales_orders"]),
        _edge("e_aw_shipping_delivery", "wf_aw_shipping", "kpi_aw_on_time_delivery", Relation.CONTRIBUTES_TO,
              strength=0.95, substitutability=0.1, criticality=Criticality.high,
              evidence_refs=["ev_aw_sales_orders"]),
        _edge("e_aw_quality_scrap", "wf_aw_quality", "kpi_aw_scrap_rate", Relation.CONTRIBUTES_TO,
              strength=0.9, substitutability=0.2, criticality=Criticality.high,
              evidence_refs=["ev_aw_work_orders"]),
    ])

    # Complete every imported department with a small, scenario-ready context pack.
    # Imported staffing and transaction records remain the factual source; the
    # workflow/knowledge narrative is explicitly marked synthetic demo context.
    primary_workflow_by_raw = {
        "1": "wf_aw_engineering_change_control",
        "2": "wf_aw_tooling_design_release",
        "3": "wf_aw_sales_fulfillment",
        "4": "wf_aw_demand_planning",
        "5": "wf_aw_procurement",
        "6": "wf_aw_product_design_validation",
        "7": workflow_by_category.get("1", next(iter(workflow_by_category.values()))),
        "8": "wf_aw_production_scheduling",
        "9": "wf_aw_workforce_onboarding",
        "10": "wf_aw_financial_close",
        "11": "wf_aw_business_systems_support",
        "12": "wf_aw_controlled_document_publishing",
        "13": "wf_aw_quality",
        "14": "wf_aw_preventive_maintenance",
        "15": "wf_aw_shipping",
        "16": "wf_aw_executive_operating_review",
    }
    workflow_name_by_raw = {
        "1": "Engineering change control",
        "2": "Tooling design and release",
        "4": "Demand planning",
        "6": "Product design validation",
        "8": "Production scheduling",
        "9": "Workforce onboarding",
        "10": "Financial close",
        "11": "Business systems support",
        "12": "Controlled document publishing",
        "14": "Preventive maintenance",
        "16": "Executive operating review",
    }
    existing_entity_ids = {entity.id for entity in entities}
    budget_by_raw = {
        raw_id: sum(annual_pay[employee_id] for employee_id in employees_by_dept[raw_id])
        for raw_id in dept_name
    }
    for raw_id, workflow_name in workflow_name_by_raw.items():
        if raw_id not in dept_id:
            continue
        workflow_id = primary_workflow_by_raw[raw_id]
        if workflow_id in existing_entity_ids:
            continue
        entities.append(Entity(
            id=workflow_id,
            type=EntityType.workflow,
            name=workflow_name,
            department_id=dept_id[raw_id],
            criticality=Criticality.high,
            min_qualified_owners=1,
            documented_pct=0.5,
            failure_cost_per_day_usd=max(1_000, budget_by_raw[raw_id] // 260),
            customer_facing=raw_id in {"4"},
            exception_documented_pct=0.5,
            automation_pct=0.4,
            max_downtime_days=5,
            tags=["adventureworks_demo_context", "derived_assumption"],
            evidence_refs=[f"ev_aw_context_{raw_id}"],
        ))
        existing_entity_ids.add(workflow_id)

    existing_kpi_by_raw = {
        "3": "kpi_aw_sales",
        "5": "kpi_aw_purchase_spend",
        "10": "kpi_aw_gross_margin",
        "13": "kpi_aw_scrap_rate",
        "15": "kpi_aw_on_time_delivery",
    }
    primary_kpi_by_raw: dict[str, str] = {}
    for raw_id, name, *_ in department_rows:
        kpi_id = existing_kpi_by_raw.get(raw_id, f"kpi_aw_{_slug(name)}_staffed_capacity")
        primary_kpi_by_raw[raw_id] = kpi_id
        if kpi_id not in existing_entity_ids:
            entities.append(Entity(
                id=kpi_id,
                type=EntityType.kpi,
                name=f"{name} staffed capacity",
                department_id=dept_id[raw_id],
                criticality=Criticality.medium,
                kpi_baseline=float(len(employees_by_dept[raw_id])),
                kpi_unit="assigned_fte",
                higher_is_better=True,
                tags=["adventureworks_derived", "staffing_baseline"],
                evidence_refs=[f"ev_aw_context_{raw_id}"],
            ))
            existing_entity_ids.add(kpi_id)

    context_documents: list[Document] = []
    context_evidence: list[Evidence] = []
    existing_edges = {(item.source, item.target, item.relation) for item in edges}
    for raw_id, name, group_name, _ in department_rows:
        did = dept_id[raw_id]
        workflow_id = primary_workflow_by_raw[raw_id]
        kpi_id = primary_kpi_by_raw[raw_id]
        knowledge_id = f"kn_aw_{raw_id}_operating_knowledge"
        evidence_id = f"ev_aw_context_{raw_id}"
        document_id = f"doc_aw_context_{raw_id}"
        head_role = head_role_by_dept.get(raw_id)

        workflow = next(entity for entity in entities if entity.id == workflow_id)
        kpi = next(entity for entity in entities if entity.id == kpi_id)
        workflow.evidence_refs = sorted(set([*workflow.evidence_refs, evidence_id]))
        kpi.evidence_refs = sorted(set([*kpi.evidence_refs, evidence_id]))
        entities.append(Entity(
            id=knowledge_id,
            type=EntityType.knowledge_asset,
            name=f"{name} operating knowledge",
            department_id=did,
            criticality=workflow.criticality,
            documented_pct=0.65,
            tags=["adventureworks_demo_context", "department_operating_knowledge"],
            evidence_refs=[evidence_id],
        ))

        if head_role and (head_role, workflow_id, Relation.OWNS) not in existing_edges:
            edges.append(_edge(
                f"e_aw_context_{raw_id}_owner", head_role, workflow_id, Relation.OWNS,
                strength=0.8, substitutability=0.35, criticality=workflow.criticality,
                confidence=0.8, evidence_refs=[evidence_id],
            ))
        edges.append(_edge(
            f"e_aw_context_{raw_id}_knowledge", knowledge_id, workflow_id, Relation.SUPPORTS,
            strength=0.7, substitutability=0.4, criticality=workflow.criticality,
            confidence=0.75, evidence_refs=[evidence_id],
        ))
        if (workflow_id, kpi_id, Relation.CONTRIBUTES_TO) not in existing_edges:
            edges.append(_edge(
                f"e_aw_context_{raw_id}_outcome", workflow_id, kpi_id, Relation.CONTRIBUTES_TO,
                strength=0.65, substitutability=0.35, criticality=workflow.criticality,
                confidence=0.75, evidence_refs=[evidence_id],
            ))

        covered = [workflow_id, kpi_id, knowledge_id]
        if head_role:
            covered.insert(0, head_role)
        context_documents.append(Document(
            id=document_id,
            title=f"{name} demo operating context",
            department_id=did,
            owner_role_id=head_role,
            doc_type=DocumentType.workflow_map,
            uri=f"canary://adventureworks/departments/{did}/context",
            mime_type="application/json",
            status=DocumentStatus.current,
            summary=(
                f"Scenario-ready {name} ownership and workflow context derived from public "
                f"AdventureWorks {group_name} staffing records. Workflow assumptions are synthetic."
            ),
            covers_entity_ids=covered,
            synthetic=True,
            ingested=True,
            uploaded_at=created_at,
        ))
        context_evidence.append(Evidence(
            id=evidence_id,
            source_type=EvidenceSource.workflow_map,
            document_id=document_id,
            snippet=(
                f"{name} has {len(employees_by_dept[raw_id])} assigned employees across "
                f"{len(roles_by_dept[raw_id])} roles; {workflow.name} is the seeded demo workflow."
            ),
            synthetic=True,
        ))

    channel_rows = [
        ("5", "7", ChannelKind.capability, "supplier inputs"),
        ("7", "8", ChannelKind.capability, "production output"),
        ("8", "15", ChannelKind.capability, "finished goods"),
        ("15", "3", ChannelKind.value, "fulfilled orders"),
        ("3", "4", ChannelKind.signal, "customer demand"),
        ("4", "7", ChannelKind.signal, "demand forecast"),
        ("10", "5", ChannelKind.budget, "procurement budget"),
        ("13", "7", ChannelKind.constraint, "quality gates"),
        ("11", "7", ChannelKind.capability, "information services"),
    ]
    for index, (source, target, kind, label) in enumerate(channel_rows, 1):
        edges.append(_edge(
            f"ch_aw_{index}", dept_id[source], dept_id[target], Relation.FLOWS_TO,
            strength=0.7, substitutability=0.3, confidence=0.8, lag_days=7,
            evidence_refs=["ev_aw_departments"], label=label, channel_kind=kind,
        ))

    def source_checksum(*filenames: str) -> str:
        """Checksum the normalized imported rows represented by one source document."""
        digest = hashlib.sha256()
        for filename in filenames:
            digest.update(filename.encode())
            for row in data[filename]:
                digest.update("\x1f".join(row).encode())
                digest.update(b"\n")
        return digest.hexdigest()

    documents = [
        Document(id="doc_aw_departments", title="AdventureWorks departments and employee assignments",
                 doc_type=DocumentType.org_chart, uri=f"{_PROVENANCE_BASE}/Department.csv", mime_type="text/csv",
                 status=DocumentStatus.current, summary="Microsoft sample department structure and current employee assignments.",
                 covers_entity_ids=[entity.id for entity in entities
                                    if entity.type in {EntityType.department, EntityType.role}],
                 checksum_sha256=source_checksum("Department.csv", "Employee.csv", "EmployeeDepartmentHistory.csv",
                                                 "EmployeePayHistory.csv"),
                 synthetic=False, ingested=True, uploaded_at=created_at),
        Document(id="doc_aw_purchasing", title="AdventureWorks purchasing records", department_id=dept_id["5"],
                 doc_type=DocumentType.contract, uri=f"{_PROVENANCE_BASE}/PurchaseOrderHeader.csv", mime_type="text/csv",
                 status=DocumentStatus.current, summary="Public vendor, product-vendor, and purchase-order records.",
                 covers_entity_ids=[entity.id for entity in entities if entity.type is EntityType.vendor]
                 + ["wf_aw_procurement", "kpi_aw_purchase_spend"],
                 checksum_sha256=source_checksum("Vendor.csv", "ProductVendor.csv", "PurchaseOrderHeader.csv",
                                                 "PurchaseOrderDetail.csv"),
                 synthetic=False, ingested=True, uploaded_at=created_at),
        Document(id="doc_aw_production", title="AdventureWorks production records", department_id=dept_id["7"],
                 doc_type=DocumentType.workflow_map, uri=f"{_PROVENANCE_BASE}/WorkOrderRouting.csv", mime_type="text/csv",
                 status=DocumentStatus.current, summary="Public product, work-order, routing, and work-center records.",
                 covers_entity_ids=[entity.id for entity in entities if entity.type is EntityType.system]
                 + [*workflow_by_category.values(), "wf_aw_quality", "kpi_aw_scrap_rate"],
                 checksum_sha256=source_checksum("Product.csv", "ProductCategory.csv", "ProductSubcategory.csv",
                                                 "Location.csv", "WorkOrder.csv", "WorkOrderRouting.csv"),
                 synthetic=False, ingested=True, uploaded_at=created_at),
        Document(id="doc_aw_sales", title="AdventureWorks sales records", department_id=dept_id["3"],
                 doc_type=DocumentType.kpi_report, uri=f"{_PROVENANCE_BASE}/SalesOrderHeader.csv", mime_type="text/csv",
                 status=DocumentStatus.current, summary="Public sales-order records used to derive revenue and delivery KPIs.",
                 covers_entity_ids=["wf_aw_sales_fulfillment", "wf_aw_shipping", "kpi_aw_sales",
                                    "kpi_aw_gross_margin", "kpi_aw_on_time_delivery"],
                 checksum_sha256=source_checksum("SalesOrderHeader.csv", "SalesOrderDetail.csv"),
                 synthetic=False, ingested=True, uploaded_at=created_at),
        *context_documents,
    ]
    evidence = [
        Evidence(id="ev_aw_departments", source_type=EvidenceSource.architecture_note,
                 document_id="doc_aw_departments", snippet=f"AdventureWorks defines {len(department_rows)} departments.",
                 synthetic=False),
        Evidence(id="ev_aw_employee_assignments", source_type=EvidenceSource.activity_log,
                 document_id="doc_aw_departments", snippet=f"{len(current_assignments)} current employee-department assignments were imported.",
                 synthetic=False),
        Evidence(id="ev_aw_employees", source_type=EvidenceSource.activity_log,
                 document_id="doc_aw_departments", snippet=f"{len(employee_rows)} fictitious employee records were used only in aggregate.",
                 synthetic=False),
        Evidence(id="ev_aw_pay_history", source_type=EvidenceSource.finance_forecast,
                 document_id="doc_aw_departments", snippet="Latest employee pay rates were annualized at 2,080 hours for department budgets.",
                 synthetic=False),
        Evidence(id="ev_aw_vendors", source_type=EvidenceSource.contract, document_id="doc_aw_purchasing",
                 snippet=f"{len(vendor_rows)} public fictitious vendor records were imported.", synthetic=False),
        Evidence(id="ev_aw_product_vendor", source_type=EvidenceSource.architecture_note,
                 document_id="doc_aw_purchasing",
                 snippet=f"{len(product_vendor_rows)} product-vendor relationships support substitution analysis.",
                 synthetic=False),
        Evidence(id="ev_aw_purchase_orders", source_type=EvidenceSource.activity_log,
                 document_id="doc_aw_purchasing",
                 snippet=f"{len(purchase_headers)} purchase orders and {len(purchase_details)} lines determine vendor spend.",
                 synthetic=False),
        Evidence(id="ev_aw_products", source_type=EvidenceSource.architecture_note,
                 document_id="doc_aw_production", snippet=f"{len(product_rows)} products map suppliers to production categories.",
                 synthetic=False),
        Evidence(id="ev_aw_locations", source_type=EvidenceSource.system_ownership,
                 document_id="doc_aw_production", snippet=f"{len(location_rows)} production work centers were imported.",
                 synthetic=False),
        Evidence(id="ev_aw_work_orders", source_type=EvidenceSource.activity_log,
                 document_id="doc_aw_production", snippet=f"{len(work_order_rows)} work orders determine production volume and scrap.",
                 synthetic=False),
        Evidence(id="ev_aw_work_order_routing", source_type=EvidenceSource.workflow_map,
                 document_id="doc_aw_production", snippet=f"{len(routing_rows)} routing steps connect work centers to product workflows.",
                 synthetic=False),
        Evidence(id="ev_aw_sales_orders", source_type=EvidenceSource.kpi_definition,
                 document_id="doc_aw_sales",
                 snippet=f"{len(sales_headers)} sales orders and {len(sales_details)} lines determine commercial KPIs.",
                 synthetic=False),
        *context_evidence,
    ]

    return Twin(
        version=VersionInfo(
            twin_version=twin_version or f"adventureworks-{as_of.isoformat()}",
            settings_version=1,
            prompt_version="real-v1",
            model_id="none",
            engine_version="deterministic-v1",
            created_at=created_at,
            as_of_date=as_of,
            data_snapshot_id="microsoft-sql-server-samples-master",
            created_by="adventureworks_importer",
        ),
        organization=Organization(
            id="org_adventure_works",
            legal_name="Adventure Works Cycles",
            display_name="Adventure Works",
            sector=Sector.manufacturing,
            sub_sector="Bicycle manufacturing and retail",
            secondary_sectors=[Sector.retail_ecommerce],
            business_model=BusinessModel.mixed,
            size_band=SizeBand.mid_market,
            headquarters_country="US",
            operating_regions=["North America", "Europe", "Pacific"],
            annual_revenue_usd=_money(sales_revenue),
            total_annual_budget_usd=total_budget,
            total_headcount_fte=float(len(current_assignments)),
            fiscal_year_start_month=1,
            regulatory_frameworks=[],
            strategic_priorities=[
                StrategicPriority(id="sp_aw_margin", text="Protect product gross margin", rank=1,
                                  kpi_ids=["kpi_aw_gross_margin"]),
                StrategicPriority(id="sp_aw_delivery", text="Maintain on-time customer delivery", rank=2,
                                  kpi_ids=["kpi_aw_on_time_delivery"]),
                StrategicPriority(id="sp_aw_supplier_cost", text="Reduce supplier spend safely", rank=3,
                                  kpi_ids=["kpi_aw_purchase_spend"]),
            ],
            description=(
                "Microsoft's fictitious bicycle manufacturer, transformed from the public AdventureWorks OLTP "
                "sample under the Microsoft SQL Server Samples MIT license."
            ),
            evidence_refs=["ev_aw_departments", "ev_aw_sales_orders"],
        ),
        department_profiles=profiles,
        entities=entities,
        edges=edges,
        documents=documents,
        evidence=evidence,
    )
