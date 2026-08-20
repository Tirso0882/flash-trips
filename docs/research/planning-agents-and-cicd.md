# Planning-agent patterns and CI/CD strategy

Date reviewed: 2026-08-19

## Scope and current repository facts

This note compares Plan-and-Execute, ReWOO, and LLMCompiler against the accepted Flash Trips architecture, then recommends a staged CI/CD strategy.

At the time of this review, `Tirso0882/flash-trips` was a private, empty GitHub repository with no remote default branch, branch protection, workflow, release, or deployable artefact. The local tree contained planning documentation but no application scaffold. CI/CD should therefore be introduced in stages rather than beginning with a production deployment workflow.

## Planning-agent architectures

LangChain presents all three as plan-and-execute variants that separate a larger planning model from task execution. The claimed advantage over ReAct is fewer large-model calls, cheaper specialised execution, and an explicit plan for multi-step work.[^planning-blog]

### Plan-and-Execute

An LLM planner creates a multi-step plan. Executors run one step at a time, then the planner is called again to finish or replan.[^planning-blog]

Strengths:

- Simple mental model and straightforward LangGraph implementation.
- Replanning can recover when the initial plan is incomplete.
- A larger model can plan while smaller models or deterministic tools execute steps.

Limitations for Flash Trips:

- Execution remains serial in the published design.
- Each task commonly uses an LLM.
- An LLM-authored global plan would compete with deterministic workflow gates, capability dependencies, and selective invalidation.
- Replanning after each sequence makes behaviour harder to reproduce and explain.

Fit: useful only inside a bounded, open-ended reasoning task. It should not plan the complete Trip lifecycle.

### ReWOO

ReWOO's planner emits interleaved reasoning and executable steps whose outputs are assigned to variables such as `#E1`; later steps can reference those variables without replanning after every observation. A solver combines the results.[^planning-blog][^rewoo-paper]

Strengths:

- Later tasks receive only the variables they need.
- Fewer planning calls than naive Plan-and-Execute.
- Explicit data dependencies make the trace easier to inspect than an unconstrained tool loop.

Limitations for Flash Trips:

- The published worker still executes sequentially.
- The LLM-defined mini-language becomes another workflow representation to validate, version, and debug.
- It has no natural advantage for approval interruption, selective capability recomputation, or parallel provider searches.
- Variable references are too weak to represent Flash Trips' typed Evidence, Plan Revision, approval, and freshness contracts.

Fit: not recommended as the system or capability orchestration pattern.

### LLMCompiler

LLMCompiler streams an LLM-generated task DAG. A task-fetching unit schedules tasks as soon as dependencies are satisfied, enabling parallel execution, and a joiner decides whether to finish or replan.[^planning-blog][^llmcompiler-paper]

Strengths:

- Best support of the three for dependency-aware parallel work.
- Streaming the task plan permits execution to start before planning is complete.
- Variable dependencies make fan-out and fan-in explicit.
- The joiner supports bounded replanning after observing results.

Limitations for Flash Trips:

- Letting an LLM invent the authoritative DAG would conflict with deterministic workflow-transition authority.
- A generated DAG can omit required safety, Evidence, approval, budget, or feasibility gates.
- Dynamic task graphs complicate replay, selective recomputation, evaluation, and change impact analysis.
- Its greatest benefit applies when the task graph is unknown. Most Flash Trips dependencies are knowable from requested capabilities and changed Plan fields.

Fit: the most relevant source of ideas, but not a framework to adopt literally.

## Recommendation for Flash Trips

Do not select any of the three as the product architecture.

Retain the accepted capability-oriented modular monolith and use a deterministic **workflow compiler** inside `TripPlanning`:

1. The typed Trip Request, current Plan Revision, confirmed action, and capability descriptors are inputs.
2. Deterministic code calculates the required capability DAG, approval gates, reuse decisions, and invalidation closure.
3. LangGraph executes that DAG, including safe parallel branches, retries, suspension, and resume.
4. Reasoning agents may propose bounded selections or research steps inside one capability.
5. Deterministic validators accept or reject every proposal before canonical state changes.
6. `RunInspector` records the compiled DAG, why every task was included, inputs and fingerprints, Evidence, reuse, costs, failures, and the terminal outcome.

This borrows LLMCompiler's dependency-aware scheduler while rejecting its LLM-authored authority. Plan-and-Execute may later be used privately for a genuinely open-ended research loop, such as finding and comparing official sources, but its output remains an untrusted proposal inside the owning capability. ReWOO adds no necessary mechanism.

Impact on current decisions:

- ADR 0002 remains unchanged: the model still does not own workflow transitions or facts.
- ADR 0005 remains unchanged: LangGraph remains private workflow machinery inside the modular monolith.
- ADR 0005 can be refined later with a new decision recording deterministic DAG compilation and LLMCompiler-inspired scheduling.
- The capability map must declare each capability's inputs, outputs, validators, Evidence policy, approval policy, and invalidation fields so the DAG can be compiled rather than invented.

## Recommended CI/CD strategy

### Platform and delivery model

Use GitHub Actions because the repository and issue workflow already live in GitHub. Authenticate to Azure through GitHub OIDC and Microsoft Entra workload identity federation rather than stored Azure client secrets.[^github-oidc-azure][^azure-oidc]

