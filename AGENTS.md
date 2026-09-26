# Repository Instructions for Coding Agents

These instructions apply to every file and directory in this repository. Follow them before making changes.

## 1. Product Mission

Canary Pact is a decision-support system that creates a decision-relevant digital twin of a company and simulates the organizational blast radius of proposed decisions.

The core product must answer:

> If the company makes this decision, which departments, workflows, systems, people, and KPIs are affected; when do those effects appear; what evidence supports them; and is there a safer way to achieve the same objective?

The product boundary is non-negotiable:

- Agents reason, identify risks, expose assumptions, and explain results.
- Deterministic code performs calculations, propagation, constraint checking, and optimization.
- Humans approve or reject real organizational decisions.

Do not turn the product into an autonomous decision executor, generic chatbot, unstructured multi-agent debate, spend dashboard, or employee-ranking system.

## 2. Sources of Truth

Read these documents before planning or implementing substantial work:

1. `docs/CANARY_PACT_MASTER_IMPLEMENTATION_PLAN.md` — authoritative product and technical plan.
2. `docs/GLASSWING_TEAM_WORK_DIVISION.md` — ownership boundaries and integration sequence.
3. `packages/contracts/` — current machine-readable interface contracts.
4. Existing tests — executable behavior that must remain valid unless the approved requirement changes it.

When sources disagree, follow this precedence:

1. The user's latest explicit instruction.
2. This `AGENTS.md` file.
3. The master implementation plan.
4. The team work-division document.
5. Existing contracts and tests.

Do not silently reinterpret the plan. State the conflict and ask for a decision when a requested change would materially alter the product direction.

## 3. Core-First Development

Work on the approved core idea before optional improvements.

The current priority order is:

1. Freeze shared contracts and stable entity identifiers.
2. Build and validate the synthetic company twin.
3. Calculate vendor overlap and graph dependencies.
4. Simulate resource removal and propagate its blast radius.
5. Enforce constraints and compare vendor portfolios.
6. Route relevant department assessments through the orchestrator.
7. Present evidence, uncertainty, mitigation, monitoring, and rollback conditions.
8. Complete the vendor-consolidation demo.
9. Complete the workforce knowledge-loss demo using the same contracts and UI.
10. Harden, test, and prepare the demonstration.

Do not add optional features while an earlier core stage is incomplete or unreliable.

## 4. Approval Gate for Additional Features

Explicit user approval is required before adding any feature not already described in the master plan or required for the core vertical slice.

Ask for approval before:

- creating another application, service, package, database, or deployment target;
- introducing a new framework or replacing an approved framework;
- adding a third demonstration scenario;
- integrating an external enterprise system;
- adding autonomous actions or writes to external systems;
- adding a 3D interface, agent debate room, social features, notifications, or unrelated analytics;
- making person-level employment recommendations;
- adding abstractions intended only for hypothetical future use;
- changing the product scope, core user, primary workflow, or decision model;
- making a breaking contract or data-model change.

When proposing additional work, explain the user value, scope, dependencies, and effect on the core milestone. Do not create an RFC, planning file, branch, placeholder, or implementation until approval is given.

## 5. Repository Structure and Ownership

Use the existing structure. Do not place files wherever convenient.

```text
apps/
├── web/                    Next.js UI and presentation logic
└── api/                    FastAPI transport, validation, and API composition
packages/
├── contracts/              Shared JSON schemas and TypeScript interfaces
├── company-twin/           Company entities, evidence, graph, and fixture loading
├── simulation-engine/      Authoritative calculations and optimization
└── agent-orchestration/    LangGraph routing and structured agent workflow
data/                       Versioned synthetic source data and demo fixtures
infra/                      Local infrastructure and deployment configuration
docs/                       Approved durable product and team documentation
```

### `apps/web`

May contain:

- routes and layouts;
- reusable UI components;
- browser-side API clients;
- presentation state, formatting, and interactions;
- visualizations of data returned by the API.

Must not contain:

- risk formulas or portfolio scoring;
- constraint enforcement;
- authoritative graph traversal;
- duplicated backend domain models beyond imported shared contracts;
- model-provider credentials or direct model calls.

### `apps/api`

May contain:

- HTTP routes and middleware;
- request and response composition;
- dependency wiring;
- authentication and authorization when approved;
- persistence adapters when approved.

Must not become a dumping ground for domain logic. Company modeling belongs in `company-twin`, calculations belong in `simulation-engine`, and agent workflow belongs in `agent-orchestration`.

### `packages/contracts`

Owns external and cross-layer interfaces. Contract changes must update all of the following together:

- TypeScript interfaces;
- JSON schemas;
- Python request or result models;
- example or synthetic payloads;
- contract and API tests.

Prefer backward-compatible, additive fields. Breaking changes require approval and coordinated migration.

### `packages/company-twin`

