"""Multi-dimensional vendor overlap (plan C-02, section 4.1; schema v2.2.0 section 7.14).

Every vendor pair is compared on the plan's 11 dimensions, each in [0, 1]:

- record_coverage: strength-weighted Jaccard of the datasets each vendor PROVIDES.
- attribute_coverage: Jaccard of those datasets' ``attribute_group`` values.
- geography: Jaccard of ``geographies``.
- history_depth: ``1 - |history_years_a - history_years_b| / max``.
- freshness: ``1 - |freshness_days_a - freshness_days_b| / max``.
- accuracy: ``1 - |accuracy_a - accuracy_b|``.
- permitted_use: Jaccard of ``permitted_uses``.
- consumer_teams: Jaccard of the departments owning the workflows that consume their datasets.
- downstream_workflows: Jaccard of the workflows that consume their datasets.
- model_features: Jaccard of the ``ml_model``-tagged systems that consume their datasets.
- substitutability: mean ``substitutability`` of both vendors' PROVIDES edges on shared datasets,
  scaled down by ``MIGRATION_FACTOR[migration_difficulty]``.

A numeric dimension with a missing value on either side scores 0: no evidence of overlap.

``OVERLAP_WEIGHTS`` sets ``overall_overlap``. Record coverage alone is deliberately a small share,
so two vendors are not called substitutes merely because they cover the same accounts: fields,
permitted use, downstream consumers, and substitutability carry most of the weight.

A vendor's unique datasets are those it PROVIDES and no other provider in the twin does; they
drive migration difficulty and ``unique_contribution``.
"""

from __future__ import annotations

from itertools import combinations

from contracts_py.engine import VendorOverlap
from contracts_py.enums import Criticality, EntityType, MigrationDifficulty, OverlapDimension, Relation
from contracts_py.twin import Entity, Twin

from company_twin import entity_map

OVERLAP_WEIGHTS: dict[OverlapDimension, float] = {
    OverlapDimension.record_coverage: 0.10,
    OverlapDimension.attribute_coverage: 0.15,
    OverlapDimension.geography: 0.05,
    OverlapDimension.history_depth: 0.05,
    OverlapDimension.freshness: 0.05,
    OverlapDimension.accuracy: 0.05,
    OverlapDimension.permitted_use: 0.10,
    OverlapDimension.consumer_teams: 0.10,
    OverlapDimension.downstream_workflows: 0.10,
    OverlapDimension.model_features: 0.05,
    OverlapDimension.substitutability: 0.20,
}

MIGRATION_FACTOR = {MigrationDifficulty.low: 1.0, MigrationDifficulty.medium: 0.75, MigrationDifficulty.high: 0.5}
CRITICALITY_WEIGHT = {Criticality.low: 0.25, Criticality.medium: 0.5, Criticality.high: 0.75, Criticality.critical: 1.0}
ML_MODEL_TAG = "ml_model"


def _jaccard(a: set, b: set) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _closeness(a: float | None, b: float | None, *, scale: bool) -> float:
    if a is None or b is None:
        return 0.0
    if not scale:
        return 1 - abs(a - b)
    top = max(abs(a), abs(b))
    return 1.0 if top == 0 else 1 - abs(a - b) / top


class _Supply:
    """Who provides each dataset and who consumes it, read once from the twin."""

    def __init__(self, twin: Twin) -> None:
        self.ents = entity_map(twin)
        self.provides: dict[str, dict[str, tuple[float, float]]] = {}
        self.providers: dict[str, set[str]] = {}
        self.consumers: dict[str, set[str]] = {}
        for e in twin.edges:
            if e.relation is Relation.PROVIDES and self.ents[e.target].type is EntityType.dataset:
                self.provides.setdefault(e.source, {})[e.target] = (e.strength, e.substitutability)
                self.providers.setdefault(e.target, set()).add(e.source)
            elif e.relation is Relation.CONSUMES and self.ents[e.source].type is EntityType.dataset:
                self.consumers.setdefault(e.source, set()).add(e.target)

    def datasets(self, vendor_id: str) -> dict[str, tuple[float, float]]:
        return self.provides.get(vendor_id, {})

    def unique(self, vendor_id: str) -> list[str]:
        return sorted(d for d in self.datasets(vendor_id) if self.providers[d] == {vendor_id})

    def groups(self, dataset_ids: dict[str, tuple[float, float]]) -> set[str]:
        return {self.ents[d].attribute_group or d for d in dataset_ids}

    def teams(self, workflow_ids: set[str]) -> set[str]:
        departments = (self.ents[w].department_id for w in workflow_ids)
        return {d for d in departments if d is not None}

    def downstream(self, vendor_id: str, kind: EntityType, tag: str | None = None) -> set[str]:
        out = set()
        for d in self.datasets(vendor_id):
            for c in self.consumers.get(d, ()):
                entity = self.ents[c]
                if entity.type is kind and (tag is None or tag in entity.tags):
                    out.add(c)
        return out


