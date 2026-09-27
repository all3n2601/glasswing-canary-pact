"""build_adventureworks_twin is a pure transformation of in-memory tables (plan B-01; AGENTS.md sections 5, 8).

The tables below are a handful of hand-written rows in the AdventureWorks OLTP column
layout, so the importer runs without the network, the clock, or any file, and its output
goes through the same in-memory ``build_twin`` as any other company twin.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import company_twin
from company_twin import ADVENTUREWORKS_TABLES, build_adventureworks_twin, build_twin, validate_twin

CREATED_AT = datetime(2026, 9, 26, 12, 30, tzinfo=timezone.utc)


def _row(width: int, **cols: str) -> list[str]:
    """A ``width``-column row with ``c<index>=value`` cells set and every other cell empty."""
    cells = [""] * width
    for key, value in cols.items():
        cells[int(key.removeprefix("c"))] = value
    return cells


def aw_tables() -> dict[str, list[list[str]]]:
    departments = [("3", "Sales", "Sales and Marketing"), ("4", "Marketing", "Sales and Marketing"),
                   ("5", "Purchasing", "Inventory Management"), ("7", "Production", "Manufacturing"),
                   ("8", "Production Control", "Manufacturing"),
                   ("10", "Finance", "Executive General and Administration"),
                   ("11", "Information Services", "Executive General and Administration"),
                   ("13", "Quality Assurance", "Quality Assurance"),
                   ("15", "Shipping and Receiving", "Inventory Management")]
    staff = [("1", "3", "Sales Representative", "30.00"), ("2", "4", "Marketing Specialist", "20.00"),
             ("3", "5", "Buyer", "18.00"), ("4", "7", "Production Technician", "14.00"),
             ("5", "7", "Production Supervisor", "25.00"), ("6", "8", "Production Control Manager", "28.00"),
             ("7", "10", "Accountant", "26.00"), ("8", "11", "Network Administrator", "32.00"),
             ("9", "13", "Quality Assurance Technician", "15.00"), ("10", "15", "Shipping Clerk", "12.00")]
    return {
        "Department.csv": [[d, name, group, "2008-04-30"] for d, name, group in departments],
        "Employee.csv": [_row(15, c0=e, c5=title) for e, _, title, _ in staff],
        "EmployeeDepartmentHistory.csv": [
            *(_row(6, c0=e, c1=d, c3="2019-01-01") for e, d, _, _ in staff),
            _row(6, c0="4", c1="13", c3="2017-01-01", c4="2018-12-31"),  # ended: not a current assignment
        ],
        "EmployeePayHistory.csv": [
            *([e, "2020-01-01", rate, "1", "2020-01-01"] for e, _, _, rate in staff),
            ["5", "2018-01-01", "19.00", "1", "2018-01-01"],  # older rate: the latest one wins
        ],
        "Vendor.csv": [_row(8, c0="1492", c2="Australia Bike Retailer", c3="1", c4="1", c5="1"),
                       _row(8, c0="1494", c2="Allenson Cycles", c3="2", c4="0", c5="1"),
                       _row(8, c0="1496", c2="Advanced Bicycles", c3="1", c4="0", c5="0")],
        "ProductVendor.csv": [_row(11, c0="1", c1="1492"), _row(11, c0="2", c1="1492"),
                              _row(11, c0="2", c1="1494"), _row(11, c0="1", c1="1496")],
        "PurchaseOrderHeader.csv": [_row(13, c0="1", c4="1492", c6="2023-04-16"),
                                    _row(13, c0="2", c4="1494", c6="2024-02-01"),
                                    _row(13, c0="3", c4="1496", c6="2024-06-11")],
        "PurchaseOrderDetail.csv": [_row(11, c0="1", c4="1", c7="12000.00"), _row(11, c0="1", c4="2", c7="3000.00"),
                                    _row(11, c0="2", c4="2", c7="5000.00"), _row(11, c0="3", c4="1", c7="2000.00")],
        "Product.csv": [_row(25, c0="1", c8="400.00", c18="1"), _row(25, c0="2", c8="20.00", c18="2"),
                        _row(25, c0="3", c8="5.00")],  # no subcategory: outside every workflow
        "ProductCategory.csv": [["1", "Bikes", "", "2008-04-30"], ["2", "Components", "", "2008-04-30"]],
        "ProductSubcategory.csv": [["1", "1", "Mountain Bikes", "", "2008-04-30"],
                                   ["2", "2", "Handlebars", "", "2008-04-30"]],
        "Location.csv": [["10", "Frame Forming", "22.50", "96.00", "2008-04-30"],
                         ["60", "Final Assembly", "0.00", "120.00", "2008-04-30"]],
        "WorkOrder.csv": [_row(10, c0="1", c1="1", c2="100", c3="98", c4="2"),
                          _row(10, c0="2", c1="2", c2="400", c3="400", c4="0")],
        "WorkOrderRouting.csv": [_row(12, c0="1", c1="1", c3="10", c8="6.0"),
                                 _row(12, c0="1", c1="1", c3="60", c8="2.0"),
                                 _row(12, c0="2", c1="2", c3="60", c8="3.5")],
        "SalesOrderHeader.csv": [_row(26, c0="43659", c2="2023-05-31", c3="2023-06-12", c4="2023-06-07", c19="2500.00"),
                                 _row(26, c0="43660", c2="2024-05-31", c3="2024-06-12", c4="2024-06-15", c19="900.00")],
        "SalesOrderDetail.csv": [_row(11, c0="43659", c3="2", c4="1", c8="1600.00"),
                                 _row(11, c0="43659", c3="10", c4="2", c8="400.00"),
                                 _row(11, c0="43660", c3="1", c4="1", c8="800.00")],
    }


def test_the_table_list_names_every_table_the_builder_reads():
    assert set(aw_tables()) == set(ADVENTUREWORKS_TABLES) and len(ADVENTUREWORKS_TABLES) == 16
    assert not hasattr(company_twin, "fetch_adventureworks")


def test_the_same_tables_and_time_build_a_byte_identical_twin():
    first = build_adventureworks_twin(aw_tables(), created_at=CREATED_AT)
    second = build_adventureworks_twin(aw_tables(), created_at=CREATED_AT)
    assert first.model_dump_json() == second.model_dump_json()


def test_the_version_comes_from_created_at_or_the_caller():
    twin = build_adventureworks_twin(aw_tables(), created_at=CREATED_AT)
    assert twin.version.twin_version == "adventureworks-2026-09-26"
    assert twin.version.created_at == CREATED_AT and twin.version.as_of_date == CREATED_AT.date()
    later = build_adventureworks_twin(aw_tables(), created_at=datetime(2027, 1, 2, tzinfo=timezone.utc))
    assert later.version.twin_version == "adventureworks-2027-01-02"
    pinned = build_adventureworks_twin(aw_tables(), created_at=CREATED_AT, twin_version="aw_import_7")
    assert pinned.version.twin_version == "aw_import_7"


def test_tables_and_created_at_are_required():
    with pytest.raises(TypeError):
        build_adventureworks_twin(aw_tables())  # type: ignore[call-arg]
    tables = aw_tables()
    del tables["WorkOrder.csv"]
    with pytest.raises(ValueError, match="WorkOrder.csv"):
        build_adventureworks_twin(tables, created_at=CREATED_AT)


def test_the_twin_is_built_from_the_rows():
    twin = build_adventureworks_twin(aw_tables(), created_at=CREATED_AT)
    ids = {e.id for e in twin.entities}
    assert {"dept_production", "vendor_aw_1492", "vendor_aw_1494", "vendor_aw_1496", "wf_aw_make_bikes",
            "wf_aw_make_components", "sys_aw_location_10", "kpi_aw_sales"} <= ids
    production = next(p for p in twin.department_profiles if p.department_id == "dept_production")
    assert production.staffing.actual_fte == 2  # the ended Quality Assurance assignment is not counted
    # Employee 5's latest rate (25.00) is annualized at 2,080 hours.
    assert next(e for e in twin.entities if e.id == "role_aw_7_production_supervisor").annual_cost_usd == 52000
    assert twin.organization.total_headcount_fte == 10
    assert twin.pressures == [] and not any(e.type.value in {"control", "dataset"} for e in twin.entities)
    # Derived profile fields are build_twin's job, not the importer's.
    assert production.owned_entity_ids == [] and production.critical_workflow_ids == []


def test_build_twin_rejects_the_adventureworks_twin_on_data_rules():
    """build_twin raises on the importer's output; the rules it breaks are pinned here (finding for B-01)."""
    twin = build_adventureworks_twin(aw_tables(), created_at=CREATED_AT)
    with pytest.raises(company_twin.TwinValidationError) as raised:
        build_twin(twin.model_dump(mode="json"))
    errors = raised.value.issues
    assert errors == [i for i in validate_twin(twin) if i.severity == "error"]
    assert {i.rule for i in errors} == {1, 19}
    missing = {i.message.split("missing required field ")[1] for i in errors if i.rule == 1}
    assert missing == {"migration_cost_usd", "geographies", "history_years", "freshness_days", "accuracy",
                       "permitted_uses", "failure_cost_per_day_usd", "time_to_train_days"}
    assert all("checksum_sha256" in i.message for i in errors if i.rule == 19)
