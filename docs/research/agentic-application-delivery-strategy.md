# Delivery strategy for safety-sensitive agentic applications

Date reviewed: 2026-09-03

## Conclusion

High-quality teams should earn autonomy rather than begin with it. Use deterministic code or a fixed workflow when the task and required checks are knowable. Use a model only where interpretation, ranking, synthesis, or an open-ended search path adds measured value. Expand from bounded proposals to broader tool choice only after representative evaluations, sandboxed tests, production-like integration evidence, complete traces, enforced limits, and effective human escalation show that the added autonomy improves outcomes without crossing the accepted risk threshold.[^anthropic-agents][^anthropic-evals][^nist-rmf]

This strongly supports Flash Trips' accepted design. Deterministic code owns identity, permissions, facts, dates, money, Evidence validation, workflow transitions, Approvals, and canonical Plan Revisions. Model calls remain purpose-specific, resource-bounded proposals. Flash Trips should stage delivery by completing thin end-to-end Capabilities under fixtures first, then activating narrowly scoped live providers, and only later considering more autonomy inside Capabilities whose paths cannot be fixed in advance.

## Evidence and implications

### 1. Prefer deterministic workflows until flexibility is necessary

Anthropic distinguishes workflows, where code defines the path, from agents, where a model directs its own process and tool use. It recommends the simplest adequate design, notes that fixed workflows are more predictable for well-defined tasks, and reserves agents for open-ended work where the steps cannot be hardcoded.[^anthropic-agents] OpenAI likewise advises matching orchestration to complexity, beginning with a single agent and adding multi-agent structure only when needed.[^openai-guide]

For Flash Trips, Trip Intake validation, capability dependencies, provider eligibility, cost reservation, feasibility, Approval binding, and commit remain deterministic workflows. A model is justified for bounded language interpretation, Candidate ranking, or grounded synthesis only when evaluations show a material gain over deterministic or single-call alternatives. An agentic loop is justified only inside an open-ended Capability with explicit stop conditions, not as the authority for the Trip lifecycle.

### 2. Make development evaluation-driven

Anthropic recommends defining success early and turning requirements and real failures into tests. It says 20 to 50 representative tasks can provide a useful initial suite, while mature systems need larger and harder sets to detect smaller changes.[^anthropic-evals] NIST calls for objective, repeatable, documented test, evaluation, verification, and validation, including documented test sets and performance evidence under conditions similar to deployment.[^nist-rmf] Microsoft recommends repeatable evaluations before publication and after meaningful changes, followed by production monitoring and trace review.[^microsoft-lifecycle]

Flash Trips already goes further in the right direction: deterministic verification takes priority, individual authority, privacy, safety, and grounding failures cannot be averaged away, and semantic judges require human calibration. Each Capability and Reasoning Profile should start with Evaluation Cases before implementation, add every escaped defect as a synthetic regression, and require an exact Fingerprint match before reusing evidence.

### 3. Treat prototype, MVP, and production as evidence levels

The primary sources do not prescribe universal definitions for these three labels. A useful risk-based synthesis is:

- **Prototype:** one narrow Capability, synthetic inputs, fixture-backed tools, no canonical or external side effects, manual inspection, and an initial evaluation set. Its purpose is to test whether model assistance adds value.
- **Invitation MVP:** several complete vertical slices, authenticated Planners, qualified live read-only providers behind explicit activation and budgets, durable Runs and Inspection Records, bound Approval Gates, kill switches, and release evaluations. Model output still cannot directly commit authority.
- **Production:** production-like evaluation evidence, versioned releases, continuous monitoring, incident response, recovery drills, security review, provider governance, and measured operational thresholds. NIST requires deployment-relevant testing and production monitoring, while Microsoft treats monitoring, trace review, versioning, evaluation, and republishing as one lifecycle.[^nist-rmf][^microsoft-lifecycle]

For Flash Trips, "MVP" must not mean relaxing Evidence, ownership, privacy, or Approval rules. Invitation-only access limits exposure but is not a substitute for production controls.

### 4. Build vertical slices through real control boundaries

No reviewed source mandates the term "vertical slice." The recommendation follows from Anthropic's advice to use simple composable patterns, ground each step in environmental results, and add complexity only when measured outcomes improve.[^anthropic-agents] A Flash Trips slice should therefore carry one Planner action through typed command admission, deterministic workflow compilation, fixture-backed dependency calls, proposal validation, an Approval Gate where applicable, canonical commit or typed failure, Run observation, and evaluation.

Prefer one complete slice such as Trip Intake or one evidence-backed planning Capability over implementing all prompts, all provider adapters, or all agent nodes horizontally. This exposes authority, persistence, interruption, privacy, and observability defects while the scope remains small.

### 5. Prove behavior offline before activating live providers

Anthropic recommends extensive testing of autonomous agents in sandboxed environments because cost and errors can compound.[^anthropic-agents] Microsoft provides offline agent evaluation in CI specifically to find problems before production release.[^microsoft-offline-eval] Google recommends continuously testing pipeline components, comparing a candidate against the current version, enforcing fixed validation thresholds, and staging candidates in a sandboxed serving environment before production.[^google-deployment-testing]

Flash Trips should keep local development and pull requests at zero live-call authority. Versioned Evaluation Fixtures and Verification Replays should cover success, malformed responses, stale or conflicting Evidence, timeouts, retries, late results, cancellation, prompt injection, and quota exhaustion. Fixture misses must fail closed. Live model or provider work begins only in an isolated test environment under Paid Execution Authorization, fixed call and spend ceilings, retention rules, and canaries that cannot mutate production state.

### 6. Observability is part of the product contract

