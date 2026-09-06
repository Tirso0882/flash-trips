set dotenv-load := true
set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

install:
    uv sync --frozen --python 3.12
    pnpm install --frozen-lockfile

format:
    uv run ruff format src tests scripts
    uv run ruff check --fix src tests scripts
    pnpm --dir apps/web exec prettier --write .

lint:
    uv run ruff format --check src tests scripts
    uv run ruff check src tests scripts
    uv run lint-imports --no-cache
    pnpm --dir apps/web lint
    pnpm --dir apps/web format:check
    pnpm traceability

typecheck:
    uv run pyright
    pnpm exec tsc --project tsconfig.json
    pnpm --dir apps/web typecheck

security:
    uv run pip-audit
    pnpm audit --audit-level high

test:
    uv run pytest
    pnpm test:traceability
    pnpm test:web-boundaries
    bash tests/scripts/publish-via-github-api.test.sh

contracts:
    pnpm contracts

contracts-check:
    pnpm contracts
    git diff --exit-code -- contracts/openapi contracts/ts

migrate:
    uv run alembic upgrade head

eval-layer1:
    uv run pytest tests/contract

containers:
    docker build --file apps/api/Dockerfile --tag flash-trips-api:local .
    docker build --file apps/web/Dockerfile --tag flash-trips-web:local .

dev:
    docker compose up -d postgres azurite
    trap 'kill 0' EXIT; uv run python -m flash_trips.composition & pnpm --dir apps/web dev & wait

verify: lint typecheck test

check: lint typecheck security contracts-check test
