# GlassWing / Canary Pact

Monorepo for Canary Pact, an AI-powered organizational decision simulator that models the company-wide blast radius of proposed decisions before they are approved.

## Applications and packages

```text
apps/
├── web/                    Next.js executive dashboard
└── api/                    FastAPI service
packages/
├── contracts/              Shared JSON contracts and TypeScript types
├── company-twin/           Organizational graph and fixtures
├── simulation-engine/      Deterministic blast-radius calculations
└── agent-orchestration/    LangGraph department workflow
data/                       Synthetic company and scenarios
infra/                      Local PostgreSQL infrastructure
docs/                       Master plan and four-person work split
```

## Quick start

Requirements: Node.js 20+, pnpm 10+, Python 3.11+, and uv.

```bash
pnpm install
uv sync --all-packages
pnpm dev
```

The dashboard runs at `http://localhost:3000`; the API and interactive documentation run at `http://localhost:8000` and `http://localhost:8000/docs`.

To start PostgreSQL separately:

```bash
docker compose -f infra/compose.yaml up -d
```

The starter API uses in-memory state so the demo runs without PostgreSQL. The database service is ready for persistence work.

## Verification

```bash
pnpm typecheck
pnpm test
```

## Documents

- [`docs/CANARY_PACT_MASTER_IMPLEMENTATION_PLAN.md`](docs/CANARY_PACT_MASTER_IMPLEMENTATION_PLAN.md) — complete product, architecture, simulation, orchestration, API, testing, and delivery plan.
- [`docs/GLASSWING_TEAM_WORK_DIVISION.md`](docs/GLASSWING_TEAM_WORK_DIVISION.md) — non-overlapping work allocation for a four-person team, including ownership, deliverables, checkpoints, and integration rules.
- [`AGENTS.md`](AGENTS.md) — mandatory scope, architecture, file-placement, quality, and approval rules for coding agents.
- [`CLAUDE.md`](CLAUDE.md) — Claude entry point that enforces the same repository rules.

## Recommended starting order

1. Read the master implementation plan as a team.
2. Replace `Person 1` through `Person 4` in the work-division document with team members' names.
3. Freeze the shared JSON contracts and stable entity IDs.
4. Create one branch per workstream.
5. Complete the early vertical slice before expanding either demonstration scenario.

## Product principle

> Agents reason; deterministic code calculates; humans decide.
