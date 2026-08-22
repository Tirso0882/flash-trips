# Compile workflows from capability contracts

Flash Trips will distinguish planner-visible product capabilities, authoritative domain modules, and supporting platform modules, rather than treating every feature, provider, graph node, or model call as an agent. For each confirmed action, deterministic code will compile the required execution DAG from typed capability contracts, the Trip Request, the current Plan Revision, Evidence validity, and approval policy; LangGraph will execute that DAG using dependency-aware parallel scheduling inspired by LLMCompiler, but an LLM will not invent authoritative dependencies, workflow gates, invalidation, or state transitions.

## Considered Options

- A literal LLMCompiler architecture was rejected because a model-generated DAG could omit required safety, Evidence, approval, budget, or feasibility gates.
- Plan-and-Execute remains available only inside a bounded capability whose open-ended research genuinely benefits from replanning; it is not the Trip lifecycle orchestrator.
- ReWOO was rejected because its sequential variable-assignment worker adds another workflow representation without improving Flash Trips' typed state, approval, or parallel-execution requirements.

## Consequences

Every executable capability contract must declare its inputs, outputs, validators, Evidence policy, approval policy, implementation version, failure behaviour, invalidation fields, candidate limits, and external-call limits. `RunInspector` must expose the compiled DAG and why work was executed, skipped, reused, repaired, or blocked so deterministic orchestration remains debuggable.

A static startup registry will hold separate immutable Capability Definitions and injected Capability Executors. Startup fails on duplicate capability identifiers, missing producers, schema incompatibility, or dependency cycles. Definitions declare schema-versioned `consumes` and `produces`; they use explicit capability-to-capability dependencies only for genuine control edges. Deterministic, versioned `required_when`, `invalidated_by`, and reuse rules decide which definitions participate in a compiled Run.

Executors have one of three closed execution policies: `deterministic`, `provider_backed`, or `reasoning_assisted`; there is no generic `agent` execution type. Executors cannot mutate canonical state. They return a complete, validated result or a typed `Blocked` or `Failed` outcome to the Trip Planning commit coordinator. `Skipped` and `Reused` describe workflow decisions and are not executor outcomes; partial success is not a valid generic outcome.

Reuse fingerprints bind the capability and implementation versions, input and dependency fingerprints, input and output schema versions, Evidence snapshot, validator and policy versions, provider-adapter versions, and—when reasoning is used—the prompt and reasoning-profile versions. A change to any bound component prevents silent reuse.

Every Capability Definition references a versioned Evidence policy. That policy declares applicable source classes, freshness, identity and scope matching, coverage, and contradiction handling. Deterministic transformations of canonical inputs may declare Evidence `not_applicable`; every other unmet Evidence requirement returns `Blocked` rather than an unsupported result. A result is `Succeeded` only after schema validation, capability and domain-invariant validation, and any applicable cross-capability completion validation have passed.

Capability Definitions declare versioned approval triggers and approval kinds, but executors neither request nor interpret approval. The compiler inserts approval gates after validated results, and the Approval module binds each decision to the exact fingerprints reviewed.

Resource policy is enforced outside the executor. Definitions declare deadlines and maxima for attempts, provider and model calls, tokens, candidates, and monetary cost; undeclared provider or model allowance defaults to zero. The compiler additionally enforces aggregate Run limits and propagates cancellation.

`Blocked` reason codes describe valid bounded execution that cannot proceed because required inputs, valid Evidence, eligible inventory, or satisfiable constraints are absent. `Failed` reason codes describe exhausted technical dependencies, contract violations, invalid output, or implementation defects. Retries are permitted only for explicitly allowlisted transient failures, use bounded attempts and idempotency keys, and preserve the original inputs. Fallbacks must be versioned, explicitly ordered, and subject to equivalent validation and Evidence requirements; they cannot silently weaken constraints or policy.

Every attempt has a deterministic execution identifier and idempotency key. Executors perform no side effects beyond declared provider reads. Results arriving after cancellation or after the Run is blocked because its context changed are recorded for diagnosis but cannot reach canonical commit.

Execution records include capability and attempt identifiers, fingerprints and versions, dependency decisions, redacted input and output hashes, Evidence references, validator decisions, timing, retries, fallbacks, usage and cost, and terminal reason codes. They exclude secrets and unnecessary personal data. These records allow `RunInspector` to reconstruct why each capability executed, was skipped or reused, and how it reached its outcome.

Every registered capability must pass a shared offline conformance suite before registration or CI can succeed. The suite covers registry and dependency validity; schema conformance; complete validated outputs; fail-closed malformed and partial outputs; missing, stale, mismatched, and contradictory Evidence; reuse and every declared invalidation trigger; exact approval binding; resource exhaustion; retry and fallback policy; idempotency and cancellation; discarded late results; outcome reason codes; trace completeness and redaction; and deterministic replay with mocked providers and models. Each execution policy adds its own conformance cases. Live-provider tests remain a separately authorised integration layer and are not required for deterministic offline acceptance.

Provider discovery may execute in parallel, but deterministic Plan Assembly evaluates results in stages: validate Candidate pools; choose anchor transport and accommodation; calculate a preliminary budget envelope; choose Dining and Activities; measure required routes and choose Ground Transport; compile the Itinerary; then produce the final Budget Assessment. It evaluates at most three complete Plan Portfolios per Run and allows at most one provider-search expansion for each affected capability, relaxing only soft preferences.

Every attempted Plan Portfolio is fingerprinted and cannot repeat. A repair must strictly improve hard-constraint and schedule conflicts, required budget coverage, target-budget excess including contingency, then Planner-preference fit, in that order. Models may rank eligible alternatives or propose substitutions, but deterministic Plan Assembly accepts only valid, unseen, improving proposals. Exhaustion returns a typed blocked outcome with attempted fingerprints, rejected alternatives, Evidence, and proposed Constraint Relaxations; it never commits the closest invalid portfolio.
