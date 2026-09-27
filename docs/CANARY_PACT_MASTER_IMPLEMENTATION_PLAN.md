# Canary Pact — Master Implementation Plan

**Product:** AI-powered organizational decision simulator  
**Core metaphor:** A flight simulator for company decisions  
**Primary demo:** Reduce $2B from seven data vendors costing $8B  
**Secondary proof:** Detect two workflows stranded by removing eight staff roles  
**Primary principle:** Agents reason; deterministic code calculates; humans decide.

---

## 1. Product definition

Canary Pact creates a decision-relevant digital twin of a company. The twin represents departments, people and roles, institutional knowledge, workflows, systems, vendors, datasets, policies, customers, business metrics, and the dependencies between them.

When leadership proposes a decision, Canary Pact:

1. freezes and versions the current company state;
2. creates isolated simulated futures;
3. routes the decision to affected department agents;
4. asks each agent to identify impacts, edge cases, risks, and missing information from its departmental perspective;
5. validates those claims against the shared company twin;
6. propagates effects across departments, workflows, systems, customers, and KPIs;
7. compares acting now, not acting, delaying, and alternative interventions;
8. recommends the feasible plan with the best company-wide outcome;
9. produces a traceable decision package with evidence, confidence, mitigations, monitoring, and rollback conditions.

### Core question

> If the company makes this decision, what is the complete organizational blast radius, what could fail, and what alternative achieves the objective with less damage?

### Product boundary

Canary Pact is a decision-support system. It does not autonomously terminate employees, cancel contracts, transfer money, or execute organizational changes. Human decision owners retain approval authority.

### What makes it distinct

Canary Pact is not:

- a spend dashboard that ranks expenses by price;
- an org-chart product that counts headcount;
- several AI personas conducting an unstructured debate;
- an LLM-generated consulting report;
- a deterministic optimizer that ignores departmental edge cases;
- an oracle claiming to predict the future precisely.

It combines:

- a shared company digital twin;
- evidence-backed dependencies;
- specialized department agents;
- deterministic impact propagation;
- counterfactual scenario comparison;
- constrained portfolio optimization;
- uncertainty and sensitivity analysis;
- human authorization and auditability.

---

## 2. Non-negotiable scope

The implementation must preserve these ideas from the main plan:

1. The company digital twin is the central product.
2. Departments are represented by specialized agents.
3. Agents inspect the same shared company state but receive permission-filtered departmental views.
4. The system reveals direct, dependent, second-order, delayed, and feedback effects.
5. The primary scenario uses seven data vendors with $8B in spend and a $2B reduction target.
6. The system calculates vendor overlap and tests all 128 keep/remove portfolios.
7. The secondary scenario exposes institutional-knowledge loss and stranded workflows.
8. Numerical results and hard constraints come from deterministic code.
9. Agent claims are structured, traceable, and challengeable.
10. A human approves or rejects the final recommendation.

### Enhancements adopted from the supporting plans

- Multi-dimensional vendor overlap rather than one overlap score
- Gross savings versus displaced cost versus net value
- Evidence references on graph edges and agent claims
- “Act now,” “do not act,” and “delay” futures
- Quick deterministic simulation for agent tools and full uncertainty simulation for final results
- Mitigation re-simulation
- Item-level counterfactuals
- Sensitivity-based missing-question selection
- Persisted run events and audit history
- Live-only agent suggestions with explicit unavailable states
- Frozen JSON contracts in Hour 0
- A planted ground-truth graph for evaluation
- Explicit honest limitations

### Ideas intentionally not adopted

| Excluded idea | Reason |
|---|---|
| Decorative 3D office expansion | Dynamic departments and an evidence-backed board review were approved on 2026-09-27; implement only the bounded scope in Section 31 |
| Long free-form agent debate | Slow, expensive, difficult to validate, and distracts from the twin |
| Person-level “fire/retain” recommendations | Creates ethical, legal, and product-positioning risk |
| Autonomous execution | Human approval must remain mandatory |
| Real enterprise integrations during the hackathon | Synthetic evidence is sufficient to prove the architecture |
| Full-fidelity replica of every company operation | The MVP is a decision-relevant twin, not a perfect corporate simulation |

---

## 3. User and business workflow

### Primary users

- CFO and FP&A teams
- COO and transformation offices
- Strategy and corporate-development teams
- Procurement and vendor-management teams
- CIO, CTO, and enterprise data leadership
- Business-unit executives

### End-to-end user journey

1. The user opens the current company twin.
2. The user enters a decision, objective, deadline, and hard constraints.
3. Canary Pact validates the brief and shows what information it will use.
4. The platform creates three default futures:
   - act now;
   - do not act;
   - delay action.
5. Candidate alternatives are generated.
6. Relevant department agents analyze each alternative.
7. The propagation engine calculates the organizational blast radius.
8. The optimizer filters infeasible alternatives and ranks the remainder.
9. The challenger identifies missed dependencies and unsupported assumptions.
10. The system asks the highest-value missing question, if needed.
11. The user answers and affected calculations are re-run.
12. The platform generates a decision package.
13. An authorized human approves, rejects, or requests another scenario.
14. The decision and its exact inputs are recorded in the audit log.

---

## 4. Demonstration scenarios

## 4.1 Primary scenario: data-vendor consolidation

### Decision brief

> Reduce annual external-data spending from $8B to no more than $6B without breaking compliance, reducing critical data coverage below 100%, reducing sales performance by more than 3%, or creating unacceptable customer impact.

### Synthetic vendor portfolio

| Vendor | Cost | Main contribution | Important overlap | Main consumers |
|---|---:|---|---|---|
| ApexData | $1.6B | Company and contact attributes | Beacon, Echo | Sales, Marketing |
| BeaconIQ | $1.2B | Contact enrichment and firmographics | Apex | Sales |
| CinderSignals | $1.4B | Purchase-intent signals | Echo | Marketing, Sales |
| DeltaVerify | $0.9B | Identity and compliance verification | Low; critical | Risk, Compliance |
| EchoMarket | $1.1B | Market and account intelligence | Apex, Cinder | Strategy, Marketing |
| FluxBehavior | $0.8B | Behavioral and product-usage signals | Low | Product, AI/Data |
| GraniteGeo | $1.0B | Geographic and macroeconomic risk | Delta | Operations, Risk |

Total synthetic spend: **$8.0B**.

### Required system behavior

- Calculate all 128 keep/remove combinations.
- Reject portfolios with less than $2B gross savings.
- Recalculate coverage, quality, freshness, permitted use, and critical attributes.
- Identify departments, workflows, systems, models, controls, and KPIs affected.
- Separate gross savings, termination cost, migration cost, displaced work, business loss, and net value.
- Compare the naive plan with the recommended plan.
- Show act-now, do-nothing, and delay futures.
- Produce a transition plan and stop/rollback conditions.

### Multi-dimensional overlap

Every vendor pair is compared across:

- entity or record coverage;
- fields and attributes;
- geographic coverage;
- historical depth;
- freshness;
- accuracy;
- licensing and permitted use;
- consumer-team overlap;
- downstream workflow overlap;
- model-feature overlap;
- substitutability and migration difficulty.

Two vendors are not considered substitutes merely because they contain the same accounts.

### Expected demonstration insight

The obvious plan may remove the most expensive vendor. The recommended plan should instead demonstrate that:

- ApexData has high company-wide marginal value;
- DeltaVerify is compliance-critical;
- BeaconIQ and EchoMarket have lower unique contribution after overlap;
- removing BeaconIQ and EchoMarket saves $2.3B before transition costs;
- a small set of unique EchoMarket attributes must be migrated first;
- the plan stays within the sales, customer, and compliance constraints.

The result must be produced from the dataset and engine, not inserted only as presentation text.

## 4.2 Secondary scenario: knowledge-loss and stranded workflows

### Decision brief

> Evaluate the operational consequences of eliminating eight staff roles that currently support two workflows.

### Required system behavior

- Model people as anonymized tokens, roles, skills, knowledge assets, backup coverage, and recent workflow activity.
- Show which procedures lose all capable owners.
- Detect two workflows that become stranded.
- Calculate documentation gaps, training time, replacement cost, recovery-time risk, and customer/service consequences.
- Avoid ranking named people or recommending who should be fired.
- Recommend workflow-level mitigations:
  - retain required role capacity temporarily;
  - document exception handling;
  - train backup owners;
  - shadow workflow execution;
  - automate repeatable steps;
  - stage the change after readiness gates pass;
  - obtain equivalent savings from lower-risk resources.
- Re-run the scenario after mitigations and show the risk reduction.

### Ethical output rule

The system may say:

> “Workflow B requires two independent qualified owners before this role reduction is operationally safe.”

It must not say:

> “Fire Person A and retain Person B.”

---

## 5. System architecture

```mermaid
flowchart TD
    A["Enterprise evidence or synthetic artifacts"] --> B["Versioned company twin"]
    B --> C["Scenario orchestrator"]
    C --> D["Department agents"]
    C --> E["Simulation and optimization engine"]
    D --> F["Impact and evidence ledger"]
    E --> F
    F --> G["Blast radius and decision package"]
```

### 5.1 Architectural rule

**The LLM reasons; code calculates.**

Agents may identify potential impacts, challenge assumptions, extract dependencies, and explain results. They may not calculate authoritative savings, override policies, invent entities, or select an infeasible plan.

### 5.2 Components

1. Evidence ingestion and normalization
2. Identity and alias resolution
3. Versioned company twin
4. Decision-brief parser
5. Scenario state manager
6. Dynamic agent router
7. Department agents
8. Agent-output validator and merger
9. Deterministic propagation engine
10. Vendor-overlap engine
11. Knowledge-risk engine
12. Baseline-pressure and time-horizon engine
13. Constraint and portfolio optimizer
14. Uncertainty and forecast engine
15. Mitigation engine
16. Sensitivity and missing-question selector
17. Explanation and decision-package generator
18. Event stream, run-state restoration, and audit log
19. Web dashboard

