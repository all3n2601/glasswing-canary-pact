# Canary Pact — Merged Schema v2.0 (24-hour build)

Merges **Canary Pact Frozen Schema v1** (the vision: futures, generic decisions, claim validation, events) with the **Glasswing schema proposal** (the discipline: lean entities, three-function engine seam, naive-vs-recommended portfolios, rebound curve). It adds the one piece neither had: **baseline pressures**, which make the "what happens if we don't act" future real.

Implementation target: Pydantic v2 models (Python) → exported JSON Schema → TypeScript types for the frontend. Once all four owners sign off (§17), the Pydantic models in the repo become the only source of truth.

### Scope tags used throughout

| Tag | Meaning | Build window |
|---|---|---|
| **[CORE]** | Required for the demo to work end to end | Hours 0–14 |
| **[T2]** | Makes the demo strong; build after the H14 checkpoint | Hours 14–19 |
| **[STRETCH]** | Only if everything else is frozen and working | Hours 19+ |

Every model and field is **[CORE]** unless tagged otherwise. [T2]/[STRETCH] models must still exist as empty/optional fields from hour 0, so adding them later never changes a contract.

---

## 1. Rules the schema must obey

1. **Agents reason, the engine calculates, humans decide.** Every number (savings, costs, risk, net value, probabilities) is computed only in `simulation-engine`. Agent-supplied magnitudes are display-only.
2. **Every decision has at least two futures: acting and not acting.** Inaction is never "free"; it carries the cost of the pressures that keep running (§4.7).
3. **People are anonymized tokens** (`pt_07`). Outputs speak about roles and workflows, never "remove person X". The decision package is rejected if any `pt_` ID appears in it.
4. **Stable IDs everywhere.** Never match on names.
5. **Every live LLM call has a cached replay**, so the demo runs offline.
6. **The model is configurable.** Nothing in the schema depends on a specific LLM provider; `model_id` is recorded, not assumed.
7. **The financial scenario is an example, not the product.** Decision types, goals, and interventions are generic (§3, §5).

---

## 2. Global conventions (from Canary)

