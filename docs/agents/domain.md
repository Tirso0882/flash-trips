# Domain Docs

This repository uses a single-context domain-documentation layout.

## Before exploring, read these

- `CONTEXT.md` at the repository root.
- `docs/adr/README.md`, then only the ADRs it identifies as relevant.

Do not scan every ADR by default. Read the whole directory only when the task explicitly requires a review across all architecture decisions.

If any document is absent, proceed silently. Domain-modelling skills create documentation lazily when decisions or terminology are resolved.

## File structure

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── README.md
│   ├── 0001-build-flash-trips-as-a-greenfield-product.md
│   └── 0002-separate-model-proposals-from-deterministic-authority.md
└── src/
```

## Use the glossary's vocabulary

Use concepts as defined in `CONTEXT.md`. Avoid synonyms that the glossary explicitly rejects.

If a necessary concept is missing, reconsider whether it belongs or note the gap for domain modelling.

## Flag ADR conflicts

Explicitly surface any proposal that contradicts an existing ADR instead of silently overriding the decision.