NIST requires production behavior and controls to be monitored, not merely tested before release.[^nist-rmf] Microsoft recommends reviewing traces when behavior changes and monitoring quality and safety after publication.[^microsoft-lifecycle] Google describes full-lifecycle OpenTelemetry traces and agent evaluation that includes tool requests and responses, rather than assessing only the final answer.[^google-continuous-eval]

Flash Trips' durable Run event sequence, Inspection Records, immutable accepted inputs, attempts, Fingerprints, cost lineage, Approval state, and terminal outcomes fit this guidance. Keep public progress separate from restricted diagnostic records. Capture typed decisions, tool arguments and outcomes, policy versions, latency, resource use, retries, and redacted dependency digests, but not secrets, unnecessary Sensitive Trip Data, or hidden chain-of-thought.

### 7. Put human approval at the side-effect boundary

OpenAI recommends pausing before sensitive side effects and placing validation next to the tool that creates the effect. Its approval lifecycle records the interruption, stores resumable state, records approve or reject, and resumes the same run.[^openai-approvals] OpenAI also identifies repeated failure and sensitive, irreversible, or high-stakes actions as human-intervention triggers.[^openai-guide] NIST warns that overly frequent human prompts can produce consent fatigue, so approvals should be scoped and meaningful rather than used as a substitute for policy enforcement.[^nist-agent-identity]

Flash Trips should retain immutable Approval Requests bound to the exact proposed result, Plan Revision, Evidence, and policy. Free-text assent is insufficient. Approval never authorizes a broader tool scope, extra cost, a changed proposal, or a stale revision. Deterministic checks still mediate every action before and after approval.

### 8. Enforce security outside the model

OpenAI says high-risk tool calls should be checked against target, arguments, identity, scope, and time window, with independent filesystem, network, identity, and project boundaries, recorded decisions, and fail-closed review.[^openai-approvals] NIST emphasizes granular authorization, attenuated delegated rights, tightly scoped access, and distinct agent identity.[^nist-agent-identity] Anthropic recommends clear, carefully tested tool interfaces and making invalid actions hard to express.[^anthropic-agents]

For Flash Trips, continue to treat Planner, provider, and model text as untrusted data. Models must never create authority, credentials, destinations, permissions, citations, or state transitions. Enforce typed schemas, destination allowlists, least-privilege identities, resource ceilings, complete mediation, idempotency, output sanitization, SSRF defenses, adapter kill switches, and canonical commit-time rechecks in deterministic code.

## Criteria for expanding autonomy

Expand autonomy for one Capability at a time only when all of these are true:

1. A fixed workflow has been measured and shown insufficient for a material class of valid requests. Added autonomy produces a statistically and operationally meaningful gain on representative Evaluation Cases.[^anthropic-agents][^anthropic-evals]
2. Deterministic invariants, critical-failure cases, security cases, and deployment-like integration tests pass with no waiver of authority, privacy, grounding, or safety failures.[^nist-rmf][^google-deployment-testing]
3. The proposed tools are narrower than the Capability, use least privilege, have typed arguments and outputs, and cannot directly commit canonical state.[^openai-approvals][^nist-agent-identity]
4. Every run has bounded steps, wall time, calls, spend, retries, data access, and stop conditions. Ambiguity, exhausted limits, unavailable oversight, or policy mismatch fails closed.[^anthropic-agents][^openai-approvals]
5. Operators can inspect the trajectory and policy decisions, detect regressions, cancel work, disable each adapter or model route, and reconstruct outcomes without hidden reasoning.[^microsoft-lifecycle][^google-continuous-eval]
6. Human approval remains mandatory for consequential or high-risk actions until evidence for that exact action class supports a reviewed policy change. Invitation-only exposure alone does not satisfy this criterion.[^openai-guide][^nist-agent-identity]
7. Rollout is narrow, reversible, monitored, and tied to a versioned release record. Production evidence feeds new synthetic evaluations without copying private Trip data into development.

For the current product boundary, these criteria support bounded reasoning inside Capabilities but do not support model-owned workflow planning, autonomous provider activation, autonomous constraint relaxation, direct Plan Revision commits, booking, payment, cancellation, or handbook delivery.

## Sources

[^anthropic-agents]: Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents), 2024-12-19.
[^anthropic-evals]: Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), 2026-01-09.
[^openai-guide]: OpenAI, [A practical guide to building AI agents](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/).
[^openai-approvals]: OpenAI Developers, [Guardrails and human review](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals).
[^nist-rmf]: NIST, [Artificial Intelligence Risk Management Framework (AI RMF 1.0)](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf), NIST AI 100-1, 2023-01.
[^nist-agent-identity]: NIST, [Back to the Future: Why Agentic AI Needs a Strong Identity Foundation](https://www.nist.gov/blogs/cybersecurity-insights/back-future-why-agentic-ai-needs-strong-identity-foundation), 2025-08-28.
[^microsoft-lifecycle]: Microsoft Learn, [Agent development lifecycle in Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/development-lifecycle).
[^microsoft-offline-eval]: Microsoft Learn, [How to run an evaluation in Azure DevOps](https://learn.microsoft.com/en-us/azure/foundry/how-to/evaluation-azure-devops).
[^google-deployment-testing]: Google for Developers, [Production ML systems: Deployment testing](https://developers.google.com/machine-learning/crash-course/production-ml-systems/deployment-testing).
[^google-continuous-eval]: Google Cloud, [From "Vibe Checks" to Continuous Evaluation: Engineering Reliable AI Agents](https://cloud.google.com/blog/topics/developers-practitioners/from-vibe-checks-to-continuous-evaluation-engineering-reliable-ai-agents).
