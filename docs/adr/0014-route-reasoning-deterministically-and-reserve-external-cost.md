# Route reasoning deterministically and reserve external cost

Flash Trips will route every reasoning task through deterministic, versioned policy and will reserve the worst-case external cost before dispatching any model or provider call. Correctness, grounding, Evidence, deterministic validation, and canonical authority are fixed constraints; within routes that pass those constraints, policy prefers deterministic execution, then the least expensive approved reasoning profile, then latency.

## Routing

Reasoning Runtime owns a closed catalogue of purpose-specific Reasoning Profiles rather than generic model-size tiers:

- `classification` classifies otherwise-unresolved natural-language Turns.
- `structured_interpretation` produces untrusted typed Trip Intake and Amendment Proposals.
- `grounded_synthesis` answers and explains only from an applicable validated Evidence packet and, for Trip-grounded questions, canonical Trip and Plan Revision records.
- `bounded_reasoning` ranks eligible Candidates and proposes bounded research syntheses, substitutions, or repairs for deterministic evaluation.

Greetings, application help, structured actions, protocol decisions, commands, Approval responses, cancellation, status templates, money, dates, validation, workflow transitions, permissions, fingerprints, and rendering remain deterministic. A model cannot select its own profile, escalate itself, broaden its inputs, invent a workflow dependency, relax a constraint, approve an external call, or make canonical state authoritative.

Each Reasoning Profile pins its provider and deployment, model version or compatibility target, parameters, input and output token maxima, response schema, tool prohibition or allowlist, permitted data classes, prompt version, timeout, retry and fallback policy, pricing reference, and evaluation release gate. A route binds the exact profile and prompt versions into its Fingerprint and Inspection Records. Production initially uses Azure OpenAI behind the reasoning port; another model provider requires equivalent privacy, pricing, conformance, and evaluation evidence before activation.

Routing uncertainty fails closed. Classification uncertainty produces one focused Pending Clarification rather than escalating to a stronger model. A reasoning-assisted Capability may use at most one explicitly ordered, versioned fallback when its contract declares the trigger and reserves the fallback's worst-case cost in advance. The fallback receives the same authoritative inputs and must satisfy equivalent Evidence, schema, safety, and validation policy.

Guest Session, Guest General, and Guest Intake Transfer are deferred from the invitation-only release. If a Guest surface is later enabled, Guest Sessions may use only `classification` and `grounded_synthesis`, subject to strict Turn, session, rate, and cost limits. They cannot use strong bounded reasoning, inventory searches, or travel-provider calls. A submitted eligible read-only Turn authorises only the calls predeclared by its deterministic route; a cache miss never creates authority for a paid call.

Changing a task's Reasoning Profile, provider, prompt, or parameters creates a new routing-policy version and must pass the task-specific quality, schema, grounding, safety, latency, and cost gates owned by the evaluation decision. Existing Runs keep their accepted version. Rollback selects a previously approved version rather than mutating history.

## Resource policy

Resource policy is enforced outside executors and applies to both reasoning and travel-provider work. Every Capability and route declares maxima for attempts, calls, input and output tokens or other billable units, candidates, wall-clock time, and native and reporting-currency cost. Effective allowance is the strictest applicable value across the Capability contract, Reasoning Profile or Provider Market Profile, environment policy, principal or Guest Session policy, and remaining Turn or Run budget. An absent, unlimited, unpriced, or unconvertible allowance is zero unless a versioned policy supplies a conservative reservation.

The compiler assigns non-overlapping Capability sub-budgets whose sum cannot exceed the aggregate Run ceiling. Each assignment includes every declared retry and fallback; unallocated capacity can move only through a recorded deterministic reallocation decision. Before dispatch, an atomic reservation must succeed against the attempt, Capability, Turn or Run, Guest Session or principal, environment rolling-day and rolling-month, and provider billing-period scopes that apply. Parallel work cannot race past a ceiling. Completion atomically reconciles estimated and final usage, while abandoned reservations are reconciled before recovery can repeat work.

Admission reserves conservative worst-case billable units and monetary cost using a versioned pricing source. Final usage releases the unused difference. An unknown final amount retains its reservation until a correction establishes the charge, and unknown values are never treated as zero. Active reserved calls may finish after a longer-horizon ceiling is reached, but no new reservation may begin.

Every active profile and provider must have explicit numeric limits in versioned release policy. The ADR does not freeze those values: initial and changed values must pass the evaluation and cost gates before release. CI and local development have zero live-call allowance by default.

Runs retain the policy version accepted at creation. Operators may lower service-wide limits or cancel work immediately as an emergency stop, but a later increase never expands an existing Run. Warning thresholds and hard ceilings produce operational alerts for reservation failures, unknown-cost growth, correction overruns, repeated quota failures, and hard-ceiling activation without exposing private Trip content.

