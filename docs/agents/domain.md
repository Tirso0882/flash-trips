# Domain Docs

This repository uses a single-context domain-documentation layout.

## Before exploring, read these

- `CONTEXT.md` at the repository root.
- Relevant decisions under `docs/adr/`.

If either is absent, proceed silently. Domain-modelling skills create documentation lazily when decisions or terminology are resolved.

## File structure

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-build-flash-trips-as-a-greenfield-product.md
│   └── 0002-separate-model-proposals-from-deterministic-authority.md
└── src/
```

## Use the glossary's vocabulary

Use concepts as defined in `CONTEXT.md`. Avoid synonyms that the glossary explicitly rejects.

If a necessary concept is missing, reconsider whether it belongs or note the gap for domain modelling.

## Flag ADR conflicts

Explicitly surface any proposal that contradicts an existing ADR instead of silently overriding the decision.
