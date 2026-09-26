"""Company-twin domain models.

Single source of truth: the shared contract package ``contracts_py`` (schema v2.1).
company-twin, simulation-engine and the API now all use the SAME Entity/Edge/Twin
classes. This module only re-exports them (plus backward-compat aliases and an
``entity_map`` helper, since ``Twin`` has no such method).
"""

from __future__ import annotations

from contracts_py.twin import (
    ChannelKind,
    Criticality,
    DepartmentBudget,
    DepartmentProfile,
    DepartmentStrength,
    Document,
    Edge,
    Entity,
    EntityType,
    Evidence,
    NeutraliserRef,
    Organization,
    Pressure,
    PressureKind,
    Relation,
    Sensitivity,
    StaffingStrength,
    StrategicPriority,
    Twin,
    VersionInfo,
)

# Backward-compat aliases (pre-unification names used across this package).
CompanyTwin = Twin
EntityKind = EntityType


def entity_map(twin: Twin) -> dict[str, Entity]:
    """id -> Entity. contracts_py.Twin has no method for this, so we provide one."""
    return {e.id: e for e in twin.entities}


__all__ = [
    "Twin",
    "CompanyTwin",
    "Entity",
    "Edge",
    "EntityType",
    "EntityKind",
    "Relation",
    "ChannelKind",
    "Criticality",
    "Sensitivity",
    "PressureKind",
    "Pressure",
    "NeutraliserRef",
    "Organization",
    "StrategicPriority",
    "DepartmentProfile",
    "DepartmentBudget",
    "DepartmentStrength",
    "StaffingStrength",
    "Document",
    "Evidence",
    "VersionInfo",
    "entity_map",
]
