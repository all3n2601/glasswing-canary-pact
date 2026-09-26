from .graph import build_graph, downstream_paths
from .loader import load_company_twin
from .models import (
    CompanyTwin,
    Edge,
    Entity,
    EntityType,
    Organization,
    Pressure,
    Relation,
    Twin,
)

# Backward-compat alias during the v2 migration: simulation-engine / agent-orchestration
# still import `EntityKind`. Remove once those packages migrate to `EntityType`.
EntityKind = EntityType

__all__ = [
    "CompanyTwin",
    "Twin",
    "Entity",
    "EntityType",
    "EntityKind",
    "Edge",
    "Relation",
    "Organization",
    "Pressure",
    "build_graph",
    "downstream_paths",
    "load_company_twin",
]
