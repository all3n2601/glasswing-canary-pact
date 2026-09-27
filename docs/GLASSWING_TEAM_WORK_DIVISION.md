# GlassWing / Canary Pact — Four-Person Work Division

## 1. Project Goal

Build a decision-relevant digital twin of a company that can simulate a proposed organizational decision before leadership commits to it.

The hackathon demonstration should answer:

> If the company makes this decision, what is the organizational blast radius, which departments and workflows are affected, what risks appear over time, and is there a safer way to achieve the same objective?

The primary demonstration is vendor consolidation: the company must reduce data-provider spending while preserving critical data coverage, workflows, compliance, and business performance. The second demonstration is workforce knowledge loss: removing employees may strand workflows that only they understand.

## 2. Team Structure

| Team member | Primary ownership | Final deliverable |
|---|---|---|
| Person 1 | Company twin, data model, and dependency graph | Validated company graph and synthetic dataset |
| Person 2 | Simulation, risk propagation, and optimization | Deterministic scenario and recommendation engine |
| Person 3 | Department agents, orchestration, and backend API | Structured AI analysis exposed through stable APIs |
| Person 4 | Frontend, integration, testing, and demo | Complete interactive dashboard and demo experience |

Replace `Person 1` through `Person 4` with the team members' names before starting.

## 3. Shared Contract Freeze — Complete Before Parallel Development

The team should spend the first 1–2 hours agreeing on the following JSON contracts. After they are approved, only the assigned contract owner may edit them. Any breaking change requires agreement from every affected team member.

### Required contracts

1. `CompanyTwin`
2. `ScenarioRequest`
3. `ScenarioResult`
4. `DepartmentAssessment`
5. `ExecutiveReport`

### Required identifiers

Every department, employee, vendor, workflow, dataset, KPI, and dependency must have a stable unique ID. All teams must reference those IDs rather than names.

### Data flow

```text
Person 1: CompanyTwin + DependencyGraph
                       |
                       v
Person 2: ScenarioResult + PortfolioRecommendation
                       |
                       v
Person 3: DepartmentAssessments + ExecutiveReport + API
                       |
                       v
Person 4: Dashboard + End-to-End Demo
```

Each person must create example JSON outputs immediately. Downstream teammates should build against these mock files instead of waiting for the upstream implementation.

---

## 4. Person 1 — Company Twin and Dependency Graph

### Mission

Create the trusted representation of the fictional company. This workstream defines what exists in the company and how resources, workflows, departments, and outcomes are connected.

### Exclusive ownership

```text
backend/models/
backend/graph/
backend/fixtures/
data/
tests/models/
tests/graph/
shared/contracts/
```

### Tasks

- [ ] Define the shared Pydantic/JSON schemas and publish example payloads.
- [ ] Create a synthetic company with Finance, Marketing, Sales, Operations, Engineering, AI/Data, People, Compliance, and Customer functions.
- [ ] Model seven data vendors, including annual cost, datasets, fields, coverage, quality, freshness, contracts, and substitutability.
- [ ] Model workflows, consuming departments, responsible employees, downstream systems, and affected KPIs.
- [ ] Add evidence and confidence metadata to every important dependency.
- [ ] Build the organizational graph with nodes and typed edges.
- [ ] Calculate vendor overlap, unique coverage, and required-field coverage.
- [ ] Model employee knowledge ownership and identify workflows with no backup owner.
- [ ] Provide graph traversal helpers for upstream and downstream dependencies.
- [ ] Export stable demo fixtures for the other three workstreams.

### Required outputs

- `company_twin.json`
- `vendor_overlap.json`
- `knowledge_map.json`
- `graph_snapshot.json`
- Shared schema definitions and example payloads

### Acceptance checks

- Every graph edge refers to valid source and target IDs.
- Every vendor has cost, coverage, consumers, and replacement information.
- Every critical workflow has at least one owner or is explicitly marked as a knowledge risk.
- Removing a node allows the system to find all downstream departments, workflows, and KPIs.
- The fixture validates without manual corrections.

### Must not modify

Simulation scoring, optimization algorithms, agent prompts, API routes, frontend code, or deployment configuration.

---

## 5. Person 2 — Simulation and Optimization Engine

### Mission

Build the deterministic engine that calculates what changes when a resource is removed, reduced, replaced, or retained. This workstream owns all authoritative arithmetic and recommendations.

### Exclusive ownership

```text
backend/engine/
backend/simulation/
backend/optimizer/
tests/engine/
tests/simulation/
tests/optimizer/
```

### Tasks

