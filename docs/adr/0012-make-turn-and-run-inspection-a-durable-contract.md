# Make Turn and Run inspection a durable contract

Flash Trips will make inspection an append-only, typed application contract rather than treating logs, LangGraph state, or vendor telemetry as the explanation of what happened. Every Turn has Inspection Records whether or not it starts a Run; a Turn may reference an existing Run or cause at most one new Run. Every Run has enough records to reconstruct its compiled DAG, decisions, attempts, Evidence, validation, approvals, resource use, progress, and exactly one terminal outcome.

`RunInspector` is read-only with respect to canonical Trip state but owns the inspection boundary. Authoritative modules emit typed facts through its validated sink instead of writing trace storage directly. RunInspector validates, orders, persists, projects, reconstructs, and replays those facts without inventing domain decisions. Its transport-neutral read port exposes Turn and Run summaries, ordered timelines, compiled DAGs, decision families, costs, reconstruction, replay eligibility, and replay differences; later application-interface decisions own HTTP and streaming transports.

## Inspection records and integrity

Inspection Records form one logical contract even if Turn records, Run records, Replay Bundles, and operational projections use different physical storage or retention. Each immutable record has a schema version, opaque record identifier, subject references, a closed record kind, typed correlation and causation references, an authoritative subject-local sequence, observed and persisted times, producing component and version, sensitivity classification, and an integrity digest. Explicit relationships such as `caused`, `references`, `responds_to`, `approves`, `cancels`, `retries`, and `replays` form a causality graph; timestamps never imply causation.

Subject-local sequence and declared dependency edges are authoritative for ordering. UTC timestamps explain wall-clock time and monotonic durations measure latency. Concurrent capabilities retain their separate sequences and causality instead of being forced into a false total order. Identical appends under one deterministic record identifier are idempotent; different content under the same identifier is an integrity failure that blocks state-changing progress.

Every durable pause closes a verifiable segment with a manifest binding its ordered records. The terminal record seals all decision-affecting segments and binds the final outcome; exactly one terminal outcome exists. A result that arrives after cancellation, supersession, or termination is recorded only in a marked post-terminal diagnostic segment with disposition `discarded_late`. It cannot satisfy dependencies, enter Plan Assembly, receive more than safe decoding, or change reconstruction, Approval, or canonical state.

Historical record payloads are never rewritten or reinterpreted. Readers retain support or deterministic adapters for persisted major schema versions, and an unsupported version produces a typed inspection limitation. A semantic correction appends a record referencing the original and its reason. Legally required erasure and compromised-secret removal remain separate security operations.

Fingerprints and integrity digests have separate purposes. Fingerprints deterministically bind the exact inputs, dependencies, Evidence, policies, schemas, and implementation versions governing reuse, decisions, and Approvals. Integrity digests establish record or payload identity. Sensitive payloads use protected keyed digests to resist guessing, while audience views expose opaque references rather than raw Fingerprints or digests.

## Required record families

The closed, schema-versioned record union covers:

- **Turn routing:** Conversation Scope and visible revision references, principal class, input schema and protected digest, structured or client action reference, deterministic protocol decisions, classifier attempt when used, primary and secondary categories, uncertainty, selected handler, Evidence references, typed outcome, Pending Clarification, and related Runs. Unrestricted conversation text is not retained.
- **Run compilation:** compiler and registry versions; Trip Request, base Plan Revision, Evidence, and policy Fingerprints; aggregate resource limits; every considered Capability; included nodes; typed dependency edges; Approval Gates; inclusion and exclusion reason codes; and the compiled DAG Fingerprint. Diagrams are derived views, not records of authority.
- **Workflow decisions:** one explicit decision for each considered Capability, including the rule and version, dependency Fingerprints, evaluated result, reason code, component-level reuse comparison, invalidation propagation, and resulting execute, skip, reuse, repair, or block action. An absent attempt never implies a decision.
- **Evidence decisions:** each bounded Provider Observation admitted to capability evaluation, its source identity and digest, scope and observation time, Evidence-policy version, deterministic checks, freshness, contradiction links, and accepted Evidence reference or rejection code. Transport noise that never becomes a valid Provider Observation remains in the provider attempt.
- **Validation:** the ordered applicable schema, domain-invariant, and cross-capability completion validators, with identifier, kind, version, input Fingerprint, verdict, typed findings, dependency references, and timing. `Succeeded` requires the complete applicable chain to pass.
- **Attempts and resources:** deterministic execution and attempt identifiers, a protected idempotency-key reference, Capability and execution policy, provider or model and applicable adapter, prompt, and reasoning-profile versions, request and response digests, safe parameters, timing, retries, fallback position, usage, billable units, quota information, exact-decimal cost and currency, cancellation or late-result disposition, and typed outcome or error. Chain-of-thought is never recorded.
- **Approval and execution progress:** why an Approval Gate was inserted; the exact Approval Request binding and lifecycle; decision, expiry, or supersession; and resume-context comparisons. Execution Checkpoints expose only identity, schema and version, integrity reference, progress position, and resume decision, never raw private LangGraph state.
- **Errors and outcomes:** stable classification and reason code, origin, retryability, safe recovery actions, related attempt or decision, and either a canonical commit reference or an explicit no-commit reason. Raw stack traces remain restricted operational telemetry.
- **Plan Assembly:** every attempted Plan Portfolio Fingerprint, objective, conflicts, rejected alternatives, repair proposal, before-and-after objective, strict-improvement verdict, search expansion, and exhaustion reason. The records prove that no portfolio repeated and no closest invalid portfolio committed.

