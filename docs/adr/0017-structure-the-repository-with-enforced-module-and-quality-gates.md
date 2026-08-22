# Structure the repository with enforced module and quality gates

Flash Trips will keep application code in one GitHub repository: a single installable Python package for the modular monolith, a Next.js BFF/UI app, committed generated HTTP contracts, top-level evaluations, and deployment-target-neutral quality gates. Internal capability seams are directories plus an import linter, not separately versioned packages. A vertical slice is a Planner-, Guest-, or Operator-visible journey through UI, BFF, typed command or query, and PostgreSQL, not a module or a layer.

## Considered Options

- An agent/RAG tree organised around `agents/`, `tools/`, `prompts/`, `services/`, and `components/` was rejected because it restates the technical roles Flash Trips already refused: models, tools, and LangGraph are private machinery, not product structure. Authoritative modules remain Trip Request, Trip Structure, Air Travel, Accommodation, Dining, Activities, Ground Transport, Travel Readiness, Budget, Itinerary, and Plan Assembly.
- Polyglot `apps/` + `packages/` workspaces and split web/API repositories were rejected because they add package versioning without matching the in-process monolith or the single Alembic history.
- JSON Schema or OpenAPI as the authored source of truth, and independently handwritten TypeScript types, were rejected because API and Capability contracts already live as Pydantic models.
- Module-cut slices (“finish Air Travel”) and per-slice Azure deploy plus semantic judging were rejected: vertical means through the stack; Layers 2–4 and hosted promotion remain the evaluation and Azure tickets’ gates.

## Consequences

The tree is:

```text
apps/web/                 # Next.js BFF + Guest, Planner, and Operator UI
apps/api/                 # Dockerfile only; runs python -m flash_trips.composition
src/flash_trips/
  kernel/                 # IDs, money, time, problem types, Fingerprints
  application/            # TripPlanning façade, commands, queries, commit coordinator
  capabilities/           # one directory per authoritative module
  platform/               # Workflow Compiler, Reasoning Runtime, RunInspector, Handbook Compiler, Approval, Evidence Ledger
  adapters/               # HTTP, PostgreSQL, providers, identity, models
  composition/            # FastAPI app factory and wiring only
contracts/openapi/        # generated OpenAPI, committed
contracts/ts/             # generated @flash-trips/api-client, committed
evals/                    # cases, fixtures, Contract Baselines, Quality Baselines, rubrics
tests/                    # unit, contract, persistence, integration
scripts/                  # seed, healthcheck, and other utilities; not Alembic
infra/                    # Bicep and hosted-profile files when they exist
docs/
```

Pydantic models are canonical. FastAPI emits OpenAPI; `just contracts` generates the TypeScript client. CI fails if generated files are stale. Hand-editing generated files is forbidden.

Import linter rules, enforced in CI:

- `kernel` imports no other `flash_trips` package.
- A capability imports `kernel`, its own contracts/ports, and Evidence Ledger, Approval, or Route Measurement **ports** only. It never imports a sibling capability, adapters, composition, FastAPI, LangGraph, Azure SDKs, or provider/model clients.
- Platform modules import `kernel`, their own ports, and Capability Definition types where the compiler or registry needs them.
- `application` imports `kernel`, capability public contracts, and platform ports.
- Adapter families implement ports and do not import other adapter families, capability internals, or composition.
- `composition` may wire everything; nothing else imports `composition`.
- Dining and Activities share place identifiers only through `kernel` utilities. There is no Place Discovery module.
- Cross-capability data moves only through schema-versioned `consumes` / `produces`. Canonical writes go through the Trip Planning commit coordinator.

Local development runs PostgreSQL and Azurite in Docker Compose and FastAPI plus Next.js as native `uv` and `pnpm` processes. Identity, providers, and models use in-process fakes and locally signed test identities by default. Alembic lives at `src/flash_trips/adapters/postgres/migrations/` with one linear history. Dockerfiles sit beside `apps/web` and `apps/api`. Hosted Azure wiring, scale, identities, and promotion remain the Azure topology decision.

Tooling is Python 3.12, `uv`, Ruff, Pyright strict, pytest, Alembic, and import-linter; Node 22, `pnpm`, TypeScript strict, ESLint, Prettier, and a Next.js production build. A root `justfile` is the only command surface for format, lint, typecheck, test, contracts, migrate, eval-layer1, and dev. Pre-commit runs formatters; CI is the gate.

`evals/` holds cases by capability, Reasoning Profile, flow, and Trip; fixtures with provenance and digest; reviewed Contract and Quality Baselines; and rubrics. Evaluation results are not committed. Capability conformance lives in `tests/contract/`. Guest, Planner, and Operator UI live in separate Next.js route groups; `apps/web/app/api` is BFF-only.

A slice may merge only when format, lint, types, and import rules pass; generated contracts are current; Alembic has a single head and, if the schema changed, upgrade from the previous schema plus rollback to the previous application image is proven against real PostgreSQL; module, contract, and affected Evaluation Layer 1 tests pass with frozen fixtures; any new Capability passes the shared offline conformance suite; default tests make no live provider, model, or judge calls; and, once Dockerfiles exist, both images still build without push. Layers 2–4, live canaries, and Azure deploy are not per-slice merge gates.

Pull requests run those engineering checks. `main` adds real-PostgreSQL integration, persistence/resume, SSE, handbook smoke, and digest-identified container smoke once images exist.