### 5.3 Recommended hackathon stack

- Python 3.11+
- FastAPI and Uvicorn
- Pydantic for all contracts
- NetworkX for the company graph
- NumPy for uncertainty sampling
- JSON files or SQLite for scenario state and audit records
- Next.js/React
- Cytoscape.js or React Flow for graph visualization
- Recharts or another simple chart library
- WebSockets or server-sent events for live progress
- One model provider behind a thin wrapper

### 5.4 Production evolution

- Graph database for large twins
- Event-sourced state and temporal graph history
- Workflow engine with retries and durable execution
- Enterprise data connectors
- Identity resolution across source systems
- Customer-cloud or isolated deployment
- Fine-grained authorization and source-permission inheritance
- Calibrated causal models and customer-specific coefficients
- Large-scale mathematical optimization
- Observed-versus-predicted outcome learning

---

## 6. Twin construction and evidence

### 6.1 Hackathon source artifacts

Use synthetic but realistic artifacts:

- vendor-contract summaries;
- data-catalog export;
- workflow inventory;
- system ownership file;
- model-feature registry;
- department and KPI definitions;
- runbooks and architecture notes;
- anonymized workflow activity;
- knowledge and backup-owner matrix;
- policy and compliance-control definitions.

### 6.2 Evidence-backed edges

Every inferred dependency edge stores:

- source entity;
- target entity;
- relationship type;
- strength;
- criticality;
- substitutability;
- time lag;
- confidence;
- evidence source and snippet;
- extraction method;
- last validation date.

### 6.3 AI extraction proof

The digital twin may be seeded from JSON for demo reliability, but include a narrow AI proof:

1. Give the system three to five noisy synthetic artifacts.
2. Extract selected entities, aliases, and dependency edges.
3. Compare the extracted edges against a hidden planted graph.
4. Display precision, recall, and F1 for:
   - simple keyword baseline;
   - zero-shot extraction;
   - Canary Pact extraction plus alias resolution.

This proves that AI helps construct the map rather than merely narrating a hard-coded graph.

### 6.4 Twin versioning

Every baseline and scenario must record:

- `twin_version`;
- `data_snapshot_id`;
- `policy_version`;
- `coefficient_version`;
- `agent_prompt_version`;
- `model_id`;
- `created_at`;
- `created_by`.

The baseline is immutable during a simulation. Each future is an isolated clone.

---

## 7. Core data model

### 7.1 Entities

- Organization
- Department
- PersonToken
- Role
- Skill
- KnowledgeAsset
- Procedure
- Workflow
- Project
- System
- Vendor
- Contract
- Dataset
- DataField
- Model
- CustomerSegment
- KPI
- Policy
- Control
- Decision
- Intervention
- Scenario
- Impact
- Mitigation
- Evidence

### 7.2 Relationships

- `OWNS`
- `WORKS_ON`
- `KNOWS`
- `BACKS_UP`
- `ENABLES`
- `MAINTAINS`
- `PROVIDES`
- `CONSUMES`
- `DEPENDS_ON`
- `SUPPORTS`
- `SUBSTITUTES_FOR`
- `CONTRIBUTES_TO`
- `SERVES`
- `CONSTRAINED_BY`
- `REQUIRES_CONTROL`
- `APPROVES`
- `AFFECTS`

### 7.3 Scenario state

```json
{
  "run_id": "run_2026_09_26_001",
  "decision_id": "dec_vendor_reduction",
  "baseline_twin_version": "twin_v12",
  "phase": "department_analysis",
  "active_scenario_ids": ["act_now", "inaction", "delay"],
  "candidate_plan_ids": [],
  "agent_assessments": [],
  "computed_impacts": [],
  "questions": [],
  "recommendation_id": null,
  "status": "running"
}
```

---

## 8. Frozen contracts

The team must freeze these contracts before parallel work begins. Any schema change after Hour 1 requires agreement from every owner.

### 8.1 Decision brief

```json
{
  "decision_id": "dec_vendor_reduction",
  "decision_type": "resource_reduction",
  "statement": "Reduce annual data-vendor spending by at least $2B.",
  "goal": {
    "metric": "annual_vendor_savings_usd",
    "target": 2000000000
  },
  "horizon_days": 365,
  "resource_scope": ["data_vendors"],
  "constraints": {
    "preserve_compliance": true,
    "minimum_critical_coverage_pct": 100,
    "maximum_sales_impact_pct": 3,
    "maximum_customer_impact_pct": 2
  },
  "futures": ["act_now", "inaction", "delay"]
}
```

### 8.2 Typed impact

```json
{
  "impact_id": "impact_102",
  "decision_id": "dec_vendor_reduction",
  "scenario_id": "act_now_plan_4",
  "source_entity": "vendor_echo",
  "affected_entity": "marketing_segmentation",
  "affected_department": "marketing",
  "level": "dependent",
  "direction": "decrease",
  "metric": "segment_coverage_pct",
  "magnitude": 4.2,
  "unit": "percent",
  "first_effect_day": 14,
  "peak_effect_day": 60,
  "reversibility": "medium",
  "confidence": 0.79,
  "dependency_path": [
    "vendor_echo",
    "account_intelligence",
    "marketing_segmentation"
  ],
  "evidence_refs": ["contract_echo_2", "catalog_edge_81"],
  "assumptions": ["ApexData retains company-level coverage"],
  "status": "computed"
}
```

### 8.3 Department-agent assessment

```json
{
  "agent": "operations",
  "scenario_id": "act_now_plan_4",
  "affected_entities": ["workflow_vendor_reconciliation"],
  "proposed_impacts": [],
  "failure_modes": ["unmatched records accumulate after schema changes"],
  "edge_cases": ["historical records remain licensed but refresh access ends"],
  "missing_dependencies": [],
  "questions": ["Who currently resolves schema exceptions?"],
  "objections": [],
  "assumptions": ["no replacement integration exists"],
  "evidence_refs": ["workflow_map_7", "incident_22"],
  "confidence": 0.82
}
```

### 8.4 Simulation result

```json
{
  "plan_id": "plan_beacon_echo",
  "future": "act_now",
  "interventions": ["remove_beacon", "remove_echo"],
  "gross_savings_usd": 2300000000,
  "termination_cost_usd": 90000000,
  "migration_cost_usd": 130000000,
  "displaced_cost_usd": 120000000,
  "expected_business_loss_usd": 0,
  "net_value_usd": 1960000000,
  "affected_departments": ["sales", "marketing", "engineering", "ai_data"],
  "constraint_violations": [],
  "orphaned_workflows": [],
  "impacts": [],
  "risk": {
    "score": 28,
    "p10_net_value_usd": 1700000000,
    "p50_net_value_usd": 1960000000,
    "p90_net_value_usd": 2100000000
  },
  "assumptions": [],
  "monitoring": [],
  "feasible": true
}
```

### 8.5 Event

```json
{
  "event_id": "evt_000123",
  "run_id": "run_2026_09_26_001",
  "sequence": 123,
  "type": "agent_assessment_completed",
  "actor": "operations",
  "scenario_id": "act_now_plan_4",
  "timestamp": "2026-09-26T16:10:00Z",
  "payload": {}
}
```

---

## 9. Orchestration state machine

The orchestrator is deterministic Python, not an LLM.

```text
VALIDATE BRIEF
      ↓
FREEZE BASELINE TWIN
      ↓
BUILD ACT / INACTION / DELAY FUTURES
      ↓
GENERATE AND VALIDATE CANDIDATE PLANS
      ↓
ROUTE TO AFFECTED DEPARTMENT AGENTS
      ↓
PARALLEL DEPARTMENT ANALYSIS
      ↓
VALIDATE AND MERGE STRUCTURED OUTPUTS
      ↓
DETERMINISTIC IMPACT PROPAGATION
      ↓
ONE CROSS-AGENT CHALLENGE ROUND
      ↓
ONE TARGETED DEPARTMENT RESPONSE ROUND
      ↓
VALIDATE REPLIES + PROPAGATE NEW DEPENDENCIES
      ↓
CONSTRAINT FILTER + OPTIMIZATION
      ↓
FULL UNCERTAINTY RUN ON FINALISTS
      ↓
MISSING-FACT SELECTION
      ↓
OPTIONAL USER ANSWER + PARTIAL RE-RUN
      ↓
MITIGATION RE-SIMULATION
      ↓
DECISION PACKAGE + HUMAN APPROVAL
```

### 9.1 Dynamic routing

Define all department agents but run only those connected to the proposed decision through the graph.

Example:

- Vendor removal routes to Finance, Sales, Marketing, Operations, Engineering, AI/Data, Risk/Compliance, and Customer/Market.
- Workforce knowledge loss routes to Finance, People/Knowledge, Operations, Engineering, Risk/Compliance, and Customer/Market.

This preserves the department-agent concept without wasting time and tokens on irrelevant agents.

### 9.2 Parallel and serial stages

- Independent department assessments run in parallel.
- Output merging waits until the first pass completes.
- Deterministic propagation runs after merging.
- One challenge round is serially triggered from the merged blast radius.
- One targeted response round follows the challenge: at most three departments, each answering at most three objections in severity order. Each receives its prior assessment, linked objections, and the updated permission-filtered simulation context.
- Reply positions are revised, supported, or unresolved. Supported/revised positions require visible evidence references and do not establish consensus or resolve the criticism automatically.
- Final optimization runs after reply validation and dependency propagation; unaddressed concerns remain in the decision package.

### 9.3 Convergence

User-approved extension (2026-09-27): stop agent iteration after one challenge round and one bounded targeted response round. Do not respond recursively to replies. Production may stop when:

- no new severity-3-or-higher risk is found;
- no new dependency is proposed;
- no constraint status changes;
- candidate ranking remains unchanged;
- or a configured iteration limit is reached.

### 9.4 Orchestrator pseudocode

