# TASK

Merge the following reviewed Task commits into the current Feature integration
branch:

{{BRANCHES}}

They correspond to these issues:

{{ISSUES}}

The Task branch names are context only. The pinned commit SHAs are
authoritative. Several commits can belong to independent Tasks under one
Feature.
For each entry, in order:

1. Run `git merge <pinned-sha> --no-edit`
2. If there are conflicts, resolve them by reading both sides and choosing the correct resolution. See the conflict rules below.
3. Run `just verify` to confirm the merged state works.
4. If it fails, fix it before moving to the next branch.

Never merge the mutable branch name or move a source branch ref. The
orchestrator independently checks that every pinned SHA is present.

# CONFLICT RULES SPECIFIC TO THIS REPO

For each conflict, inspect the conflicting files, both source commits, their
commit messages, and the supplied issue context before editing. Preserve both
intents where they are compatible. Where they are not, choose the resolution
that satisfies the reviewed issues without inventing new behavior.

Three kinds of conflict here have a right answer that is not "read both sides and pick."

**Anything under `contracts/`** is generated from the Pydantic models. Never hand-resolve it. Take either side to clear the conflict, then run `just contracts` and commit whatever it produces. `just check` runs a staleness check that will catch you if you skip this.

**Alembic migrations** must keep one linear history. After merging anything that touched `src/flash_trips/adapters/postgres/migrations/`, run `uv run alembic heads`. If it reports more than one head, do not merge them with a merge revision: repoint the later revision's `down_revision` at the other head so the history stays linear, and renumber nothing else.

**`requirements/registry.json`** is reconciled against `requirements/coverage.md` by `pnpm traceability`, which runs inside `just lint`. On a conflict, union the entries from both sides rather than picking one, then let the traceability check tell you whether the result is consistent.

For everything else, if you cannot resolve a conflict confidently, abort that one branch with `git merge --abort`, leave the rest merged, and report which branch you skipped and why. A skipped branch is retried next round. A wrongly resolved merge is not.

# FINISH

Run `just check` once after all merges are done. It is the pre-commit gate and it catches what `just verify` does not: the security audit and the generated-contracts staleness check.

Do not create an extra summary commit. Each successful `git merge --no-edit`
already records the merge when one is needed, and a fast-forward already
carries the source commits.

# DO NOT WRITE TO THE TRACKER

Do not close issues, move labels, publish branches, or comment. The orchestrator
publishes the verified Feature branch and closes each Task only after it
validates the remote tree and pull request.

In your final message, state plainly which branches merged and which you skipped, so the skipped ones are not mistaken for done.

Once you've merged everything you can, output <promise>COMPLETE</promise>.