Use Azure Container Registry as the deployment registry and Azure Container Apps as the target. Build each deployable image once, tag it with the Git commit SHA, capture its immutable digest, and promote that same digest across environments. Do not rebuild per environment or maintain unrelated GHCR and ACR release artefacts.

Use Bicep for reproducible Azure infrastructure. Run Bicep validation and `what-if` before deployment.[^bicep-what-if]

### Branch and environment flow

Use trunk-based development:

- Short-lived feature branches.
- Pull requests into protected `main`.
- Required provider-free CI checks before merge.
- Automatic deployment of the merged immutable artefact to `test` once a deployable system exists.
- Protected `production` GitHub environment with explicit approval, deployment concurrency control, and environment-scoped OIDC identity.[^github-environments][^github-concurrency]

For a solo repository, require status checks and resolved conversations. Add a required independent approval only when another maintainer is available; do not create a rule the sole maintainer cannot satisfy.

### Pull-request CI

PR checks should be hermetic, parallel, and cancel superseded runs:

1. Repository/documentation contract checks.
2. Python formatting, linting, type checking, unit tests, and contract tests.
3. Frontend formatting, linting, type checking, component tests, and production build.
4. Deterministic EDD Layer 1 for affected capabilities.
5. Database migration validation against ephemeral PostgreSQL when persistence exists.
6. Container build without pushing when Dockerfiles exist.
7. Dependency review, secret scanning, CodeQL, and container/filesystem vulnerability scanning where the GitHub plan supports them.[^github-dependency-review][^github-codeql]

PR CI must not call Azure OpenAI, travel providers, live search, model judges, or mutate LangSmith/Azure. Cached fixtures must fail closed on a miss.

### Main build and test deployment

After a merge to `main`:

1. Require the same commit's CI to succeed.
2. Build API and frontend images once.
3. Generate an SBOM and provenance/attestation where supported.[^github-attestations]
4. Push immutable SHA-tagged images to ACR and resolve their digests.
5. Deploy the digests to the `test` Container Apps environment.[^aca-github-actions]
6. Apply backward-compatible database migrations through a controlled job.
7. Run health, API-contract, ownership, persistence/resume, streaming, and deterministic handbook smoke tests.
8. Record the commit, image digests, migration version, configuration version, and test evidence.

### Production promotion

Production should promote the already-tested digests through a protected environment; it must not rebuild them.

Use Container Apps revisions for controlled rollout and rapid traffic rollback.[^aca-revisions] Before promotion, require:

- successful test deployment and smoke checks;
- deterministic EDD and security gates;
- explicit confirmation of database migration and rollback compatibility;
- budgeted, approval-gated live provider canaries when relevant;
- an identified rollback target and operator.

Model-judge EDD Layers 2-4, live provider capture, load tests, and resilience tests belong in manually dispatched or scheduled workflows with declared cases, expected external calls, token/credit budget, and approval. They should inform promotion but never run accidentally on every PR.

### Staged introduction

1. **Now — documentation CI:** establish `main`, ignore local artefacts, validate Markdown links/ADR numbering/domain documents, and add repository rules.
2. **Application scaffold:** add Python/frontend quality gates and deterministic tests.
3. **Persistence and containers:** add PostgreSQL contract tests, migration checks, and image builds.
4. **Test environment:** provision ACR/Container Apps with Bicep and OIDC; deploy immutable digests automatically from `main`.
5. **Invitation-only release:** add protected production promotion, canaries, rollback, operational dashboards, alerts, and recovery tests.

This avoids writing speculative deployment YAML before build commands, artefact boundaries, health contracts, migrations, and infrastructure exist.

## Sources

[^planning-blog]: LangChain, [Plan-and-Execute Agents](https://www.langchain.com/blog/planning-agents), published 2024-02-13 and reviewed 2026-08-19.
[^rewoo-paper]: Xu et al., [ReWOO: Decoupling Reasoning from Observations for Efficient Augmented Language Models](https://arxiv.org/abs/2305.18323).
[^llmcompiler-paper]: Kim et al., [An LLM Compiler for Parallel Function Calling](https://arxiv.org/abs/2312.04511).
[^github-oidc-azure]: GitHub Docs, [Configuring OpenID Connect in Azure](https://docs.github.com/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-azure).
[^azure-oidc]: Microsoft Learn, [Use the Azure Login action with OpenID Connect](https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect).
[^bicep-what-if]: Microsoft Learn, [Bicep deployment what-if operation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/deploy-what-if).
[^github-environments]: GitHub Docs, [Managing environments for deployment](https://docs.github.com/actions/managing-workflow-runs-and-deployments/managing-deployments/managing-environments-for-deployment).
[^github-concurrency]: GitHub Docs, [Control workflow concurrency](https://docs.github.com/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).
[^github-dependency-review]: GitHub Docs, [About dependency review](https://docs.github.com/code-security/supply-chain-security/understanding-your-software-supply-chain/about-dependency-review).
[^github-codeql]: GitHub Docs, [About code scanning with CodeQL](https://docs.github.com/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql).
[^github-attestations]: GitHub Docs, [Using artifact attestations to establish provenance](https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds).
[^aca-github-actions]: Microsoft Learn, [Deploy to Azure Container Apps with GitHub Actions](https://learn.microsoft.com/azure/container-apps/github-actions).
[^aca-revisions]: Microsoft Learn, [Revisions in Azure Container Apps](https://learn.microsoft.com/azure/container-apps/revisions).