```python
async def run_decision(brief: DecisionBrief) -> DecisionPackage:
    validate_brief(brief)
    baseline = twin_store.freeze_current()
    run = create_run(brief, baseline.version)

    futures = scenario_factory.create_default_futures(brief, baseline)
    candidates = candidate_engine.generate(brief, baseline)
    candidates = deterministic_validator.filter_invalid(candidates, brief)

    for candidate in candidates:
        affected_agents = agent_router.select(candidate, baseline.graph)
        assessments = await run_agents_parallel(
            affected_agents,
            candidate,
            baseline.permission_filtered_views(),
        )
        validated = validate_agent_outputs(assessments, baseline)
        merged = merge_into_impact_ledger(validated)
        quick_result = simulation.quick(candidate, baseline, merged)
        run.record(candidate, quick_result)

    challenged = await challenger.review(run.top_candidates(3))
    run.merge_challenges(challenged)
    replies = await respond_to_targeted_objections(run, max_agents=3, max_issues_per_agent=3)
    run.validate_and_merge_replies(replies)
    rerun_changed_candidates(run)

    feasible = constraints.filter(run.candidates, brief.constraints)
    ranked = optimizer.rank(feasible)
    finalists = simulation.full(ranked[:3], futures, seed=brief.seed)

    question = sensitivity.highest_value_question(finalists)
    mitigated = mitigation_engine.generate_and_resimulate(finalists[0])

    package = decision_package.build(
        brief=brief,
        baseline=baseline,
        futures=futures,
        finalists=finalists,
        question=question,
        mitigated=mitigated,
    )
    return package
```

---

## 10. Department-agent design

### 10.1 Agent roster

| Agent | Owns |
|---|---|
| Finance | Savings, penalties, displaced costs, payback, financial pressure |
| Marketing | Audience coverage, campaigns, attribution, acquisition |
| Sales | Account coverage, enrichment, pipeline, conversion, renewals |
| Operations | Process continuity, handoffs, manual workload, service levels |
| Engineering | Integrations, reliability, maintenance, migration, technical debt |
| AI/Data | Data overlap, lineage, quality, freshness, features, model effects |
| People/Knowledge | Skills, documentation, backup coverage, training, knowledge concentration |
| Risk/Compliance | Policies, controls, legal limitations, hard constraints |
| Customer/Market | Customer experience, churn, trust, competitive reaction |
| Challenger | Missing departments, unsupported assumptions, circular logic, overlooked combinations |

### 10.2 Agent input

Each agent receives:

- role and responsibility;
- decision brief;
- relevant scenario and intervention;
- permission-filtered twin subgraph;
- computed direct effects;
- relevant policies and hard constraints;
- evidence snippets;
- a compact list of already-known impacts;
- exact structured-output schema.

Agents do not receive the complete raw twin unless authorized and necessary.

### 10.3 Agent tools

- `get_entity(id)`
- `list_dependencies(id, direction, max_depth)`
- `get_evidence(edge_id)`
- `get_policy(policy_id)`
- `run_quick_impact(interventions)`
- `compare_candidates(candidate_ids)`
- `propose_dependency(source, target, type, evidence)`
- `submit_assessment(assessment)`

Tools are read-only except submission of structured hypotheses and assessments.

### 10.4 Output enforcement

- Use provider structured-output mode when available.
- Validate all output with Pydantic.
- Reject unknown entity IDs.
- Clamp confidence to `[0, 1]`.
- Convert unsupported facts into hypotheses.
- Require evidence references for factual dependency claims.
- Retry once after validation failure.
- Mark the assessment unavailable if the retry fails.

### 10.5 Agent context management

- Put fixed role instructions first to benefit from prompt caching.
- Include only the permission-filtered subgraph.
- Send compact impact summaries, not full transcripts.
- Limit each agent to three tool calls.
- Limit the challenge pass to the highest-severity unresolved impacts.
- Maintain a per-run token and time budget.

### 10.6 Agent failure policy

An agent failure must never block the deterministic engine.

- Mark the agent assessment unavailable.
- Surface the missing perspective in the final package.
- Increase uncertainty for dependencies owned by that department.
- Continue if hard constraints can still be evaluated.

---

## 11. Simulation engine

### 11.1 Two execution modes

#### Quick mode

- Deterministic midpoint assumptions
- Millisecond-to-low-second target
- Used by agents and interactive UI
- Returns one expected impact path

#### Full mode

- Runs only on the top three alternatives plus inaction and delay
- Samples uncertain edge weights and impact coefficients
- Returns P10/P50/P90 ranges
- Uses a fixed random seed for reproducible results

### 11.2 Scenario futures

Every decision produces:

1. **Act now:** apply the intervention immediately.
2. **Inaction:** do not apply it, but continue the pressure that created the decision.
3. **Delay:** apply the recommended intervention after a configured delay.
4. **Alternative plans:** other feasible ways to reach the objective.

Inaction is not modeled as “nothing happens.” The cost pressure, contract renewals, operational fragility, or other triggering forces continue.

### 11.3 Propagation

Start with direct loss or change at intervention nodes, then traverse outgoing dependencies.

Recommended MVP behavior:

- maximum depth: 4;
- minimum effect threshold: 2%;
- store the strongest explanatory path;
- propagate time lags;
- iterate cycles to a fixed point;
- cap iteration count at 10;
- label every impact as direct, dependent, second-order, delayed, or feedback.

A noisy-OR combination can merge independent upstream losses:

```text
loss(target) = 1 - product(1 - loss(source) × edge_weight)
```

### 11.4 Cost accounting

```text
net_company_value
= gross_recurring_savings
- termination_cost
- migration_cost
- displaced_labor_cost
- displaced_infrastructure_cost
- expected_business_loss
- risk_penalty
- uncertainty_penalty
```

Always show the components separately.

### 11.5 Vendor optimizer

- Generate all 128 vendor portfolios.
- Apply hard constraints first.
- Calculate quick impacts for feasible portfolios.
- Rank by net company value.
- Keep the top three for full simulation.
- Preserve rejection reasons for every infeasible option.

### 11.6 Knowledge-risk engine

For every critical workflow, calculate:

- capable owner count;
- independent backup count;
- recent execution coverage;
- documentation completeness;
- exception-path documentation;
- automation coverage;
- recovery knowledge;
- time to train a replacement;
- workflow criticality;
- maximum acceptable downtime.

A workflow is stranded when it loses all qualified owners or falls below its configured minimum coverage.

### 11.7 Risk score

Return a 0–100 score with visible components:

| Component | Suggested weight |
|---|---:|
| Financial downside | 25 |
| Capability and workflow loss | 25 |
| Customer and revenue impact | 20 |
| Compliance and control risk | 20 |
| Execution and uncertainty | 10 |

Do not hide the component values behind the headline score.

### 11.8 Mitigation re-simulation

Mitigations are graph changes with cost and duration.

Examples:

- migrate unique fields;
- negotiate temporary read access;
- add a replacement feed;
- document a workflow;
- train a backup owner;
- add monitoring;
- stage a contract termination;
- delay a role reduction until readiness gates pass.

The engine must re-run after mitigation and show whether the plan becomes feasible.

### 11.9 Item-level counterfactual

For each intervention in the recommended plan, show:

- what that intervention contributes;
- what happens if it is removed from the plan;
- whether the savings target is still met;
- which replacement closes the gap;
- whether the replacement creates more damage;
- recommendation: keep, replace, or borderline.

### 11.10 Missing-fact selector

Perturb every uncertain input within its allowed range. Rank questions by:

```text
probability_of_changing_winner
× value_gap_between_alternatives
- cost_of_getting_answer
```

Ask only the top question during the demo.

---

## 12. Backend services

### 12.1 API endpoints

- `POST /api/twin/build`
- `GET /api/twin`
- `GET /api/twin/entities/{id}`
- `GET /api/twin/edges/{id}/evidence`
- `GET /api/twin/evaluation`
- `POST /api/decisions`
- `POST /api/decisions/{id}/run`
- `GET /api/runs/{id}`
- `GET /api/runs/{id}/events`
- `GET /api/runs/{id}/agent-assessments`
- `GET /api/runs/{id}/blast-radius`
- `POST /api/runs/{id}/answer`
- `POST /api/runs/{id}/mitigate`
- `POST /api/runs/{id}/decision`
- `GET /api/runs/{id}/recommendation`
- `GET /api/audit`

### 12.2 Run lifecycle

Statuses:

- `created`
- `validating`
- `building_futures`
- `running_agents`
- `propagating`
- `challenging`
- `optimizing`
- `forecasting`
- `awaiting_answer`
- `generating_package`
- `completed`
- `failed`

### 12.3 Event streaming

Emit typed events for:

- phase changes;
- agent started/completed/failed;
- proposed dependency;
- impact computed;
- constraint violated;
- candidate rejected;
- challenge raised;
- question selected;
- mitigation applied;
- recommendation completed;
- human decision recorded.

Persist events in sequence so run history and audit state can be restored exactly.

### 12.4 LLM wrapper

One wrapper owns:

- model configuration;
- structured output;
- timeout;
- retry with backoff;
- concurrency semaphore;
- token budget;
- prompt metadata and response metrics;
- response validation;
- explicit unavailable results when live calls fail.

No application module calls a provider SDK directly.

---

## 13. Frontend

### 13.1 Screen: Twin map

- Department, resource, workflow, system, knowledge, customer, and KPI nodes
- Evidence-backed edges
- Confidence and last-validated indicators
- Search and node filters
- Click an edge to inspect evidence

### 13.2 Screen: Decision composer

- Natural-language statement
- Objective and target
- Time horizon
- Protected entities
- Hard constraints
- Candidate intervention scope

### 13.3 Screen: Simulation progress

- Current orchestration phase
- Which department agents are active
- Structured edge cases and objections
- No long chat transcript by default
- Conflicts and missing evidence highlighted

### 13.4 Screen: Blast radius

