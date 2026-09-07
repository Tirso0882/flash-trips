# Coding Standards

The reviewer agent loads this file during code review, so these standards are enforced without costing tokens during implementation.

Scope note: rules that a tool already enforces are listed only where a reviewer can catch the intent behind them earlier or better than the tool can. `just check` is the gate. This file is for what survives a green build.

## Style

- Python is Ruff-formatted at 88 columns, `E,F,I,UP,B,SIM,RUF,S`, and Pyright strict. TypeScript is strict, ESLint via `eslint-config-next`, Prettier-formatted.
- A silencing comment is not a fix. `Any`, `# type: ignore`, `# noqa`, `eslint-disable`, and unchecked casts each need a comment saying why the checker is wrong, or they need removing.
- Name things in the vocabulary of `CONTEXT.md`. Each entry there carries an `_Avoid_` list of nearby words that mean something else in this domain, and picking one of those is how a codebase quietly loses a distinction. Selection is not a Candidate, an Approval is not a confirmation message, and a Trip Handbook is not a report.
- Comments state constraints the code cannot show. Not what the next line does, and not where the change came from.
- Prefer named exports. Prefer a switch or an if/else chain over nested ternaries.

## Testing

- Every acceptance criterion in the ticket has a test that would fail without the implementation. A criterion covered only by "the app still boots" is not covered.
- Tests go through the seam the ticket names. If the ticket proposes a new seam, the test drives that seam rather than reaching around it.
- Default tests make no network call. Sockets are disabled via pytest's `--disable-socket`, and the web boundary tests run under `tests/node/deny-network.mjs`. Use the in-process fakes and locally signed test identities.
- Tests requiring real PostgreSQL carry the `persistence` marker and live in `tests/persistence/`. Boundary and conformance tests live in `tests/contract/`.
- No live provider, model, or judge calls in the default suite, and no evaluation results committed.
- Test names say the expected behaviour, not the function under test.

## Architecture

- Module boundaries are the ones in `.importlinter`, and they are the point of the layout rather than a formality. `kernel` depends on nothing. A capability never imports a sibling capability, an adapter, `composition`, or a framework. Nothing outside a module imports its `_implementation`. Nothing imports `composition`.
- Cross-capability data moves only through schema-versioned `consumes` and `produces`. Canonical writes go through the Trip Planning commit coordinator.
- Pydantic models are canonical. FastAPI emits the OpenAPI document, `just contracts` generates the TypeScript client, and both are committed. Hand-editing anything under `contracts/` is forbidden.
- Models propose, deterministic code decides. Facts, money, permissions, safety, and state transitions are validated in application code. A model's output is untrusted input until it has been through a typed validation.
- Fail closed. On an unresolved identity, ownership, authority, or eligibility question, deny. Error responses are RFC 9457 problems and do not disclose which internal check failed.
- Committed records are immutable. Plan Revisions, Handbook Snapshots, audit records, and inspection records are appended, never edited in place.
- Alembic keeps one linear history under `src/flash_trips/adapters/postgres/migrations/`.
- Keep modules deep: a small interface over substantial functionality. A new abstraction that only forwards its arguments is one more thing to read and nothing to gain.
