# TASK

Implement issue {{TASK_ID}}: {{ISSUE_TITLE}}

Work on branch {{BRANCH}}. This branch belongs only to this Task. Its base
contains the last published integration for the parent Feature. Independent
sibling Tasks may run at the same time, so do not absorb their scope.

Only work on the issue specified. If you finish early, stop.

# PAID SESSION CONTRACT

You have one paid, non-resumable session. A planning-only response wastes the
entire Task attempt.

- Do not delegate exploration to subagents. They cannot implement in this
  worktree, and their findings do not survive this session.
- Start from the ticket's `Touches`, `Seams`, and `Tests`. Read only files
  needed for the next red-green step.
- Before your twelfth tool call, either run the named targeted test or make the
  first test edit. Do not perform a broad repository survey first.
- Do not stop after analysis, a plan, or a progress update. Continue using
  tools until you have committed complete work or found a concrete blocker
  that makes implementation unsafe.
- If blocked, name the missing fact or failed command precisely. Do not spend
  the rest of the session researching unrelated paths.

# READ THE TICKET

The host orchestrator fetched this Task, its comments, and its parent Feature
before starting the sandbox:

<issue-context>

{{ISSUE_CONTEXT}}

</issue-context>

1. Read the Task body and comments in the supplied context.
2. If the context includes a parent Feature, read its body and comments too. The Feature owns the requirements; the Task restates the ones it must satisfy.
3. Read the ADRs the ticket cites, by number, through `docs/adr/README.md`. Read only those. The index exists so you do not have to read the directory, and reading all nineteen will cost you the context you need for the code.
4. Read the `CONTEXT.md` entries for the domain terms in the ticket. This repo's vocabulary is precise and the definitions carry the `_Avoid_` list that tells you which nearby word means something different.

A ticket in this repo is specified as four things: **Criteria** restated in full, the test **Seams** the work goes through, the **Tests** that prove the criteria, and a closing **Touches** line naming the primary code paths. If any of the four is genuinely missing and you cannot resolve it from the Feature or the ADRs, stop and say so in your final message rather than guessing. Guessing the criteria produces code that passes review and misses the spec.

# CONTEXT

Here are the last 10 commits:

<recent-commits>

!`git log -n 10 --format="%H%n%ad%n%B---" --date=short`

</recent-commits>

# EXPLORATION

Explore narrowly from the paths in the ticket's `Touches` line. Read the named
test seam and the production code directly behind it, then begin the first
red-green cycle.

Pay extra attention to the existing tests that touch the relevant code. `tests/contract/` holds the boundary tests: import rules, hermetic network, structured logging, runtime settings, HTTP status shapes, and generated-OpenAPI staleness. If your change is visible at a boundary, one of those files probably already tests the boundary and should be extended rather than duplicated.

# ARCHITECTURE YOU MUST RESPECT

The module boundaries are enforced by `.importlinter` and checked in `just lint`, so violating them fails the build rather than merely annoying a reviewer. The shape:

- `kernel/` imports nothing else in `flash_trips`, and no framework or driver.
- `capabilities/` import `kernel`, their own contracts and ports, and the Evidence Ledger, Approval, or Route Measurement **ports** only. Never a sibling capability, never adapters, never composition, never FastAPI or SQLAlchemy.
- `platform/` imports `kernel`, its own ports, and capability definition types.
- `application/` imports `kernel`, capability public contracts, and platform ports.
- `adapters/` implement ports. The HTTP and PostgreSQL adapter families do not import each other.
- `composition/` wires everything, and nothing imports `composition`.
- Anything under a `_implementation` module is private to its own capability or platform module.

Two more rules that are easy to trip over:

- Pydantic models are canonical. FastAPI emits the OpenAPI document and `just contracts` generates the TypeScript client. **Never hand-edit anything under `contracts/`.** If you changed the API surface, run `just contracts` and commit the regenerated files.
- Models propose, deterministic code decides. Facts, money, permissions, safety, and state transitions are validated in application code, never trusted from a model's output.

# EXECUTION

Use red-green cycles at the ticket's named Seams. Those Seams are the
pre-agreed public boundaries for this work:

1. RED: write one targeted failing test that proves one acceptance criterion
   through its named Seam, then run it and confirm it fails for the expected
   reason.
2. GREEN: write only enough implementation to make that test pass, then rerun
   the targeted test.
3. Run the relevant typechecker regularly during the cycles.
4. REPEAT one criterion at a time until every criterion has a test behind it.

Do not add speculative tests or implementation, and do not test private
internals. Leave optional cleanup and refactoring to the review phase.

Tests run with sockets disabled (`--disable-socket`). Default tests make no live provider, model, or judge calls; use the in-process fakes. Tests needing real PostgreSQL carry the `persistence` marker.

Python is Pyright strict and Ruff with `E,F,I,UP,B,SIM,RUF,S`. TypeScript is strict. Neither `Any` nor a silencing comment is a fix.

# FEEDBACK LOOPS

Use `just verify` as the iteration loop. Run `just check` before committing: it adds the security audit and the generated-contracts staleness check, and the ticket's own criteria almost always include `just check` passing.

If a requirement ID moved or a source changed, `pnpm traceability` reconciles `requirements/registry.json` against `requirements/coverage.md`, and it runs inside `just lint`.

# TICKET ACCEPTANCE

Register a short, repeatable acceptance check in
`acceptance/issues/{{TASK_ID}}.json`. Use schema version 1, the numeric issue
ID, the issue title without its Task prefix, one plain-language outcome
sentence, and one or more focused checks:

```json
{
  "schema_version": 1,
  "issue": 239,
  "title": "Establish the authenticated principal contract",
  "outcome": "Added a protected endpoint that returns redacted identity data and safe authentication problems.",
  "checks": [
    {
      "name": "authenticated principal HTTP contract",
      "command": ["uv", "run", "pytest", "-q", "tests/contract/test_http_principal.py"]
    }
  ]
}
```

Commands are argument arrays, not shell strings. Keep them hermetic and focused
on the public Seams named by the Task. Prefer browser-level checks for
user-visible behavior and HTTP or contract checks for backend-only behavior.
Do not put setup instructions or a second specification in the manifest.

Run `just accept {{TASK_ID}}` before the final gate. A successful run must print
only the title, the one-sentence outcome, and PASS.

# COMMIT

Commit your work. Match the existing log: a short imperative sentence-case summary, no type prefix, referencing the issue number.

```
Establish the authenticated principal contract (#239)

Add the provider-neutral principal type in application/, declare the
token verifier port, and wire a fake in the composition root for tests.

Left the JWKS cache for T-03, which owns real verification.
```

The body should carry the decisions you made, anything a later Task on this branch needs to know, and any blocker you hit. Keep it short. Commit messages are the handoff between rounds, because your context does not survive to the next one.

# DO NOT WRITE TO THE TRACKER

Produce commits. That is your whole output surface.

Do not close the issue, comment on it, move a label, or open a pull request. The orchestrator does all of that afterwards, from facts it can verify, so that every irreversible write is a deterministic step that can be read, replayed, and reverted. A bad run should cost a branch, not a specification.

If the work is incomplete, say so in your final message and leave the reason in your last commit body.

Once complete, output <promise>COMPLETE</promise>.

# FINAL RULES

ONLY WORK ON A SINGLE TASK.