- Ripple from intervention to department and company outcome
- Direct, dependent, second-order, delayed, and feedback labels
- Department impact cards
- Cost displacement breakdown
- Risk-over-time chart
- Confidence and evidence drawer

### 13.5 Screen: Futures and alternatives

- Act now
- Inaction
- Delay
- Naive plan
- Lowest gross cost
- Lowest risk
- Recommended balanced plan
- Rejection reason for infeasible plans

### 13.6 Screen: Decision package

- Recommendation
- Alternatives considered
- Department impacts
- Critical risks
- Missing information
- Assumptions and confidence
- Mitigations
- Implementation sequence
- Monitoring and rollback triggers
- Approve/reject control
- Audit record

### 13.7 Primary hero moment

The user selects the naive vendor cut. The graph turns red as data loss propagates into models, workflows, departments, and KPIs. The user then clicks **Find safer plan** and sees a different portfolio reach the same $2B target with fewer violations and higher net value.

### 13.8 Secondary hero moment

The user applies the workforce reduction. Two workflows immediately become stranded because knowledge coverage falls to zero. A mitigation plan restores backup coverage and changes the scenario from infeasible to conditionally feasible.

### 13.9 Interactive office and structured board review

The existing office becomes a data-driven view of the company twin, with department inspection, proposed organization changes, dependency paths, and time-based impacts. A board-review mode presents actual agent assessments and the existing challenger pass. Section 31 defines the approved implementation sequence and acceptance checks. The graph and accessible department list remain available alongside the office.

---

## 14. Repository structure

```text
canary-pact/
├── README.md
├── .env.example
├── contracts/
│   ├── decision_brief.schema.json
│   ├── twin.schema.json
│   ├── impact.schema.json
│   ├── agent_assessment.schema.json
│   ├── simulation_result.schema.json
│   └── event.schema.json
├── data/
│   ├── generate_company.py
│   ├── synthetic_company.json
│   ├── vendor_scenario.json
│   ├── workforce_scenario.json
│   ├── artifacts/
│   └── ground_truth_graph.json
├── backend/
│   ├── app.py
│   ├── api/
│   ├── models/
│   ├── db.py
│   └── event_bus.py
├── twin/
│   ├── loader.py
│   ├── normalize.py
│   ├── resolve.py
│   ├── extract.py
│   ├── graph.py
│   ├── clone.py
│   ├── versioning.py
│   └── permissions.py
├── orchestration/
│   ├── workflow.py
│   ├── router.py
│   ├── merge.py
│   ├── challenge.py
│   └── budgets.py
├── agents/
│   ├── base.py
│   ├── finance.py
│   ├── marketing.py
│   ├── sales.py
│   ├── operations.py
│   ├── engineering.py
│   ├── data_ai.py
│   ├── people_knowledge.py
│   ├── risk_compliance.py
│   ├── customer_market.py
│   └── challenger.py
├── engine/
│   ├── futures.py
│   ├── changes.py
│   ├── overlap.py
│   ├── knowledge_risk.py
│   ├── propagate.py
│   ├── constraints.py
│   ├── optimize.py
│   ├── forecast.py
│   ├── mitigate.py
│   └── sensitivity.py
├── llm/
│   ├── client.py
│   ├── prompts.py
│   ├── schemas.py
│   └── explain.py
├── eval/
│   ├── graph_eval.py
│   ├── engine_tests.py
│   └── agent_checks.py
├── runs/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── hooks/
│   └── lib/
└── tests/
```

---

## 15. Contract-first integration strategy

No owner waits for another owner.

### Hour-0 shared artifact

Publish schema-valid example payloads for each frozen contract, including event variants and loading, success, empty, and error responses. These fixtures let downstream layers build before upstream implementations are ready, but they are development inputs only and must never be served as recorded agent advice.

### Parallel development

| Layer | Develops against |
|---|---|
| Twin and engine | Real synthetic company and ground-truth graph |
| Agents | Stub `run_quick_impact()` with frozen schema |
| Backend | Frozen contracts and schema-valid request/response fixtures |
| Frontend | Mock API payloads covering every required UI state |

### Integration sequence

1. Engine replaces the quick-impact stub.
2. Agent assessments feed the real event ledger.
3. Backend streams real events.
4. Frontend consumes the live run event source.
5. The full vendor run is validated against deterministic acceptance checks.
6. Workforce proof reuses the same contracts and UI.

---

## 16. Build plan

### Phase 0 — Freeze the product contract

**Exit condition:** schemas, reference scenarios, dataset totals, constraints, and UI event sequence are agreed.

- Freeze all schemas in `contracts/`.
- Freeze seven vendors totaling $8B.
- Freeze the $2B objective and hard constraints.
- Freeze workforce scenario entities and expected stranded workflows.
- Prepare the live-provider test configuration.
- Assign directory ownership.

### Phase 1 — Build the company twin

**Exit condition:** baseline graph loads, validates, renders, and can be cloned.

- Generate the synthetic company.
- Validate unique IDs and relationship targets.
- Add vendor, workflow, system, KPI, policy, customer, role, and knowledge nodes.
- Add evidence and confidence to every important edge.
- Build permission-filtered department views.
- Implement baseline versioning and scenario cloning.

### Phase 2 — Build the deterministic vendor engine

**Exit condition:** all 128 portfolios run and return repeatable feasibility and ranking results.

- Implement multi-dimensional overlap.
- Implement vendor-removal operators.
- Implement graph propagation.
- Implement cost displacement.
- Implement constraints.
- Enumerate 128 portfolios.
- Store rejection reasons.
- Verify the expected recommended portfolio.

### Phase 3 — Build orchestration and agents

**Exit condition:** a decision routes to affected agents, outputs validate, and one challenge pass completes.

- Implement the orchestrator state machine.
- Implement dynamic routing.
- Create department prompts and permission views.
- Implement tools and structured outputs.
- Validate and merge assessments.
- Add challenger pass.
- Add timeout, retry, token budget, and missing-perspective handling.

### Phase 4 — Build futures and uncertainty

**Exit condition:** top alternatives are shown against inaction and delay with reproducible ranges.

- Implement act-now, inaction, and delay futures.
- Implement time lags and pressure model.
- Add quick and full modes.
- Add seeded uncertainty sampling.
- Calculate P10/P50/P90.
- Add risk score and component breakdown.

### Phase 5 — Build decision intelligence

**Exit condition:** the system explains why the recommendation wins and how to make it safer.

- Implement item counterfactuals.
- Implement missing-fact sensitivity.
- Implement mitigation generation.
- Re-simulate mitigations.
- Build recommendation and rejected-option explanations.
- Add monitoring and rollback triggers.

### Phase 6 — Build workforce proof

**Exit condition:** removing the eight roles strands two workflows and mitigation restores required coverage.

- Add role, knowledge, procedure, and backup edges.
- Implement knowledge concentration.
- Implement stranded-workflow rules.
- Add role-level privacy rules.
- Run the same orchestration and blast-radius pipeline.
- Verify the workforce scenario with live department agents.

### Phase 7 — Build frontend and resilience

**Exit condition:** both scenarios run end-to-end with live agents and surface provider failures honestly.

- Build twin map.
- Build decision composer.
- Build agent progress.
- Build blast-radius graph.
- Build futures comparison.
- Build decision package and audit view.
- Add one-click reset.
- Record backup video.

---

## 17. Hackathon execution schedule

### First 45 minutes

- Confirm rules and submission requirements.
- Freeze contracts and dataset.
- Confirm model access.
- Create branches and directory ownership.
- Publish schema-valid cross-layer example payloads.

### Build block 1

- Twin owner: dataset, graph, clone, validation.
- Engine owner: overlap, change operators, constraints.
- Agent/backend owner: LLM wrapper, Pydantic models, orchestrator skeleton.
- Frontend owner: application shell and live-event-driven twin graph.

### Build block 2

- Complete single-vendor ablation.
- Complete graph impact propagation.
- Run all 128 portfolios.
- Complete one department-agent call.
- Connect the live event stream to the UI.

### Build block 3

- Complete dynamic routing and parallel assessments.
- Merge assessments and run challenge pass.
- Complete act/inaction/delay comparison.
- Replace mock backend events with live events.

### Build block 4

- Complete decision package.
- Add missing question and mitigation re-simulation.
- Add compact workforce scenario.
- Verify both live scenarios against their deterministic acceptance checks.

### Final block

- Test seeded results.
- Test live-agent failure and missing-perspective handling.
- Fix only correctness and demo blockers.
- Record backup video.
- Write submission and rehearse.

### Cut order if behind

1. Natural-language decision parsing
2. Live prose generation
3. Full Monte Carlo; keep deterministic midpoint and labeled ranges
4. Delay future; keep act and inaction
5. Graph-extraction comparison UI; keep evidence-backed seeded graph
6. Advanced graph editing

Never cut:

- shared company twin;
- department-agent orchestration;
- deterministic propagation and constraints;
- vendor overlap;
- naive-versus-recommended comparison;
- traceable blast radius;
- workforce stranded-workflow proof;
- explicit unavailable-agent handling;
- human approval.

---

## 18. Four-person ownership

| Owner | Responsibilities | Merge boundary |
|---|---|---|
| Twin/data owner | Dataset, graph, evidence, cloning, views, knowledge model, graph evaluation | `data/`, `twin/`, `eval/graph_eval.py` |
| Engine owner | Changes, overlap, propagation, futures, constraints, optimization, forecast, mitigations, sensitivity | `engine/`, engine tests |
| Agent/backend owner | LLM wrapper, agents, orchestration, APIs, events, run restoration, audit | `agents/`, `orchestration/`, `backend/`, `llm/` |
| Frontend/product owner | UX, graph, blast radius, futures, decision package, demo, pitch, submission | `frontend/`, product fixtures, demo assets |

The team integrates through frozen contracts. `main` must remain runnable. Merge small changes frequently.

---

## 19. Verification plan

### 19.1 Twin tests

