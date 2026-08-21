# Evaluate releases with layered, risk-weighted evidence

Flash Trips will promote changes only from versioned evaluation evidence owned by the boundary under test. It will adapt Wanderlisted's four evaluation techniques without inheriting its runners, caches, trajectories, labels, scores, or baselines. Deterministic correctness and individual critical failures take precedence over aggregate model-quality scores.

## Evaluation layers

The four complementary Evaluation Layers are:

1. **Deterministic verification** checks typed decisions, authority, schemas, Evidence, workflow, permissions, Fingerprints, costs, resumability, and artefact validity over frozen or mocked dependencies. Trajectories are evaluator inputs rather than a separate layer. Every applicable check must pass, and missing, expired, or unknown fixtures fail closed.
2. **Pointwise semantic judging** independently scores grounding, safety-boundary adherence, constraint coverage, helpfulness, and task-specific Reasoning Profile dimensions against the request and permitted Evidence. Anchored scores run from `0` for a critical violation through `3` for complete satisfaction. Grounding and safety require every case to score at least `2` and a mean of at least `2.8`; coverage and helpfulness require every case to score at least `1`, a mean of at least `2.5`, and no material Quality Baseline regression. The dimensions are never blended into one quality score.
3. **Pairwise comparison** changes exactly one factor, compares the candidate with the accepted Quality Baseline in both presentation orders, and folds order disagreement into a tie. Any critical regression blocks. With at least 30 applicable pairs, non-inferiority requires the one-sided 95% confidence bound to exclude degradation worse than five percentage points; an improvement claim requires the bound to exclude zero. Smaller runs are informative rather than release evidence.
4. **Human calibration** assesses each judge against a separate, balanced holdout of at least 30 human-labelled cases. Judge evidence becomes gate-authoritative only when quadratic-weighted Cohen's kappa is at least `0.75`, MAE is at most `0.4`, absolute bias is at most `0.2`, and no human-labelled critical violation is missed. Critical and borderline labels receive independent second review.

A judge is a pinned model stronger than and distinct from the candidate deployment where practical. It receives only the rubric, permitted case inputs, candidate output, and Evidence. If no calibrated independent judge is available, human assessment is required. Retained judge evidence contains structured scores, cited Evidence spans, and a concise decision rationale rather than hidden chain-of-thought.

## Cases, fixtures, and baselines

Evaluation Cases are owned separately by each Capability, Reasoning Profile task, integration flow, and end-to-end Trip outcome. Initial families cover conversational routing, provider validation, Plan Assembly, grounding and Travel Readiness, amendments and Approvals, interruption and resume, handbook compilation, and adversarial security. Corpora cover single- and multi-city Trips, currencies and date boundaries, accessibility and Companion Travel Constraints, provider markets, ambiguity, Evidence freshness and conflict, resource exhaustion, and external failures. Initial cases remain English-only and never infer protected or sensitive attributes.

Wanderlisted may seed scenario shapes for multi-city constraint preservation, accessibility, budget limits, missing-destination clarification, official safety and health sources, conflicting Evidence, prompt injection, provider failure, and fixed regressions. Each adapted case records provenance but derives new ground truth from Flash Trips contracts. Multilingual and venue-rental cases, booking-specific behaviour, Wanderlisted agent and tool topology, LangSmith assumptions, and existing evaluation artefacts are excluded.

Permitted Evaluation Fixtures are hand-authored synthetic fixtures, lawful sanitised provider captures, sealed Replay Bundles, and small golden Inspection Record traces. Each records provenance, schema, capture time, permitted use, expiry, and digest. A cache miss or fixture failure never authorises a live call.

Contract Baselines prove deterministic evaluator, schema, and fixture integrity without making a model-quality claim. Quality Baselines bind actual trajectories and semantic results to exact datasets, fixtures, policies, schemas, models, prompts, judges, and implementation versions. Both are reviewed, immutable, append-only, and never created automatically from a passing run. Production failures may seed only manually abstracted synthetic regressions; private Trip data, raw prompts, outputs, and provider payloads do not enter evaluation datasets.

