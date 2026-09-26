"""Vendor overlap + unique-coverage + required-field-coverage (Person 1 output).

Produces data/vendor_overlap.json for the primary demo (7 data vendors, $8B spend,
$2B cut). This is the DATA layer only: the overlap matrix, each vendor's unique value,
required-field coverage, and substitutability. The 128-portfolio optimisation itself is
the engine's job; this file gives it the inputs and records the expected recommendation.

Deterministic, standard-library only.  Run:  python3 data/vendor_overlap.py

Source: master implementation plan, synthetic vendor portfolio (all figures synthetic,
whole US dollars at $B scale). Vendor ids follow the v2 `vendor_` convention and will be
reconciled against data/id_registry.json when published.
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any

SAVINGS_TARGET_USD = 2_000_000_000  # cut at least $2B from $8B

# id, name, annual_cost_usd, consumers, critical (compliance), data fields provided,
# geo coverage set, freshness (0-1), accuracy (0-1)
VENDORS: list[dict[str, Any]] = [
    {
        "id": "vendor_apex", "name": "ApexData", "annual_cost_usd": 1_600_000_000,
        "consumers": ["dept_sales", "dept_marketing"], "critical": False,
        "fields": {"company_name", "company_domain", "company_size", "industry",
                   "contact_name", "contact_title", "contact_email", "contact_phone"},
        "geo": {"na", "emea", "apac", "latam"}, "freshness": 0.85, "accuracy": 0.90,
        "note": "Global company and contact attributes; broadest, high company-wide marginal value.",
    },
    {
        "id": "vendor_beacon", "name": "BeaconIQ", "annual_cost_usd": 1_200_000_000,
        "consumers": ["dept_sales"], "critical": False,
        "fields": {"company_name", "company_domain", "company_size", "industry",
                   "contact_name", "contact_title", "contact_email"},
        "geo": {"na", "emea"}, "freshness": 0.80, "accuracy": 0.86,
        "note": "Contact enrichment and firmographics; heavily overlaps Apex.",
    },
    {
        "id": "vendor_cinder", "name": "CinderSignals", "annual_cost_usd": 1_400_000_000,
        "consumers": ["dept_marketing", "dept_sales"], "critical": False,
        "fields": {"intent_topic", "intent_score", "surge_signal", "buying_stage",
                   "company_domain", "industry"},
        "geo": {"na", "emea", "apac"}, "freshness": 0.92, "accuracy": 0.83,
        "note": "Purchase-intent signals; overlaps Echo on market signals.",
    },
    {
        "id": "vendor_delta", "name": "DeltaVerify", "annual_cost_usd": 900_000_000,
        "consumers": ["dept_compliance"], "critical": True,
        "fields": {"identity_verified", "kyc_status", "sanctions_flag", "beneficial_owner",
                   "compliance_score"},
        "geo": {"na", "emea", "apac", "latam"}, "freshness": 0.88, "accuracy": 0.97,
        "note": "Identity and compliance verification; low overlap, mandatory for controls.",
    },
    {
        "id": "vendor_echo", "name": "EchoMarket", "annual_cost_usd": 1_100_000_000,
        "consumers": ["dept_product", "dept_marketing"], "critical": False,
        "fields": {"market_size", "account_intel", "competitor_map", "intent_topic",
                   "company_domain", "industry"},
        "geo": {"na", "emea"}, "freshness": 0.78, "accuracy": 0.82,
        "note": "Market and account intelligence; overlaps Apex (company) and Cinder (intent).",
    },
    {
        "id": "vendor_flux", "name": "FluxBehavior", "annual_cost_usd": 800_000_000,
        "consumers": ["dept_product", "dept_ai_data"], "critical": False,
        "fields": {"product_usage", "feature_adoption", "session_behavior", "churn_signal"},
        "geo": {"na", "emea", "apac"}, "freshness": 0.95, "accuracy": 0.88,
        "note": "Behavioural and product-usage signals; unique, low overlap.",
    },
    {
        "id": "vendor_granite", "name": "GraniteGeo", "annual_cost_usd": 1_000_000_000,
        "consumers": ["dept_operations", "dept_compliance"], "critical": False,
        "fields": {"geo_risk", "macro_indicator", "region_stability", "supply_risk",
                   "compliance_score"},
        "geo": {"na", "emea", "apac", "latam"}, "freshness": 0.83, "accuracy": 0.9,
        "note": "Geographic and macroeconomic risk; small overlap with Delta on compliance_score.",
    },
]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return round(len(a & b) / len(a | b), 3)


def compute() -> dict[str, Any]:
    by_id = {v["id"]: v for v in VENDORS}
    ids = [v["id"] for v in VENDORS]

    # pairwise overlap across fields and geography
    pairwise = []
    for a, b in combinations(ids, 2):
        va, vb = by_id[a], by_id[b]
        field_ov = _jaccard(va["fields"], vb["fields"])
        geo_ov = _jaccard(va["geo"], vb["geo"])
        pairwise.append({
            "a": a, "b": b,
            "field_overlap": field_ov,
            "geo_overlap": geo_ov,
            "shared_fields": sorted(va["fields"] & vb["fields"]),
        })

    # per-vendor unique coverage, substitutability, and unique-value
    all_other_fields = {v["id"]: set().union(*[o["fields"] for o in VENDORS if o["id"] != v["id"]])
                        for v in VENDORS}
    vendors_out = []
    for v in VENDORS:
        unique_fields = sorted(v["fields"] - all_other_fields[v["id"]])
        # substitutability = best field-overlap with any other vendor (1 = fully replaceable)
        subst = max((_jaccard(v["fields"], o["fields"]) for o in VENDORS if o["id"] != v["id"]),
                    default=0.0)
        # dominated_by = other single vendors whose fields fully contain this vendor's
        # (i.e. this vendor is fully redundant given that one -> the clean, safe cut)
        dominated_by = [o["id"] for o in VENDORS
                        if o["id"] != v["id"] and v["fields"] <= o["fields"]]
        vendors_out.append({
            "id": v["id"], "name": v["name"], "annual_cost_usd": v["annual_cost_usd"],
            "consumers": v["consumers"], "critical": v["critical"],
            "field_count": len(v["fields"]),
            "unique_fields": unique_fields,
            "unique_field_count": len(unique_fields),
            "substitutability": round(subst, 3),
            "dominated_by": dominated_by,
            "freshness": v["freshness"], "accuracy": v["accuracy"],
            "note": v["note"],
        })

    # required-field coverage: a field is "covered" if any KEPT vendor still provides it
    def coverage_if_removed(removed: set[str]) -> dict[str, Any]:
        kept_fields: set[str] = set().union(
            *[v["fields"] for v in VENDORS if v["id"] not in removed]) if len(removed) < len(VENDORS) else set()
        all_fields: set[str] = set().union(*[v["fields"] for v in VENDORS])
        lost = sorted(all_fields - kept_fields)
        breaks_compliance = any(by_id[r]["critical"] for r in removed)
        savings = sum(by_id[r]["annual_cost_usd"] for r in removed)
        return {
            "removed": sorted(removed), "gross_savings_usd": savings,
            "meets_target": savings >= SAVINGS_TARGET_USD,
            "required_field_coverage_pct": round(len(kept_fields) / len(all_fields) * 100, 1),
            "lost_fields": lost,                       # unique fields that would be dropped
            "fields_to_migrate": lost,                 # migrate these before termination
            "breaks_compliance": breaks_compliance,
            "feasible_pure_removal": savings >= SAVINGS_TARGET_USD and not lost and not breaks_compliance,
            # feasible once the unique fields are migrated and no mandatory control is broken
            "feasible_after_migration": savings >= SAVINGS_TARGET_USD and not breaks_compliance,
        }

    # expected recommendation: remove the two lowest-unique, highest-overlap non-critical vendors
    recommended = {"vendor_beacon", "vendor_echo"}
    naive = {"vendor_apex", "vendor_cinder"}  # cut the two most expensive -> loses unique value
    return {
        "note": "Synthetic. Overlap DATA for the vendor-consolidation demo; the 128-portfolio "
                "optimisation is the engine's job. Vendor ids reconcile to id_registry.json.",
        "savings_target_usd": SAVINGS_TARGET_USD,
        "total_annual_spend_usd": sum(v["annual_cost_usd"] for v in VENDORS),
        "vendors": vendors_out,
        "pairwise_overlap": pairwise,
        "expected_recommended_plan": coverage_if_removed(recommended),
        "naive_plan": coverage_if_removed(naive),
    }


def main() -> None:
    data = compute()
    out = Path(__file__).resolve().parent / "vendor_overlap.json"
    out.write_text(json.dumps(data, indent=2) + "\n")
    rec = data["expected_recommended_plan"]
    print(f"Wrote {out}")
    print(f"  total spend ${data['total_annual_spend_usd']:,}  target ${data['savings_target_usd']:,}")
    print(f"  recommended remove {rec['removed']}: save ${rec['gross_savings_usd']:,}, "
          f"coverage {rec['required_field_coverage_pct']}%, migrate {rec['fields_to_migrate']}, "
          f"feasible_after_migration={rec['feasible_after_migration']}")
    n = data["naive_plan"]
    print(f"  naive remove {n['removed']}: save ${n['gross_savings_usd']:,}, "
          f"coverage {n['required_field_coverage_pct']}%, lost_fields={len(n['lost_fields'])}")


if __name__ == "__main__":
    main()
