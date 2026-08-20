# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply/remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v`; `gh` does this automatically inside the repository.

## Pull requests as a triage surface

**PRs as a request surface: no.**

When enabled, PRs use the equivalent `gh pr` operations and the same triage labels.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Wayfinding operations

The map is a single issue labelled `wayfinder:map`, with child issues representing tickets.

- Create maps and children through `gh`.
- Prefer GitHub sub-issues and native issue dependencies.
- Fall back to task lists and `Blocked by: #<n>` when those features are unavailable.
- Claim work with `gh issue edit <n> --add-assignee @me`.
- Resolve it by commenting with the answer and closing the issue.