Development, calibration, and release holdouts remain separate. Product and evaluator changes are not tuned directly against release holdouts. A holdout is refreshed after leakage, repeated exposure, material scope change, or loss of representativeness. Evaluators and rubrics require positive, negative, alternate-valid, not-applicable, malformed-input, adversarial-injection, and mutation tests.

## Failure and uncertainty

A Critical Evaluation Failure is an individual correctness, safety, grounding, authority, privacy, or execution-control violation that aggregate scores cannot offset. It includes deterministic or permission violations; unsupported externally verifiable claims; unsafe or personalised legal, immigration, or medical guidance; acceptance of stale or contradictory Evidence; incorrect Approval, Fingerprint, revision, or resume binding; privacy leakage; and unapproved live execution. Critical failures cannot be waived.

Evaluation outcomes distinguish valid `passed` and `failed` assessments from `blocked_external` provider, quota, or approved-access failures and `invalid_evaluation` judge, evaluator, fixture, schema, or evidence failures. Blocked and invalid runs do not assess product quality and cannot become baselines. A non-critical threshold exception must be time-bounded and record its cases, risk, compensating controls, owner, and expiry without changing the baseline or rubric.

Mandatory resumability cases cover interruption before and after external dispatch, matching and mismatched checkpoints, persistence outage, Approval Gate pause, expiry and supersession, duplicate command delivery, late results, SSE reconnection, linked retry, cancellation, and attempts to reopen a terminal Run. Every case verifies canonical state, cost lineage, and Inspection Records. Critical, ambiguous, and known-regression semantic cases run at least three independent repetitions; the broader corpus runs once, with variance and confidence intervals reported.

## Authorization and release

Live capture, model judging, pairwise comparison, and canaries require Paid Execution Authorization bound to the exact cases, layer, purpose, environment, model, provider and judge versions, maximum calls, tokens and spend, capture policy, retention, approver, and expiry. Mismatch or exhaustion blocks execution. Scheduled work may run unattended only inside an unexpired pre-authorized per-run and cumulative envelope and cannot renew its own authority.

Release gates are:

- Pull requests run affected deterministic suites and cross-cutting safety and security cases without live dependencies.
- Main and test run deterministic integration, migration, persistence and resume, streaming, and handbook smoke tests.
- Model, prompt, provider, rubric, or Reasoning Profile candidates run Layers 1–3 with a currently valid Layer-4 calibration. Existing evidence is reusable only under an exact matching Fingerprint.
- Production promotion requires an immutable Evaluation Release Record bound to the identical tested image digest.
- Initial invitation and provider activation additionally require the established security drills and authorized live canaries.

Affected-suite selection uses deterministic metadata linking capabilities, schemas, policies, prompts, models, providers, evaluators, and shared libraries to owned suites. Uncertain impact expands the suite rather than suppressing a gate.

The Evaluation Release Record binds the commit and image digest, affected boundaries, datasets, fixtures, Quality Baseline, evaluator, judge and rubric versions, model and prompt versions, per-case results, denominators and exclusions, uncertainty, costs, Paid Execution Authorization, critical-failure status, approver, and promotion decision.

Reviewed synthetic cases, fixtures, and Contract Baselines remain in repository history. Quality Baselines and calibration evidence remain while active plus one year after supersession; promotion evidence remains one year; raw live-capture staging remains at most 24 hours; unpromoted sanitised captures remain seven days; and production-derived Replay Bundles retain their 30-day maximum and are never promoted directly.

Logical responsibilities are Evaluation Maintainer, Domain Reviewer, Operator, Security Reviewer, and Release Approver. One person may hold multiple pilot roles, but each action remains separately recorded; independent security review remains mandatory before invitation production.

A post-promotion correctness or safety breach freezes promotion, preserves its evidence, rolls back to the last eligible digest when required, and becomes a manually abstracted synthetic regression case. The Quality Baseline changes only after the defect is fixed and the complete affected gate passes.
