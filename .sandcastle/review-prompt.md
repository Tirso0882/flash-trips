# TASK

Review issue {{TASK_ID}}: {{ISSUE_TITLE}}

The implementation is on branch `{{BRANCH}}`. Gate it against the ticket, the repository's standards, and the architecture. Fix clear problems directly when they stay within the ticket's scope.

# CONTEXT

## Issue

The host orchestrator fetched this Task, its comments, and its parent Feature
before starting the sandbox:

<issue-context>

{{ISSUE_CONTEXT}}

</issue-context>

## Branch diff

!`git diff {{TARGET_BRANCH}}...{{BRANCH}}`

## Commits on this branch

!`git log {{TARGET_BRANCH}}..{{BRANCH}} --oneline`

# REVIEW PROCESS

1. **Understand the change**: Read the supplied issue context, diff, and commits
   above. Pin `{{TARGET_BRANCH}}` as the fixed point for the whole review.

2. **Run two independent review axes**: Run them in parallel if subagents are
   available. Otherwise make two separate passes. Keep their findings separate
   so a pass on one axis cannot mask a failure on the other.

   **Standards axis**

   Apply @.sandcastle/CODING_STANDARDS.md and the architecture rules below.
   Record every documented-standard breach by file and hunk and cite the rule.
   Also check the smell baseline below. Smells are judgement calls, not hard
   violations, and a documented repository standard always wins. Skip facts
   that tooling conclusively enforces.

   - Mysterious Name: a name does not reveal what it does or holds. Rename it.
   - Duplicated Code: the same logic shape appears more than once. Extract the
     shared shape.
   - Feature Envy: code reaches into another object's data more than its own.
     Move the behavior toward that data.
   - Data Clumps: the same fields or parameters repeatedly travel together.
     Bundle the domain concept.
   - Primitive Obsession: a primitive stands in for a domain concept. Give the
     concept a focused type.
   - Repeated Switches: the same conditional dispatch recurs. Centralize it.
   - Shotgun Surgery: one logical change requires scattered edits. Gather what
     changes together.
   - Divergent Change: one module changes for unrelated reasons. Separate the
     responsibilities.
   - Speculative Generality: an abstraction serves no current requirement.
     Remove or inline it.
   - Message Chains: a caller navigates a long object chain. Hide the walk
     behind the owning interface.
   - Middle Man: a layer mainly delegates without adding value. Call the real
     target directly.
   - Refused Bequest: an implementation ignores most of what it inherits. Use
     composition instead.

   **Spec axis**

   For every finding, quote the relevant ticket criterion. Check for:

   - requirements that are missing or only partially implemented
   - behavior the ticket did not request
   - requirements that look implemented but behave incorrectly
   - changed behavior without a test through the ticket's named Seam

3. **Check cross-cutting risks**:
   - Look for unhandled edge cases, injection vulnerabilities, credential
     leaks, and unsafe casts or silencing comments.
   - Anything under `contracts/` is generated. If the API surface changed, run
     `just contracts` and commit the generated result.
   - Reject capability imports of sibling capabilities, adapters,
     `composition`, or another module's `_implementation`.
   - Keep deterministic authority in application code. Validate model output
     before it affects facts, money, permissions, safety, or state.
   - Keep errors as non-disclosing RFC 9457 problems and tests off the network.
   - Match `CONTEXT.md` vocabulary, including its `_Avoid_` terms.

4. **Preserve scope and clarity**: Fix ticket-scoped findings from either axis.
   Do not add unrelated cleanup, over-simplify useful abstractions, or make code
   more compact at the cost of clarity.

# EXECUTION

If you find improvements to make:

1. Make the changes directly on this branch
2. Use `just verify` while iterating
3. Run `just check` as the final gate
4. Commit the refinements, matching the log's style: a short imperative sentence-case summary referencing issue {{TASK_ID}}

If the code is already clean and well-structured, do nothing. A no-op review is a fine outcome and better than churn.

Approve only if the implementation satisfies the ticket and `just check` passes. Block it if a correctness, security, architecture, test coverage, or verification problem remains unresolved. Cosmetic preferences alone are not blockers.

# DO NOT WRITE TO THE TRACKER

Produce commits, nothing else. Do not close the issue, comment on it, move a label, or open a pull request. The orchestrator handles every tracker write afterwards.

If you found a problem you could not fix, leave it in your commit body when you made a commit.

# OUTPUT

End with exactly one JSON object wrapped in `<review>` tags:

<review>
{"verdict":"approved","summary":"The implementation satisfies the ticket and just check passes."}
</review>

Use `"blocked"` when any merge-blocking problem remains, and state the concrete reason in `summary`. Always emit the tags, including after a no-op review.