- Every referenced node exists.
- Every critical edge has evidence and confidence.
- The baseline is unchanged after a scenario.
- Alias resolution maps planted aliases correctly.
- Permission-filtered views do not reveal unauthorized entities.
- Graph-evaluation metrics regenerate from code.

### 19.2 Vendor tests

- Vendor costs total exactly $8B.
- Exactly 128 portfolios are considered.
- Removing a fully redundant vendor preserves required coverage.
- Removing a partially overlapping vendor reports unique field and workflow loss.
- Removing DeltaVerify violates compliance.
- A plan saving less than $2B is rejected.
- Two individually safe removals can become unsafe together.
- The expected best feasible portfolio ranks first.
- Re-running the same input produces the same quick result.

### 19.3 Workforce tests

- Removing all eight roles strands both workflows.
- A qualified backup prevents a workflow from becoming stranded.
- Missing exception knowledge is detected separately from ordinary documentation.
- Knowledge transfer changes the risk result.
- No output ranks named individuals.
- The recommended mitigation reports time and cost.

### 19.4 Agent tests

- Only affected agents execute.
- Every output validates against the schema.
- Unknown entities are rejected.
- Unsupported claims are labeled hypotheses.
- Every material factual claim has evidence.
- Agent numbers agree with deterministic tool results.
- One challenge round surfaces the planted missed dependency.
- Timeout and malformed output surface an unavailable assessment without substituting recorded advice.

### 19.5 Simulation tests

- Empty intervention equals the inaction baseline.
- Every loss remains within `[0,1]`.
- Propagation stops at configured depth.
- Cycles converge within the iteration cap.
- Wider uncertainty ranges produce wider output bands.
- A fixed seed produces identical P10/P50/P90 results.
- A mitigation changes only the expected nodes and metrics.
- Changing the high-value answer can change the winning plan.

### 19.6 Demo tests

- Live run completes twice from reset.
- A forced live-agent failure surfaces the missing perspective without substituting recorded advice.
- Browser refresh restores the selected run.
- The UI works at projector resolution.
- Every figure shown can be traced to a result or labeled assumption.
- The pitch fits the confirmed time limit.

---

## 20. Failure handling

| Failure | Behavior |
|---|---|
| Model timeout | Retry once, then mark the agent unavailable |
| Malformed agent JSON | Validate, repair safe fields, retry once, then mark unavailable |
| Missing department assessment | Continue, increase uncertainty, surface missing perspective |
| Constraint engine error | Fail closed; do not recommend the plan |
| Live event disconnect | Reconnect from last sequence number |
| Frontend refresh | Reload run state and resume events from the last persisted sequence |
| Provider outage | Continue deterministic calculations, surface missing perspectives, and withhold unsupported suggestions |
| Invalid decision brief | Return field-level validation errors |
| No feasible plan | Explain violated constraints and show closest alternatives |
| Incomplete evidence | Label hypothesis and ask for verification |

---

## 21. Security, privacy, and responsible use

### Hackathon

- Synthetic company only
- Anonymized person tokens
- Secrets only in environment variables
- No real employee or customer data
- No autonomous action

### Production

- Customer-controlled deployment option
- Encryption in transit and at rest
- Tenant isolation
- Fine-grained role and attribute-based access
- Source permissions inherited by agent tools
- HR, finance, customer, and engineering data separated
- Immutable audit trail
- Model, prompt, twin, coefficient, and policy versioning
- Retention and deletion policies
- Human authorization
- Workforce fairness and legal review
- No productivity scoring or person-level termination ranking
- Prediction-versus-outcome monitoring

---

## 22. Observability and audit

Record for every model call:

- run and scenario IDs;
- agent;
- model identifier;
- prompt version and hash;
- tool calls;
- input/output token counts;
- latency;
- validation failures;
- unavailable status and validation errors.

Record for every decision:

- exact decision brief;
- twin and data versions;
- candidate alternatives;
- constraints and rejection reasons;
- assumptions and confidence;
- agent assessments;
- computed impacts;
- human override;
- final approval or rejection;
- post-decision observed outcomes when available.

---

## 23. Performance and budget targets

### Hackathon targets

- Twin load: under 1 second
- Quick simulation: under 250 ms per vendor portfolio
- All 128 portfolios: under 5 seconds locally
- Department-agent first pass: under 60 seconds wall time with bounded parallelism
- Final full simulation: under 10 seconds for top alternatives
- Complete live run: under 2 minutes

### Controls

- Concurrency semaphore
- Per-agent tool-call limit
- Per-call timeout
- Per-run token ceiling
- Cached fixed prompt prefixes

---

## 24. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Agent orchestration exceeds available time | High | High | Dynamic routing, one challenge round, frozen schemas, cached outputs |
| Agents hallucinate dependencies | Medium | High | Evidence requirement, unknown-ID rejection, deterministic validation |
| Results look hard-coded | Medium | High | Compute 128 portfolios, expose constraints, add AI graph-extraction evaluation |
| Live model is slow or unavailable | Medium | Critical | Bounded retry, missing-perspective state, deterministic results, backup video |
| Vendor assumptions are challenged | High | Medium | Show assumptions, confidence, sensitivity, and synthetic labels |
| Workforce scenario appears like a layoff recommender | Medium | High | Role/workflow-level output only; no named-person ranking |
| Contract drift blocks integration | Medium | High | Freeze schemas in Hour 0 and add contract tests |
| Graph becomes visually unreadable | Medium | Medium | Depth filters, impact threshold, scenario-specific subgraphs |
| Monte Carlo consumes time | Medium | Medium | Run only on finalists; cut to deterministic ranges if necessary |
| Team builds separate demos instead of one system | Medium | High | Same twin, contracts, orchestration, event stream, and UI for both scenarios |

---

## 25. Demo script

### Opening

“A company needs to remove $2 billion from seven data vendors costing $8 billion. Finance can see the invoices, but not every model, workflow, team, customer, and compliance control depending on the data. Canary Pact lets the company rehearse the decision first.”

### Demo sequence

1. Show the company twin and evidence-backed dependencies.
2. Enter the $2B reduction objective and constraints.
3. Load the naive plan: remove the largest vendors.
4. Run affected department agents.
5. Show the blast radius spreading through Data, Engineering, Sales, Marketing, Risk, and customers.
6. Show gross savings collapsing after displaced cost and business impact.
7. Compare act-now, inaction, and delay.
8. Click **Find safer plan**.
9. Show all feasible portfolios and the recommended BeaconIQ/EchoMarket plan.
10. Ask the highest-value missing question and update the result.
11. Apply the migration mitigation and show the improved risk.
12. Switch to the workforce proof.
13. Remove eight role tokens and show two workflows become stranded.
14. Apply knowledge-transfer and backup-owner mitigation.
15. Show the decision package and human approval gate.

### Closing

“The savings target did not change. What changed was the company left behind. Canary Pact is the flight simulator for organizational decisions.”

---

## 26. Definition of done

The project is complete for the hackathon only when:

- the company twin loads and renders;
- the baseline can be cloned without mutation;
- department agents receive filtered views and return valid structured assessments;
- the vendor engine calculates multi-dimensional overlap;
- all 128 portfolios are evaluated;
- hard constraints reject unsafe portfolios;
- the blast radius shows traceable cross-department paths;
- gross savings, displaced cost, and net value are separated;
- act-now, inaction, and at least one alternative are compared;
- the workforce scenario detects both stranded workflows;
- one mitigation is re-simulated;
- every important claim has evidence or an assumption label;
- live agent failures are surfaced without substituting recorded advice;
- the user must approve or reject the recommendation;
- the demo has been rehearsed successfully at least three times.

---

## 27. Production roadmap

### Stage 1 — Vendor and resource decisions

- Data-vendor consolidation
- SaaS and software rationalization
- Cloud and infrastructure optimization
- Contract-renewal simulations

### Stage 2 — Operational resilience

- Workflow ownership and institutional knowledge
- System and on-call dependencies
- Project cancellation and sequencing
- Tool and platform migrations

### Stage 3 — Enterprise planning

- Budget allocation
- Reorganizations
- Market-entry and product decisions
- Site consolidation
- M&A integration

### Stage 4 — Living organizational twin

- Continuous source-system synchronization
- Temporal company graph
- Learned impact coefficients
- Observed-versus-predicted calibration
- Decision templates and industry packs
- API integration into enterprise planning systems

---

## 28. Honest limitations

- The hackathon company and results are synthetic.
- A decision-relevant twin does not reproduce every organizational behavior.
- Impact coefficients are assumptions until calibrated against real outcomes.
- Agent-generated edge cases may be persuasive without being correct.
- Dependency completeness determines simulation quality.
- Uncertainty bands describe the supplied assumptions, not every possible future.
- Workforce analysis requires strict governance and human review.
- Canary Pact surfaces risks and alternatives; it does not guarantee the future.

These limitations should be stated clearly. The product’s value is making dependencies, tradeoffs, uncertainty, and the cost of alternatives visible before leadership acts.

---

## 29. Sequenced implementation backlog

This backlog is the build order. A task is complete only when its acceptance check passes.

### Milestone A — Contracts and reference scenarios

| ID | Task | Owner | Depends on | Acceptance check |
|---|---|---|---|---|
| A-01 | Freeze product vocabulary and entity IDs | All | — | No duplicate or ambiguous entity IDs |
| A-02 | Create six JSON schemas | Agent/backend | A-01 | Valid and invalid fixtures behave as expected |
| A-03 | Define seven-vendor fixture and coefficients | Twin/data | A-01 | Costs total $8B; expected winning plan documented |
| A-04 | Define workforce fixture | Twin/data | A-01 | Removing eight role tokens strands exactly two workflows |
| A-05 | Publish cross-layer example payloads | Frontend + agent/backend | A-02–A-04 | Schema-valid fixtures cover required API, event, and UI states without recorded agent advice |

### Milestone B — Company twin

