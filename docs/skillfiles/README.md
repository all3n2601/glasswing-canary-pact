# Department Skillfiles

Design source for the LangGraph department agents (`packages/agent-orchestration`). One file per
agent, named `<agent_id>.md`, matching the schema v2 agent roster.

**Conventions (per Member C):**
- Files are named by **agent_id** (schema §8.1): `finance, engineering, ai_data, operations, product,
  marketing, sales, customer_success, compliance` + `challenger`.
- Entity references use twin IDs. These will be **swept to `data/id_registry.json`** once Adhi
  publishes it (16:00); until then they match `data/synthetic_company.json`.
- **No output-format section** (the harness supplies the `AgentOutput` shape) and **no dollar
  figures** (the simulation engine supplies all numbers). Each file is pure domain content:
  what the agent represents/protects, what it owns, the hidden dependencies it uniquely knows,
  failure modes, negotiation posture, and the evidence it can cite.

## Roster

| agent_id | file | Role in the demo |
|---|---|---|
| finance | [finance.md](finance.md) | Target + net-vs-gross; owns vendor contracts (procurement folds in) |
| engineering | [engineering.md](engineering.md) | Core systems; **Decision 4** target |
| ai_data | [ai_data.md](ai_data.md) | Data lineage; migration cutover; overlap analysis |
| operations | [operations.md](operations.md) | **Decision 1** target; holds the billing-recon trap (Platform Ops folds in) |
| product | [product.md](product.md) | **Decision 3** target; migration carry-cost trap (PMO folds in) |
| marketing | [marketing.md](marketing.md) | Segmentation/pipeline; redundant enrichment vendor |
| sales | [sales.md](sales.md) | Enterprise renewals; downstream of billing |
| customer_success | [customer_success.md](customer_success.md) | Churn/SLA voice; second-order customer impact |
| compliance | [compliance.md](compliance.md) | **Decision 2** feed; SOC 2/PCI hard constraints |
| challenger | [challenger.md](challenger.md) | Audits the plan; finds the planted cross-domain dependency |

## The four demo decisions
1. reduce `dept_operations` → billing reconciliation stranded
2. remove `vendor_auditlog` → SOC 2 CC7.2 broken
3. stop `proj_warehouse_migration` → legacy carry cost (rebound)
4. reduce `dept_engineering` → core-api maintenance → uptime SLA

Planted challenger find + hidden costs: `data/planted_items.json`.

## Data the agents read (produced by Person 1)
- `data/synthetic_company.json` - the twin (entities, edges, pressures, documents, evidence, profiles)
- `data/knowledge_map.json` - person→knowledge→workflow, bus factor, stranding risk
- `data/vendor_report.json` - per-vendor consumers, substitutability, coverage, replacement
- `data/graph_snapshot.json` - nodes + edges for the graph view
- `data/planted_items.json` - the challenger's missed dependency + hidden costs
