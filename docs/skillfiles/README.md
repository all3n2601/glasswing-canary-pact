# Department Skillfiles

Design source for the LangGraph department agents (`packages/agent-orchestration`). One file per
agent, named `<agent_id>.md`, matching the schema v2.1 agent roster (`contracts.CORE_AGENT_IDS`).

**Conventions (per Member C):**
- Named by **agent_id**: `finance, engineering, ai_data, operations, product, marketing, sales,
  customer_success, compliance, people_knowledge` + `challenger`.
- Entity references use the canonical ids from `data/id_registry.json` (Northstar Technologies).
- **No output-format section** (the harness supplies the `AgentOutput` shape), **no dollar figures**
  (the engine supplies numbers), and **no person-token ids** (roles only; the decision-package guard
  rejects `pt_` ids). Each file is pure domain content.

## Roster

| agent_id | file | Role in the demo |
|---|---|---|
| finance | [finance.md](finance.md) | savings target; vendor contracts; financial-close strand |
| engineering | [engineering.md](engineering.md) | Core systems + reliability |
| ai_data | [ai_data.md](ai_data.md) | Data lineage; proves vendor uniqueness vs redundancy |
| operations | [operations.md](operations.md) | Billing-recon strand; hidden account-intel dependency |
| product | [product.md](product.md) | Owns EchoMarket + FluxBehavior; account-intel migration |
| marketing | [marketing.md](marketing.md) | CinderSignals intent data; segmentation |
| sales | [sales.md](sales.md) | ApexData (keep) vs BeaconIQ (safe cut); account planning |
| customer_success | [customer_success.md](customer_success.md) | Churn/SLA voice; second-order impact |
| compliance | [compliance.md](compliance.md) | DeltaVerify + mandatory controls (hard constraints) |
| people_knowledge | [people_knowledge.md](people_knowledge.md) | Backup coverage, bus factor, the workforce proof |
| challenger | [challenger.md](challenger.md) | Audits the plan; finds the account-intel planted dependency |

## The two demo scenarios (master plan)
1. **Vendor consolidation** - 7 data vendors, cut to the savings target, all 128 keep/remove portfolios.
   Recommended: remove **BeaconIQ** (redundant with ApexData) and **EchoMarket** (migrate its unique
   `ds_account_intel` first); keep **DeltaVerify** (compliance-critical). Naive "cut the priciest"
   loses unique coverage.
2. **Workforce knowledge loss** - removing eight roles strands exactly two workflows
   (`wf_financial_close` and `wf_billing_recon`); a mitigation (document, train a backup) restores coverage.

Planted challenger dependency + hidden costs: `data/planted_items.json`.

## Data the agents read (Person 1 outputs)
- `data/synthetic_company.json` - the twin (entities, edges, pressures, documents, evidence, profiles)
- `data/vendor_overlap.json` - per-vendor overlap, unique coverage, required-field coverage
- `data/knowledge_map.json` - knowledge -> holder roles -> workflow, bus factor, stranding risk
- `data/graph_snapshot.json` - nodes + edges for the graph view (person tokens shown as roles)
- `data/id_registry.json` - canonical entity ids