Owns entities, dependencies, evidence metadata, stable IDs, graph construction, graph validation, fixture loading, and company-state versioning.

It must not score scenarios or call language models.

### `packages/simulation-engine`

Owns authoritative arithmetic, propagation, cost displacement, constraints, portfolio enumeration or optimization, knowledge-risk detection, uncertainty calculations, mitigation re-simulation, and recommendation feasibility.

All deterministic business rules belong here, not in the API, agents, or frontend.

### `packages/agent-orchestration`

Owns scenario workflow, department routing, structured assessments, evidence challenges, clarification questions, explanations, and human checkpoints.

Agents may not invent company entities, override constraints, or replace deterministic calculations.

### `data`

Contains durable synthetic fixtures needed by the application or tests. Use stable IDs. Do not add copied API responses, manual exports, secrets, personal information, or throwaway samples.

### `infra`

Contains infrastructure that the project actually runs. Do not add speculative deployment configurations for unused platforms.

### `docs`

Contains durable, approved project documentation. Do not create a new Markdown file for every discussion, status update, idea, or implementation note. Update an existing authoritative document when appropriate, or keep temporary reasoning in the conversation.

## 6. File-Creation Discipline

Do not generate useless files.

Before creating a file, confirm that:

1. it has a clear runtime, testing, configuration, or durable documentation purpose;
2. no existing file is the correct home for the change;
3. its directory matches the ownership rules above;
4. another team member can understand why it exists;
5. it will be maintained after the current task.

Do not commit:

- scratch files, temporary exports, editor files, local databases, logs, screenshots, or debug dumps;
- generated caches, virtual environments, build output, coverage output, or dependency directories;
- duplicate README files or duplicate configuration files without a concrete need;
- empty placeholder modules, speculative interfaces, or commented-out implementation;
- one-off scripts when the same behavior belongs in an existing package, test, or documented command;
- parallel `v2`, `new`, `final`, `final-final`, or `backup` copies of files.

Delete temporary artifacts created during a task. If a generated artifact is necessary locally, add the narrowest safe ignore rule instead of committing it.

## 7. Folder and Module Quality

- Keep modules cohesive and named after domain responsibilities.
- Split a module when it combines unrelated responsibilities, not merely because it is long.
- Do not create a directory containing only an unnecessary wrapper or re-export.
- Keep tests close to the application or package they verify.
- Prefer imports through a package's public interface over reaching into another package's internals.
- Do not create circular dependencies between packages.
- Shared contracts may be depended on by all layers; higher layers must not be imported by lower layers.
- Use stable IDs rather than display names or array positions for integration.
- Preserve the dependency direction:

```text
contracts
    ↓
company-twin
    ↓
simulation-engine
    ↓
agent-orchestration
    ↓
api
    ↓
web
```

If the folder structure starts to violate these boundaries, clean it up as part of the relevant change. Do not perform broad cosmetic reorganizations unrelated to the task.

## 8. Implementation Standards

- Keep domain calculations deterministic and testable.
- Validate inputs and structured agent outputs.
- Attach evidence, confidence, timing, and dependency paths to reported impacts.
- Make assumptions explicit; do not present uncertain model output as fact.
- Preserve offline replay or deterministic fallback behavior for the demo.
- Keep secrets in environment variables and maintain `.env.example` with names only.
- Prefer small, reviewable changes that complete one vertical behavior.
- Reuse existing dependencies before adding another library.
- Add a dependency only when it removes meaningful complexity or is directly required by the approved plan.
- Do not weaken types, schemas, tests, or constraints to make a failing change pass.
- Do not duplicate calculations between Python and TypeScript.

## 9. Verification Requirements

Run checks proportional to the files changed. Before considering a cross-layer task complete, run:

```bash
pnpm typecheck
pnpm test
pnpm build
```

For API or engine changes, also exercise the relevant endpoint or domain function with a realistic fixture. For UI changes, verify loading, success, empty, and error states. Report any check that could not run and why.

Do not claim completion when tests are failing, contracts disagree, or generated output is the only evidence that the feature works.

## 10. Git and Team Coordination

- Preserve other contributors' changes.
- Do not rewrite shared history or use destructive Git commands unless explicitly requested.
- Keep commits focused and describe the behavior changed.
- Follow the workstream ownership in `docs/GLASSWING_TEAM_WORK_DIVISION.md`.
- Integrate through shared contracts rather than editing another workstream's internals.
- Resolve integration failures in the layer that owns the broken behavior; do not patch around them downstream.
- Keep the repository clean at handoff.

## 11. Completion Checklist

Before finishing a task, confirm:

- the change advances the approved core plan;
- no unapproved feature was added;
- every new file has a necessary and correct home;
- no domain rule was duplicated in another layer;
- relevant contracts and tests agree;
- temporary and generated files are not tracked;
- validation commands passed;
- the final summary names the important files changed and any remaining limitation.

