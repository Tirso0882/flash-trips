# ISSUES

Here is the explicitly authorised backlog, with its declared dependency graph:

<issues-json>

{{AUTHORIZED_ISSUES}}

</issues-json>

The host orchestrator fetched and validated this snapshot before starting you.
It includes only issues carrying both `ready-for-agent` and
`agent:implement`. The first means the ticket is specified well enough for an
agent to implement without asking a question. The second is the human's
explicit instruction to work it now. Everything below is a further filter on
that authorised list.

# TASK

Select the Tasks that can be worked right now, in parallel, without conflicting
with each other. The host has already checked external gates and Task
environment requirements. Never infer credentials from the issue text.

Select at most {{MAX_PARALLEL_ISSUES}} tickets. If more tickets are equally workable after applying the conflict rules, prefer lower issue numbers so repeated plans are deterministic.

## Refuse these outright

Drop a ticket from consideration, without reading further, if any of these hold:

- It carries the `roadmap` label. Sequencing and charter tickets are specifications to read, never work to pick up.
- It is missing either `ready-for-agent` or `agent:implement`.
- It carries `needs-info`, `ready-for-human`, `agent:in-progress`, `agent:blocked`, or `wontfix`.
- Its `subIssueCount` is greater than zero. A ticket with sub-issues is a Feature, and Features are never implemented directly. Its Tasks are the workable units.
- Its `blockersTruncated` value is true. An incomplete dependency list is not
  proof that the ticket is unblocked.

## Blocking

`blockedBy` is authoritative. This repo declares blockers as native GitHub issue dependencies, so the list you were given is the real graph and you do not need to infer it from prose. A ticket with a non-empty `blockedBy` is blocked, full stop.

Beyond that, treat a ticket as blocked if it would collide with another ticket you are already selecting this round:

- It needs code, schema, or infrastructure that another selected ticket introduces.
- It would touch the same files or modules, making concurrent work a merge conflict.
- It depends on an API shape or a decision another selected ticket establishes.

## Branch assignment

Branch names must be deterministic, so that re-planning the same ticket produces the same branch and accumulated work is preserved.

- Every Task goes on its own branch: `sandcastle/task-{number}`.

No slug, no suffix.

Independent Tasks under one Feature may be selected together. Native
`blockedBy` dependencies still control the dependency-ready frontier. If two
siblings are likely to collide in the same files or establish competing API
shapes, select the lower-numbered Task and leave the other for a later round.

# OUTPUT

Output your plan as a JSON object wrapped in `<plan>` tags:

<plan>
{"issues": [{"id": "240", "title": "[T-02] Establish the persistence foundation and the Planner record", "branch": "sandcastle/task-240"}]}
</plan>

Include only the tickets you selected. If every ticket is blocked, output the empty plan rather than forcing a choice: a blocked ticket worked early is a wasted branch, and the next round will pick it up once its blocker closes.

Always emit the `<plan>` tags, even when there is nothing to do. If there is no workable ticket at all, output `<plan>{"issues": []}</plan>` so the run can exit cleanly.

# DO NOT WRITE TO THE TRACKER

You are reading the tracker, not editing it. Do not create, close, label, or comment on anything. The orchestrator makes every tracker write from your validated plan, so that each one is deterministic and reversible.