- [ ] Load `CompanyTwin` and validate required simulation inputs.
- [ ] Implement direct-impact calculations such as savings, termination costs, and migration effort.
- [ ] Propagate indirect and second-order effects through the dependency graph.
- [ ] Calculate cost displacement between departments.
- [ ] Detect workflow degradation, broken dependencies, and stranded workflows.
- [ ] Evaluate vendor removal individually and in combinations.
- [ ] Apply hard constraints such as compliance coverage, required fields, maximum revenue impact, and savings targets.
- [ ] Score feasible portfolios using savings, business loss, transition cost, operational risk, and uncertainty.
- [ ] Implement quick deterministic simulation and optional full uncertainty simulation.
- [ ] Re-simulate proposed mitigations and compare the before/after risk.
- [ ] Produce ranked recommendations with rejected alternatives and rejection reasons.

### Required outputs

- `ScenarioResult`
- `BlastRadius`
- `RiskTimeline`
- `PortfolioRecommendation`
- `MitigationComparison`

### Acceptance checks

- The same inputs always produce the same deterministic result.
- The engine can evaluate all 128 keep/remove combinations for seven vendors.
- No recommendation may violate a hard constraint.
- Savings, migration costs, and displaced costs reconcile numerically.
- Removing the employees who uniquely own a workflow marks that workflow as stranded.
- Every reported impact contains its dependency path and confidence value.

### Must not modify

Company fixtures and schemas, agent prompts, API routes, frontend components, or deployment configuration.

---

## 6. Person 3 — Department Agents, Orchestration, and API

### Mission

Coordinate specialized department perspectives, convert leadership requests into structured scenarios, explain deterministic results, and expose the product through a stable backend API.

### Exclusive ownership

```text
backend/agents/
backend/orchestration/
backend/llm/
backend/api/
tests/agents/
tests/orchestration/
tests/api/
```

### Tasks

- [ ] Translate a leadership request into a validated `ScenarioRequest`.
- [ ] Implement Finance, Engineering, Marketing, Sales, Operations, AI/Data, People, Compliance, and Customer evaluators.
- [ ] Dynamically run only the department agents relevant to the affected graph area.
- [ ] Require every agent to return structured JSON with impacts, assumptions, evidence, confidence, and open questions.
- [ ] Prevent agents from performing authoritative arithmetic or overriding engine constraints.
- [ ] Combine department assessments with Person 2's deterministic results.
- [ ] Detect disagreements, missing evidence, and decision-changing unknowns.
- [ ] Generate clarification questions using sensitivity-analysis thresholds supplied by the engine.
- [ ] Generate the executive explanation, alternatives, mitigation plan, monitoring plan, and rollback conditions.
- [ ] Use live agent suggestions only; surface unavailable agents without mock or recorded substitutes.
- [ ] Expose the agreed REST endpoints and publish OpenAPI documentation.

### Minimum API surface

```text
GET  /health
GET  /company
GET  /company/graph
POST /scenarios
POST /scenarios/{scenario_id}/simulate
GET  /scenarios/{scenario_id}/results
GET  /scenarios/{scenario_id}/blast-radius
POST /scenarios/{scenario_id}/clarifications
POST /scenarios/{scenario_id}/mitigations/simulate
GET  /scenarios/{scenario_id}/report
```

### Acceptance checks

- Every endpoint returns payloads matching the frozen contracts.
- Invalid requests return understandable validation errors.
- Agent failures degrade gracefully and do not erase deterministic results.
- Each claim in the executive report links to evidence, an assumption, or a deterministic calculation.
- A failed live agent appears as a missing perspective and never injects recorded advice.
- API contract tests pass using Person 4's mock payloads.

### Must not modify

Company fixtures, graph implementation, deterministic scoring, optimization logic, frontend components, or deployment configuration.

---

## 7. Person 4 — Frontend, Integration, Quality, and Demo

### Mission

Turn the system into a clear executive decision experience and own the final integrated demonstration. Frontend development begins with mock responses and switches to the real API only after contract tests pass.

### Exclusive ownership

```text
frontend/
demo/
tests/e2e/
deployment/
```

### Tasks

- [ ] Create the application shell, navigation, loading, empty, and error states.
- [ ] Build the company-twin overview and organizational graph view.
- [ ] Build scenario creation using a leadership objective and constraints.
- [ ] Visualize vendor cost, overlap, unique value, and department consumers.
- [ ] Build the interactive organizational blast-radius view.
- [ ] Show direct, indirect, second-order, delayed, and feedback effects.
- [ ] Build department impact cards with timing, severity, confidence, and evidence.
- [ ] Build portfolio comparison for recommended and rejected alternatives.
- [ ] Show cost displacement rather than only gross savings.
- [ ] Build assumptions, clarification, mitigation, monitoring, and rollback panels.
- [ ] Add a one-click preloaded vendor-consolidation demo.
- [ ] Add a one-click workforce knowledge-loss demo.
- [ ] Implement end-to-end smoke tests against mock and real APIs.
- [ ] Own deployment configuration, demo script, screenshots, and backup recording.

### Required demo flow