| ID | Task | Owner | Depends on | Acceptance check |
|---|---|---|---|---|
| B-01 | Load and validate company JSON | Twin/data | A-02–A-04 | Invalid references fail with readable errors |
| B-02 | Build NetworkX graph | Twin/data | B-01 | All entities and relationships appear in graph |
| B-03 | Add evidence and confidence | Twin/data | B-02 | Critical edges have evidence refs and confidence |
| B-04 | Implement clone and versioning | Twin/data | B-02 | Scenario mutation leaves baseline byte-equivalent |
| B-05 | Implement permission-filtered agent views | Twin/data | B-02 | Each agent receives only permitted subgraph data |
| B-06 | Render graph in frontend | Frontend | B-02, A-05 | User can inspect nodes, paths, evidence, and confidence |

### Milestone C — Deterministic simulation

| ID | Task | Owner | Depends on | Acceptance check |
|---|---|---|---|---|
| C-01 | Implement intervention operators | Engine | B-04 | Vendor removal changes only the scenario clone |
| C-02 | Implement multi-dimensional overlap | Engine | B-02, A-03 | Expected unique and duplicated fields are calculated |
| C-03 | Implement dependency propagation | Engine | C-01 | Planted blast-radius path is reproduced |
| C-04 | Implement cost displacement | Engine | C-01, C-03 | Gross, displaced, transition, loss, and net remain separate |
| C-05 | Implement hard constraints | Engine | C-02–C-04 | Compliance-breaking plan is rejected |
| C-06 | Enumerate and rank 128 portfolios | Engine | C-05 | Expected best feasible plan ranks first |
| C-07 | Implement workforce knowledge risk | Engine | B-02, A-04 | Both planted stranded workflows are detected |

### Milestone D — Orchestration and agents

| ID | Task | Owner | Depends on | Acceptance check |
|---|---|---|---|---|
| D-01 | Implement live model wrapper | Agent/backend | A-02 | One live structured call validates |
| D-02 | Implement deterministic phase state machine | Agent/backend | D-01, B-04 | Run phases progress and persist in order |
| D-03 | Implement dynamic agent routing | Agent/backend | B-05, D-02 | Vendor and workforce scenarios route different agent sets |
| D-04 | Implement department prompts and tools | Agent/backend | D-01, C-03 | Agents can inspect evidence and call quick simulation |
| D-05 | Validate and merge assessments | Agent/backend | D-04 | Unknown IDs rejected; valid impacts enter ledger |
| D-06 | Implement one challenger pass | Agent/backend | D-05 | Planted overlooked dependency is surfaced |
| D-07 | Add timeout, retry, unavailable states, and budgets | Agent/backend | D-01–D-06 | Forced provider failure surfaces a missing perspective |

### Milestone E — Futures and decision intelligence

| ID | Task | Owner | Depends on | Acceptance check |
|---|---|---|---|---|
| E-01 | Implement act-now and inaction futures | Engine | C-06 | Empty action equals baseline with active pressure model |
| E-02 | Implement delay future | Engine | E-01 | Effects begin at configured delay and pressure continues |
| E-03 | Implement full uncertainty mode | Engine | C-06, E-01 | Same seed reproduces P10/P50/P90 |
| E-04 | Implement risk score | Engine | E-03 | Score and components match fixture expectations |
| E-05 | Implement item counterfactuals | Engine | C-06 | Removing one recommended item shows shortfall and replacement |
| E-06 | Implement missing-fact selector | Engine | E-03 | Planted sensitive unknown ranks first |
| E-07 | Implement mitigation re-simulation | Engine | C-07, E-03 | Knowledge transfer or data migration changes feasibility |

### Milestone F — Backend and audit history

| ID | Task | Owner | Depends on | Acceptance check |
|---|---|---|---|---|
| F-01 | Implement run and decision APIs | Agent/backend | D-02, C-06 | API creates run and returns stable IDs |
| F-02 | Implement typed event stream | Agent/backend | F-01 | Events arrive in sequence and validate |
| F-03 | Persist runs and audit decisions | Agent/backend | F-02 | Refresh restores complete run and approval record |
| F-04 | Restore persisted run state | Agent/backend | F-02, A-05 | Refresh restores run and audit history without re-running agents |
| F-05 | Add one-click reset | Agent/backend + frontend | F-04 | Demo returns to baseline in one action |

### Milestone G — Product experience

| ID | Task | Owner | Depends on | Acceptance check |
|---|---|---|---|---|
| G-01 | Decision composer | Frontend | F-01 | Brief validates and starts run |
| G-02 | Agent progress view | Frontend | F-02 | Active agents and structured findings update live |
| G-03 | Blast-radius view | Frontend | C-03, F-02 | User can trace intervention to company outcome |
| G-04 | Futures comparison | Frontend | E-01–E-04 | Act, inaction, delay, and alternatives compare consistently |
| G-05 | Decision package | Frontend | E-05–E-07 | Recommendation, assumptions, mitigation, and rollback visible |
| G-06 | Workforce proof | Frontend | C-07, E-07 | Stranded workflows and mitigated state are unmistakable |
| G-07 | Missing-agent state | Frontend | F-04 | Provider failure is visible and no recorded suggestion is substituted |

### Milestone H — Evaluation and delivery

| ID | Task | Owner | Depends on | Acceptance check |
|---|---|---|---|---|
| H-01 | Add narrow evidence-extraction pipeline | Twin/data | B-03 | Extracts planted edges from noisy artifacts |
| H-02 | Compare graph extraction methods | Twin/data | H-01 | Precision, recall, and F1 regenerate from code |
| H-03 | Run full automated test suite | All | A–G | Required tests pass from a clean checkout |
| H-04 | Verify performance budgets | All | H-03 | Run times meet Section 23 targets or fallback selected |
| H-05 | Record backup demo | Frontend/product | G-07 | Video covers both hero moments |
| H-06 | Complete README and submission | Frontend/product | H-03 | Setup, architecture, real-vs-synthetic, and limitations included |
| H-07 | Rehearse three times | All | H-05, H-06 | Pitch finishes within limit with no manual recovery |

---

## 30. Release gates

### Gate 1 — Schemas frozen

Required:

- Decision, impact, agent assessment, simulation result, event, and twin schemas validated
- Both scenario fixtures defined
- Cross-layer example payloads committed and schema-valid

If this gate is not complete, parallel implementation must not begin.

### Gate 2 — Deterministic vertical slice

Required:

- Baseline twin loads
- One vendor can be removed in a clone
- Blast radius propagates
- Constraints evaluate
- Frontend renders the result from real backend data

This is the first end-to-end product, even without live agents.

### Gate 3 — Agent-assisted vertical slice

Required:

- Dynamic routing works
- At least three affected agents run in parallel
- Outputs validate and merge
- Agent findings alter or enrich the blast radius without overriding deterministic facts
- A forced model failure leaves deterministic results intact and surfaces the missing perspective

### Gate 4 — Complete vendor decision

Required:

- All 128 portfolios evaluated
- Naive and recommended plans compared
- Act and inaction futures shown
- Missing question selected
- One mitigation re-simulated
- Decision package generated

### Gate 5 — Generality proof

Required:

- Workforce scenario uses the same twin contracts, orchestrator, impact ledger, and UI
- Two workflows become stranded
- Role-level mitigation restores minimum coverage
- No named-person recommendation appears

### Gate 6 — Demo safe

Required:

- Live run succeeds
- Missing live-agent perspectives are surfaced without fallback advice
- One-click reset succeeds
- Backup video exists
- Final README and submission are complete
- Three timed rehearsals succeed

---

## 31. Approved expansion: interactive office and structured board review

**Approved:** 2026-09-27, following the user's request for dynamic departments, richer office interactions, and a visualization of agents presenting and defending their findings. This section supersedes the earlier exclusion of the 3D office only for this scope. It does not authorize free-form agent debate, autonomous organizational actions, another demonstration scenario, or a new service/framework.

**Outcome:** A user can inspect their company, add or reduce departments in a proposed scenario, compare the changed organization with its baseline, and follow evidence-backed departmental assessments around the meeting table. Agents explain; the engine calculates; the user decides.

**Delivery order:** Verify core behavior → agree contracts → persist department changes → make the office dynamic → show scenario effects → connect live events → present the board review → verify both existing demos. These are implementation tasks, not claims that the current product already supports them.

### 31.1 Current implementation and concrete gaps

| Area | Current implementation | Required change |
|---|---|---|
| Office scene | `apps/web/components/office-scene.tsx` loads one GLB, animates six fixed routes from the forecast day, and toggles named workstations plus six generic slots | Render zones and representatives from stable IDs; separate agent activity from forecast playback |
| Department placement | `apps/web/lib/simulation-view.ts` has fixed coordinates and cycles through six fallback positions | Assign stable, non-overlapping slots with explicit overflow behavior |
| Department controls | Onboarding toggles local state; the organization settings save handler acknowledges local changes without persisting those edits | Persist validated company changes and refresh the server-backed profile before reporting success; preserve the existing working context-addition flow |
| Results | The dashboard applies the recommended result (or naive fallback), polls run state, and switches to the graph on completion | Keep the user's chosen view; explicitly select baseline, plan, future, and mitigation result |
| Live events | The API has a WebSocket event stream and persisted event history; the web client does not consume individual events | Add authenticated incremental event access through the existing web proxy and recover by sequence |
| Assessments | The orchestrator publishes started/completed/failed and challenge events; the API exposes perspectives | Present validated outputs and the approved targeted response round without fabricating dialogue or invoking models during playback |
| Agent mapping | The roster and routing include built-in department IDs | Support explicit profile-to-agent mapping for additional departments, or show an unavailable perspective |
| Web verification | The web package's current test command prints a placeholder message | Establish real behavior checks using existing verification tools; a successful placeholder command is insufficient |

### 31.2 Experience and state rules

The authenticated simulation office is the primary surface. The public landing illustration may reuse the renderer but must remain visibly illustrative and must not load private company data.

