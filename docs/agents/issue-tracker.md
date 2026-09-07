# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --limit 200 --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters. Keep `--limit` high: `gh` returns 30 by default, which silently hides most of the backlog.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply/remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v`; `gh` does this automatically inside the repository.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs use the equivalent `gh pr` operations and the same triage labels. This flag governs triage only. The pipeline's own `agent:review` label is unrelated to it and applies to pull requests the pipeline itself opened.

## Ticket kinds

The tracker holds two kinds, and the title prefix declares which:

A **Feature** is the unit that owns requirements. It carries the acceptance criteria, the entry in `requirements/registry.json`, and the `FT-*` or `E-*` prefix. Its pull request closes it after the last Task and any final human review complete.

A **Task** is the unit of agent work. It restates every criterion it must satisfy, names the seams under test, and carries the `T-*` prefix. It must fit one agent session inside 100K tokens.

Tasks are flat. A Task that needs sub-issues is a Feature that was cut too coarsely; split it into peer Tasks instead. Native dependencies define execution order. Independent Tasks under one Feature may run concurrently.

Roadmap grouping is not a Feature. Release sequencing is a GitHub milestone, which is not an issue and so can never be picked up. The product charter stays an issue, because `requirements/registry.json` sources most requirements to it, and it carries the `roadmap` label instead.

### What the pipeline reads

The graph says how a ticket runs, and the labels say whether it may run at all. Size is never inferred from the graph.

Refuse a ticket labelled `roadmap` before reading the graph. Sequencing and charter tickets are specifications to read, never work to pick up.

| Graph shape | How it runs |
| --- | --- |
| Has sub-issues | Never implemented directly. Its Tasks integrate into one Feature branch, and that branch opens one pull request |
| Has a parent, no sub-issues | One agent session on `sandcastle/task-{Task}` |
| Neither | One agent session, on its own branch |

A Feature that has no Tasks yet is not workable, however small it looks. Decompose it first. `ready-for-agent` is what holds this line: the pipeline honours `agent:implement` only on a ticket that also carries `ready-for-agent`, and only a Task body can satisfy the four requirements below. So `ready-for-agent` belongs on Tasks, never on the Feature above them.

## Task bodies

A Task is `ready-for-agent` when an agent can implement it without asking a question. That requires all four of:

- **Criteria** restated in full. A pointer to the Feature is not a restatement.
- **Seams** named: the existing test seams the work goes through, and any new seam the Task is proposing.
- **Tests** named: the failing tests that prove the criteria.
- **Touches**: one closing line naming up to three primary code paths plus the ADR numbers to read, for example `Touches: src/flash_trips/capabilities/trip_request/. See ADR 0008, ADR 0014.` Cite ADRs by number and let the reader reach them through `docs/adr/README.md`. Point at `contracts/openapi/openapi.json` rather than `contracts/`.

When a Task is missing any of the four, comment what is missing, apply `needs-info`, and stop. Guessing the criteria produces code that passes review and misses the spec.

To fill the gaps, label the Task `agent:explore`. The exploration pass reads the repo and posts a comment reporting difficulty, the files the change lands in, whether the Task's claims hold up against the code, and what an implementer still needs to resolve. It changes no files.

## Dependencies

Declare blockers as native GitHub issue dependencies. The pipeline resolves what is workable with the GraphQL `blockedBy` and `blocking` connections, so a dependency written in prose is invisible to it.

## Pipeline labels

Two label families, answering two different questions.

The **triage labels** describe how well a ticket is specified. See `docs/agents/triage-labels.md`.

The `agent:*` labels describe where a ticket sits in the pipeline. Humans apply `agent:autopilot`, `agent:implement`, `agent:explore`, `agent:review`, and `agent:queued`; automation owns the rest.

| Label | Meaning |
| --- | --- |
| `agent:autopilot` | Opt a parent Feature into automatic Task authorization and scheduled execution |
| `agent:gates-cleared` | Confirm that one Task's external pre-run gates and disposable credentials are ready |
| `agent:implement` | Work this now. Honoured only alongside `ready-for-agent` |
| `agent:queued` | Work this once its blockers close. Promoted to `agent:implement` automatically |
| `agent:explore` | Run the exploration pass and post the findings |
| `agent:review` | Review this pull request |
| `agent:in-progress` | A run holds this ticket |
| `agent:blocked` | The last run refused or failed. The comment carries the reason |

One label sits outside both families. `roadmap` marks a sequencing or charter ticket, and every workflow refuses it outright.

`agent:autopilot` is persistent spending, publication, and pull-request
authorization for one Feature. Sandcastle authorizes its dependency-ready
frontier and may run independent Tasks concurrently within the global
three-Task cap. Each Task has `sandcastle/task-{Task}`. Reviewed Tasks integrate
into `sandcastle/feature-{Feature}`, which owns one draft pull request into the
checked-out base branch. A Task closes only after the remote Feature tree and
pull request are verified. The pull request becomes ready when no agent Task
remains. Remove `agent:autopilot` to stop new claims; a claimed Task finishes.

## External gates and Task credentials

A Task with a non-empty `## External human or evidence gates` section requires
`agent:gates-cleared`. Use that section only for pre-run gates. Put approval of
an artefact that does not exist yet in a later `ready-for-human` Task.

Credential names go in an exact, names-only section:

```md
## AFK environment

- FLASH_TRIPS_OIDC_CLIENT_ID
- FLASH_TRIPS_OIDC_CLIENT_SECRET
```

The operator puts values in the process environment or `.sandcastle/.env` and
adds the names to `SANDCASTLE_TASK_ENV_ALLOWLIST`. Sandcastle checks the label,
allowlist, and non-empty values before authorization and again before claim. It
passes only those variables to that Task sandbox. `GH_TOKEN`, `GITHUB_TOKEN`,
and `CURSOR_API_KEY` can never be Task environment entries. Secret values never
enter prompts, comments, logs, or run state.

If Sandcastle already marked the Task `agent:blocked`, apply
`agent:gates-cleared`, remove `agent:blocked`, and leave `ready-for-agent` in
place after the gate is prepared.

## Who writes to the tracker

Automation writes to the tracker. Agents do not.

An agent invoked by the pipeline produces commits and one validated JSON payload, and its prompt states this directly. Creating issues, closing issues, moving labels, opening pull requests, and posting comments are all done afterwards by the workflow, from that payload. Every irreversible write is therefore a deterministic step that can be read, replayed, and reverted.

This is what keeps a bad run cheap. An agent that misreads its scope wastes a branch; an agent holding the close button loses specifications.

## Superseding a ticket

Re-specification closes tickets rather than editing them, which keeps the original wording readable.

Close the superseded ticket as not planned, and comment with the numbers of the tickets that replace it. Carry the requirement IDs across in `requirements/registry.json` in the same commit. A ticket closed this way is archive, not lost work, and its supersession comment is the path forward from it.

## Wayfinding operations

The map is a single issue labelled `wayfinder:map`, with child issues representing tickets.

- Create maps and children through `gh`.
- Claim work with `gh issue edit <n> --add-assignee @me`.
- Resolve it by commenting with the answer and closing the issue.
