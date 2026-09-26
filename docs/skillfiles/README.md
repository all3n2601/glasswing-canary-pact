# Department Skillfiles + Data Brainstorm

**What this folder is.** A *skillfile* is one department agent's defense pack: everything it needs to
(a) see its slice of the company twin, (b) argue — with evidence — why a proposed cut is safe or
dangerous, and (c) return a structured `DepartmentAssessment` the deterministic engine can trust.

These are the design source for the LangGraph department agents in
`packages/agent-orchestration`. They reference real IDs from `data/synthetic_company.json`
(Halcyon Freight). The agent **reasons and cites evidence; it never computes authoritative
numbers** — every figure comes from the simulation engine tool `run_quick_impact`.

**The four decisions every agent is arguing about (the demo):**

| # | Intervention | Naive view | Hidden blast radius (what a skillfile surfaces) |
|---|---|---|---|
| 1 | `reduce dept_platform 20%` | "save ~$180K on infra ops" | billing-recon loses its only 2 knowledge holders → invoicing breaks → revenue + SLA |
| 2 | `remove vendor_sentinelaudit` | "save $300K, low seat use" | audit-log stream gone → SOC 2 CC7.2 fails → audit exposure + remediation |
| 3 | `stop proj_warehouse_migration` | "save $400K project" | legacy warehouse keeps running → $400K/yr carry cost → saving reversed |
| 4 | `reduce dept_eng 20%` | "save ~$460K labor" | critical maintenance slows → incident risk → delivery slips → customer impact |

---

## High-level data inventory — everything the plan needs

Grouped by who owns it and where it lives. ✅ = exists in the fixture today. ⬜ = still to add.

### A. Twin structural data — `packages/company-twin` / `data/`
- ✅ **Entities** by kind: department, (team), person(token), vendor, dataset, system, workflow, knowledge, document, control, project, kpi.
- ✅ **Dependencies**: typed, directed edges (`MAINTAINS`, `KNOWS`, `POWERS`, `PROVIDES`, `REQUIRES_CONTROL`, `REPLACES`, `CONTRIBUTES_TO`, …) with `importance / substitutability / confidence`.
- ⬜ **`lag_days` per edge** (when an effect shows up) — needed for the 12-month curve.
- ⬜ **Evidence table** (`id`, `source`, `snippet`) + `evidence_ids[]` on edges — provenance backbone.

### B. Financial coefficients — per entity, in `metadata`
- ✅ `annual_cost` (vendors, systems, projects, dept budgets), `transition_cost`, `cancel_cost`.
- ✅ `carry_cost_if_halted_usd` (legacy warehouse = $400K), `revenue_linked_usd`.
- ⬜ per-person / per-capacity cost for `reduce N%` interventions (salaries exist; need the % → $ rule).

### C. Rebound / value-leakage coefficients — engine assumptions (label them synthetic!)
- ⬜ Boomerang rehire **probability** + **premium** (e.g. 55% @ +25–120%).
- ⬜ Orphan-system **incident rate** (λ/quarter) and **MTTR multiplier** without owners.
- ⬜ **Realisation rate** (share of capacity loss that becomes revenue loss, ≈0.6).
- ⬜ **SLA penalty** rates and **control-remediation** cost per failed control.

### D. Ownership / knowledge data — the "stranded" mechanic
- ✅ Person tokens with `KNOWS` / `BACKS_UP` edges, `bus_factor`, `documented`, `time_to_hire`.
- ✅ Workflow `min_owners` / criticality / RTO. ⬜ formal `OwnershipChange` before/after computation.

### E. Constraint definitions — `ScenarioRequest.constraints`
- ⬜ `protected_entity_ids` (e.g. `ctl_cc72_audit`), `compliance_coverage = 1.0`,
  `max_revenue_impact_pct`, `max_customer_impact_pct`, `savings_target = 2_000_000`.

### F. Evidence artifacts — `data/artifacts/` (also feed the extraction proof)
- ⬜ Synthetic source docs: vendor contracts, on-call rota CSV, CODEOWNERS, SOC 2 control register,
  data-catalog lineage export, incident post-mortems, PMO project charters.
- ⬜ **Ground-truth graph** (`data/ground_truth_graph.json`) for precision/recall/F1 of extraction.

### G. Scenario & intervention data
- ⬜ The 4 interventions (type = remove/reduce/stop, `reduction_pct`, `start_day`).
- ⬜ Naive plan vs candidate set for the 2ⁿ optimizer (4 decisions → 16 portfolios).

### H. Mitigation catalog — fixed cost + duration (engine-owned, agents only *pick*)
- ⬜ `reassign_owner`, `document_runbook`, `reassign_on_call`, `replace_vendor`, `resequence_project`
  — each maps to a graph edit; cost/duration come from a table, **not** the agent.

### I. KPI baselines & thresholds
- ✅ 6 KPIs exist. ⬜ current baseline values + tolerance bands per KPI.

### J. Engine control data
- ⬜ `relationship → blast dimension` map (ownership/technical/operational/business/compliance/financial).
- ⬜ Savings ramp + 12-month bucket rules; deterministic seed for reproducible replay.

### K. Replay / demo safety — `cache/`
- ⬜ `golden_run.json` (full event stream) + cached LLM outputs so the demo runs offline.

### L. Agent skill/defense data — **this folder**
- ✅/⬜ One skillfile per department (below) + challenger.

---

## Skillfile index

| Domain | File | Role in the demo |
|---|---|---|
| Finance / FP&A | [`finance.md`](finance.md) | Sets the $2M target; catches displaced/rebound costs |
| Engineering & Product | [`engineering.md`](engineering.md) | Defends core systems; decision 4 target |
| Platform / Infra Ops | [`platform-ops.md`](platform-ops.md) | **Holds the billing-recon trap**; decision 1 target |
| AI / Data | [`ai-data.md`](ai-data.md) | Data lineage; warehouse cutover knowledge |
| Sales & Marketing | [`sales.md`](sales.md) | Pipeline/NRR; concedes redundant enrichment vendor |
| Customer Success | [`customer-success.md`](customer-success.md) | Churn/SLA voice; downstream of billing + incidents |
| Risk / Compliance / Security | [`risk-compliance.md`](risk-compliance.md) | **Holds the SOC 2 trap**; owns hard constraints; decision 2 |
| PMO / Transformation | [`pmo.md`](pmo.md) | **Holds the migration carry-cost trap**; decision 3 |
| Procurement / Vendor Mgmt | [`procurement.md`](procurement.md) | Vendor terms, substitutability, transition costs |
| Challenger (meta) | [`challenger.md`](challenger.md) | Finds missed deps, optimism, unsafe combinations |

**Shared output contract** every agent returns (`DepartmentAssessment`): `department_id`,
`scenario_id`, `status` (live/replayed/unavailable), `affected_entity_ids` (must exist in twin),
`failure_modes`, `edge_cases`, `assumptions`, `questions`, `evidence_ids`, `confidence`.

**Shared tools** every agent may call (read-only except submit): `get_entity(id)`,
`list_dependencies(id, direction)`, `get_evidence(edge_id)`, `run_quick_impact(interventions)`,
`what_if_not(plan_id, entity_id)`, `submit_assessment(assessment)`.