## Attempts, deadlines, and quotas

An external attempt may be retried once only for an allowlisted transport failure, `429`, or provider `5xx`, while respecting `Retry-After`, the original inputs and idempotency key, the remaining Capability and Run deadlines, and every resource ceiling. Schema-invalid, unsafe, ungrounded, contradictory, or low-confidence model output is not retried; it follows the declared equivalent fallback or fails closed. A timeout consumes its attempt and recorded usage. Results received after timeout, cancellation, a Run-blocking context change, or another terminal outcome are recorded as discarded and cannot satisfy a dependency or reach canonical commit.

Reasoning and provider adapters track configured account quotas and trusted response metadata. A bounded circuit opens after rate or quota exhaustion, honours a known reset time, and prevents paid probe calls while open. Only a predeclared equivalent provider or reasoning fallback may be attempted; model memory, a weaker source class, a cheaper unapproved profile, or relaxed validation cannot substitute.

## Reuse and paid-call authorization

Flash Trips will not use semantic model caching. It may reuse only an exact Fingerprint-bound validated result after current Evidence, policy, scope, and completion validation pass. Reasoning results are isolated by principal or Guest Session and Conversation Scope and are never shared across Planners. Terms-permitted public Provider Observations and deterministic reference data may use a shared cache, but source cache directives may shorten Evidence freshness and never extend it.

A Planner's accepted planning action authorises only the bounded paid calls compiled into that Run. An eligible read-only Turn similarly authorises only its route's bounded calls. Crossing a ceiling is prohibited and cannot be approved inline; recovery requires a separately initiated action or linked Run under applicable policy.

Live evaluation capture, model judging, provider probes, canaries, shadow calls, and comparison calls require a separate Operator-controlled Paid Execution Authorization bound to purpose, environment, providers, maximum spend, and expiry. It is not a Planner Approval. Experimental calls use separate budgets and Inspection Records, receive only lawful redacted inputs, and cannot affect canonical state or Planner-visible output.

## Cost lineage

Every external charge belongs to exactly one attempt and initiating Turn or Paid Execution Authorization and, where applicable, one Run and Capability. Inspection Records capture provider or model and adapter, request and response digests, profile and prompt versions, pricing source and version, billable units, quota information, timing, retries, fallback position, native exact-decimal cost and currency, reporting-currency estimate, usage status, and outcome without recording chain-of-thought, secrets, or unnecessary personal data.

Native billing amounts remain authoritative. Aggregate reporting initially uses USD through a versioned foreign-exchange snapshot. Estimated, final, and unknown costs remain distinct; later invoice or billing-export data appends a correction rather than rewriting history. Aggregation by Turn, Run, Capability, principal class, environment, provider, profile, and authorization references the same underlying charges without duplication.

Cancellation stops new dispatch, requests provider cancellation where supported, and retains each reservation until the attempt is finalized or conservatively charged. Incurred cost remains attributable even when the result is discarded.

## Exhaustion and recovery

A deterministic policy ceiling reached before dispatch returns `Blocked(resource_budget_exhausted)`. Provider or model quota exhaustion after the allowed retry and equivalent fallback returns `Failed(provider_quota_exhausted)`. Other exhausted technical dependencies and invalid outputs use their typed `Failed` reasons. These outcomes never silently downgrade quality, weaken Evidence or constraints, expose internal provider, model, quota, or cost details to the Planner, or commit the closest partial result.

Validated completed results and their Inspection Records remain available for diagnosis and exact future reuse, but a partially completed Travel Plan cannot become canonical. Recovery presents a deterministic safe explanation and available actions. It never starts another Run automatically: the Planner must initiate a linked retry Run with fresh limits, and every proposed reuse is revalidated against that Run's inputs, Evidence, policies, and Fingerprints.

## Consequences

Reasoning Runtime is a supporting module with no canonical authority. The Workflow Compiler owns deterministic route and budget allocation; the resource ledger owns atomic reservations and reconciliation; RunInspector owns durable routing, usage, quota, and cost lineage. Planner-facing inspection continues to hide internal models, providers, quotas, and service costs while exposing safe progress, limitations, and recovery options.

Offline conformance must cover every route, deterministic fast path, profile and policy version, zero-default allowance, reservation race, retry and fallback trigger, timeout, cancellation, cache hit and miss, cross-principal isolation, quota circuit, cost estimate and correction, unknown cost, policy change, authorization boundary, alert condition, exhaustion outcome, partial-result rejection, and fixture-only replay. Live calls remain a separately authorised integration layer.