1. Open the fictional company's digital twin.
2. Enter a cost-reduction objective.
3. Compare seven vendors and their overlapping data.
4. Run the simulation.
5. Reveal the organizational blast radius.
6. Show why an obvious cut creates hidden damage.
7. Present the safer recommended portfolio.
8. Add a mitigation and re-run the simulation.
9. Show the executive report, monitoring signals, and rollback conditions.

### Acceptance checks

- The frontend works against mock JSON before backend integration.
- Every API state has loading, success, empty, and error handling.
- The main demo completes without editing data manually.
- A judge can identify the recommendation, affected departments, savings, risks, and evidence within two minutes.
- The demo surfaces unavailable live agents while retaining deterministic calculations.
- The deployed version passes the end-to-end smoke test.

### Must not modify

Shared schemas, company fixtures, graph logic, engine calculations, agent prompts, or backend API behavior.

---

## 8. Conflict-Prevention Rules

1. **One folder, one owner.** Only the assigned person edits files in that workstream's directories.
2. **Contract-first development.** Shared payloads are frozen before parallel coding starts.
3. **Mocks prevent waiting.** Every producer supplies example JSON; every consumer starts with those mocks.
4. **No duplicate calculations.** Person 2 exclusively owns arithmetic, constraints, risk scores, and portfolio rankings.
5. **No hidden agent authority.** Person 3's agents explain, challenge, and identify assumptions; they do not silently change calculated results.
6. **No frontend business logic.** Person 4 displays results and may format values, but does not recreate scoring rules in the browser.
7. **Stable IDs everywhere.** Integration uses IDs and versioned contracts, never display names or hard-coded array positions.
8. **Changes are additive when possible.** New fields should initially be optional to avoid breaking teammates.
9. **Breaking changes require a short team review.** Update the schema, example payload, and affected contract tests together.
10. **Integration fixes stay with the owner.** If an API response is wrong, Person 3 fixes it; Person 4 does not patch around it in the frontend.

## 9. Git Workflow

Use one long-lived branch per person:

```text
main
person-1-company-twin
person-2-simulation-engine
person-3-agents-api
person-4-frontend-demo
```

Rules:

- Pull from `main` before beginning a task.
- Make small commits with one purpose each.
- Do not commit generated secrets, credentials, or local environment files.
- Open a pull request only after the workstream's tests pass.
- The workstream owner resolves conflicts inside their own directories.
- Merge shared contracts first, followed by Parts 1, 2, 3, and 4.
- Tag the last known working demo before major integration changes.

## 10. Integration Schedule

### Checkpoint 1 — Contract freeze

- Approve all shared schemas.
- Validate example payloads.
- Confirm stable entity IDs and API paths.
- Person 4 begins UI work with mocks.

### Checkpoint 2 — Vertical slice

- Person 1 provides one small company graph.
- Person 2 simulates removal of one vendor.
- Person 3 exposes the result through one endpoint.
- Person 4 displays the blast radius.

This is the first end-to-end milestone and should happen early.

### Checkpoint 3 — Full vendor scenario

- Load all seven vendors.
- Evaluate 128 portfolios.
- Apply constraints and generate a recommendation.
- Display rejected alternatives and organizational consequences.

### Checkpoint 4 — Knowledge-loss scenario

- Remove the selected employees.
- Detect stranded workflows and missing knowledge backups.
- Display mitigation options and re-simulated outcomes.

### Checkpoint 5 — Demo freeze

- Stop adding features.
- Fix only demo-blocking defects.
- Verify missing live-agent perspectives are surfaced without substitution.
- Run the complete demo three times.
- Capture screenshots and a backup demo recording.

## 11. Shared Definition of Done

The project is complete when:

- [ ] A user can enter a company-wide objective and constraints.
- [ ] The system can simulate vendor removal and workforce knowledge loss.
- [ ] Direct, indirect, second-order, and delayed effects are traceable.
- [ ] Every impact identifies affected departments, workflows, KPIs, timing, confidence, and evidence.
- [ ] Vendor overlap and unique value influence the recommendation.
- [ ] Hard constraints cannot be violated by a recommendation.
- [ ] Gross savings, displaced costs, migration costs, and estimated business loss are shown separately.
- [ ] Department agents add explanations without overriding deterministic calculations.
- [ ] Users can compare alternatives and re-simulate mitigations.
- [ ] The application never substitutes mock or recorded agent suggestions when a live model is unavailable.
- [ ] The complete demonstration is deployed and reproducible.

## 12. Scope Guardrails

Do not add the following until the core demonstration is complete:

- A 3D boardroom interface
- Uncontrolled debates between agents
- Production integrations with every enterprise system
- Person-level employment recommendations
- Autonomous execution of company decisions
- Complex real-time data ingestion
- Additional scenarios that do not strengthen the vendor or knowledge-loss demonstrations

The hackathon priority is a reliable, explainable vertical slice—not a production-complete company twin.
