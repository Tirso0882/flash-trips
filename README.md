# Flash Trips

Flash Trips is an invitation-only, evidence-backed travel planning product. The
repository contains one Python modular monolith, a Next.js BFF and UI, generated
HTTP contracts, tests, and deployment-neutral build files.

## Prerequisites

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js 22 and pnpm 10.33.2
- [just](https://just.systems/)
- Docker for PostgreSQL, Azurite, and container checks

## Local setup

```sh
just install
cp .env.example .env
docker compose up -d postgres azurite
just migrate
uv run pre-commit install
```

Run FastAPI and Next.js together with `just dev`. The Planner shell is at
`http://localhost:3000/planner`, the Operator shell is at
`http://localhost:3000/operator`, and the BFF status route is at
`http://localhost:3000/api/status`.

## Quality gates

- `just format`: apply Python and web formatting
- `just lint`: formatting, lint, import boundaries, and traceability
- `just typecheck`: strict Python and TypeScript checks
- `just contracts`: regenerate OpenAPI and `@flash-trips/api-client`
- `just contracts-check`: fail when committed generated contracts drift
- `just test`: contract, persistence, and traceability tests
- `just containers`: build both non-root OCI images
- `just verify`: run lint, type checks, and tests during development
- `just check`: run the complete non-container quality suite

Persistence tests use real PostgreSQL. They skip only when `DATABASE_URL` and
`MIGRATION_DATABASE_URL` are absent. CI and `.env.example` provide both values.

Local and CI configuration grants zero live-call authority. Identity, model,
travel-provider, and Azure calls are outside this scaffold.
