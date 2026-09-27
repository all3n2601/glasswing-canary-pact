# Canary Pact

Canary Pact shows what a proposed cut breaks before anyone approves it. It maps which workflows,
systems, vendors, controls and KPIs depend on each team, simulates acting now, doing nothing and
waiting, and hands a human a decision package with the evidence behind every claim.

> Agents reason; deterministic code calculates; humans decide.

## Problem

Companies under pressure to cut cost make the cuts team by team, without seeing what each cut
breaks: the vendor that feeds three other teams, or the two people who are the only ones who
understand a critical workflow. The cut goes through, the knowledge walks out, and the company
rehires at a premium.

The evidence that this goes wrong is public:

- Only **14%** of companies fully captured the value of their top cost initiative in 2025, and only
  **24%** account for value leakage when they set targets
  ([Deloitte 2026](https://www.prnewswire.com/news-releases/organizations-are-betting-on-cost-transformation-to-fund-growth--but-few-are-capturing-the-full-value-302875992.html)).
- Only about **10%** of cost-reduction programs show sustained results three years later (2010)
  ([McKinsey](https://www.mckinsey.com/capabilities/strategy-and-corporate-finance/our-insights/five-ways-cfos-can-make-cost-cuts-stick)).
- Of leaders who made staff redundant because of AI, **55%** admit they made wrong decisions about
  those redundancies (2025)
  ([Orgvue](https://www.orgvue.com/news/55-of-businesses-admit-wrong-decisions-in-making-employees-redundant-when-bringing-ai-into-the-workforce/)).
- High performers are rehired **120%** more often, often at about **25%** higher pay
  ([Visier, 142 enterprises](https://www.visier.com/blog/true-cost-layoff-boomerangs/)).
- **42%** of institutional knowledge is unique to the individual employee
  ([Panopto](https://www.panopto.com/company/news/inefficient-knowledge-sharing-costs-large-businesses-47-million-per-year/)).
- There were **1.2M** announced US job cuts in 2025
  ([Challenger](https://www.challengergray.com/blog/2025-year-end-challenger-report-highest-q4-layoffs-since-2008-lowest-ytd-hiring-since-2010/)).
- **96%** of organizations are pursuing, have completed or plan a cost transformation, and **77%**
  expect to invest **$0.20 to $0.90** for every dollar of savings targeted ([Deloitte 2026](https://www.prnewswire.com/news-releases/organizations-are-betting-on-cost-transformation-to-fund-growth--but-few-are-capturing-the-full-value-302875992.html)).

## Who pays

- **Buyer:** the CFO or transformation office running a cost program.
- **Users:** department heads, who review what the cut does to their workflows and approve or reject.
- **Pricing:** an annual license priced by headcount or by modelled spend.
- **ROI:** avoided rehire premiums and outages, and savings that stick.
- **Positioning:** they find the savings; we tell you what breaks. Canary Pact is meant to sit
  next to the planning tools a company already uses (for example Orgvue, Pigment or Workday) as
  the blast-radius check; no integration exists yet.
- **Scope:** it scores teams and systems, never individuals. People appear only as anonymous person
  tokens, which are replaced by their roles before anything reaches a human, and a decision package
  is rejected if any person token remains.

## How it works

1. **Company twin.** A graph of departments, roles, workflows, systems, datasets, vendors, controls,
   KPIs and knowledge assets, with typed edges, 25 department channels, baseline pressures (renewal
   uplifts, cost growth, failure hazards) and evidence records that point into source documents.
2. **Decision brief.** The decision to test: candidate interventions (remove a vendor, remove roles,
   reduce capacity), a savings goal, hard and soft constraints, and the futures to compare
   (act now, do nothing, wait 90 days).
3. **Orchestration.** A LangGraph run goes through validating, building futures, optimizing,
   running agents, propagating, challenging, comparing futures, generating the package and
   awaiting approval. Every step is an event on a per-run stream.
4. **Department agents.** Finance, engineering, AI and data, operations, product, marketing, sales,
   customer success, compliance and people knowledge are routed by decision type and graph
   reachability. Each sees only its permitted view of the twin and returns a structured assessment
   of acting now and of doing nothing.
5. **Challenger.** A final agent looks for missed dependencies, unsupported assumptions and
   underestimated inaction.
6. **Merge rules.** Agent claims about unknown entity IDs are rejected. Claims with resolving
   evidence are validated; the rest stay hypotheses and never change the numbers. Claims that
   contradict an engine impact are rejected. A validated new dependency is added to a copy of the
   twin, and the run is simulated and optimized again. Agents never supply numbers.
7. **Engine.** Deterministic code computes savings, costs, pressure costs, constraint results,
   risk scores and blast radius for each future. All engine and twin calls go through one module,
   `apps/api/src/canary_api/engine_port.py`.
8. **Decision package.** The recommendation, the futures comparison, naive and recommended
   portfolios, both blast radii, critical risks, assumptions and open questions. An approver
   approves, rejects or asks for another scenario, and the decision is stored with a hash of the
   exact package shown.

The pieces live in:

```text
apps/api                     FastAPI service: runs, events, WebSocket, replay, auth, storage
apps/web                     Next.js dashboard
packages/contracts-py        Pydantic contracts (source of the JSON Schemas and TypeScript types)
packages/contracts           Generated JSON Schemas and TypeScript types
packages/agent-orchestration Agents, prompts, router, merge rules, orchestrator, eval harness
packages/company-twin        Twin loader, validation, graph queries, role-level views
packages/simulation-engine   Deterministic engine (in progress; see below)
data/                        Synthetic Northstar twin and the two scenario briefs
```

## What is real vs mocked

Real today:

- **The Northstar twin**, `data/synthetic_company.json`: 154 entities, 108 edges, 30 evidence
  records and 30 documents, loaded and validated by `packages/company-twin`. The company is
  synthetic.
- **Two scenario briefs:** `data/vendor_scenario.json` (consolidate seven data vendors) and
  `data/workforce_scenario.json` (eliminate eight roles behind two critical workflows).
- **Live LLM agents** on DeepSeek V4.1 Flash, served through Sciforium's OpenAI-compatible API,
  with structured output, one retry, a timeout and a replay cache.
- **The orchestration, routing, merge and validation rules,** and the person-token guard.
- **Authentication:** sign-up creates viewers; only an approver can record a decision. There is
  one demo approver, created from environment variables at startup.
- **Storage:** files and SQLite by default, or Postgres when `DATABASE_URL` is set.
- **Replay and the eval harness.**

Mocked today:

- **The simulation engine's money values.** `simulation_engine` has `check_result`,
  `quick_impact`, `optimize`, `blast_radius` and quick-mode `simulate` so far. Until
  `compare_futures` and the inaction and delay futures land, the demo runs on the stub engine,
  which returns fixed constants from `apps/api/src/canary_api/stubs/`. Every
  package built on them says so in its assumptions ("Stub engine output: fixed constants,
  expected-value mode."). This README will be updated when the engine lands.
- **The company.** Northstar Technologies is synthetic, and so are its documents and evidence.

Measured agent ablations can be produced with `uv run python -m canary_api.eval_cli`, which writes
`data/artifacts/eval/ablation.csv`.

## Running it

Prerequisites: Node.js 20+, pnpm 10+, Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-packages
pnpm install --frozen-lockfile
cp .env.example .env        # then fill in what you need; never commit .env
```

Start both apps with `pnpm dev`, or separately:

```bash
pnpm dev:api    # FastAPI on http://localhost:8000, docs at /docs
pnpm dev:web    # Next.js on http://localhost:3000
```

Important environment variables (see `.env.example`; names only here):

- `ENGINE_IMPL` and `TWIN_IMPL`: `stub` or `real`. The twin follows the engine unless set.
  `TWIN_IMPL=real` with the default stub engine runs the real Northstar twin.
- `SCIFORIUM_API_KEY`, `SCIFORIUM_BASE_URL`, `MODEL_STRONG`, `MODEL_FAST`: live model access.
- `CANARY_ALLOW_LIVE`: must be `true` before a run may use `llm_mode=live`.
- `CANARY_STRUCTURED_OUTPUT`: `auto` (default), `json_schema` or `function_calling`.
- `CANARY_AUTH_SECRET`: token signing secret. If blank, tokens reset on every restart.
- `CANARY_DEMO_APPROVER_EMAIL`, `CANARY_DEMO_APPROVER_PASSWORD`: create the demo approver.
- `DATABASE_URL`, `CANARY_DB_SCHEMA`: optional Postgres (tables live in a private `canary` schema).

LLM modes are chosen per run with `POST /decisions?llm_mode=mock|replay|live`. The default is
`replay`, which answers from the recorded cache and falls back to mock answers, recording that in
the package's assumptions, when the cache is empty.

Offline demo with no model or database: start the API and replay the recorded run.

```bash
curl -X POST "http://localhost:8000/replays/sample_run/play?speed=2"
# then watch ws://localhost:8000/runs/<run_id>/events or GET /runs/<run_id>/package
```

Tests and checks:

```bash
uv run pytest -q
pnpm typecheck
uv run python -m canary_api.eval_cli --mode mock   # or replay; live needs CANARY_ALLOW_LIVE=true and makes paid model calls
```

The Postgres tests run only when `CANARY_TEST_DATABASE_URL` is set; they use a throwaway schema.

## Prior work

The history of `origin/main` starts on 2026-09-26, the day of the hackathon:

- 2026-09-26 12:11 (UTC-4), M A Allen Febi: "Add Canary Pact master plan and team work split"
- 2026-09-26 12:27, M A Allen Febi: "Scaffold Canary Pact monorepo"
- 2026-09-26 12:34, M A Allen Febi: "Add repository guardrails for coding agents"
- 2026-09-26 14:31, Adhithyan245: "Add files via upload (#1)"

Every commit on `dev` is also dated during the event.

## Documents

- [`docs/CANARY_PACT_MASTER_IMPLEMENTATION_PLAN.md`](docs/CANARY_PACT_MASTER_IMPLEMENTATION_PLAN.md): product and technical plan.
- [`docs/CANARY_PACT_SCHEMA_v2_merged.md`](docs/CANARY_PACT_SCHEMA_v2_merged.md): the merged data schema.
- [`docs/architecture.md`](docs/architecture.md): architecture diagrams.
- [`docs/GLASSWING_TEAM_WORK_DIVISION.md`](docs/GLASSWING_TEAM_WORK_DIVISION.md): team work split.
- [`docs/skillfiles/`](docs/skillfiles/): the department knowledge each agent is given.
- [`AGENTS.md`](AGENTS.md) and [`CLAUDE.md`](CLAUDE.md): repository rules for coding agents.

## Team

Adhithyan (Adhithyan245), Hemnaath (hemnaath04), M A Allen Febi, Mithuna Murugesh.