A retry is a new attempt bound to the original input Fingerprint and its allowlisted transient failure. A fallback is a new attempt that also records declared order and deterministic policy equivalence before execution. Reuse records the source result, component-by-component Fingerprint equality, current Evidence and policy applicability, and current completion validation; it creates no provider or model attempt. Invalidation records its trigger, old and new Fingerprints, traversed dependency edges, affected outputs and Approvals, handbook or delivery consequences, and resulting action without rewriting history.

Attempt-level resource usage records the pricing source and version and marks monetary cost `estimated`, `final`, or `unknown`. Aggregates preserve unknown values rather than treating them as zero, and corrections append records. The model-routing and external-cost decision owns ceilings and reporting-currency policy.

## Durability, redaction, and views

The minimum Inspection Record must be durable before any Turn performs a model or provider call, and required result disposition must be durable before downstream use. If inspection persistence is unavailable, read-only Turns return a typed temporary-unavailable outcome and state-changing work cannot commit. If a result is received but cannot be recorded, it is not consumed; the Run waits for recovery or ends `failed` when that failure can be persisted. Reconciliation resolves abandoned started attempts without silently repeating non-idempotent work. Malformed, unsafe, or missing required records are `inspection_contract_violation` and prevent a successful outcome.

Production records retain only allowlisted identifiers, versions, decisions, reason codes, summaries, and protected digests. They exclude secrets, unnecessary personal data, unrestricted prompts, raw conversation, raw provider or model payloads, and chain-of-thought. Prohibited content is removed before persistence; audience projections apply an additional reduction. Redaction rules, sensitivity labels, and unknown-field behaviour are part of the conformance contract.

Server-side authorisation chooses the projection before records are fetched; callers cannot request a more privileged view, and unauthorized identifiers are indistinguishable from nonexistent identifiers. The initial views are:

- A Planner may inspect safe lifecycle state, product-facing capability progress, required action, limitations or failure explanations, applicable Evidence attribution, and recovery options for their own Trip. Internal nodes, undisclosed providers or models, prompts, validator internals, Fingerprints, quotas, and costs remain hidden.
- An Operator receives aggregate service health and opaque Run references without private Trip content.
- A developer receives complete synthetic or non-production traces; production access defaults to the Operator view.
- Evaluators and tests receive synthetic fixtures and schema-versioned redacted exports, not production records by default.

Planner-facing status and explanations use deterministic templates over typed records. A later model may improve explicitly non-authoritative wording, but it may not infer missing causes or receive hidden trace content. Exceptional production-content access is not implied by RunInspector and remains a security decision.

Azure Monitor and Application Insights own service health, latency, aggregate usage and cost, exceptions, alerts, and safe operational metadata. They may receive opaque correlation, record kind, lifecycle state, safe reason class, latency, aggregate resource data, and service errors, but not complete Inspection Records or domain causality.

## Reconstruction and verification replay

Every Run supports Run Reconstruction: a read-only historical explanation from its Inspection Records with no execution. Verification Replay is available only when a complete, lawful Replay Bundle was assembled incrementally during original execution and sealed at the relevant durable pause or terminal outcome. The bundle manifest binds recorded logical inputs, dependency responses, versions, artifact and fixture digests, completeness, lawful-retention status, and any typed reason replay is unavailable. Missing content cannot later be recovered from hashes.

Verification Replay has two targets:

- **Reproduction** uses the original bound implementation and policy artifacts and requires exact Fingerprint, deterministic decision, Approval-Gate placement, workflow-outcome, and terminal-reason equality.
- **Comparison** uses a candidate implementation. Expected implementation and version changes are reported separately, while field-aware semantic differences identify changed decisions and outcomes.

Both targets use fixture-only model and provider ports without production secrets, live network calls, Planner Approval creation, or any canonical commit path. Historical usage and cost remain fixture metadata; replay compute cost is separate. Each replay has its own linked inspection trace and exactly one outcome: `matched`, `diverged`, `unavailable`, or `failed`. Semantic divergence is distinct from technical replay failure.

## Conformance

Capability and routing-handler registration and CI require schema compatibility, complete required-path records, deterministic reason codes, redaction and audience projections, interruption recovery, cost lineage, and fixture-only replay. The normative matrix covers deterministic and model routing; DAG inclusion and exclusion; execute, skip, reuse, invalidation, retry, fallback, repair, and exhaustion; Evidence acceptance and every rejection class; validator pass and fail; Approval, rejection, expiry, and supersession; resume match and mismatch; resource exhaustion; cancellation and late results; every terminal outcome; persistence outage; corrections; duplicate appends; and post-terminal diagnostics.

Tests primarily assert typed semantics, causality, required fields, manifests, and audience views rather than snapshotting nondeterministic serialization. Small versioned golden traces establish compatibility. Redaction tests use field allowlists, sensitivity-label coverage, synthetic secret and personal-data canaries, prompt and provider leakage probes, low-entropy digest attacks, and rejection of fields without an explicit policy. Replay tests cover exact reproduction, intentional candidate divergence, unavailable or corrupted bundles, incompatible schemas, missing artifacts, attempted live access or mutation, and technical failure.

Schema-versioned evaluator exports contain a trace manifest, selected redacted Inspection Records, lawful fixture or Replay Bundle references, expected semantic outcomes, and provenance. Storage duration, deletion propagation, physical PostgreSQL schema, indexes, partitioning, cleanup, HTTP and SSE transport, cost ceilings, and evaluation baselines remain owned by their dedicated decisions.