1. **Explore company:** click a zone or choose it from an accessible list; focus the camera and open its existing detail panel. Show capacity, budget, workflows, dependencies, and evidence. Hover previews are optional conveniences, never the only way to inspect a department.
2. **Edit company baseline:** create, edit, or archive a department through a saved, versioned company change. Validate owned work and references before archiving. An archived department remains available to historical runs. A display filter only hides a zone; it never changes the twin or simulation scope.
3. **Test a proposed change:** open a draft from the selected department, add capacity, reduce capacity, introduce a department, or propose its closure and work transfer. Preview the proposed shape immediately with an “Unsimulated draft” label. Calculate consequences only after an explicit simulation request.
4. **Compare outcomes:** retain baseline zone locations and show added zones, ghost outlines for closed departments, and affected dependencies. Select the exact plan/future/result. Mitigated results appear only after re-simulation succeeds.
5. **Review at the table:** open live analysis or a labeled review of a completed run. Inspect each representative's actual findings and the challenger output. End with the existing decision package and human approval controls.

Maintain separate state for `run_id`, baseline twin version, scenario/plan/future/result selection, selected department, view mode, live event cursor, and forecast day. Animation time is presentation-only. A day-30 effect must not imply that an agent takes 30 days to answer. Changing the baseline while reviewing an older run must not change that run's scene, evidence, or numbers.

### 31.3 Contracts and domain decisions

Complete these decisions in the contract-owning layer before downstream implementation:

- Reuse `DepartmentProfile`, department entities, `AgentSpec`, `Intervention`, `Impact`, `AgentAssessment`, `Event`, `RunState`, and `DecisionPackage`. Reconcile the handwritten web profile projection with generated contracts; do not create a third domain model.
- Define typed department create/update/archive requests with an expected twin version. Apply changes atomically and reject stale edits. Return the saved version and validated profile. Require a stable ID, mission, ownership, staffing/budget inputs, evidence or explicit assumptions, and an optional supported agent mapping. Incomplete departments can exist but must show missing modeling inputs.
- For scenario capacity changes, use the existing `add_capacity` and `reduce_capacity` interventions. Confirm backend behavior for zero capacity, cost caps, dependencies, and knowledge coverage; do not equate zero capacity with deleting an entity.
- Full department creation, closure, and ownership transfer need explicit scenario semantics beyond toggling `enabled`. Specify a typed, optional organization-change collection on the scenario request/brief, applied only to a cloned twin. Cover new department IDs, effective days, transferred workflow ownership, unresolved obligations, and transition assumptions. Do not encode these operations as arbitrary prose or silently reinterpret an existing action.
- Preserve existing consumers by defaulting new optional collections to empty. Any enum expansion or other change that an existing consumer cannot accept requires the separate breaking-contract approval and coordinated migration described in Section 8 and `AGENTS.md`.
- Expose engine-owned per-department baseline/scenario capacity and budget values, lifecycle state, and effective day when existing results do not contain them. The UI may format these values but may not calculate capacity, savings, feasibility, or impact propagation. A result with insufficient evidence says “Not modeled,” not “No impact.”
- Keep coordinates, camera targets, animation poses, and visual slots in web presentation state; they are not company facts. Key saved layout preferences by organization and stable department IDs, independently from run events and numerical results.
- Use existing event/assessment fields first. Only add correlation fields if necessary to distinguish agent, plan, pass, and retry. Update Python models in the existing `packages/contracts-py`, JSON schemas, TypeScript contracts, fixture payloads, and contract/API tests together. Do not create a new contracts package.

### 31.4 Phased implementation backlog

#### O-00 — Establish the baseline and freeze the extension contracts

**Owners:** Frontend/integration, twin/contracts, engine, and agent/backend owners. **Depends on:** existing core release gates.

- Verify the deterministic vendor slice and workforce knowledge-loss behavior before optional visual work. Resolve failures in their owning layer.
- Inspect the actual GLB object hierarchy and reusable geometry. Identify baked desks, avatars, and labels that would remain visible after a department is removed.
- Freeze the changes in Section 31.3 and publish valid/invalid example payloads for a created department, a capacity cut, closure with unresolved work, and a transfer. These are tests of the two existing scenarios, not a third product demo.
- Define verification cases for 0, 1, 6, 12, and 24 departments, plus long names and custom IDs. Confirm installed tools for web tests; read the repository's installed Next.js guidance before editing web code.

**Exit check:** Existing core failures are resolved or explicitly block the affected phase; contract fixtures validate; owners agree on the representation of lifecycle changes and result values.

#### O-01 — Persist department changes and simulate structural changes

**Owners:** Twin/contracts for company state; engine for scenario operators; API for transport; frontend for forms. **Depends on:** O-00.

- Extend the existing company-twin package to create/update/archive departments with graph validation, evidence references, stable IDs, and new twin versions. Retain historical snapshots and reject dangling ownership references.
- Add the necessary operations inside the existing API and persistence mechanism. Wire onboarding/settings save actions to them; show pending, success, validation, version-conflict, and server-error states. Invalidate department details, graph, and profile caches by twin version after a successful save.
- In the simulation engine, apply proposed creation/closure/transfer operations to an isolated scenario. Reuse capacity operators where their semantics match; validate transfer destinations and expose unresolved ownership instead of inventing a replacement team.
- Calculate affected workflows, costs, capacity, knowledge coverage, constraints, and time-based effects in the engine. New departments without roles/dependencies/evidence cannot silently provide quantified coverage or safe outcomes.
- Resolve additional department routing from explicit profile mappings and the shared graph, including departments represented by the same supported specialist. Build permission-filtered context for the actual department IDs rather than relying solely on the built-in roster IDs. Preserve mandatory cross-company reviewers. If no supported perspective exists, report it as unavailable.

**Exit check:** A created department survives refresh; stale edits fail safely; proposed removal/transfer leaves the baseline unchanged; impacted workflows and financial results reconcile; custom IDs receive the right context or an honest missing-perspective state.

#### O-02 — Replace fixed scene slots with a dynamic office

**Owner:** Frontend. **Depends on:** O-00; integrates O-01 saved profiles.

- Keep the existing Three.js/React Three Fiber stack. Reuse the office shell and reusable furniture geometry; remove or hide baked department furniture so it cannot duplicate generated zones. Update the existing Blender source and GLB together if asset changes are necessary.
- Generate one zone for each active department. Use stable slot assignments, reserve removed slots while comparing a scenario, and append new slots around the central table. Do not derive positions from array indices or reuse slots modulo six.
- Use outer rows and an explicit office-page control beyond 24 visible zones; display the full department count and preserve access through the list/graph. No department silently disappears or overlaps another.
- Generate representatives and seat positions from actual participants. Representatives denote departmental perspectives, not individual employees; display exact staffing as text/capacity indicators rather than rendering one avatar per employee.
- Add click-to-focus, selection highlighting, reset camera, and accessible list controls. Reuse the department metrics sidebar and evidence UI. Add reduced-motion behavior and an error boundary/loading state with graph/list fallback for asset or WebGL failure.

**Exit check:** 0/1/6/12/24 department fixtures render correctly; adding/removing a department updates furniture and labels without moving unchanged zones; overflow remains navigable; selection and data inspection work without 3D input.

#### O-03 — Visualize proposed changes, dependencies, and forecast effects

**Owners:** Frontend; engine/contracts for missing authoritative result data. **Depends on:** O-01, O-02.

- Add an in-context action to prepare a department change in the existing decision composer. Separate local draft previews from saved baselines and completed scenarios; allow cancel/reset.
- Extend the simulation presentation adapter to take an explicit baseline snapshot and selected result. Remove the implicit recommended-only selection and the automatic graph switch on completion.
- Draw evidence-backed dependency connections for the selected department. Use backend-provided dependency paths; the browser does not discover authoritative impacts by traversing the graph itself.
- Render new-zone previews, closed-zone outlines, capacity changes, ownership transfers, and workflow warnings from scenario data. Use text/icons with color; neutral means no reported effect, not confirmed safety.
- Drive impact appearance by `first_effect_day` and display peak timing and confidence. Do not interpolate numerical forecasts or assume recovery after the peak unless the backend supplies that behavior. Use the requested horizon instead of a fixed 90-day story.
- Support baseline/proposal/mitigated and act/inaction/delay comparisons where results exist. Preserve positions across views; disable unavailable comparisons with a clear reason.

**Exit check:** The same selected result yields matching values and evidence in office, graph, and decision package; effects respect their dates; closure leaves visible unresolved dependencies; mitigation indicators change only after a successful engine rerun.

#### O-04 — Deliver reliable live events to the web client

**Owners:** Agent/backend and frontend. **Depends on:** O-00; integrates O-03 run selection.

- Add an authenticated HTTP event-history endpoint, for example `GET /runs/{run_id}/event-log?after_sequence=N&limit=...`, in the existing API. Return ordered typed events and the last returned cursor, bounded for large histories. Keep the existing WebSocket route intact.
- Extend the existing same-origin Next.js proxy allowlist and API client. Use incremental polling initially, approximately once per second while active, with bounded backoff on transient failures. This fits the current proxy, which buffers HTTP responses and does not relay WebSocket upgrades. No new transport dependency or service is needed.
- Authorize event access consistently with run/package access and apply the same sensitive-content rules used for perspectives. Never expose model credentials or private reasoning in events.
- Build a deterministic event reducer: filter by run, order by sequence, deduplicate events, and correlate agent/plan/pass/assessment. A failed or invalid assessment must not become successful merely because an `agent_completed` envelope follows it. The same assessment may appear in both completion and challenge events and must not be counted twice.
- Reconnect from the last applied sequence, fetch all pages, and restore state on refresh. Reconstruct the snapshot before animating new arrivals; do not repeat completed entrances. Abort obsolete requests on run changes and unmount. Stop polling after terminal state and event reconciliation.
- On disconnect, retain received findings and show reconnecting status; use run-state polling for coarse progress without inventing individual activity. Completed historical review uses only that run's persisted events, clearly labeled, and never substitutes for a failed live agent.

