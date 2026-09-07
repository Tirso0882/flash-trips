# Sandcastle AFK reliability review

Date reviewed: 2026-09-06

## Scope and source snapshots

This review compares the local orchestration in `.sandcastle/main.mts` and
`.sandcastle/*.md` with:

- `mattpocock/sandcastle` at
  [`e99f832f26dc9d245c019a9ddd19fa5dee792427`](https://github.com/mattpocock/sandcastle/tree/e99f832f26dc9d245c019a9ddd19fa5dee792427).
  This is the source for Sandcastle 0.12.0, the version declared by this
  repository.
- `mattpocock/course-video-manager` at
  [`3db4a824d958045f9aca10ea98081fe3af1181ae`](https://github.com/mattpocock/course-video-manager/tree/3db4a824d958045f9aca10ea98081fe3af1181ae),
  specifically its `.sandcastle/` directory.

Only source code, repository documentation, ADRs, templates, and tests from
those two repositories were used.

## Executive conclusion

The local orchestration should remain the base. It is already safer for
unattended issue work than either example:

- The planner sees only issues carrying both `ready-for-agent` and
  `agent:implement`, while the source examples broadly inspect open work
  ([official prompt](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/templates/parallel-planner-with-review/plan-prompt.md#L1-L36),
  [course prompt](https://github.com/mattpocock/course-video-manager/blob/3db4a824d958045f9aca10ea98081fe3af1181ae/.sandcastle/plan-prompt.md#L1-L34)).
- The plan is schema-validated, duplicate-checked, branch-format-checked, and
  capped at three issues in `.sandcastle/main.mts:54-93`. The course example
  extracts JSON with a regular expression and unchecked cast
  ([course main](https://github.com/mattpocock/course-video-manager/blob/3db4a824d958045f9aca10ea98081fe3af1181ae/.sandcastle/main.ts#L12-L26)).
- Claims are revalidated immediately before execution in
  `.sandcastle/main.mts:219-259`, and queued issues are promoted only when
  their declared blockers are closed in `.sandcastle/main.mts:261-295`.
- Each issue gets one shared sandbox for implementation and review, every
  pipeline closes it in `finally`, and `Promise.allSettled` isolates failures
  in `.sandcastle/main.mts:377-455`. This follows the official reviewed
  parallel template
  ([official template](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/templates/parallel-planner-with-review/main.mts#L104-L169)).
- Review is a real merge gate. The local reviewer must emit one validated
  `approved` or `blocked` verdict in `.sandcastle/main.mts:95-119`, and blocked
  work is excluded from the merger in `.sandcastle/main.mts:419-434`. Neither
  source example parses a blocking review verdict.
- Tracker writes are owned by deterministic orchestration, not agents. The
  source prompts let agents comment on or close issues
  ([official implement prompt](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/templates/parallel-planner-with-review/implement-prompt.md#L42-L48),
  [official merge prompt](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/templates/parallel-planner-with-review/merge-prompt.md#L16-L23),
  [course merge prompt](https://github.com/mattpocock/course-video-manager/blob/3db4a824d958045f9aca10ea98081fe3af1181ae/.sandcastle/merge-prompt.md#L15-L22)).
- The local merger creates no artificial summary commit, runs `just verify`
  after each branch, runs `just check` once at the end, and the orchestrator
  closes only branches proven to be ancestors of `HEAD` in
  `.sandcastle/main.mts:514-566`. Both source merge prompts request an extra
  summary commit.

The remaining reliability gaps are around interruption and recovery, not the
core planning policy.

## Detailed comparison

### Orchestration and iteration strategy

All three designs use a plan, parallel execution, and merge loop. The official
reviewed template uses ten outer cycles, an unrestricted planner result, up to
100 Claude iterations per implementer, one reviewer iteration, and one merger
iteration
([official template](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/templates/parallel-planner-with-review/main.mts#L41-L50),
[implementation and review](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/templates/parallel-planner-with-review/main.mts#L123-L145)).
The course manager uses ten outer cycles, a semaphore capped at four issue
pipelines, and a merger allowed ten iterations
([course main](https://github.com/mattpocock/course-video-manager/blob/3db4a824d958045f9aca10ea98081fe3af1181ae/.sandcastle/main.ts#L4-L8),
[semaphore](https://github.com/mattpocock/course-video-manager/blob/3db4a824d958045f9aca10ea98081fe3af1181ae/.sandcastle/main.ts#L41-L58),
[merger](https://github.com/mattpocock/course-video-manager/blob/3db4a824d958045f9aca10ea98081fe3af1181ae/.sandcastle/main.ts#L140-L153)).

The local ten-round limit and three-issue plan cap are stronger. Because the
schema itself caps the plan, `Promise.allSettled` cannot create more than three
issue pipelines. A second semaphore would add no protection unless issue
pipelines can enter the map from another source. Keeping every Cursor call at
one iteration also matches current Sandcastle semantics: one iteration is the
default, structured output is restricted to one iteration, and resumption
cannot be combined with multiple iterations
([run options](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/run.ts#L330-L428),
[validation](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/run.ts#L532-L557)).

### Prompts and authority

The local prompts are materially better suited to this repository:

- Planning uses native GitHub blockers, refuses Features and unsafe labels,
  chooses deterministic lower issue numbers, and allows an empty plan instead
  of forcing blocked work (`.sandcastle/plan-prompt.md:15-59`). Both source
  planning prompts instruct the planner to choose a blocked candidate when
  everything is blocked
  ([official](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/templates/parallel-planner-with-review/plan-prompt.md#L27-L36),
  [course](https://github.com/mattpocock/course-video-manager/blob/3db4a824d958045f9aca10ea98081fe3af1181ae/.sandcastle/plan-prompt.md#L28-L34)).
- Implementation reads the Task, parent Feature, cited ADRs, and relevant
  domain terms before touching code. It requires criteria, seams, tests, and
  touches, and directs the agent through `just verify` and `just check`
  (`.sandcastle/implement-prompt.md:8-89`). The source prompts provide only
  generic issue, test, and commit guidance
  ([official](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/templates/parallel-planner-with-review/implement-prompt.md#L1-L53),
  [course](https://github.com/mattpocock/course-video-manager/blob/3db4a824d958045f9aca10ea98081fe3af1181ae/.sandcastle/implement-prompt.md#L1-L54)).
- Review checks the issue and repository architecture, may fix only in-scope
  problems, requires `just check`, and emits a blocking verdict
  (`.sandcastle/review-prompt.md:1-82`). The source reviews can improve code
  but always return normal completion, so orchestration treats any commits
  from the implementer as mergeable
  ([official review prompt](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/templates/parallel-planner-with-review/review-prompt.md#L1-L61),
  [official orchestration](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/templates/parallel-planner-with-review/main.mts#L136-L183)).

Sandcastle expands prompt shell expressions concurrently, caps each at 30
seconds, and fails the prompt on timeout or non-zero exit rather than handing
the agent incomplete context
([preprocessor](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/PromptPreprocessor.ts#L33-L79),
[ADR 0020](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/docs/adr/0020-prompt-expansion-fails-fast.md#L22-L47)).
That makes the local planner's embedded GitHub query fail closed, which is the
right AFK behavior.

### Sandbox lifecycle

The local implementation correctly uses `createSandbox` when two agents need
the same branch and sandbox. Sandcastle creates or reuses the named worktree,
starts the provider, runs ready hooks, and removes the newly created worktree
if setup fails
([createSandbox setup](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/createSandbox.ts#L900-L1058)).
The local `just install` sandbox hook plus copied pnpm stores follows the
official copy-then-install pattern, while accounting for this repository's
Python and pnpm toolchains.

On close, Sandcastle removes a clean worktree but preserves a dirty one and
returns its path
([createSandbox close](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/createSandbox.ts#L1070-L1106)).
The general `run()` lifecycle likewise attaches preserved paths to agent and
idle-timeout errors
([cleanup](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/SandboxFactory.ts#L190-L249)).
The local `finally { await sandbox.close(); }` guarantees teardown, but discards
the returned path. This loses the best recovery pointer when an agent leaves
useful uncommitted work.

The course manager's `await using sandbox` is concise
([course main](https://github.com/mattpocock/course-video-manager/blob/3db4a824d958045f9aca10ea98081fe3af1181ae/.sandcastle/main.ts#L59-L70)),
but it is not safer than the local explicit `try/finally`. The explicit form is
easier to extend so the close result can be recorded.

### Error handling and observability

The local `Promise.allSettled` usage is the most important source pattern
already adopted: one failed issue does not cancel sibling work. Local tracker
writes also degrade to warnings, while inability to claim an issue fails that
issue closed.

Sandcastle 0.12 supplies several lower-level protections without local code:

- default ten-minute no-output timeout;
- one-minute grace after a completion signal, after which a hanging child
  process is force-completed successfully so committed work can still be
  collected;
- cancellation through `AbortSignal`;
- explicit timeouts for worktree copies, git setup, commit collection, and
  merge-to-host lifecycle work
  ([run options](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/run.ts#L320-L410),
  [orchestrator defaults](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/Orchestrator.ts#L245-L325),
  [completion-timeout rationale](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/docs/adr/0019-completion-timeout-for-hanging-process.md#L1-L15)).

The local code currently relies on those defaults and has no whole-run
deadline. Ten rounds bound calls, not elapsed time.

Default file logging is already enabled by Sandcastle. Run names form part of
the log filename
([logging and filename behavior](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/run.ts#L92-L147),
[logging option](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/run.ts#L215-L257)).
Local issue run names include issue IDs, but planner and merger names repeat
across rounds, making AFK diagnosis less direct.

### Structured-output recovery

The course repository contains tested helpers that split side-effecting work
from structured-output extraction and retry malformed output by resuming the
same Claude session
([run-with-extraction](https://github.com/mattpocock/course-video-manager/blob/3db4a824d958045f9aca10ea98081fe3af1181ae/.sandcastle/run-with-extraction.ts#L30-L58),
[run-with-retry](https://github.com/mattpocock/course-video-manager/blob/3db4a824d958045f9aca10ea98081fe3af1181ae/.sandcastle/run-with-retry.ts#L24-L45),
[tests](https://github.com/mattpocock/course-video-manager/blob/3db4a824d958045f9aca10ea98081fe3af1181ae/.sandcastle/run-with-extraction.test.ts#L72-L178)).
They are utilities, not part of the course repository's active `main.ts`
orchestration.

Sandcastle 0.12 now has built-in `Output.*({ maxRetries })` support using the
same resume-and-correct pattern
([Output API](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/Output.ts#L5-L43),
[retry implementation](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/run.ts#L840-L889)).
It is not applicable to this local policy. The Cursor provider explicitly has
no filesystem-backed session storage and is non-resumable
([Cursor provider](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/AgentProvider.ts#L827-L873));
Sandcastle rejects output retries for providers without session storage
([validation](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/run.ts#L559-L576)).
The current one-iteration Cursor choice should remain.

### Merge behavior and partial failure

The local merge prompt is stronger than both examples because it defines
repository-specific conflict rules, verifies after every branch, runs the full
gate once, does not create an extra commit, and never edits the tracker
(`.sandcastle/merge-prompt.md:1-42`).

There is one concrete correctness gap. If the merge agent successfully merges
one branch and then the Sandcastle run throws while processing a later branch,
the catch block at `.sandcastle/main.mts:530-541` marks every completed issue
`agent:blocked` without checking which branches already landed. The normal
success path does perform that ancestry check at
`.sandcastle/main.mts:545-566`. A partially successful merge can therefore
leave merged code on the target branch while its issue remains open and
blocked.

Sandcastle's own merge-to-host lifecycle preserves the source branch when a
merge fails and collects commits from repository state after a successful
merge
([lifecycle](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/SandboxLifecycle.ts#L404-L509)).
The same fact-based reconciliation principle should be applied on both local
merge success and merge failure.

### Concurrent and interrupted AFK runs

The local plan cap controls fan-out within one process. It does not prevent two
separate Sandcastle processes from planning at the same time. Claims reduce
the window, but validation and label mutation are separate GitHub operations,
so two processes can both validate an issue before either label update becomes
visible.

The official worktree-locking ADR specifies an atomic lock file, PID-based
stale detection, fail-fast contention, and cleanup on close or process exit
([ADR 0007](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/docs/adr/0007-worktree-locking.md#L10-L47)).
However, the 0.12.0 `WorktreeManager` source in the reviewed snapshot does not
implement that lock. It reuses an existing managed worktree, including a dirty
one
([current implementation](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/WorktreeManager.ts#L277-L350)).
The local workflow must not assume named-branch worktrees are process-locked.

Sandcastle registers shared `SIGINT`, `SIGTERM`, and `exit` handlers so every
live sandbox can print worktree recovery guidance without adding one listener
per sandbox
([shutdown registry](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/shutdownRegistry.ts#L1-L83),
[createSandbox registration](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/createSandbox.ts#L1070-L1081)).
Those handlers cannot repair GitHub labels. A process killed after
`claimIssue()` can leave `agent:in-progress` indefinitely, and the planner
correctly refuses to select it on the next run.

## Recommended adaptations

### Priority 0: reconcile merges in one shared function

After the merger returns or throws, inspect every attempted branch with
`branchLanded`:

- close and clear pipeline labels for every branch already in `HEAD`;
- comment and set `agent:blocked` only for branches that did not land;
- include the merge error only on branches that remain unmerged.

This fixes a real partial-success inconsistency without changing models,
rounds, review policy, merge style, or issue authorization.

### Priority 0: add durable claim recovery

Persist a small round manifest before or immediately after each successful
claim. It should contain the target branch and starting SHA, round, issue ID,
issue branch, and state transitions. On startup, reconcile unfinished entries
from facts:

- branch is an ancestor of target: close and clear labels;
- branch has commits but did not land: preserve it and set `agent:blocked`;
- branch has a dirty preserved worktree: set `agent:blocked` and report its
  path;
- no branch work exists: return it to `agent:implement`, but only after
  re-running the same strict authorization checks.

This closes the SIGTERM, host reboot, and Node crash gap. It also preserves the
current policy that automation, not agents, owns tracker writes.

### Priority 1: add a process-wide orchestration lock

Acquire one atomic host lock before planning, with PID and start time, and
release it in a top-level `finally`. Fail fast when a live owner exists and
remove only demonstrably stale locks. This applies the sound pattern from ADR
0007 at the level that matters for strict claims. Do not rely on Sandcastle
0.12.0 to lock a reused named worktree.

### Priority 1: make time budgets explicit

Define and pass explicit `idleTimeoutSeconds`,
`completionTimeoutSeconds`, and lifecycle `timeouts` to all runs and
`createSandbox` calls. Add a configurable whole-run `AbortSignal` deadline.
The outer ten-round cap should remain. These are complementary limits: rounds
bound work selection, while timeouts bound wall-clock hangs. Record timeout
reasons through the existing blocked-label path.

### Priority 1: preserve recovery diagnostics

Capture `await sandbox.close()` and propagate `preservedWorktreePath` into the
pipeline result and issue comment. On thrown agent and idle-timeout errors,
also inspect the error's preserved path when present. Never delete dirty work
automatically.

Use round-specific run names such as `planner-round-3` and
`merger-round-3`; keep issue-specific implementer and reviewer names. This
makes the existing file logs unambiguous.

### Priority 1: preflight target safety

Before any claim:

- require the target branch name and SHA to be recorded;
- refuse a dirty target working tree, because Docker's default bind-mount
  strategy is `head`, which operates on the current host checkout
  ([branch default](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/run.ts#L500-L513));
- check GitHub CLI authentication and Docker availability;
- immediately before merge, verify that the current branch is still the
  recorded target. If its SHA moved, allow the merge agent to work from the
  new tip only when the branch name is unchanged and log the movement.

This prevents an AFK run from merging into a checkout that an operator changed
mid-run.

### Priority 2: test orchestration decisions

Extract and unit-test the pure parts of:

- review parsing;
- plan duplicate and branch validation;
- outcome-to-label classification;
- partial merge reconciliation;
- startup recovery from each manifest state.

The course repository's retry helpers are accompanied by focused tests for
missing tags, malformed output, exhausted attempts, non-retryable errors, and
missing sessions. The useful pattern is testing the orchestration state
machine, not adopting its Claude-specific retry implementation.

## Patterns explicitly rejected

- **Do not increase Cursor iterations.** Reject the official template's 100
  implementation iterations and the course merger's ten iterations. Preserve
  one Cursor iteration per planner, implementer, reviewer, and merger call.
- **Do not adopt session-resumed output retries.** Cursor is non-resumable in
  Sandcastle 0.12.0. The course retry wrappers and `Output.maxRetries` are for
  providers with captured session storage.
- **Do not force blocked work into a plan.** Both source planner prompts do
  this. Preserve the local empty plan and let dependency promotion make work
  eligible in a later round.
- **Do not broaden issue selection.** Preserve the dual
  `ready-for-agent` plus `agent:implement` authorization, native blocker
  checks, Feature refusal, strict claim, and queued promotion.
- **Do not replace schema validation with regex plus `JSON.parse`.** The
  course main has no shape, duplicate, branch, or fan-out validation.
- **Do not treat a review run as approval merely because it returned.**
  Preserve the independent Claude Opus reviewer and its blocking structured
  verdict.
- **Do not let agents mutate the tracker.** Source prompts comment, close, or
  infer parent closure. Preserve commit-only agents and deterministic tracker
  reconciliation.
- **Do not add a second in-process semaphore.** The validated plan already
  caps pipelines at three. Add a process-wide lock for cross-process safety
  instead.
- **Do not move dependency installation to a host-only hook.** Keep
  `just install` in the sandbox and the copied pnpm directories as a speed
  optimization. The sandbox must be able to restore platform-specific
  dependencies itself.
- **Do not create an extra merge summary commit.** Preserve normal merge or
  fast-forward history and the existing `just verify` and `just check` gates.
- **Do not silently retry or degrade failed prompt expansion.** Missing issue
  context must abort before an agent acts. The official source intentionally
  fails this stage closed.
- **Do not assume Sandcastle 0.12.0 locks reused named worktrees.** Its ADR
  describes a lock, but the reviewed implementation reuses them without one.

## Recommended order

1. Fix partial-merge reconciliation.
2. Add the durable claim manifest and startup recovery.
3. Add the process-wide lock and target preflight.
4. Make time budgets explicit and retain preserved-worktree paths.
5. Add focused orchestration tests and round-specific log names.

These changes improve unattended recovery without changing the local planner
filters, queued promotion, strict claims, three-issue cap, ten rounds, model
assignments, blocking review, one-iteration Cursor policy, merge history, or
verification commands.

## Adapted in this repository

The implementation following this review adopted the applicable safeguards:

- a clean-checkout, named-branch, host GitHub permission, required-label,
  Cursor credential, Docker daemon, and Docker image preflight;
- an atomic process lock with stale-PID recovery;
- an atomic active-claim manifest with startup reconciliation after interruption
  or host restart;
- strict claim checks for title, labels, issue shape, open blockers, and the
  deterministic Feature branch;
- explicit whole-run, phase, idle, completion, hook, copy, git, commit
  collection, and merge time limits;
- dirty reused-worktree refusal and preserved-worktree diagnostics;
- implementer completion-signal and reviewer-cleanliness gates;
- host-fetched, validated tracker snapshots injected into prompts, with
  `GH_TOKEN` cleared in every agent container;
- isolated planner and integration worktrees instead of agent access to the
  host checkout;
- pinned reviewed commit SHAs, an orchestrator-run `just check`, and a
  race-checked host fast-forward;
- fact-based issue reconciliation after both successful and failed merge runs;
- round-specific planner and merger logs;
- focused tests for plan, review-output, and reserved prompt argument
  validation;
- an exact Sandcastle 0.12.0 dependency pin.

The Claude-specific resumed retry helpers were not adopted because Cursor
sessions are non-resumable. The existing one-iteration policy remains.
