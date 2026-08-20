# Revise plans through validated amendments

Planners will change a Travel Plan through typed Plan Amendments that produce identifiable Plan Revisions, rather than directly overwriting generated output. A model-extracted Amendment Proposal remains untrusted until the Planner confirms its typed change and impact. This adds revision and dependency-management complexity, but preserves provenance, enables selective recomputation, and prevents conversational edits from silently invalidating dates, prices, Evidence, approvals, or schedules.

## Consequences

Each plan-changing Run is bound to one base revision and may atomically commit at most one new immutable revision after all required validation and approvals succeed. Run-local and partial results remain inspectable execution artefacts, never canonical Travel Plan state, and the previous revision remains current while work is incomplete. Concurrent mutations fail through optimistic revision checks rather than implicit merging.

Evidence and old revisions remain immutable when inputs, freshness, or policies change. Deterministic dependency analysis instead derives `Revalidation Required`, supersedes affected approvals, and prevents new handbook generation until a linked Run refreshes the invalidated outputs. Terminal Runs never reopen; manual continuation or retry creates a linked Run and may reuse only outputs whose complete fingerprints still match.