def _migration_difficulty(supply: _Supply, unique_ids: list[str]) -> MigrationDifficulty:
    datasets = [supply.ents[d] for d in unique_ids]
    if any(d.criticality is Criticality.critical for d in datasets):
        return MigrationDifficulty.high
    consumers = set().union(*(supply.consumers.get(d, set()) for d in unique_ids)) if unique_ids else set()
    if any(d.criticality is Criticality.high for d in datasets) or len(consumers) >= 3:
        return MigrationDifficulty.medium
    return MigrationDifficulty.low


def _pair(supply: _Supply, a: Entity, b: Entity) -> VendorOverlap:
    da, db = supply.datasets(a.id), supply.datasets(b.id)
    union = set(da) | set(db)
    shared = sorted(set(da) & set(db))
    weighted = sum(max(da.get(d, (0, 0))[0], db.get(d, (0, 0))[0]) for d in union)
    record = sum(min(da.get(d, (0, 0))[0], db.get(d, (0, 0))[0]) for d in union) / weighted if weighted else 0.0
    unique_a, unique_b = supply.unique(a.id), supply.unique(b.id)
    difficulty = _migration_difficulty(supply, sorted({*unique_a, *unique_b}))
    subs = [da[d][1] for d in shared] + [db[d][1] for d in shared]
    workflows_a = supply.downstream(a.id, EntityType.workflow)
    workflows_b = supply.downstream(b.id, EntityType.workflow)

    dims = {
        OverlapDimension.record_coverage: record,
        OverlapDimension.attribute_coverage: _jaccard(supply.groups(da), supply.groups(db)),
        OverlapDimension.geography: _jaccard(set(a.geographies), set(b.geographies)),
        OverlapDimension.history_depth: _closeness(a.history_years, b.history_years, scale=True),
        OverlapDimension.freshness: _closeness(a.freshness_days, b.freshness_days, scale=True),
        OverlapDimension.accuracy: _closeness(a.accuracy, b.accuracy, scale=False),
        OverlapDimension.permitted_use: _jaccard(set(a.permitted_uses), set(b.permitted_uses)),
        OverlapDimension.consumer_teams: _jaccard(supply.teams(workflows_a), supply.teams(workflows_b)),
        OverlapDimension.downstream_workflows: _jaccard(workflows_a, workflows_b),
        OverlapDimension.model_features: _jaccard(supply.downstream(a.id, EntityType.system, ML_MODEL_TAG),
                                                  supply.downstream(b.id, EntityType.system, ML_MODEL_TAG)),
        OverlapDimension.substitutability: (sum(subs) / len(subs)) * MIGRATION_FACTOR[difficulty] if subs else 0.0,
    }
    dims = {k: round(min(1.0, max(0.0, v)), 6) for k, v in dims.items()}
    overall = round(sum(OVERLAP_WEIGHTS[k] * v for k, v in dims.items()), 6)
    return VendorOverlap(
        vendor_a=a.id, vendor_b=b.id, dimensions=dims, overall_overlap=min(1.0, overall),
        shared_dataset_ids=shared, unique_dataset_ids_a=unique_a, unique_dataset_ids_b=unique_b,
        migration_difficulty=difficulty,
    )


def vendor_overlap(twin: Twin, vendor_ids: list[str]) -> list[VendorOverlap]:
    """One ``VendorOverlap`` per unordered pair of ``vendor_ids``, ``vendor_a < vendor_b``, sorted by pair."""
    supply = _Supply(twin)
    vendors = []
    for vendor_id in sorted(set(vendor_ids)):
        entity = supply.ents.get(vendor_id)
        if entity is None or entity.type is not EntityType.vendor:
            raise ValueError(f"{vendor_id} is not a vendor in the twin")
        vendors.append(entity)
    return [_pair(supply, a, b) for a, b in combinations(vendors, 2)]


def unique_contribution(twin: Twin, vendor_id: str) -> float:
    """Criticality-weighted coverage a vendor alone supplies: what the company loses if it goes.

    For each dataset the vendor PROVIDES, the share of coverage no other provider supplies
    (schema 7.14 unique value, plan 4.1 marginal value), weighted by the dataset's criticality.
    """
    supply = _Supply(twin)
    total = 0.0
    for dataset_id, (strength, _) in supply.datasets(vendor_id).items():
        others = 1.0
        for provider in supply.providers[dataset_id] - {vendor_id}:
            others *= 1 - supply.datasets(provider)[dataset_id][0]
        covered = 1 - others * (1 - strength)
        without = 1 - others
        share = (covered - without) / covered if covered else 0.0
        total += share * CRITICALITY_WEIGHT[supply.ents[dataset_id].criticality]
    return round(total, 6)