**Exit check:** Duplicate events, delayed responses, reconnects, refresh, terminal failure, and switching runs preserve the correct state without duplicated findings, lost events, credential exposure, or cross-run content.

#### O-05 — Present a structured board review

**Owner:** Frontend, with agent/backend validation. **Depends on:** O-02, O-04; result comparison integrates O-03.

- Add Office / Graph / Board review modes within the existing dashboard. The office table and modular avatars are reused; a second app or scene engine is unnecessary.
- Seat agents based on actual run participation. Distinguish department representatives from cross-company reviewers such as the challenger. For a larger roster, keep at most 12 representatives in the table view with a paged participant list and explicit hidden count; every finding remains reachable.
- Map `agent_started` to analyzing, valid completed assessments to findings available, failed/invalid assessments to unavailable, and challenge events to review attention. Animate short arrivals/focus changes from those states; never delay the backend to finish an animation.
- Present concise claim cards from existing output summaries: position, affected workflow, evidence, assumptions/confidence, objection, and proposed mitigation where supplied. Allow opening the underlying assessment and evidence. Show multiple agents analyzing concurrently; camera focus does not imply serial execution or an actual spoken exchange.
- Show linked original claims, department/challenger objections, and one real targeted response round. Label revised/supported/unresolved as agent positions; do not present them as consensus or automatic resolution. Missing/invalid replies stay unresolved. Do not generate rebuttals merely to make the meeting dramatic.
- Keep the central summary synchronized to deterministic feasibility, costs, and selected result. A visually persuasive agent cannot override a hard constraint. End with the existing human decision controls; no agent voting or automatic approval.
- Present six readable stages in both the board and storyboard: proposal, findings, challenge, response, recalculation, and decision. Play/pause/step controls advance stages rather than raw transport events. Each stage uses the actual recorded history, preserving initial and response assessments separately. Show the engine’s before/after values with their plan identities and timing/dependency paths for modeled effects.
- Label completed runs as recorded review with the run and twin version. Historical runs without a response round say so explicitly. Speech synthesis, lip-sync, and rounds beyond the single approved response round remain outside this implementation.

**Exit check:** Every displayed claim resolves to an actual assessment/event; a failed agent has no invented speech; the challenge pass and remaining uncertainty are visible; review playback never invokes models or changes results.

#### O-06 — Verify and deliver the complete flow

**Owners:** All, coordinated by frontend/integration. **Depends on:** O-01–O-05.

- Exercise the vendor demo with naive versus recommended portfolios, department impact paths, and the actual agent review.
- Exercise the workforce demo with exactly the expected stranded workflows and engine-verified mitigation. Include capacity reductions, department additions, closure/transfer cases, and custom IDs as integration tests of the same contracts.
- Verify loading, success, empty, and error states for profiles, scene assets, department details, events, assessments, and comparisons. Include expired authentication, API failure, provider failure, refresh during a run, no feasible plan, an unknown department ID, and missing evidence.
- Check keyboard access, reduced motion, narrow screens, labels at supported zoom levels, and fallback when WebGL is unavailable. Target at least 30 FPS with 24 zones on the documented demo machine; record viewport/device and measure. Use less geometry/shadows or the graph/list fallback if the budget is missed.
- Run `pnpm typecheck`, `pnpm test`, and `pnpm build`, plus relevant twin/engine/orchestration/API tests and realistic endpoint exercises. Add real web interaction verification; explicitly report if the web test script still only prints a placeholder.
- Confirm historical baseline isolation, snapshot/result agreement, authorization, and that no change introduced an external system write. Keep temporary screenshots, logs, and generated caches out of commits.

**Exit check:** Both existing demos and all extension acceptance checks pass; no unsupported numerical claim or agent dialogue is presented; remaining limits and verification results are documented in the existing project documentation.

### 31.5 File ownership and implementation boundaries

| Responsibility | Existing home / likely touchpoints |
|---|---|
| Shared contracts and generation | `packages/contracts-py/src/contracts_py/`, `packages/contracts/src/`, `packages/contracts/schemas/`; update together |
| Twin mutations, validation, historical state | `packages/company-twin/src/company_twin/` and its tests |
| Capacity, closure/transfer consequences, mitigation | `packages/simulation-engine/src/simulation_engine/interventions.py`, propagation/knowledge/result modules, and tests |
| Department mapping and real agent events | `packages/agent-orchestration/src/agent_orchestration/router.py`, `context.py`, `roster.py`, `orchestrator.py`, and tests |
| API, saved changes, incremental event access | `apps/api/src/canary_api/app.py`, `runtime.py`, `events.py`, `storage.py`, and relevant tests; keep domain operations in their packages |
| Profile persistence and request transport | Existing onboarding/settings components, `apps/web/lib/canary-api-client.ts`, and `apps/web/app/api/canary/[...path]/route.ts` |
| Scene, interactions, comparisons | `office-scene.tsx`, `decision-dashboard.tsx`, `department-metrics-sidebar.tsx`, `simulation-view.ts`, existing graph/evidence components |
| Assets | Existing `apps/web/assets/3d/office.blend` and `apps/web/public/assets/3d/office.glb` |

Create separate web modules only for cohesive responsibilities that now require them: stable scene layout, run-event state reduction, or the board-review panel. Do not create a generic scene framework, parallel dashboard, duplicate result model, speculative database, or new deployment target. The team work-division document's legacy folder names are interpreted through the current repository ownership in `AGENTS.md`.

### 31.6 Scope control and release priority

The minimum complete delivery includes persisted department edits, scenario-isolated addition/reduction/closure behavior, dynamic zones, evidence-backed impacts, real event delivery, and a structured board review. More lifelike movement is polish after those behaviors work.

If time is constrained, defer cinematic cameras, walking paths, and richer furniture first. Preserve accessible cards and simple state-driven representatives. Do not cut baseline isolation, event authenticity, custom-department visibility, evidence links, deterministic validation, or the two core demos. The single bounded response round and six-stage storyboard were approved on 2026-09-27. Any proposal for voice, further rebuttal rounds, arbitrary agent generation, external integrations, or unrelated analytics requires a separate scope decision.


### 31.7 Implementation and verification — 2026-09-27

Implemented in the existing applications and packages:

- Versioned department and organization saves with stale-version rejection, validated assumptions, saved settings, and historical run profile/graph/detail reads. PostgreSQL snapshot insertion and activation share a transaction.
- Scenario-only creation, capacity changes, closure and workflow transfers. New staffing and budget declarations do not fabricate workflow capability. Closure retains obligations and exposes knowledge loss; a workflow ownership transfer does not create trained owners.
- Dynamic office zones, reusable furniture/representatives, stable ID-based slots, camera selection/reset, accessible department selection, and explicit paging beyond 24 zones. Dense views use compact labels. The public illustration remains separate from actual company state.
- Quick office previews return a matching deterministic result and blast graph from the same baseline. The dashboard compares baseline, plan/future and mitigation results, preserves the selected view, and uses frozen run snapshots for historical inspection.
- Authenticated, paginated event history, sequence deduplication, reconnect handling, per-plan/per-pass assessments, real failure states, and recorded review playback. Board findings and evidence come from validated run outputs; there are no invented speeches or additional debate calls.
- A human decision control records approval, rejection or a scenario request using the served package hash. It does not execute organization changes. Infeasible selected results cannot be approved through this control.

Verification: `pnpm typecheck`, `pnpm test`, and `pnpm build` passed. The regression suite includes both existing demonstration fixtures, 504 passing Python tests (four opt-in integration tests skipped), and 21 passing browser-side behavior tests. The generated Python/JSON/TypeScript contracts agree. Existing company fixture evidence excerpts were synchronized with the shared fixture's added source records; acceptance snapshots include the additive office projection.

Browser verification used a separate local data store and explicitly labeled test-provider assessments. Checked department creation and persistence after refresh, isolated closure at day 30, baseline restoration, a full agent run, frozen source evidence, recorded review stepping, human rejection, scene transitions, and 25-department overflow across two office pages. The reviewed desktop viewport was 919 × 863. Three-dimensional labels use the normal DOM with projected anchors to avoid per-label React root lifecycle errors.

Repeated office hardening: three consecutive focused runs each passed 21 frontend checks and 10 office API/engine tests; a fresh full suite passed 504 Python tests with four opt-in skips. A 1280 × 720 browser pass checked capacity reduction/addition, empty and valid workflow transfer, closure timing, scenario-only addition, saved department persistence, frozen evidence, and three board replay/view-switch cycles. Fixed seated orientation, chair proportions, grounded hand gestures driven by agent activity, board camera framing, overlapping labels and controls, stale asynchronous run/evidence responses, failure-state seats, replay pagination, fractional FTE formatting, and scenario-only detail handling. Added cutaway walls, windows and planters without new assets or dependencies.

Modern office visual pass (user-approved): shared modular furniture now serves the illustrative home scene and the live company view. Added oak workstations with screens and acoustic dividers, varied representative clothing, ergonomic chairs, glass meeting partitions, a lounge and coffee counter, planted greenery, and daylight/evening lighting. Decorative head/hand and plant motion is independently pausable and honors reduced-motion preferences; stronger typing and screen pulses require actual analyzing events. Camera selection eases into focus and yields to manual orbit input. Furniture is isolated in `apps/web/components/office-furnishings.tsx`; no backend, contract, asset download or dependency was introduced. Browser verification used the current 16-department company at 1280 × 720 and repeated lighting, pause/resume, selection and camera-reset controls three times. Full verification passed 608 Python tests (four opt-in skips), 21 frontend tests, typecheck and production build.

Verification limits: paid live-provider calls and a configured PostgreSQL integration environment were not exercised; the 30 FPS target and narrow-device performance have not been measured. The current office projection presents final department staffing changes at their effective date; more detailed multi-stage staffing timelines remain a limitation. Cross-process concurrent baseline editing has not been exercised. Cinematic walking, speech and lip-sync remain outside this delivery.