| Rule | Detail |
|---|---|
| IDs | lowercase `snake_case`, regex `^[a-z][a-z0-9_]*$`, max 80 chars |
| ID prefixes | `dept_`, `pt_` person token, `role_`, `kn_` knowledge, `sys_`, `vendor_`, `proj_`, `wf_` workflow, `ctl_` control, `kpi_`, `ds_` dataset, `seg_` customer segment, `pr_` pressure, `org_` organization, `doc_` document, `str_` department strength, `gap_` department gap, `set_` settings, `preset_` sector preset, `ch_` channel edge, `e_` other edge, `ev_` evidence, `dec_`, `plan_`, `scn_`, `imp_`, `res_`, `cmp_`, `q_`, `evt_`, `run_`, `pkg_` |
| Money | whole US dollars as integers (`USD = int`). Never floats, never "in millions" |
| Ratios / probabilities | floats in `[0, 1]` |
| Severity | integer 1–5 (1 negligible, 5 critical) |
| Unknown fields | rejected everywhere (`extra = "forbid"`) |
| Time | wall-clock: UTC ISO-8601. Simulation: integer **days** from decision day 0. The engine steps **monthly** (month = day // 30) for timelines |
| Versioning | every top-level payload carries `schema_version: "2.0.0"` |
| Randomness | every full-mode run carries a `seed`; same seed → identical output |

---

## 3. Resolved decisions (team confirms at hour 0)

These are recommendations that close the open items in both source files. Tick or overrule each one in the first 30 minutes; nothing else can start until they're fixed.

| # | Question | Recommendation | Why |
|---|---|---|---|
| R1 | Department list (Map 1 vs Map 2) | **Map 1's 9 departments.** Map 2's Platform/Infra Ops → `dept_operations`; Procurement's vendor contracts → owned by `dept_finance`; PMO's projects → owned by `dept_product` | Keeps all 23 drawn channels intact; no department exists only for one scenario |
| R2 | Scale ($M vs $B) | **Pick the one your pitch slides already use and apply it everywhere.** Schema is unit-free (integer USD) | Purely a fixture decision; mixing scales is the only real mistake |
| R3 | Demo scenarios | **Primary:** the 4-decision diagram scenario (reduce Platform Ops, remove vendor, stop migration, reduce Engineering) → 16 plans. **Secondary [T2]:** one *non-cost* decision (e.g., "start the automation project or not") to prove generality. **[STRETCH]:** 7 vendors → 128 plans | 16 plans fit the 2ⁿ optimizer instantly; the secondary scenario answers "is this only a cost-cutting tool?" |
| R4 | Goal basis | `basis = "gross"` for the target check; **net value always shown beside it** | Matches how CFOs state targets; net is where the insight is |
| R5 | Naive plan | **"Apply every candidate intervention"** | Easiest to explain on stage |
| R6 | Rebound | **Separate line** `rebound_cost_usd`, first term renamed `gross_savings_usd` | Glasswing's recommendation; keeps the formula honest |
| R7 | Person tokens | **Yes**, with `OWNS`/`BACKS_UP`/`KNOWS` edges | They make "stranded workflow" real rather than asserted |
| R8 | Risk score | **Keep**, 5 components (§6.5), owned by the Engine person | Judges want one comparable number; the components explain it |
| R9 | Monthly curve | **Real 12-month curve** (24 hours is enough) | It's the chart that shows inaction and rebound over time |
| R10 | Mitigations | **6 types** (§4.1), including `resequence_project` and `retain_capacity_temporarily` | Covers every harmful effect in the primary scenario, so no plan is rejected merely for lack of a mitigation type |
| R11 | Drawing paths not in the map | **Add 2 channels:** `ch_sales_marketing_launch` and `ch_operations_compliance_evidence` (§4.9) | The engine can only draw paths that exist in the twin |
| R12 | Agent roster | 9 department agents + `challenger` **[CORE]**; `people_knowledge` **[T2]** | Routing (§7.1) means typically only 5–7 run per scenario |
| R13 | Inaction pressure (planted) | At least **3 pressures** in the fixture: one cost growth, one renewal step-up, one hazard (§4.7) | Without them, inaction looks free and the core pitch collapses |

---

## 4. Enums

| Enum | Values |
|---|---|
| `EntityType` | department, person_token, role, knowledge_asset, system, vendor, project, workflow, control, kpi, customer_segment, dataset |
| `Layer` *(derived from type, never stored)* | people (person_token, role), knowledge, system (system, vendor, dataset), workflow (workflow, project), control, outcome (kpi, customer_segment), org (department) |
| `Relation` | OWNS, BACKS_UP, KNOWS, MAINTAINS, RUNS, PROVIDES, CONSUMES, DEPENDS_ON, SUPPORTS, FUNDS, CONTROLS, CONTRIBUTES_TO, SUBSTITUTES_FOR, **FLOWS_TO** (department channel) |
| `ChannelKind` | constraint, budget, capability, signal, value |
| `Criticality` | low, medium, high, critical |
| `Sensitivity` | general, finance, hr, customer, security |
| `EvidenceSource` | contract, workflow_map, system_ownership, kpi_definition, runbook, architecture_note, activity_log, knowledge_matrix, policy, incident, finance_forecast |
| `DecisionType` | cost_reduction, vendor_consolidation, capacity_change, project_decision, investment, restructure, mixed |
| `InterventionKind` | action, mitigation |
| `ActionType` | remove_vendor, reduce_capacity, **add_capacity**, remove_roles, stop_project, **start_project**, **delay_project**, **invest** |
| `MitigationType` | reassign_owner, document_runbook, reassign_on_call, add_replacement_feed, resequence_project, retain_capacity_temporarily |
| `Future` | act_now, inaction, delay, alternative |
| `PressureKind` | cost_growth, renewal_step, hazard, kpi_drift, budget_ceiling, deadline |
| `ImpactLevel` | direct, dependent, second_order, delayed, feedback |
| `ImpactCategory` | ownership, technical, operational, business, compliance, financial |
| `Polarity` | benefit, harm |
| `Direction` | increase, decrease, no_change |
| `ClaimStatus` | computed, validated, hypothesis, rejected |
| `Origin` | engine, agent, challenger, user |
| `RiskLevel` | low (0–24), medium (25–49), high (50–74), critical (75–100) |
| `Sector` | technology_saas, financial_services, banking, insurance, healthcare, pharma_life_sciences, manufacturing, retail_ecommerce, telecom, energy_utilities, logistics_transport, media_entertainment, professional_services, education, public_sector, nonprofit, other |
| `BusinessModel` | b2b, b2c, b2b2c, marketplace, public_service, mixed |
| `SizeBand` | startup, smb, mid_market, enterprise, large_enterprise |
| `StrengthCategory` | capability, expertise, process, asset, relationship, data |
| `DocumentType` | contract, policy, runbook, sop, architecture_note, org_chart, budget_report, financial_forecast, kpi_report, incident_report, audit_report, workflow_map, knowledge_matrix, meeting_minutes, strategy_memo, other |
| `DocumentStatus` | current, outdated, draft, archived |
| `RiskAppetite` | conservative, balanced, aggressive |
| `RunStatus` | created, validating, building_futures, running_agents, propagating, challenging, optimizing, comparing_futures, mitigating, generating_package, awaiting_approval, completed, failed |

**Added vs Canary v1:** generic decision/action types (`investment`, `restructure`, `add_capacity`, `start_project`, `delay_project`, `invest`), `PressureKind`, `comparing_futures` status. **Removed:** `skill`, `procedure`, `contract`, `data_field`, `model`, `policy`, `organization` entity types (folded into others, as Glasswing did), `ExtractionMethod`, `OverlapDimension`, `Reversibility`, `awaiting_answer` status (only needed for the [STRETCH] question flow).

---

## 5. Company twin (owner: **A — Twin/data**)

### 5.1 `Evidence`

| Field | Type | Notes |
|---|---|---|
| id | ID | `ev_…` |
| source_type | EvidenceSource | |
| document_id | ID | the `Document` (§5.12) this snippet was taken from |
| location | str? | page, section, or line reference inside the document |
| snippet | str | the line that supports the claim (≤ 300 chars) |
| synthetic | bool | default `true` |

### 5.2 `VersionInfo` (stamped on every twin, run, and package)

`twin_version`, `settings_version`, `prompt_version`, `model_id`, `engine_version`, `created_at`. (Trimmed from Canary's 8 fields; `data_snapshot_id`, `policy_version`, `coefficient_version` are [STRETCH].)

### 5.3 `Entity` — flat, Glasswing-style, with a few typed fields

One flat model with optional fields. The validator enforces which fields are **required per type** (table below) instead of 12 separate attribute blocks.

| Field | Type | Notes |
|---|---|---|
| id | ID | |
| type | EntityType | |
| name | str | display name; never a real person's name |
| department_id | ID? | must point to a `department`; required for everything except departments and `kpi_company` |
| criticality | Criticality | default `medium` |
| sensitivity | Sensitivity | default `general`; person tokens forced to `hr` |
| annual_cost_usd | USD? | vendors, systems, projects, roles, department budget |
| one_time_exit_cost_usd | USD? | termination/cancellation/severance to stop it |
| migration_cost_usd | USD? | cost to move its function elsewhere |
| capacity_fte | float? | roles, departments |
| min_qualified_owners | int? | workflows: below this after the change = **stranded** |
| documented_pct | float? | knowledge, workflows (0–1) |
| failure_cost_per_day_usd | USD? | workflows, systems: cost of an outage day |
| customer_facing | bool? | workflows, systems |
| completion_pct | float? | projects (0–1) |
| retires_entity_ids | list[ID] | projects: what finishing it lets you switch off (drives **rebound** when stopped) |
| role_id | ID? | person tokens |
| kpi_baseline | float? | kpis |
| kpi_unit | str? | kpis |
| higher_is_better | bool? | kpis |
| mandatory | bool? | controls |
| framework | str? | controls (SOC2, GDPR, …) |
| arr_usd | USD? | customer segments |
| tags | list[str] | |
| evidence_refs | list[ID] | |

**Required fields by type:**

| Type | Required |
|---|---|
| department | annual_cost_usd (= budget), capacity_fte |
| vendor | annual_cost_usd, one_time_exit_cost_usd |
| system | annual_cost_usd, failure_cost_per_day_usd |
| project | annual_cost_usd, completion_pct |
| workflow | min_qualified_owners, failure_cost_per_day_usd |
| role | annual_cost_usd, capacity_fte |
| person_token | role_id |
| knowledge_asset | documented_pct |
| control | mandatory |
| kpi | kpi_baseline, kpi_unit, higher_is_better |
| customer_segment | arr_usd |

### 5.4 `Edge`

| Field | Type | Notes |
|---|---|---|
| id | ID | `ch_…` for channels, `e_…` otherwise |
| source, target | ID | must exist |
| relation | Relation | |
| label | str? | e.g. "qualified leads" |
| channel_kind | ChannelKind? | **required** when relation = FLOWS_TO |
| strength | 0–1 | share of target's capacity that depends on source (dependency strength; unrelated to department strengths in §5.11) |
| strength_range | [low, high] | must contain `strength`; sampled in full mode. Default `[strength×0.7, min(1, strength×1.3)]` |
| substitutability | 0–1 | 1 = trivially replaceable; effective transfer = `strength × (1 − substitutability)` |
| lag_days | int ≥ 0 | when the effect shows up |
| criticality | Criticality | |
| confidence | 0–1 | |
| evidence_refs | list[ID] | **required** when criticality is high/critical |

### 5.5 `Pressure` — NEW (makes inaction real)

A pressure is something that happens to the company **regardless of what it decides**, unless an intervention neutralises it or makes it worse. The engine applies every active pressure in **every** future, including inaction.

| Field | Type | Notes |
|---|---|---|
| id | ID | `pr_…` |
| kind | PressureKind | |
| name | str | e.g. "Audit-log vendor price increase at renewal" |
| target_entity_id | ID | what it acts on |
| start_day | int ≥ 0 | |
| end_day | int? | null = to horizon |
| rate | float? | **cost_growth**: fractional increase per month (0.01 = +1%/month). **kpi_drift**: KPI change per month |
| rate_range | [low, high]? | sampled in full mode |
| step_pct | float? | **renewal_step**: one-off % increase applied at `start_day` |
| monthly_probability | float? | **hazard**: chance per month the event happens |
| probability_range | [low, high]? | |
| cost_per_event_usd | USD? | **hazard**: cost each time it happens |
| capacity_sensitivity | float ≥ 0 | **hazard**: probability multiplier from capacity loss. Effective p = `monthly_probability × (1 + capacity_sensitivity × capacity_loss(target))`. This is how cuts make incidents likelier |
| threshold | float? | **budget_ceiling / deadline**: the level that triggers the consequence |
| consequence_cost_usd | USD? | **budget_ceiling / deadline**: cost incurred if breached |
| neutralised_by | list[NeutraliserRef] | interventions that switch this pressure off |
| evidence_refs | list[ID] | |
| description | str | shown in the UI's "what happens if we wait" panel |

`NeutraliserRef` = `{ intervention_type: ActionType | MitigationType, target_entity_id: ID }`. Example: `pr_auditlog_renewal` is neutralised by `{remove_vendor, vendor_auditlog}`, so removing the vendor also avoids its price rise, and that avoided cost shows up in the act-now future.

**Fixture minimum (R13):** one `cost_growth` (e.g., cloud spend +1.5%/month), one `renewal_step` (vendor +12% at day 120), one `hazard` with `capacity_sensitivity > 0` (e.g., billing reconciliation failure, 4%/month, $400K per event, sensitivity 3.0).

### 5.6 `Twin`

`schema_version`, `version: VersionInfo`, `organization: Organization`, `department_profiles[]`, `entities[]`, `edges[]`, `pressures[]`, `documents[]`, `evidence[]`.

`OrganizationSettings` is **not** part of the twin (§5.13); it's loaded alongside it.

Load-time integrity checks: unique entity/edge/pressure IDs; every edge and pressure endpoint exists; every evidence ref exists and every evidence item points to an existing document; every `department_id` points to a department; every department has exactly one profile; required-per-type fields present (§5.3); every cross-department Layer-2 edge matches a Layer-1 channel between those departments (§5.9).

### 5.7 `AgentView`

`agent_id`, `twin_version`, `organization` (always included), `department_profile?` (the agent's own department, in full), `other_department_summaries[]` (mission + strengths names + staffing only), `entities[]`, `edges[]`, `pressures[]`, `documents[]` (metadata + summary, filtered by sensitivity), `evidence[]`, `redacted_entity_count`. Built by filtering on the agent's `visible_sensitivity` and `visible_entity_types`.

### 5.8 Department map level (Glasswing's aggregation)

`GET /company/graph?level=domain` aggregates entity edges by department for the overview chart. The 23+2 department channels (§5.9) are **stored** as FLOWS_TO edges, because the propagation rule depends on them and the aggregation alone would lose their labels.

### 5.9 Department channel map (Layer 1 seed)

Department IDs: `dept_finance`, `dept_engineering`, `dept_ai_data`, `dept_operations`, `dept_product`, `dept_marketing`, `dept_sales`, `dept_customer_success`, `dept_compliance`. KPI node: `kpi_company`.

| Edge id | Source → Target | Label | channel_kind |
|---|---|---|---|
| ch_finance_engineering_budget | Finance → Engineering | budget limits | budget |
| ch_finance_marketing_budget | Finance → Marketing | budget limits | budget |
| ch_finance_operations_cost | Finance → Operations | cost targets | budget |
| ch_finance_sales_revenue | Finance → Sales | revenue targets | budget |
| ch_ai_data_engineering_models | AI and Data → Engineering | models and data | capability |
| ch_ai_data_marketing_scores | AI and Data → Marketing | scores and segments | capability |
| ch_engineering_product_features | Engineering → Product | features and platforms | capability |
| ch_engineering_operations_automation | Engineering → Operations | automation | capability |
| ch_operations_engineering_incidents | Operations → Engineering | incidents and capacity | signal |
| ch_product_sales_roadmap | Product → Sales | roadmap and releases | capability |
| ch_product_cs_product | Product → Customer Success | product changes | capability |
| ch_marketing_sales_qualified | Marketing → Sales | qualified leads | signal |
| ch_sales_product_customer | Sales → Product | customer demand | signal |
| ch_sales_cs_commitments | Sales → Customer Success | commitments | signal |
| ch_cs_product_feedback | Customer Success → Product | feedback and churn signals | signal |
| ch_compliance_ai_data_controls | Compliance → AI and Data | controls | constraint |
| ch_compliance_engineering_policies | Compliance → Engineering | policies | constraint |
| ch_compliance_operations_process | Compliance → Operations | process controls | constraint |
| ch_finance_kpi_profitability | Finance → Company KPIs | profitability | value |
| ch_marketing_kpi_acquisition | Marketing → Company KPIs | acquisition cost | value |
| ch_sales_kpi_pipeline | Sales → Company KPIs | pipeline | value |
| ch_product_kpi_delivery | Product → Company KPIs | delivery | value |
| ch_cs_kpi_retention | Customer Success → Company KPIs | retention | value |
| **ch_sales_marketing_launch** *(new, R11)* | Sales → Marketing | launch timing | signal |
| **ch_operations_compliance_evidence** *(new, R11)* | Operations → Compliance | control evidence | signal |

Seed values: strength 0.5, range [0.3, 0.7], confidence 0.9, evidence `ev_department_map_v1`. The Twin owner tunes strengths.

**Feedback loops** the engine must converge on (fixed point, max 10 iterations, change < 0.001): Sales ⇄ Product, Customer Success ⇄ Product, Engineering ⇄ Operations, and now Operations → Compliance → Operations. Impacts that return around a loop are labelled `feedback`. Propagation depth cap: **4 hops**.

### 5.10 `Organization` — NEW (who the company is and what sector it's in)

One per twin. It gives every agent and every screen the same picture of the company, and the sector drives sensible defaults (§5.14).

| Field | Type | Notes |
|---|---|---|
| id | ID | `org_…` |
| legal_name | str | fictional in the fixture |
| display_name | str | shown in the UI header |
| sector | Sector | primary sector (enum, §4) |
| sub_sector | str? | free text, e.g. "B2B payments SaaS" |
| secondary_sectors | list[Sector] | for diversified companies |
| business_model | BusinessModel | b2b, b2c, b2b2c, marketplace, public_service, mixed |
| size_band | SizeBand | startup (< 50), smb (50–249), mid_market (250–999), enterprise (1,000–9,999), large_enterprise (10,000+) |
| headquarters_country | str | ISO 3166-1 alpha-2, e.g. `US` |
| operating_regions | list[str] | ISO country codes or regions (`EU`, `APAC`) |
| annual_revenue_usd | USD | |
| total_annual_budget_usd | USD | must equal the sum of department budgets (§12) |
| total_headcount_fte | float | must equal the sum of department staffing (§12) |
| fiscal_year_start_month | int 1–12 | |
| regulatory_frameworks | list[str] | e.g. `["SOC2", "GDPR", "PCI_DSS"]`; each must have at least one `control` entity |
| strategic_priorities | list[`StrategicPriority`] | `id`, `text`, `rank` (1 = highest), `kpi_ids[]`. Agents weigh trade-offs against these |
| description | str | 2–4 sentences for agent context |
| evidence_refs | list[ID] | |

### 5.11 `DepartmentProfile` — NEW (department strengths, staffing, and assets)

The `department` entity (§5.3) stays lean so the graph code stays simple. Everything descriptive about a department lives here, one profile per department, keyed by `department_id`.

"Strength" is covered in both senses: **staffing strength** (how many people, how stretched) and **capability strengths** (what the department is good at).

| Field | Type | Notes |
|---|---|---|
| department_id | ID | must point to a `department` entity; one profile per department |
| mission | str | one sentence |
| head_role_id | ID? | the role that leads it (never a person token) |
| agent_id | ID? | which agent speaks for it (§8.1) |
| staffing | `StaffingStrength` | see below |
| budget | `DepartmentBudget` | see below |
| strengths | list[`DepartmentStrength`] | see below; at least 1, ideally 2–4 |
| gaps | list[`DepartmentGap`] **[T2]** | known weaknesses; agents use them to argue risk |
| maturity_level | int 1–5 | overall process maturity (1 ad hoc … 5 optimised) |
| owned_entity_ids | list[ID] | derived at load: all entities with this `department_id` |
| critical_workflow_ids | list[ID] | subset of owned workflows with criticality high/critical |
| kpi_ids | list[ID] | KPIs this department is accountable for |
| document_ids | list[ID] | derived at load: documents with this `department_id` |
| documentation_coverage | float 0–1 | derived: share of `critical_workflow_ids` covered by at least one **current** document (§5.12) |

**`StaffingStrength`**

| Field | Type | Notes |
|---|---|---|
| sanctioned_fte | float | approved positions |
| actual_fte | float | filled positions |
| contractors_fte | float | |
| open_positions | int | |
| attrition_rate_annual | float 0–1 | |
| avg_time_to_hire_days | int | |
| utilisation | float 0–1.5 | above 1.0 = overstretched; the engine treats capacity cuts on an overstretched department as more harmful (§5.11 engine use) |

Rule: the department entity's `capacity_fte` must equal `actual_fte + contractors_fte`.

**`DepartmentBudget`**

| Field | Type | Notes |
|---|---|---|
| annual_budget_usd | USD | must equal the department entity's `annual_cost_usd` |
| spent_ytd_usd | USD | |
| fixed_cost_pct | float 0–1 | share that can't be cut within the horizon (leases, locked contracts); the engine caps savings at `budget × (1 − fixed_cost_pct)` |
| budget_owner_role_id | ID? | |

**`DepartmentStrength`**

| Field | Type | Notes |
|---|---|---|
| id | ID | `str_…` |
| name | str | e.g. "Deep payments-integration expertise" |
| category | StrengthCategory | capability, expertise, process, asset, relationship, data |
| level | int 1–5 | 3 = industry average, 5 = best in class |
| supports_entity_ids | list[ID] | the workflows/systems/KPIs this strength props up |
| key_role_ids | list[ID] | roles that hold it (never person tokens) |
| concentration | float 0–1 | how concentrated it is in few people; 1 = one role holds it all. Feeds the ownership risk |
| evidence_refs | list[ID] | at least one required when `level` ≥ 4 |

**`DepartmentGap` [T2]:** `id`, `name`, `category` (StrengthCategory), `severity` (1–5), `affected_entity_ids[]`, `evidence_refs[]`.

**How the engine uses profiles** (all deterministic, all in `simulation-engine`):

| Input | Effect | Tier |
|---|---|---|
| `budget.fixed_cost_pct` | caps achievable savings on department-level `reduce_capacity` | CORE |
| `staffing.utilisation` | effective capacity loss = `cut_pct × max(1, utilisation)`; cutting an overstretched team hurts more than proportionally | CORE |
| strength `level` ≥ 4 on an entity it supports | absorbs part of an incoming capacity loss: × (1 − 0.1 × (level − 3)), i.e. 10% at level 4, 20% at level 5 | T2 |
| strength `concentration` | if a `remove_roles` / `reduce_capacity` hits a key role of a strength with concentration ≥ 0.7, the strength's supported entities get an extra `ownership` impact | T2 |
| `documentation_coverage` | a stranded workflow with coverage ≥ 0.8 is downgraded one severity level (someone can pick it up from the docs) | CORE |

### 5.12 `Document` — NEW (the documents the organisation actually has)

The inventory of what's on file. `Evidence` (§5.1) now points **into** these documents; the document itself is the file, evidence is a quoted line from it.

| Field | Type | Notes |
|---|---|---|
| id | ID | `doc_…` |
| title | str | |
| doc_type | DocumentType | contract, policy, runbook, sop, architecture_note, org_chart, budget_report, financial_forecast, kpi_report, incident_report, audit_report, workflow_map, knowledge_matrix, meeting_minutes, strategy_memo, other |
| department_id | ID? | owning department; null = company-wide |
| owner_role_id | ID? | never a person token |
| uri | str | repo-relative path (e.g. `artifacts/runbooks/billing_recon.md`) or URL |
| mime_type | str | e.g. `text/markdown`, `application/pdf` |
| status | DocumentStatus | current, outdated, draft, archived |
| version | str? | e.g. `v3.2` |
| last_reviewed | date? | |
| review_cycle_days | int? | a current document becomes **stale** when `today − last_reviewed > review_cycle_days` (or `settings.doc_staleness_days` if null) |
| sensitivity | Sensitivity | drives which agents can see it |
| covers_entity_ids | list[ID] | the workflows/systems/vendors/controls it documents |
| framework_refs | list[str] | e.g. `["SOC2"]` for audit evidence |
| summary | str | ≤ 60 words, shown in agent context instead of the full text |
| page_count | int? | |
| checksum_sha256 | str? | for integrity; required if `synthetic` is false |
| synthetic | bool | default `true` |
| ingested | bool | true once evidence snippets have been extracted from it |
| uploaded_at | datetime | |

**What documents drive:** each workflow's and knowledge asset's `documented_pct` can be **derived** at load time as the share of its required document types (runbook + sop for workflows) that are covered by a current, non-stale document. If the fixture sets `documented_pct` by hand, the loader warns when it disagrees with the derived value. Compliance agents use `framework_refs` to check that each mandatory control still has audit evidence after the change.

### 5.13 `OrganizationSettings` — NEW (manageable settings)

Settings are **mutable** configuration, deliberately kept **outside** the frozen twin: changing a setting never changes the company, only how it's analysed. Every change creates a new `settings_version`, which is stamped on runs and packages, so any result can be traced to the settings it used.

| Group | Field | Type | Default | Notes |
|---|---|---|---|---|
| **Identity** | settings_id | ID | `set_default` | |
| | organization_id | ID | | |
| | settings_version | int | 1 | increments on every save |
| | updated_by, updated_at | str, datetime | | |
| **Display** | display_currency | str | `USD` | display only; stored money stays integer USD **[CORE]**; conversion rates **[STRETCH]** |
| | money_display_scale | `auto` \| `K` \| `M` \| `B` | `auto` | resolves R2 on screen |
| | timezone | str | `UTC` | IANA name |
| | locale | str | `en-US` | number/date formatting |
| **Simulation defaults** (pre-fill every new `DecisionBrief`) | default_horizon_days | int | 365 | |
| | default_futures | list[Future] | `[act_now, inaction, delay]` | inaction always re-added |
| | default_delay_days | int | 90 | |
| | mc_samples | int | 1000 | 200–5000 |
| | default_seed | int | 42 | |
| | propagation_max_hops | int | 4 | 1–6 |
| | min_impact_threshold | float | 0.02 | losses below this are hidden |
| **Risk appetite** | risk_appetite | `conservative` \| `balanced` \| `aggressive` | `balanced` | shifts `risk_level_thresholds` and the optimizer's tie-break |
| | risk_level_thresholds | `{medium, high, critical}` ints | `{25, 50, 75}` | conservative preset `{20, 40, 60}`, aggressive `{30, 60, 85}` |
| | risk_weights | `{financial, capability_workflow, customer_revenue, compliance_control, execution_uncertainty}` ints | `{25, 25, 20, 20, 10}` | must sum to 100; replaces the fixed maxima in §7.5 |
| | optimizer_objective | `max_net_value` \| `min_risk` \| `balanced` | `max_net_value` | `balanced` = maximise p50 net value − λ × risk, λ from appetite |
| **Guardrails** | default_constraints | list[Constraint] | from sector preset | copied into new briefs; editable per brief |
| | always_protected_entity_ids | list[ID] | `[]` | merged into every brief's `protected_entity_ids` |
| | require_human_approval | bool | `true` | locked `true` in the demo |
| | anonymize_people | bool | `true` | **locked `true`**; the UI shows it but can't change it |
| **Agents** | enabled_agent_ids | list[ID] | all CORE agents | finance, compliance, challenger can't be disabled |
| | llm_mode | `live` \| `replay` \| `mock` | `replay` | `replay` is the safe demo default |
| | model_id_strong / model_id_fast | str | from env | overrides env for this org |
| | max_tool_calls | int | 3 | 0–5 |
| | temperature | float | 0.4 | |
| | agent_timeout_seconds | int | 45 | on timeout → `fallback_cached` |
| **Documents** | doc_staleness_days | int | 365 | used when a document has no `review_cycle_days` |
| | required_doc_types_per_workflow | list[DocumentType] | `[runbook, sop]` | drives derived `documented_pct` |
| **Sector** | sector_preset_id | ID? | from `Organization.sector` | §5.14 |

**Rules:** settings never contain secrets (API keys stay in env). Changing settings mid-run doesn't affect that run; the run keeps the `settings_version` it started with.

### 5.14 [T2] `SectorPreset` (sector-aware defaults)

Picks sensible starting settings from the organisation's sector so the tool isn't tuned only for one kind of company.

| Field | Type | Notes |
|---|---|---|
| id | ID | e.g. `preset_healthcare` |
| sector | Sector | |
| mandatory_frameworks | list[str] | e.g. healthcare → `HIPAA`; financial services → `SOX`, `PCI_DSS`; SaaS → `SOC2`, `GDPR` |
| default_constraints | list[Constraint] | e.g. healthcare adds `customer_impact_pct <= 1` as hard |
| risk_weights | risk_weights? | e.g. financial services raises `compliance_control` to 30 |
| pressure_templates | list[Pressure] | typical sector pressures (e.g., retail: seasonal demand hazard) the fixture can instantiate |
| typical_departments | list[str] | hint for the fixture builder; not enforced |

**[CORE] fallback:** if presets aren't built, `sector` is still stored and shown, and settings use the global defaults above.


---

## 6. Decision (owner: **C — Agents/API**; used by everyone)

### 6.1 `Goal`

`metric` (str, e.g. `annual_savings_usd`, `net_value_usd`, `kpi_company`), `target` (number), `unit` (default `usd`), `basis` (`gross` | `net`, default gross), `direction` (`at_least` | `at_most`, default at_least).

Because the metric is a string the engine knows how to compute, the same shape covers "save $2M", "keep net value above zero", or "raise retention KPI by 2 points". This is what stops the schema being a cost-cutting tool only.

### 6.2 `Constraint`

| Field | Type | Notes |
|---|---|---|
| id | ID | unique within the brief |
| metric | str | one of the **engine-computable metrics** below |
| operator | `<=` \| `>=` \| `==` | |
| threshold | number | |
| unit | str | |
| hard | bool | hard → plan infeasible if violated; soft → adds to risk only |
| scope_entity_id | ID? | limit the check to one entity |
| description | str | |

**Engine-computable metrics (the only allowed values) [CORE]:** `annual_savings_usd`, `net_value_usd`, `revenue_impact_pct`, `customer_impact_pct`, `compliance_controls_broken`, `stranded_workflows`, `critical_systems_degraded`, `max_capacity_loss_pct`. Anything else is rejected at brief validation, so nobody writes a constraint the engine can't evaluate.

The four Glasswing plan checks map onto these: `savings_achieved` → goal check; `critical_systems_protected` → `critical_systems_degraded == 0`; `compliance_preserved` → `compliance_controls_broken == 0`; `business_impact_within_limits` → `revenue_impact_pct <= X` and `customer_impact_pct <= Y`.

### 6.3 `DecisionBrief`

| Field | Type | Notes |
|---|---|---|
| schema_version | str | |
| decision_id | ID | |
| decision_type | DecisionType | used by the agent router |
| title | str | short, for UI |
| statement | str | natural-language description of the decision |
| goal | Goal | |
| horizon_days | int > 0 | default 365 |
| candidate_interventions | list[Intervention] | the actions under consideration (4 in the primary scenario) |
| protected_entity_ids | list[ID] | no intervention may target these |
| constraints | list[Constraint] | |
| futures | list[Future] | default `[act_now, inaction, delay]`; **inaction is always added if missing** |
| delay_days | int | default 90 |
| active_pressure_ids | list[ID] | default: all pressures in the twin |
| seed | int | default 42 |
| mc_samples | int | default 1000 (full mode) |
| created_by | str | |

### 6.4 `Intervention` (actions and mitigations share one shape)

| Field | Type | Notes |
|---|---|---|
| id | ID | |
| kind | action \| mitigation | must agree with `type` |
| type | ActionType \| MitigationType | |
| target_entity_id | ID | |
| amount_pct | 0–100? | **required** for `reduce_capacity`, `add_capacity`, `retain_capacity_temporarily` |
| amount_usd | USD? | **required** for `invest`, `start_project` |
| start_day | int ≥ 0 | the delay future adds `delay_days` to this |
| duration_days | int? | mitigations and temporary actions |
| one_time_cost_usd | USD | default 0; mitigations must set it |
| new_owner_id | ID? | `reassign_owner`, `reassign_on_call` (a role or person token) |
| params | dict | e.g. `{"replacement_vendor_id": "vendor_beacon"}` |
| rationale | str | |

**How the engine translates each type into graph edits** (agents and UI never edit edges; they only pick from this list):

| Type | Graph edit |
|---|---|
| remove_vendor | target capacity → 0 from start_day; its annual cost → saved; exit cost charged once |
| reduce_capacity | target capacity × (1 − amount_pct/100); proportional cost saved; person tokens with lowest `BACKS_UP` coverage retained last |
| add_capacity | target capacity × (1 + amount_pct/100); proportional cost added |
| remove_roles | role FTE → 0; OWNS/KNOWS edges of its person tokens removed |
| stop_project | project capacity → 0; remaining cost saved; entities in `retires_entity_ids` **keep running** (→ rebound cost) |
| start_project / invest | new capacity on target from `start_day + lag`; cost added; benefits flow via its outgoing edges |
| delay_project | shifts the project's effects and costs by `duration_days` |
| reassign_owner / reassign_on_call | adds an OWNS edge from `new_owner_id`; restores workflow owner count |
| document_runbook | target `documented_pct` → 1.0 after `duration_days`; lowers hazard sensitivity by half |
| add_replacement_feed | adds a SUBSTITUTES_FOR edge from `params.replacement_vendor_id`; raises substitutability of the removed vendor's edges |
| resequence_project | moves a stopped project's `retires_entity_ids` cutoff earlier, or keeps a minimal slice running (removes most of the rebound) |
| retain_capacity_temporarily | keeps `amount_pct` of cut capacity for `duration_days`; its cost is added |

### 6.5 `CandidatePlan`

`plan_id`, `label`, `intervention_ids[]`, `source` (naive | enumerated | optimizer | agent | user | mitigated), `parent_plan_id?` (set when source = mitigated).

### 6.6 `Scenario` (one isolated future; always a fresh clone of the frozen baseline twin)

`scenario_id`, `run_id`, `future`, `plan_id?` (**null only for inaction**), `delay_days`, `baseline_twin_version`, `created_at`.

**What each future means, precisely:**

| Future | Interventions | Pressures | Story it tells |
|---|---|---|---|
| inaction | none | all active pressures run from day 0 | "What happens if we do nothing" |
| act_now | plan's interventions at their `start_day` | all run; some neutralised or amplified by the plan | "What happens if we take the decision" |
| delay | plan's interventions shifted by `delay_days` | all run; neutralisation only starts after the delay | "What waiting costs us" |
| alternative | another plan (e.g., naive or lowest-risk) | all run | "What happens if we take a different decision" |

---

## 7. Simulation engine outputs (owner: **B — Engine**)

### 7.1 `Impact` (one row of the impact ledger)

| Field | Type | Notes |
|---|---|---|
| impact_id, decision_id, scenario_id | ID | |
| source_entity | ID | intervention target or pressure target where the ripple began |
| source_kind | `intervention` \| `pressure` | **new:** lets the UI show harms caused by *not* acting |
| source_ref | ID | intervention ID or pressure ID |
| affected_entity | ID | |
| affected_department | ID? | |
| level | ImpactLevel | hop distance; `delayed` when first effect > 90 days; `feedback` via a loop |
| category | ImpactCategory | derived: person/role/knowledge → ownership; system/vendor/dataset → technical; workflow/project → operational; kpi/segment → business; control → compliance; cost terms → financial |
| polarity | benefit \| harm | |
| direction | Direction | |
| metric, magnitude, unit | str, float, str | e.g. `capacity_loss`, 0.42, `ratio` |
| value_usd | USD? | monetised effect over horizon, if priced |
| severity | 1–5 | |
| first_effect_day, peak_effect_day | int | peak ≥ first |
| confidence | 0–1 | product of edge confidences along the path |
| dependency_path | list[ID] | entity IDs from source_entity to affected_entity (inclusive) |
| edge_path | list[ID] | the edge IDs between them |
| evidence_refs, assumptions | lists | |
| constraint_refs | list[ID] | constraints this impact pushes on |
| origin | Origin | |
| status | ClaimStatus | engine impacts are always `computed` |

### 7.2 `WorkflowCoverage` (merges Glasswing's `OwnershipChange` with Canary's knowledge-risk block)

`workflow_id`, `criticality`, `owners_before[]` (person tokens), `owners_after[]`, `min_qualified_owners`, `backup_count_after`, `documented_pct`, `stranded`, `reasons[]`.

Rule: `stranded == (len(owners_after) < min_qualified_owners)`, enforced by the validator.

### 7.3 `ValueBreakdown` (merged formula; every line shown separately)

```
net_value_usd = gross_savings_usd
              − transition_cost_usd          (exit + migration + one-time intervention costs)
              − added_cost_usd               (investments, retained capacity, mitigation run-cost)
              − rebound_cost_usd             (things that keep running because a project stopped)
              − expected_business_loss_usd   (priced harm from propagated impacts)
              − pressure_cost_usd            (cost of pressures that still materialise in this future)
              + avoided_failure_cost_usd     (hazard costs prevented by mitigations)
```

| Field | Type | Notes |
|---|---|---|
| gross_savings_usd | USD | |
| transition_cost_usd | USD | |
| added_cost_usd | USD | |
| rebound_cost_usd | USD | |
| expected_business_loss_usd | USD | |
| pressure_cost_usd | USD | **new** — in inaction this is usually the biggest line |
| avoided_failure_cost_usd | USD | |
| net_value_usd | USD | validator rejects anything that doesn't equal the sum exactly |
| monthly_net_usd | list[USD] | length = horizon months (12); **cumulative** net value per month; drives the rebound/futures chart |
| p10_net_value_usd, p50_net_value_usd, p90_net_value_usd | USD? | full mode only; all set or none; p10 ≤ p50 ≤ p90 |

Dropped from Canary v1: `risk_penalty_usd` and `uncertainty_penalty_usd`. Risk is reported separately (§7.5) instead of being hidden inside a dollar figure nobody could explain.

### 7.4 `ConstraintResult`

`constraint_id`, `metric`, `operator`, `threshold`, `value`, `hard`, `passed`, `explanation`, `impact_ids[]`.

### 7.5 `RiskScore`

`score` (0–100, must equal the sum of components), `level` (RiskLevel, using `settings.risk_level_thresholds`), `settings_version`, `components`. The maxima below are the defaults; the live values come from `settings.risk_weights` (§5.13):

| Component | Max | Computed from |
|---|---:|---|
| financial | 25 | downside: `(p50 − p10) / |goal target|`, and whether goal is missed |
| capability_workflow | 25 | stranded workflows, critical systems degraded, max capacity loss |
| customer_revenue | 20 | revenue_impact_pct and customer_impact_pct vs their constraint thresholds |
| compliance_control | 20 | broken controls (any broken mandatory control = full 20) |
| execution_uncertainty | 10 | mean `1 − confidence` of harm impacts, plus hypotheses count |

Each component's exact formula lives in `simulation-engine/risk.py` with a docstring; the UI shows the stacked breakdown.

### 7.6 `SimulationResult`

| Field | Notes |
|---|---|
| result_id, run_id, scenario_id | |
| future | |
| plan_id | null = inaction |
| mode | `quick` (point estimate, < 100 ms) \| `full` (Monte Carlo) |
| seed | required in full mode |
| intervention_ids | |
| value | ValueBreakdown |
| goal_met | bool |
| constraint_results | list[ConstraintResult] |
| impacts | list[Impact] |
| workflow_coverage | list[WorkflowCoverage] — only those that changed |
| pressures_triggered | list[`{pressure_id, expected_events, expected_cost_usd, neutralised}`] |
| risk | RiskScore |
| affected_department_ids | |
| feasible | false if any hard constraint failed |
| rejection_reasons | required when infeasible |
| assumptions | list[str] |
| computed_at | |

### 7.7 `FutureComparison` — NEW (the "take it vs don't take it" answer)

Compares every future against **inaction**. Computed in full mode with **common random numbers**: each Monte Carlo sample draws edge strengths, pressure rates, and hazard events **once** and reuses them in every future, so differences reflect the decision rather than noise.

| Field | Type | Notes |
|---|---|---|
| comparison_id | ID | `cmp_…` |
| decision_id, run_id | ID | |
| reference_result_id | ID | the inaction result |
| rows | list[FutureRow] | one per future (and per alternative plan) |
| best_row_index | int? | highest p50 delta among feasible rows; null if none feasible |
| headline | str | template-generated, e.g. "Acting now beats doing nothing in 87% of simulated futures; waiting 90 days costs ~$310K." |

**`FutureRow`**

| Field | Type | Notes |
|---|---|---|
| future | Future | |
| plan_id | ID? | |
| result_id | ID | |
| label | str | |
| net_value_p50_usd | USD | |
| delta_vs_inaction_p10_usd / p50 / p90 | USD | this future minus inaction, sample by sample |
| p_better_than_inaction | float | share of samples where this future's net value > inaction's |
| breakeven_day | int? | first day cumulative net value exceeds inaction's; null if never within horizon |
| cost_of_delay_usd | USD? | **delay row only:** act_now p50 − delay p50 |
| feasible | bool | |
| risk_score | float | |
| monthly_delta_usd | list[USD] | cumulative delta vs inaction per month (the "two futures" chart) |

### 7.8 `PortfolioComparison` (Glasswing; the optimizer's output)

| Field | Notes |
|---|---|
| evaluated_count | 2ⁿ subsets of `candidate_interventions` (4 → 16) |
| naive | Portfolio (R5: apply everything) |
| recommended | Portfolio? — best feasible by p50 net value, ties broken by lower risk |
| alternatives | list[Portfolio] — lowest gross cost, lowest risk, plus every rejected plan with its failed checks |

`Portfolio` = `plan_id`, `intervention_ids[]`, `rank` (null if infeasible), `result: SimulationResult` (quick mode during search; the recommended and naive are re-run in full mode).

For 2ⁿ > 256 [STRETCH], switch to greedy + local search; the output shape doesn't change.

### 7.9 `MitigationComparison`

`plan_id_before`, `plan_id_after`, `actions: list[Intervention]` (kind = mitigation), `before: SimulationResult`, `after: SimulationResult`, `restored_entity_ids[]`, `changed_metrics[]`, `feasible_before`, `feasible_after`.

### 7.10 `BlastRadius` (exactly what the frontend draws)

- **BlastNode:** `node_id`, `kind` (decision | department | entity | pressure | outcome), `department_id?`, `entity_id?`, `pressure_id?`, `headline`, `level?`, `category?`, `polarity?`, `severity?`, `value_usd?`, `first_effect_day?`, `impact_ids[]`
- **BlastEdge:** `source`, `target`, `label` ("Direct impact", "Indirect impact", "Second-order risk", "Critical constraint", "Revenue effect", "Pressure"), `level?`, `critical_constraint` (bool), `channel_id?`
- **DepartmentImpactSummary:** `department_id`, `headline`, `polarity`, `severity`, `impact_ids[]`
- **CompanyOutcome:** `net_value_usd`, `risk_level`, `headline`
- **BlastRadius:** `run_id`, `scenario_id`, `future`, `plan_id?`, `root_node_id`, `nodes[]`, `edges[]`, `departments[]`, `outcome`. Every edge must reference existing nodes.

The **inaction** blast radius is rooted at a `decision` node labelled "Do nothing", with `pressure` nodes as its first ring. That's how the UI shows "what breaks if we don't act" in the same visual language as "what breaks if we do".

### 7.11 [T2] `ItemCounterfactual`

`intervention_id`, `contribution_usd`, `net_value_without_usd`, `goal_still_met`, `verdict` (keep | drop | borderline), `explanation`. One per intervention in the recommended plan: "what if we took this plan *without* this one piece?" Computed by re-running quick mode with that intervention removed.

### 7.12 [STRETCH] `MissingQuestion` + `UserAnswer`

Simplified from Canary: `question_id`, `text`, `uncertain_input` (e.g. `vendor_auditlog.retains_history_after_termination`), `current_assumption`, `answer_type` (boolean | number | choice), `options[]`, `changes_recommendation_if` (str), `value_gap_usd`. No scoring formula; the fixture plants one question and the engine re-runs when it's answered. `UserAnswer` = `question_id`, `value`, `answered_by`, `answered_at`.

### 7.13 Engine interface (the seam between B and C)

```python
def quick_impact(twin: Twin, interventions: list[Intervention]) -> SimulationResult: ...   # agent tool, < 100 ms
def simulate(twin: Twin, brief: DecisionBrief, scenario: Scenario,
             plan: CandidatePlan | None, mode: Literal["quick", "full"]) -> SimulationResult: ...
def compare_futures(twin: Twin, brief: DecisionBrief,
                    plan: CandidatePlan) -> FutureComparison: ...                          # runs all futures with CRN
def optimize(twin: Twin, brief: DecisionBrief) -> PortfolioComparison: ...
def mitigate(twin: Twin, brief: DecisionBrief, plan: CandidatePlan,
             actions: list[Intervention]) -> MitigationComparison: ...
def blast_radius(result: SimulationResult, twin: Twin) -> BlastRadius: ...
```

The engine **never** calls an LLM. The agent layer **never** computes a number. Validated agent dependencies (§8.5) enter the engine as extra `Edge`s on the scenario clone, then the engine re-propagates.

---

## 8. Agents (owner: **C — Agents/API**)

### 8.1 Roster (`AgentSpec`)

| agent_id | department_id | Owns | Visible sensitivity | Routes for | Tier |
|---|---|---|---|---|---|
| finance | dept_finance | savings, exit costs, rebound, budget pressure, vendor contracts | general, finance | all | CORE |
| engineering | dept_engineering | integrations, reliability, maintenance, migration effort | general, security | vendor, capacity, project, investment | CORE |
| ai_data | dept_ai_data | datasets, lineage, model effects | general | vendor, capacity, project | CORE |
| operations | dept_operations | process continuity, on-call, platform ops, service levels | general | all except investment | CORE |
| product | dept_product | roadmap, releases, projects (PMO) | general | capacity, project, investment | CORE |
| marketing | dept_marketing | segmentation, campaigns, acquisition | general, customer | vendor, capacity, investment | CORE |
| sales | dept_sales | pipeline, committed features | general, customer | vendor, capacity, project | CORE |
| customer_success | dept_customer_success | escalations, SLAs, churn | general, customer | vendor, capacity, project | CORE |
| compliance | dept_compliance | policies, controls, audit paths, hard constraints | general, security | all | CORE |
| challenger | — | missed departments, unsupported assumptions, circular logic, the **cost of doing nothing** | general | all (challenge pass only) | CORE |
| people_knowledge | — | backup coverage, documentation, knowledge concentration (role level only) | general, hr | capacity, restructure, cost_reduction | T2 |

`AgentSpec` fields: `agent_id`, `display_name`, `department_id?`, `responsibilities[]`, `owned_metrics[]`, `visible_entity_types[]`, `visible_sensitivity[]`, `routes_for[DecisionType]` (`all` expands to every type), `prompt_version`.

**Routing rule:** an agent runs when its `routes_for` includes the brief's `decision_type` **and** its department is reachable within 4 hops from any intervention target **or any active pressure target**. Finance, Compliance, and Challenger always run. Including pressure targets matters: a department hit only by inaction still gets a voice.

**Futures per agent:** each routed agent assesses **two** scenarios, `act_now` (for the recommended plan) and `inaction`, in one call. It doesn't assess delay or every alternative; the engine covers those. This keeps calls ≈ 2 × routed agents rather than exploding.

### 8.2 `AgentContext` (input to one agent call)

| Field | Notes |
|---|---|
| schema_version, run_id | |
| agent | AgentSpec, placed first in the prompt so it can be cached |
| brief | DecisionBrief |
| plan | CandidatePlan being assessed |
| view | AgentView (permission-filtered) |
| act_now_effects | list[Impact], engine-computed, filtered to the agent's view |
| inaction_effects | list[Impact], engine-computed, filtered to the agent's view |
| known_impact_summaries | list[str], one-liners from other agents (compact, not transcripts) |
| settings | the subset of `OrganizationSettings` agents need: `risk_appetite`, `optimizer_objective`, `display_currency`, `money_display_scale` (strategic priorities arrive via `view.organization`) |
| max_tool_calls | from settings (default 3) |

**Tools:** `get_entity`, `list_dependencies`, `get_evidence`, `get_pressure`, `get_department_profile`, `list_documents`, `get_document_summary`, `run_quick_impact`, `propose_dependency`, `submit_assessment`. Read-only except the last two. `ToolCall` = `name`, `args`, `ok`, `result_summary`.

> **If tool calling is unreliable on your chosen model:** precompute the tool results into `AgentContext` and drop tools. The output schema doesn't change.

### 8.3 LLM-facing output — `AgentOutput`

Entity references are **plain strings**, not validated IDs, so one hallucinated ID doesn't fail the whole response; the merger checks each claim individually.

| Field | Type |
|---|---|
| affected_entities | list[str] |
| act_now_view | FutureView |
| inaction_view | FutureView |
| proposed_dependencies | list[ProposedDependency] |
| questions | list[AgentQuestion] |
| objections | list[Objection] |
| assumptions | list[str] |
| evidence_refs | list[str] |
| confidence | 0–1 |

Sub-objects:

- **FutureView:** `summary` (≤ 40 words), `failure_modes[Finding]`, `edge_cases[Finding]`, `proposed_impacts[ProposedImpact]`
- **Finding:** `text`, `entity_ids[]`, `severity` (1–5), `evidence_refs[]`
- **ProposedImpact:** `affected_entity`, `metric`, `direction`, `polarity`, `category`, `level`, `estimated_magnitude?` (*display-only, never authoritative*), `unit?`, `first_effect_day?`, `severity`, `rationale`, `dependency_path[]`, `evidence_refs[]`, `confidence`
- **ProposedDependency:** `source`, `target`, `relation`, `rationale`, `evidence_refs[]`, `confidence`
- **AgentQuestion:** `text`, `why_it_matters`, `entity_ids[]`
- **Objection:** `target_ref` (plan_id or impact_id), `text`, `severity`

Splitting the output into `act_now_view` and `inaction_view` forces every department to say what happens to it **both** ways. That is the product's core idea, enforced at the schema level.

### 8.4 LLM-facing output — `ChallengerOutput`

`missing_agents[]`, `unsupported_assumptions[Finding]`, `circular_logic[Finding]`, `overlooked_combinations[list[str]]`, `missed_dependencies[ProposedDependency]`, `inaction_underestimated[Finding]` (**new:** harms of doing nothing nobody raised), `objections[Objection]`, `confidence`.

### 8.5 Merge rules (how agent claims enter the system)

| Claim condition | Result |
|---|---|
| References an unknown entity ID | claim → `rejected`; ID logged in `ValidationReport.rejected_entity_ids` |
| Known IDs **and** evidence refs that resolve | → `validated`; a proposed dependency is added to the scenario clone and the engine **re-propagates** |
| Known IDs, no evidence | → `hypothesis`; shown in the UI, never changes numbers or feasibility |
| Contradicts an engine-computed fact | → `rejected` with reason |
| Any number | never taken from the agent |
| Confidence outside [0, 1] | clamped; logged in `clamped_fields` |

Planted fixture item: **one** missed dependency the Challenger is expected to find (a real edge removed from the agents' views but present in evidence), so the "agent found something the model didn't" moment is reliable.

### 8.6 Stored — `AgentAssessment`

| Field | Notes |
|---|---|
| assessment_id, run_id, plan_id?, agent_id | |
| pass_type | first_pass \| challenge |
| status | ok \| replayed \| fallback_cached \| unavailable \| invalid |
| output | AgentOutput? |
| challenge | ChallengerOutput? |
| accepted_impacts | list[Impact], the claims that entered the ledger |
| validation | `ValidationReport`: `rejected_entity_ids[]`, `downgraded_to_hypothesis[]`, `clamped_fields[]`, `retries` (0–1), `errors[]` |
| metrics | `CallMetrics`: `model_id`, `prompt_version`, `prompt_hash`, `latency_ms`, `input_tokens`, `output_tokens`, `tool_calls[]` |
| created_at | |

An `unavailable` agent appears in `missing_perspectives` and widens the `strength_range` of edges its department owns by ±0.1 in full mode, so missing input visibly increases uncertainty.

### 8.7 `Claim` (Glasswing; used in the report)

`text`, `source` (`calculation` | `evidence` | `assumption` | `agent_validated`), `ref` (result/impact ID, evidence ID, assumption text, or assessment ID). Every sentence in the executive summary is a `Claim`.

---

## 9. Decision package (owner: **C** builds, **D** renders)

**`DecisionPackage`**

| Field | Notes |
|---|---|
| package_id, run_id, decision_id | |
| versions | VersionInfo |
| brief | DecisionBrief |
| recommendation | `Recommendation?` = `plan_id`, `future` (may be **inaction** if doing nothing genuinely wins), `result_id`, `headline`, `claims[Claim]`. Null = no feasible plan; closest alternatives explained instead |
| futures | FutureComparison |
| portfolios | PortfolioComparison |
| blast_radius_act_now | BlastRadius |
| blast_radius_inaction | BlastRadius |
| department_impacts | list[DepartmentImpactSummary] |
| critical_risks | list[Impact] (severity ≥ 4) |
| mitigations | list[MitigationComparison] |
| counterfactuals | list[ItemCounterfactual] **[T2]** |
| missing_information | list[MissingQuestion] **[STRETCH]** |
| implementation | list[`ImplementationStep`] = `order`, `day`, `action`, `intervention_id?`, `gate?` **[T2]** |
| monitoring | list[`MonitorRule`] = `metric`, `entity_id?`, `operator`, `threshold`, `action` (watch \| pause \| rollback \| escalate), `description` **[T2]** |
| assumptions | list[str] |
| open_questions | list[str] |
| missing_perspectives | list[agent_id] |
| status | awaiting_approval \| approved \| rejected \| another_scenario_requested |
| created_at | |

**Ethics guard:** the package is rejected if any `pt_…` ID appears anywhere in it.

**`HumanDecision`**: `run_id`, `package_id`, `decision` (approve | reject | request_scenario), `decided_by`, `decided_at`, `notes`, `package_hash` (sha256 of the exact package shown).

---

## 10. Events and run state (owner: **C**; consumed by **D**)

### 10.1 `Event`

`event_id`, `run_id`, `sequence` (strictly increasing per run; the key for replay and reconnect), `type`, `actor` (orchestrator | engine | agent_id | user), `scenario_id?`, `future?`, `timestamp`, `payload`.

### 10.2 Event type → payload

| type | payload |
|---|---|
| run_created | DecisionBrief |
| phase_changed | `{from_status, to_status}` |
| scenario_created | Scenario |
| pressure_activated | `{pressure_id, future, expected_cost_usd}` |
| candidate_generated | CandidatePlan |
| candidate_rejected | `{plan_id, reasons[]}` |
| agent_started | `{agent_id, plan_id?}` |
| agent_completed | AgentAssessment |
| agent_failed | `{agent_id, reason, fallback_used}` |
| dependency_validated | `{assessment_id, edge: Edge}` |
| impact_computed | Impact |
| constraint_violated | ConstraintResult |
| challenge_raised | AgentAssessment |
| simulation_completed | SimulationResult |
| futures_compared | FutureComparison |
| portfolio_ranked | PortfolioComparison |
| blast_radius_ready | BlastRadius |
| mitigation_applied | MitigationComparison |
| package_ready | DecisionPackage |
| human_decision_recorded | HumanDecision |
| question_selected / answer_received | MissingQuestion / UserAnswer **[STRETCH]** |
| settings_updated | `{settings_version, changed_fields[]}` |
| document_registered | Document (metadata only) **[T2]** |
| run_failed | `{reason}` |

`sample_run.json` (hand-written, hour 1) and `golden_run.json` (best real run, saved ~hour 14) are ordered arrays of `Event`. The frontend sorts by `sequence`, never arrival time.

### 10.3 `RunState`

`run_id`, `decision_id`, `baseline_twin_version`, `status`, `scenario_ids[]`, `candidate_plan_ids[]`, `assessment_ids[]`, `result_ids[]`, `comparison_id?`, `package_id?`, `last_sequence`, `created_at`, `updated_at`.

---

## 11. API (owner: **C**)

```text
GET  /health
GET  /company                             Twin
GET  /company/graph?level=entity|domain
GET  /company/pressures                   list[Pressure]
GET  /organization                        Organization
PUT  /organization                        Organization -> Organization              [T2: editable in UI]
GET  /organization/settings               OrganizationSettings
PATCH /organization/settings              partial OrganizationSettings -> OrganizationSettings (new version)
GET  /organization/settings/history       list[{settings_version, updated_by, updated_at, changed_fields[]}]
GET  /sector-presets                      list[SectorPreset]                          [T2]
POST /organization/settings/apply-preset  {preset_id} -> OrganizationSettings        [T2]
GET  /departments                         list[{department entity, DepartmentProfile}]
GET  /departments/{id}                    {entity, profile, owned entities, documents, channels in/out}
GET  /documents?department_id=&doc_type=&status=   list[Document]
GET  /documents/{id}                      Document (+ evidence snippets taken from it)
POST /documents                           register document metadata                 [T2]
POST /decisions                           DecisionBrief -> {run_id}; starts the full run in background
GET  /runs/{run_id}                       RunState
WS   /runs/{run_id}/events                live Event stream (replays history first on connect)
GET  /runs/{run_id}/package               DecisionPackage
POST /runs/{run_id}/decision              HumanDecision
POST /simulate/quick                      list[Intervention] -> SimulationResult   (what-if sliders)
POST /simulate/futures                    {brief, plan} -> FutureComparison
POST /simulate/optimize                   DecisionBrief -> PortfolioComparison
POST /simulate/mitigate                   {brief, plan, actions} -> MitigationComparison
GET  /replays                             list of saved runs
POST /replays/{name}/play?speed=1|2|4     re-streams a saved run over the WS
```

---

## 12. Cross-field validation rules (all enforced in code)

1. Twin: unique IDs; edge and pressure endpoints exist; evidence refs resolve; `department_id` points to a department; required-per-type fields present.
2. High/critical edges need evidence. FLOWS_TO edges need `channel_kind`. `strength` inside `strength_range`.
3. Every cross-department Layer-2 edge matches a Layer-1 channel.
4. Person tokens use `pt_` and get `hr` sensitivity.
5. Brief: protected IDs not targeted by any candidate intervention; constraint IDs unique; constraint metrics from the allowed list; `futures` contains `inaction`.
6. Intervention `kind` matches `type`; `amount_pct` / `amount_usd` present where required.
7. Only the inaction scenario may have no plan.
8. Impact paths run source → affected; `edge_path` length = `dependency_path` length − 1; peak ≥ first effect day; engine impacts are `computed`.
9. `ValueBreakdown.net_value_usd` equals its components exactly; `monthly_net_usd[-1] == net_value_usd`.
10. Risk score equals the sum of components; p10 ≤ p50 ≤ p90, all set or none.
11. `stranded` agrees with owner counts.
12. Any hard-constraint failure → infeasible with reasons; full mode needs a seed.
13. FutureComparison: exactly one row per requested future; `p_better_than_inaction` in [0, 1]; inaction row has delta 0 and p = 0.
14. Blast-radius edges reference existing nodes.
15. Decision package contains no person tokens.
16. Organization: `total_annual_budget_usd` = Σ department budgets; `total_headcount_fte` = Σ (actual + contractor FTE); every regulatory framework has ≥ 1 control entity.
17. Department profiles: exactly one per department; `budget.annual_budget_usd` = entity `annual_cost_usd`; entity `capacity_fte` = `actual_fte + contractors_fte`; `actual_fte ≤ sanctioned_fte + open_positions` is only a warning.
18. Strengths: `level` ≥ 4 needs evidence; `supports_entity_ids` and `key_role_ids` exist; no person tokens in `key_role_ids`.
19. Documents: unique IDs; `covers_entity_ids` exist; `owner_role_id` is a role, not a person token; non-synthetic documents need a checksum.
20. Settings: `risk_weights` sum to 100; thresholds strictly increasing; `anonymize_people` and `require_human_approval` are `true`; finance, compliance, challenger are in `enabled_agent_ids`; `always_protected_entity_ids` exist in the twin.

---

## 13. Examples

### 13.1 Primary `DecisionBrief` (numbers are placeholders; scale per R2)

```json
{
  "schema_version": "2.0.0",
  "decision_id": "dec_cut_2m",
  "decision_type": "cost_reduction",
  "title": "Cut $2M",
  "statement": "Reduce annual cost by $2M while protecting revenue, operations, and compliance.",
  "goal": {"metric": "annual_savings_usd", "target": 2000000, "unit": "usd", "basis": "gross", "direction": "at_least"},
  "horizon_days": 365,
  "candidate_interventions": [
    {"id": "i_platform_ops", "kind": "action", "type": "reduce_capacity", "target_entity_id": "dept_operations", "amount_pct": 20, "start_day": 0, "one_time_cost_usd": 60000, "params": {"scope": "platform_ops"}, "rationale": "Platform Ops over-provisioned vs incident load"},
    {"id": "i_auditlog", "kind": "action", "type": "remove_vendor", "target_entity_id": "vendor_auditlog", "start_day": 30, "one_time_cost_usd": 0, "params": {}, "rationale": "Overlaps with SIEM capability"},
    {"id": "i_migration", "kind": "action", "type": "stop_project", "target_entity_id": "proj_warehouse_migration", "start_day": 0, "one_time_cost_usd": 40000, "params": {}, "rationale": "Behind schedule"},
    {"id": "i_eng", "kind": "action", "type": "reduce_capacity", "target_entity_id": "dept_engineering", "amount_pct": 10, "start_day": 0, "one_time_cost_usd": 120000, "params": {}, "rationale": "Hiring ran ahead of roadmap"}
  ],
  "protected_entity_ids": ["ctl_soc2_audit_logging"],
  "constraints": [
    {"id": "c_compliance", "metric": "compliance_controls_broken", "operator": "==", "threshold": 0, "unit": "count", "hard": true, "description": "No mandatory control may break"},
    {"id": "c_critical", "metric": "critical_systems_degraded", "operator": "==", "threshold": 0, "unit": "count", "hard": true, "description": "Tier-0 systems stay whole"},
    {"id": "c_revenue", "metric": "revenue_impact_pct", "operator": "<=", "threshold": 3, "unit": "percent", "hard": true, "description": "Revenue impact within 3%"},
    {"id": "c_stranded", "metric": "stranded_workflows", "operator": "==", "threshold": 0, "unit": "count", "hard": false, "description": "Prefer no stranded workflows"}
  ],
  "futures": ["act_now", "inaction", "delay"],
  "delay_days": 90,
  "active_pressure_ids": ["pr_cloud_growth", "pr_auditlog_renewal", "pr_billing_recon_hazard"],
  "seed": 42,
  "mc_samples": 1000,
  "created_by": "demo_user"
}
```

### 13.2 Pressures for that brief

```json
[
  {"id": "pr_cloud_growth", "kind": "cost_growth", "name": "Cloud spend growth",
   "target_entity_id": "sys_cloud_platform", "start_day": 0, "rate": 0.015, "rate_range": [0.01, 0.02],
   "capacity_sensitivity": 0, "neutralised_by": [], "evidence_refs": ["ev_finance_forecast_q3"],
   "description": "Cloud costs grow ~1.5% a month on current usage."},
  {"id": "pr_auditlog_renewal", "kind": "renewal_step", "name": "Audit-log vendor renewal uplift",
   "target_entity_id": "vendor_auditlog", "start_day": 120, "step_pct": 12,
   "capacity_sensitivity": 0,
   "neutralised_by": [{"intervention_type": "remove_vendor", "target_entity_id": "vendor_auditlog"}],
   "evidence_refs": ["ev_auditlog_msa_clause_9"],
   "description": "Contract auto-renews at +12% on day 120."},
  {"id": "pr_billing_recon_hazard", "kind": "hazard", "name": "Billing reconciliation failure",
   "target_entity_id": "wf_billing_recon", "start_day": 0,
   "monthly_probability": 0.04, "probability_range": [0.02, 0.06], "cost_per_event_usd": 400000,
   "capacity_sensitivity": 3.0,
   "neutralised_by": [{"intervention_type": "document_runbook", "target_entity_id": "wf_billing_recon"}],
   "evidence_refs": ["ev_incident_22"],
   "description": "Reconciliation fails roughly twice a year; likelier if its owners lose capacity."}
]
```

This produces the intended story: inaction pays for cloud growth, the renewal uplift, and occasional reconciliation failures. The naive "cut everything" plan saves the most gross but strands `wf_billing_recon` and triples its failure rate. The recommended plan removes the vendor (also killing the renewal uplift), trims Platform Ops with a runbook mitigation, and keeps the migration running to avoid rebound.

### 13.3 `FutureComparison` (illustrative values)

```json
{
  "comparison_id": "cmp_dec_cut_2m",
  "decision_id": "dec_cut_2m",
  "run_id": "run_demo_001",
  "reference_result_id": "res_inaction",
  "best_row_index": 1,
  "headline": "Acting now beats doing nothing in 87% of simulated futures; waiting 90 days costs ~$310K.",
  "rows": [
    {"future": "inaction", "plan_id": null, "result_id": "res_inaction", "label": "Do nothing",
     "net_value_p50_usd": -640000, "delta_vs_inaction_p10_usd": 0, "delta_vs_inaction_p50_usd": 0, "delta_vs_inaction_p90_usd": 0,
     "p_better_than_inaction": 0, "breakeven_day": null, "cost_of_delay_usd": null, "feasible": true, "risk_score": 38,
     "monthly_delta_usd": [0,0,0,0,0,0,0,0,0,0,0,0]},
    {"future": "act_now", "plan_id": "plan_recommended", "result_id": "res_act_now", "label": "Recommended plan, now",
     "net_value_p50_usd": 1520000, "delta_vs_inaction_p10_usd": 610000, "delta_vs_inaction_p50_usd": 2160000, "delta_vs_inaction_p90_usd": 2900000,
     "p_better_than_inaction": 0.87, "breakeven_day": 95, "cost_of_delay_usd": null, "feasible": true, "risk_score": 31,
     "monthly_delta_usd": [-180000,-90000,20000,160000,330000,520000,730000,960000,1210000,1480000,1790000,2160000]},
    {"future": "delay", "plan_id": "plan_recommended", "result_id": "res_delay", "label": "Recommended plan, in 90 days",
     "net_value_p50_usd": 1210000, "delta_vs_inaction_p10_usd": 380000, "delta_vs_inaction_p50_usd": 1850000, "delta_vs_inaction_p90_usd": 2500000,
     "p_better_than_inaction": 0.81, "breakeven_day": 190, "cost_of_delay_usd": 310000, "feasible": true, "risk_score": 34,
     "monthly_delta_usd": [0,0,0,-170000,-80000,40000,190000,390000,620000,900000,1350000,1850000]}
  ]
}
```

### 13.4 `Organization`, one `DepartmentProfile`, and one `Document`

```json
{
  "organization": {
    "id": "org_novacorp", "legal_name": "NovaCorp Holdings Inc.", "display_name": "NovaCorp",
    "sector": "technology_saas", "sub_sector": "B2B billing and payments software",
    "secondary_sectors": ["financial_services"], "business_model": "b2b", "size_band": "mid_market",
    "headquarters_country": "US", "operating_regions": ["US", "EU"],
    "annual_revenue_usd": 48000000, "total_annual_budget_usd": 21000000, "total_headcount_fte": 420,
    "fiscal_year_start_month": 1, "regulatory_frameworks": ["SOC2", "GDPR", "PCI_DSS"],
    "strategic_priorities": [
      {"id": "sp_retention", "text": "Protect enterprise retention", "rank": 1, "kpi_ids": ["kpi_net_retention"]},
      {"id": "sp_margin", "text": "Reach 20% operating margin", "rank": 2, "kpi_ids": ["kpi_operating_margin"]}
    ],
    "description": "Mid-market SaaS company selling billing automation to enterprises in the US and EU.",
    "evidence_refs": ["ev_strategy_memo_1"]
  },
  "department_profile": {
    "department_id": "dept_operations",
    "mission": "Keep customer-facing platforms and billing operations running.",
    "head_role_id": "role_coo", "agent_id": "operations",
    "staffing": {"sanctioned_fte": 64, "actual_fte": 58, "contractors_fte": 6, "open_positions": 4,
                 "attrition_rate_annual": 0.14, "avg_time_to_hire_days": 55, "utilisation": 1.12},
    "budget": {"annual_budget_usd": 3100000, "spent_ytd_usd": 2250000, "fixed_cost_pct": 0.35,
               "budget_owner_role_id": "role_coo"},
    "strengths": [
      {"id": "str_ops_incident_response", "name": "Fast incident response", "category": "process", "level": 4,
       "supports_entity_ids": ["wf_incident_mgmt", "sys_billing_platform"], "key_role_ids": ["role_sre"],
       "concentration": 0.4, "evidence_refs": ["ev_incident_review_q2"]},
      {"id": "str_ops_billing_recon", "name": "Billing reconciliation know-how", "category": "expertise", "level": 5,
       "supports_entity_ids": ["wf_billing_recon"], "key_role_ids": ["role_billing_ops_lead"],
       "concentration": 0.85, "evidence_refs": ["ev_knowledge_matrix_3"]}
    ],
    "maturity_level": 3,
    "critical_workflow_ids": ["wf_billing_recon", "wf_incident_mgmt"],
    "kpi_ids": ["kpi_uptime"]
  },
  "document": {
    "id": "doc_runbook_billing_recon", "title": "Billing reconciliation runbook", "doc_type": "runbook",
    "department_id": "dept_operations", "owner_role_id": "role_billing_ops_lead",
    "uri": "artifacts/runbooks/billing_recon.md", "mime_type": "text/markdown",
    "status": "outdated", "version": "v1.4", "last_reviewed": "2025-03-10", "review_cycle_days": 180,
    "sensitivity": "general", "covers_entity_ids": ["wf_billing_recon"], "framework_refs": ["SOC2"],
    "summary": "Steps for monthly reconciliation; exception handling section missing since the 2025 vendor change.",
    "synthetic": true, "ingested": true, "uploaded_at": "2026-09-26T09:00:00Z"
  }
}
```

Note how these three feed the story: Operations is overstretched (utilisation 1.12), its billing-reconciliation expertise is concentrated in one role (0.85), and the runbook covering that workflow is outdated. So a Platform Ops cut hits harder than a spreadsheet suggests, and `document_runbook` becomes the obvious mitigation.

---

## 14. What was cut from Canary v1 and why

| Removed / deferred | Reason | Where it went |
|---|---|---|
| 12 typed attribute blocks | Too much validation code for the value | Flat `Entity` + required-per-type table |
| 7 entity types (skill, procedure, contract, data_field, model, policy, organization) | Rarely used by the engine | Folded into role/knowledge, vendor, dataset, control |
| `VendorOverlap` (21 pairs × 11 dims) | Only needed for the 7-vendor scenario | [STRETCH]; add back if R3 changes |
| `risk_penalty_usd`, `uncertainty_penalty_usd` | No owner, no formula, hides risk inside dollars | Risk reported separately |
| MissingQuestion scoring formula | Needs a second engine loop | Simplified [STRETCH] |
| 12 mitigation types | Only 6 are exercised by the demo | 6 kept |
| `ExtractionMethod`, `aliases` | Only for an extraction proof you're not demoing | Dropped |
| Separate `ImpactLevel.dependent` naming confusion | "Indirect" in drawings | Kept `dependent`; UI label "Indirect impact" |

## 15. What was added that neither file had

**Organisation layer:** `Organization` with sector and strategic priorities (§5.10), `DepartmentProfile` with staffing and capability strengths (§5.11), a `Document` inventory that evidence now points into (§5.12), versioned `OrganizationSettings` (§5.13), and [T2] `SectorPreset` (§5.14).

**Futures layer:** `Pressure` (§5.5), `source_kind` on `Impact`, `pressure_cost_usd` in `ValueBreakdown`, `FutureComparison` with paired Monte Carlo (§7.7), `act_now_view` / `inaction_view` in agent output (§8.3), `inaction_underestimated` in the Challenger (§8.4), an inaction blast radius (§7.10), generic `Goal.direction`, engine-computable metric whitelist (§6.2), and non-cost action types (`add_capacity`, `start_project`, `delay_project`, `invest`).

---

## 16. Ownership and 24-hour build order

| | **A — Twin/data** | **B — Engine** | **C — Agents/API** | **D — Frontend** |
|---|---|---|---|---|
| Folders | `packages/company-twin`, `data/` | `packages/simulation-engine` | `packages/agent-orchestration`, `apps/api`, `packages/contracts` | `apps/web` |
| Owns models | §5 (incl. organization, profiles, documents) | §7 (+ engine use of profiles, settings) | §6, §8–§11, settings API | renders §7.10, §9, §10; settings, departments, documents screens |
| Must not | compute results | call an LLM | compute any number | compute any number |

| Hours | A | B | C | D |
|---|---|---|---|---|
| **0–1** | *All four:* confirm R1–R13, commit Pydantic models only, generate TS types, hand-write `sample_run.json` | | | |
| 1–5 | Fixture: organization + sector, 9 depts with profiles (staffing, 2–4 strengths each), 25 channels, ~60 entities, person tokens, 3 pressures, ~20 documents + evidence | Stub all 6 engine functions returning fixtures; then `quick_impact` propagation (noisy-OR, lags, loops) | API skeleton, WS + replay on `sample_run.json`; LLM wrapper (model from env, retries, cache) | App shell, graph view (domain level), event player on `sample_run.json` |
| 5–9 | Validation script (rules 1–20); tune edge strengths so the story in §13.2 emerges | ValueBreakdown, constraints, WorkflowCoverage, risk score (weights from settings), fixed-cost cap and utilisation effect | Router, AgentContext builder (org + profiles + docs), department prompts, merge rules, settings endpoints | Organisation overview + department pages (staffing, strengths, documents); blast radius view; plan comparison table |
| 9–12 | Plant the Challenger's missed dependency and one hidden cost | `compare_futures` with CRN Monte Carlo; `optimize` (16 plans) | Challenger pass, package builder, full orchestration | **Two-futures chart** (monthly_delta), inaction blast radius |
| 12–14 | *All:* first full live run end to end; fix; save `golden_run.json` | | | |
| **14** | **⚑ Checkpoint:** freeze CORE. Only T2 items from here | | | |
| 14–19 | Secondary scenario fixture (R3, non-cost decision); department gaps; sector presets | `mitigate`, ItemCounterfactual, strength absorption + concentration effects | Mitigation flow, implementation steps, monitor rules, sector presets | Settings screen (with version history), mitigation before/after, what-if sliders, approval screen |
| 19–21 | *All:* second golden run (both scenarios), record backup video, pitch deck | | | |
| 21–24 | *All:* rehearse twice, fix show-stoppers only; sleep in shifts | | | |

Critical path: **fixture → quick_impact → compare_futures → two-futures chart**. If any of those slips past hour 12, pull someone onto it.

---

## 17. Sign-off checklist

- [ ] R1–R13 confirmed or overruled
- [ ] Scale chosen and applied to every fixture number (R2)
- [ ] 3+ pressures defined, each with evidence (R13)
- [ ] Planted items named: Challenger's missed dependency, the naive plan's hidden harm, the delay cost
- [ ] Sector chosen for the fixture company, plus regulatory frameworks and strategic priorities (§5.10)
- [ ] Every department has a profile with staffing and at least one strength (§5.11)
- [ ] Document inventory lists every file evidence points to (§5.12)
- [ ] Default settings agreed, including risk appetite and risk weights (§5.13)
- [ ] Engine-computable metric list agreed (§6.2)
- [ ] Pydantic models committed; JSON Schema and TS types generated
- [ ] `sample_run.json` validates against §10
- [ ] All four owners approve → schema frozen as **v2.0.0**
