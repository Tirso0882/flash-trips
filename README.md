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

## Sandcastle autopilot

Applying `agent:autopilot` to a parent Feature authorizes Sandcastle to process
its dependency-ready Tasks. It runs up to three independent Tasks at once on
Task-local branches, integrates them into one Feature branch, and opens or
updates a draft Feature pull request into `main`. Sandcastle must run from a
clean, remote-matched `main` checkout. A Task closes only after that remote
branch and pull request are verified.

Set `SANDCASTLE_TASK_BUDGET` and `SANDCASTLE_TIME_BUDGET_MINUTES` in
`.sandcastle/.env` to bound one AFK run. A Task with external pre-run gates
also needs `agent:gates-cleared`. If it declares an `## AFK environment`
section, allowlist those variable names with `SANDCASTLE_TASK_ENV_ALLOWLIST`.
Sandcastle passes only those configured values to that Task sandbox.

When a Feature has no remaining agent Tasks, Sandcastle marks its pull request
ready and enables squash auto-merge. GitHub merges only after the required
`quality`, `containers`, and `traceability` checks pass.

## Production deployment

Production runs on Azure Container Apps in West Europe. GitHub Actions builds
the API and web images once after `main` CI succeeds, publishes immutable image
digests to Azure Container Registry, and pauses at the protected `production`
environment before deploying those exact digests.

After the deployment files have reached `main`, run the repeatable setup wizard:

```sh
scripts/setup-azure-production.sh
```

The wizard previews the Bicep deployment, provisions the Azure app baseline,
configures secretless GitHub OIDC identities and the production approval gate,
then walks through the first release. It does not create PostgreSQL or modify
the existing Azure AI Services and External ID resources.
