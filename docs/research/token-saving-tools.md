# Token-saving tools for `flash-trips`

Date reviewed: 2026-09-07

## Executive conclusion

Do not integrate any of the four tools into the production Sandcastle path yet.

- **Headroom is the strongest direct-compression candidate**, and its core JSON
  compression worked in a local smoke test. It is the only candidate whose
  design directly addresses large tool outputs and provider prompt-cache
  stability. The blocker is the integration seam: `flash-trips` launches the
  Cursor Agent CLI inside Sandcastle. Cursor's official CLI parameters and
  configuration expose no OpenAI-compatible or Anthropic-compatible model
  endpoint override. Headroom also tracks native Cursor CLI support as an open
  issue. Sandcastle does not expose the Cursor provider request stream to
  `.sandcastle/main.mts`. Adding Headroom now would therefore put no compressor
  on the model request path.
- **Graphify works as a navigation index, but is not worth piloting yet for
  token savings.** It built a useful local TypeScript code graph, and an
  exact-symbol query found the `runIssuePipeline` neighborhood. It does not
  compress tokens already in a request. It can only save tokens if agents use
  its graph instead of reading files. On this repository, the issue contract
  already gives agents a `Touches` line and named test seams, and local graph
  queries exceeded their requested token budgets. Revisit it when product
  source exceeds about 10,000 lines or baseline data shows that exploratory
  reads dominate Sandcastle input.
- **NeuralMind is not recommended.** Its own documentation correctly says the
  headline is retrieval-input reduction, not bill reduction, and labels Cursor
  support as theoretical. Its local `42.1x` result used a hard-coded
  50,000-token baseline. A query about Cursor agents in Docker returned 1,141
  tokens but did not surface the main implementation in `.sandcastle/main.mts`.
- **Caveman is not recommended.** Its response skill changes output style, not
  input context, and the project says the skill itself adds about 1,000 to
  1,500 input tokens per turn. Its separate engine did compress and exactly
  recover a synthetic log locally, but Cursor is absent from the native proxy
  profiles, the engine is BSL-1.1 rather than MIT, and its strongest published
  proxy result cannot be independently reproduced from the public checkout.

The right next step is measurement, not installation: first record provider
input, cache-read, cache-write, output, retry, wall-clock, and acceptance data
for representative Sandcastle Tasks. Only run a retrieval shadow evaluation
later if those measurements identify repository exploration as a material
token sink.

## Scope and source snapshots

The external repositories were inspected at these default-branch commits:

- Headroom:
  [`e67b3c8a29443a60d6b0018fb22f525c5cd7e709`](https://github.com/headroomlabs-ai/headroom/tree/e67b3c8a29443a60d6b0018fb22f525c5cd7e709).
  The installed release used for the smoke test was
  [`0.37.0`](https://pypi.org/project/headroom-ai/0.37.0/), whose tag points to
  [`32d7ca4577d599b8a5f811ada74cf31504302c9d`](https://github.com/headroomlabs-ai/headroom/tree/32d7ca4577d599b8a5f811ada74cf31504302c9d).
- Graphify:
  [`c9f99018774e2e0380e9f65b3959944559a0d5f6`](https://github.com/Graphify-Labs/graphify/tree/c9f99018774e2e0380e9f65b3959944559a0d5f6),
  released as
  [`graphifyy 0.9.55`](https://pypi.org/project/graphifyy/0.9.55/).
- NeuralMind:
  [`33fd3f62fdcaa04ad635a46507b29bb67f623710`](https://github.com/dfrostar/neuralmind/tree/33fd3f62fdcaa04ad635a46507b29bb67f623710).
  The smoke test used
  [`neuralmind 3.9.0`](https://pypi.org/project/neuralmind/3.9.0/), released from
  [`d748a651a14068128f2c400c25c6974d7373cad2`](https://github.com/dfrostar/neuralmind/tree/d748a651a14068128f2c400c25c6974d7373cad2).
- Caveman:
  [`15581d14007fd01fb3f132016741962f34936ca2`](https://github.com/JuliusBrussee/caveman/tree/15581d14007fd01fb3f132016741962f34936ca2).
  The public installer release was
  [`2.6.0`](https://github.com/JuliusBrussee/caveman/releases/tag/v2.6.0), while the
  separately versioned CLI source declared `1.3.3`
  ([package metadata](https://github.com/JuliusBrussee/caveman/blob/15581d14007fd01fb3f132016741962f34936ca2/packages/cli/package.json#L1-L35)).

Repository source, package metadata, licenses, releases, CI jobs, issue
history, benchmark implementations, and installation paths were checked.
Maintainer benchmarks are reported as maintainer claims unless this review
reproduced the relevant result.

## The three different products being compared

These tools do not solve one interchangeable problem.

### Direct input compression

Headroom and Caveman Engine sit between an agent and its model provider. They
transform already-assembled context such as logs, JSON, tool results, or
history. Both support recoverable compression through a local store
([Headroom CCR](https://github.com/headroomlabs-ai/headroom/blob/e67b3c8a29443a60d6b0018fb22f525c5cd7e709/README.md#L373-L380),
[Caveman product model](https://github.com/JuliusBrussee/caveman/blob/15581d14007fd01fb3f132016741962f34936ca2/docs/technical/product-model.md)).

Caveman also ships a separate response skill. That skill asks the model to
write terse answers. It does not compress input, files, tool output, or
reasoning tokens, and its prompt is itself an input cost
([Honest Numbers](https://github.com/JuliusBrussee/caveman/blob/15581d14007fd01fb3f132016741962f34936ca2/docs/HONEST-NUMBERS.md#L5-L19)).
It must not be evaluated as if it were the proxy engine.

### Code retrieval

Graphify parses a repository into a graph and returns a query-specific
subgraph. The graph can avoid some exploratory file reads. It does not make
the model's existing messages or tool results smaller. Its benefit depends on
the agent choosing the graph result instead of doing its normal search and
read sequence.

### Retrieval plus persistent memory

NeuralMind builds a code index, retrieves progressively larger context layers,
and learns file associations across sessions. Its comparison with Headroom
explicitly says the tools act at different stages
([comparison](https://github.com/dfrostar/neuralmind/blob/33fd3f62fdcaa04ad635a46507b29bb67f623710/docs/comparisons/vs-headroom.md#L40-L69)).
NeuralMind also has Claude Code hooks that compress selected tool outputs, but
the repository labels Cursor integration as theoretical and describes
automatic tool-output compression only for Claude Code
([compatibility matrix](https://github.com/dfrostar/neuralmind/blob/33fd3f62fdcaa04ad635a46507b29bb67f623710/README.md#L68-L87)).

## `flash-trips` integration reality

### Current execution path

`flash-trips` uses Node 22 and `@ai-hero/sandcastle` 0.12.0
([package metadata](../../package.json#L1-L37)). Each implementation and review
pipeline creates a Docker sandbox from `sandcastle:flash-trips`, then calls
`sandcastle.cursor(...)` with a prompt file and interpolated arguments
([implementation and review](../../.sandcastle/main.mts#L1440-L1552)).
Planning and merging use the same Cursor provider and Docker image
([planner](../../.sandcastle/main.mts#L1769-L1797),
[merger](../../.sandcastle/main.mts#L1640-L1675)).

The image already has Node, `uv`, and the Cursor `agent` executable, so all
four projects can technically be installed in it
([Dockerfile](../../.sandcastle/Dockerfile#L1-L59)). Technical installability is
not the same as traffic interception or agent adoption.

Sandcastle's Cursor provider launches `agent --print --output-format
stream-json`; it has `captureSessions: false` and no session store
([provider source](https://github.com/mattpocock/sandcastle/blob/e99f832f26dc9d245c019a9ddd19fa5dee792427/src/AgentProvider.ts)).
The existing reliability review therefore correctly treats Cursor sessions as
non-resumable
([review](./sandcastle-afk-review.md#patterns-explicitly-rejected)).
None of the four products can depend on resuming or rewriting Cursor's internal
conversation state from `.sandcastle/main.mts`.

Cursor's official CLI authentication uses `CURSOR_API_KEY` to authenticate to
Cursor, not to an underlying model provider
([authentication](https://cursor.com/docs/cli/reference/authentication.md)).
The documented `agent --print` parameters include model selection, custom
headers, and Cursor authentication, but no model-provider base URL
([parameters](https://cursor.com/docs/cli/reference/parameters.md)).
CLI configuration supports `HTTP_PROXY` and `HTTPS_PROXY` only as generic
network transport proxies for Cursor traffic; it exposes no
`OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL`, or custom provider endpoint
([configuration](https://cursor.com/docs/cli/reference/configuration.md)).
Headroom and Caveman are model API gateways, not transparent forward proxies
for Cursor's own protocol. They therefore cannot intercept this path through a
documented configuration seam.

### Existing prompts already constrain retrieval

The implementation prompt tells the agent to start at the ticket's `Touches`
paths, read only cited ADRs and relevant domain terms, and extend tests at
named public seams
([prompt](../../.sandcastle/implement-prompt.md#L10-L78)). The reviewer receives
the exact issue context and branch diff
([review prompt](../../.sandcastle/review-prompt.md#L1-L28)). The planner sees
only a validated authorized backlog
([plan prompt](../../.sandcastle/plan-prompt.md#L1-L39)).

This is materially different from the full-repository baseline used by the
retrieval tools' headline ratios. The repository currently contains about
27,560 lines and 1.80 MB across 390 tracked files in this review's local
measurement, but most of that footprint is documentation, generated contracts,
tests, and orchestration. The product implementation is still only about 664
nonblank Python and TypeScript lines, while `.sandcastle/main.mts` contains
about 1,896 nonblank lines. Agents are not instructed to load the entire
corpus. A retrieval ratio against the whole corpus is therefore not an estimate
of Sandcastle savings.

### Exact seams available today

1. **Before Cursor starts:** the orchestrator controls the prompt file and
   `promptArgs`. Compressing those fields is technically possible but unsafe.
   They contain criteria, architecture rules, test seams, and output contracts.
   Changing them also changes the stable prompt prefix and can reduce provider
   cache hits.
2. **Inside Cursor through MCP:** Graphify and NeuralMind can be exposed as
   optional tools. Headroom and Caveman can expose recovery or explicit
   compression tools. This is not transparent compression. The model must
   decide to call the tool, and each tool description and response consumes
   context.
3. **Between Cursor and the provider:** this is the proper seam for Headroom or
   Caveman Engine, but the headless Cursor Agent CLI has no documented
   model-provider endpoint override. This seam would require a future Cursor
   capability or replacing Sandcastle's Cursor provider.
4. **Around shell commands:** a wrapper could compress command stdout before
   Cursor sees it, but Cursor owns tool execution in this design. Sandcastle
   does not receive each tool result before the model does.

## Candidate findings

### Headroom: best mechanism, blocked integration

#### What worked

Headroom 0.37.0 installed with `uvx` and compressed a synthetic 400-row JSON log
containing one `FATAL` row:

- estimated input: 15,880 tokens
- estimated output: 5,399 tokens
- reduction: 66.0%
- critical `FATAL` text preserved: yes
- elapsed compression time: 7.8 ms in the local one-shot process

This verifies that its default structural compressor works on a favorable
payload. It does not verify answer equivalence, total session savings, cache
behavior, or proxy compatibility with Cursor.

The project's own reproducible latency benchmark reports 48% to 54% reduction
for large JSON arrays and logs, 92% for one documentation fixture, and 0% for
its Python source fixture. Its accuracy section verifies that one injected
JSON error survives, but publishes no paid-LLM QA-equivalence result
([benchmark methodology](https://github.com/headroomlabs-ai/headroom/blob/e67b3c8a29443a60d6b0018fb22f525c5cd7e709/docs/content/docs/benchmarks.mdx#L10-L59)).
Those are useful component measurements, not evidence for a 50% to 90%
Sandcastle bill reduction.

#### Maturity and maintenance

Headroom declares itself beta, requires Python 3.10 or newer, and combines
Python with a compiled Rust extension
([package metadata](https://github.com/headroomlabs-ai/headroom/blob/e67b3c8a29443a60d6b0018fb22f525c5cd7e709/pyproject.toml#L1-L64)).
Release 0.37.0 had a successful CI run with four test shards, lint, type
checking, package builds, native wrapper tests, and Docker proxy smoke tests
([CI run](https://github.com/headroomlabs-ai/headroom/actions/runs/33116615692)).
The project is active and has broad tests, but the rapid release rate and large
optional dependency surface increase upgrade work.

The package explicitly excludes compromised `ast-grep-cli` 0.44.1 and pins
security floors for several transitive dependencies
([dependency policy](https://github.com/headroomlabs-ai/headroom/blob/e67b3c8a29443a60d6b0018fb22f525c5cd7e709/pyproject.toml#L48-L67),
[constraints](https://github.com/headroomlabs-ai/headroom/blob/e67b3c8a29443a60d6b0018fb22f525c5cd7e709/pyproject.toml#L360-L388)).
That shows active supply-chain maintenance, while also showing why a pinned
lock and image scan would be mandatory.

#### Privacy, license, and cache behavior

Headroom is Apache-2.0
([license](https://github.com/headroomlabs-ai/headroom/blob/e67b3c8a29443a60d6b0018fb22f525c5cd7e709/LICENSE)).
Compression is local and the project says prompt and file content are not sent
elsewhere for compression
([README](https://github.com/headroomlabs-ai/headroom/blob/e67b3c8a29443a60d6b0018fb22f525c5cd7e709/README.md#L33-L38)).
An anonymous compression-statistics beacon is on by default. It excludes
prompts, code, and file paths, and can be disabled with
`HEADROOM_BEACON=off`, `DO_NOT_TRACK=1`, or offline mode
([telemetry disclosure](https://github.com/headroomlabs-ai/headroom/blob/e67b3c8a29443a60d6b0018fb22f525c5cd7e709/README.md#L589-L600)).
Any pilot should disable it and deny indexer/proxy egress except to the chosen
model provider.

Headroom's cache design is the best fit of the four. Its live-zone mode leaves
the frozen history prefix unchanged and compresses only fresh bytes, while
CacheAligner identifies volatile content
([features](https://github.com/headroomlabs-ai/headroom/blob/e67b3c8a29443a60d6b0018fb22f525c5cd7e709/README.md#L373-L379)).
This reduces, but does not eliminate, cache risk. The actual Cursor route must
still be measured using provider-reported cache counters.

#### Compatibility decision

The README lists Cursor as manual setup rather than a supported `wrap` target
([compatibility](https://github.com/headroomlabs-ai/headroom/blob/e67b3c8a29443a60d6b0018fb22f525c5cd7e709/README.md#L226-L250)).
Native Cursor CLI support remains open
([issue 2724](https://github.com/headroomlabs-ai/headroom/issues/2724)).
Cursor's official parameter and configuration references expose no compatible
provider base URL. Until Cursor adds that seam or Sandcastle changes to an
environment-driven provider, expected production savings are **0%**, because
the compressor cannot enter the request path.

**Decision:** do not install now. Retain as the first direct-compression
candidate if the proxy seam becomes testable.

### Graphify: viable graph, unproved marginal savings

#### What worked

`graphifyy==0.9.55` installed with `uvx` and completed a code-only extraction of
the cloned `flash-trips` repository. The generated graph was queryable. An
exact query for `runIssuePipeline` found the symbol and related functions. A
natural-language query for "where are Cursor agents launched in Docker" did
not produce a useful match. A 1,500-token query budget returned a complete
3,319-token graph response because Graphify intentionally keeps all edges once
all selected nodes fit
([renderer behavior](https://github.com/Graphify-Labs/graphify/blob/c9f99018774e2e0380e9f65b3959944559a0d5f6/graphify/serve.py#L1028-L1183)).

The local `graphify benchmark` printed a `9.8x` reduction. That number is not an
end-to-end benchmark. The implementation:

- estimates tokens as characters divided by four;
- uses simple query terms matched against node labels;
- starts from at most three matching nodes;
- expands a depth-three BFS;
- compares that output with a whole-corpus estimate.

These mechanics are visible in the benchmark source
([source](https://github.com/Graphify-Labs/graphify/blob/c9f99018774e2e0380e9f65b3959944559a0d5f6/graphify/benchmark.py#L1-L132)).
It does not run a coding agent, compare with Cursor's native retrieval, check
task success, or include the likely follow-up file reads.

Graphify's broader code benchmark reports improved answer coverage on six
ERPNext questions, but at about 140,000 tokens per query. It is the project's
own harness and does not establish token savings against a modern Cursor agent
([published method](https://github.com/Graphify-Labs/graphify/blob/c9f99018774e2e0380e9f65b3959944559a0d5f6/BENCHMARKS.md#L142-L149)).

#### Maturity, operations, and privacy

Graphify 0.9.55 is Apache-2.0, requires Python 3.10 or newer, and installs a
large set of tree-sitter grammar packages by default
([package metadata](https://github.com/Graphify-Labs/graphify/blob/c9f99018774e2e0380e9f65b3959944559a0d5f6/pyproject.toml#L1-L46)).
Its release commit passed Python 3.10 and 3.12 tests, the generated-skill
consistency check, and the security scan
([CI run](https://github.com/Graphify-Labs/graphify/actions/runs/33992718367)).

Code-only AST extraction needs no model API. Semantic extraction can
auto-select a remote provider from available API keys, so a controlled pilot
must pass `--code-only` and avoid provider keys. The project says it has no
telemetry, but query metadata is logged locally by default unless
`GRAPHIFY_QUERY_LOG_DISABLE=1` is set
([privacy and logging](https://github.com/Graphify-Labs/graphify/blob/c9f99018774e2e0380e9f65b3959944559a0d5f6/README.md#L567-L569)).

Graph staleness is an operational correctness risk. Every task branch changes
the code, so the index must be built or incrementally refreshed inside that
branch's sandbox. A host index must not be shared across divergent task
branches.

#### Compatibility and cache impact

Graphify's Cursor installer writes an always-applied
`.cursor/rules/graphify.mdc`
([integration behavior](https://github.com/Graphify-Labs/graphify/blob/c9f99018774e2e0380e9f65b3959944559a0d5f6/README.md#L310-L324)).
That is not proof that the headless Cursor Agent CLI in Sandcastle will choose
the graph over its native search. The always-on rule also consumes prompt
tokens on every turn and changes the cache prefix. A narrower MCP registration
plus one short optional instruction would be safer in a later A/B.

Graphify output is dynamic, so putting it near the front of a prompt would
damage cache reuse. Used as a late tool result, it should leave the stable
system and ticket prefix intact, but its result may simply be added to normal
file reads. Net savings require fewer later reads.

**Decision:** do not pilot or integrate now. Revisit only after the product
source grows beyond about 10,000 lines, agents show repeated navigation misses,
or baseline measurements show that exploratory reads dominate input. Do not add
its rule, MCP server, generated graph, or dependency to the repository now.

### NeuralMind: benchmark baseline invalid for this decision

#### What worked and what did not

`neuralmind==3.9.0` installed with `uvx`, generated an index for the cloned
repository, and answered CLI queries. Its benchmark printed:

- average query context: 1,188 tokens
- claimed average reduction: `42.1x`
- targeted Docker/Cursor query context: 1,141 tokens
- targeted claimed reduction: `43.8x`

The ratio is mathematically correct only against the implementation's constant
`estimated_full_codebase_tokens = 50000`
([benchmark source](https://github.com/dfrostar/neuralmind/blob/33fd3f62fdcaa04ad635a46507b29bb67f623710/neuralmind/core.py#L1691-L1752)).
It is not measured from this repository and is not a Cursor baseline.

More importantly, the targeted result did not identify
`.sandcastle/main.mts`, the file that actually creates the Docker sandbox and
selects `sandcastle.cursor`. A smaller context that omits the answer is a
correctness loss, not a token saving.

The project itself discloses the main benchmark limitations: its headline is
retrieval input versus loading every code file, not total bill reduction; it
has not rigorously measured marginal benefit over Cursor's retrieval; and it
does not have strong end-to-end faithfulness or real-workload evidence
([honest assessment](https://github.com/dfrostar/neuralmind/blob/33fd3f62fdcaa04ad635a46507b29bb67f623710/docs/HONEST-ASSESSMENT.md#L82-L145)).
The supplied Headroom comparison is therefore useful product positioning, but
not independent evidence.

#### Maturity, maintenance, privacy, and license

The package classifier says Production/Stable, but Cursor, Cline, Continue,
and Codex are all explicitly marked theoretical in the compatibility matrix
([README](https://github.com/dfrostar/neuralmind/blob/33fd3f62fdcaa04ad635a46507b29bb67f623710/README.md#L68-L87)).
Recent PR CI passed Ubuntu tests and fresh installs on Python 3.10 to 3.12,
macOS and Windows tests on Python 3.12, package building, lint, and type checks
([CI run](https://github.com/dfrostar/neuralmind/actions/runs/34084049415)).
A separate self-benchmark run passed its benchmark and backend-parity jobs
([benchmark CI](https://github.com/dfrostar/neuralmind/actions/runs/34084049467)).
The test investment is meaningful, but it does not replace a physical Cursor
integration test.

NeuralMind says the engine and index run locally
([README](https://github.com/dfrostar/neuralmind/blob/33fd3f62fdcaa04ad635a46507b29bb67f623710/README.md#L142-L146)).
The smoke test downloaded Python packages and embedding-model assets during
first use, then wrote a 2.4 MB untracked `graphify-out/` directory, including a
1.5 MB TurboVec index. A production image would need pinned artifacts,
controlled model downloads, branch-local index paths, and explicit cleanup.

The project is open-core. The retrieval engine, MCP server, hooks, and token
savings are MIT, while `neuralmind/tier2/` uses a commercial source-available
license
([licensing boundary](https://github.com/dfrostar/neuralmind/blob/33fd3f62fdcaa04ad635a46507b29bb67f623710/LICENSING.md#L1-L39)).
That boundary is workable for a one-user local trial but adds a license review
before broader team or embedded use.

Persistent learned associations are branch-sensitive state. They can improve
retrieval, but they also make paired runs less reproducible and can surface
stale relationships after a rebase. A first evaluation would need learning
disabled or the same frozen index supplied to both arms.

**Decision:** reject for this project now. The local retrieval miss and
theoretical Cursor support outweigh the claimed ratio.

### Caveman: engine works, product fit does not

#### Keep the skill and engine separate

The MIT response skill supports Cursor through general skill installation, but
it only shortens model output
([installation and scope](https://github.com/JuliusBrussee/caveman/blob/15581d14007fd01fb3f132016741962f34936ca2/README.md#L79-L129)).
The maintainer states that its rules cost about 1,000 to 1,500 input tokens per
turn and documents a Cursor A/B where total tokens and wall time regressed,
although that run was not reproducible
([Honest Numbers](https://github.com/JuliusBrussee/caveman/blob/15581d14007fd01fb3f132016741962f34936ca2/docs/HONEST-NUMBERS.md#L29-L47)).
Sandcastle's own prompts already require terse structured endings. Another
large style instruction is likely negative value.

The separate BSL engine and proxy compress input. The native wrapper table
lists ten agents, but not Cursor
([wrapper matrix](https://github.com/JuliusBrussee/caveman/blob/15581d14007fd01fb3f132016741962f34936ca2/README.md#L302-L330)).
Cursor therefore has the same unproved proxy seam as Headroom, with less direct
support.

#### What worked

The Caveman CLI and engine installed into an isolated temporary home. The
engine compressed the same 400-row synthetic JSON log:

- input: 29,500 bytes
- visible compressed output: 695 bytes
- byte reduction: 97.6%
- critical `FATAL` text preserved: yes
- CCR recovery handle returned: yes
- recovered original SHA-256 matched byte for byte: yes

The 97.6% result is specific to highly repetitive synthetic JSON. It is not a
token count or an agent-quality result. The installed Caveman home consumed
about 177 MB, mostly companion binaries.

The project's strongest wrap report claims 33.2% lower
provider-reported input across 18 paired Claude Code runs with exact answers in
all Caveman arms. It also reports a negative HTML case. The report says its raw
harness and run artifacts are not public, so the result cannot be independently
reproduced from the checkout
([report and limitation](https://github.com/JuliusBrussee/caveman/blob/15581d14007fd01fb3f132016741962f34936ca2/docs/WRAP-BENCHMARK.md#L1-L38),
[reproducibility](https://github.com/JuliusBrussee/caveman/blob/15581d14007fd01fb3f132016741962f34936ca2/docs/WRAP-BENCHMARK.md#L82-L105)).
It is also Claude Code evidence, not Cursor Agent CLI evidence.

#### Maintenance, privacy, and license

The installer release passed Node 18, 20, and 22 jobs, plus Python, macOS, and
Windows PowerShell jobs
([CI run](https://github.com/JuliusBrussee/caveman/actions/runs/33820914292)).
The engine release workflow separately passed Go, TypeScript, Python,
extension, Windows, and root-surface jobs
([engine CI](https://github.com/JuliusBrussee/caveman/actions/runs/33820914303)).
The project is active, but the split packages, downloadable binaries, proxy,
MCP server, recovery store, and telemetry create more operational surface than
the other options.

The CLI sends anonymous command and token-count telemetry by default. It says
prompts, code, and paths are excluded, and supports `caveman telemetry off` or
`DO_NOT_TRACK=1`
([privacy disclosure](https://github.com/JuliusBrussee/caveman/blob/15581d14007fd01fb3f132016741962f34936ca2/README.md#L352-L366)).

The skill, CLI, and thin SDKs are MIT. The engine, proxy, MCP binary, and other
engine-linked components are BSL-1.1. First-party self-hosting is allowed, but
third-party hosted, managed, or embedded service use requires a commercial
license. Versions convert to Apache-2.0 on the stated change date
([license boundary](https://github.com/JuliusBrussee/caveman/blob/15581d14007fd01fb3f132016741962f34936ca2/LICENSING.md#L1-L68)).

**Decision:** reject both forms. The skill likely adds net input on these
already-directed agents. The engine has no proven Cursor route and carries a
less favorable license and larger runtime.

## Comparative risk and expected savings

### Correctness

- Direct compressors can remove a rare line, field, or ordering cue. Recovery
  helps only if the model notices that something is missing and calls the
  recovery tool.
- Retrieval tools can omit the right file entirely. The NeuralMind smoke test
  demonstrated this more serious failure mode.
- The implementation and review prompts are specifications. They should never
  be compressed. Restrict any future direct-compression trial to newly
  generated tool results above a measured size threshold.

### Cache impact

- Stable Sandcastle prompt files and issue context are good cache-prefix
  candidates. Do not rewrite them.
- Graphify's always-on rule and Caveman's skill enlarge and alter that prefix.
- Late tool results do not change earlier prefix bytes, but can increase total
  context if they do not replace later reads.
- Headroom's live-zone design is the only candidate explicitly built to
  preserve a frozen cache prefix. Provider-reported cache reads and writes must
  still be included in the A/B metric.

### Realistic expected savings for this repository

- **Headroom:** 0% today because no verified Cursor proxy route exists.
  Conditional upside is concentrated in large repetitive command output,
  logs, and JSON. The local 66% component result must not be applied to total
  session tokens.
- **Graphify:** unknown and likely modest. The current prompt already tells the
  agent where to start. Savings occur only when a graph call replaces more
  tokens of search and file reads than the graph tool and instruction consume.
- **NeuralMind:** unproved and potentially negative. The `42.1x` ratio is
  against a hard-coded naive baseline, and the relevant-file miss creates a
  retry and correctness risk.
- **Caveman skill:** likely negative for Sandcastle because fixed instructions
  repeat while final outputs are already short and structured.
- **Caveman engine:** 0% today because it is not on the Cursor path. Its local
  synthetic result demonstrates capability, not usable savings.

## Measurement-first pilot

### Phase 0: establish the actual baseline

Run at least 20 representative historical Task issues from pinned commits in
fresh Sandcastle sandboxes with the same Cursor CLI, model, Docker image, and
timeouts. Include small and large diffs, test failures, merge conflicts, and
large command output.

Capture per run:

- provider-reported uncached input, cache-read input, cache-write input, and
  output tokens;
- total requests, retries, and context-limit events;
- implementation, review, and merge wall time;
- `just accept`, `just verify`, and `just check` outcomes;
- reviewer verdict and human review of criterion coverage.

If Cursor or Sandcastle does not expose trustworthy provider counters, stop.
Characters, words, or a tool's own ratio are not adequate substitutes for a
bill-saving decision.

### Deferred Phase 1: Graphify shadow evaluation

Run this phase only after the product source exceeds about 10,000 lines or
Phase 0 shows that exploratory search and file reads are a material share of
provider input. For each pinned historical commit:

1. Build `graphifyy==0.9.55` with `--code-only` in a temporary, branch-local
   directory. Set `GRAPHIFY_QUERY_LOG_DISABLE=1` and deny network.
2. Query using the Task title, Criteria, and Seams, while withholding the
   ticket's `Touches` line from the query.
3. Compare top returned files with the `Touches` files, files cited by the
   Feature or ADR, and non-generated files in the accepted diff.
4. Record index build time, query time, response tokens, primary-file recall,
   irrelevant-file count, and whether the response exceeded its budget.

Proceed to an agent A/B only if:

- at least 95% of declared `Touches` files appear in the first 1,500 tokens;
- no Task has zero recall for its primary implementation file;
- at least 80% of returned file references exist at the pinned commit;
- median build plus query time is under 10 seconds per fresh task sandbox;
- no source, query, or index data leaves the container;
- a human judges that the returned context can replace, rather than supplement,
  at least one normal exploration step on half the Tasks.

### Phase 2: paired agent A/B

If Phase 1 passes, register a pinned branch-local Graphify MCP process in an
ephemeral sandbox config. Do not install the always-applied Cursor rule and do
not commit generated indexes. Add only a short instruction that the tool is
optional and that ticket `Touches` remains authoritative.

Run each Task twice from the same commit with arm order randomized:

- control: current Sandcastle;
- treatment: current Sandcastle plus Graphify MCP.

Success requires all of:

- at least 15% lower median provider-reported total input after including cache
  reads and cache writes;
- no increase in failed acceptance checks, blocked reviews, incorrect files,
  or human-found criterion misses;
- no more than 10% regression in p95 wall time;
- no reduction greater than 5 percentage points in prompt-cache hit rate;
- the treatment actually replaces file reads rather than adding graph calls on
  top of the same reads in at least half the runs.

Rollback immediately if any treatment run omits a required criterion, edits a
wrong module due to stale retrieval, leaks repository content, or increases
median total billed tokens. Rollback consists of removing the ephemeral MCP
entry and the one optional instruction, stopping index creation, and deleting
the temporary graph directory. No application code, contracts, database
schema, or tracker state should be touched by the pilot.

### Conditional Headroom pilot

Run this only after a pinned Cursor Agent CLI is proven to route all relevant
requests through a local Headroom proxy in Docker and recovery tools are
available to the same agent session.

Pin Headroom, set `HEADROOM_BEACON=off`, deny unrelated egress, preserve all
Sandcastle prompts unchanged, and initially compress only tool results above
8,000 tokens. Use paired tasks and the same success criteria as Phase 2, plus:

- exact preservation tests for errors, failed-test names, paths, and exit
  status;
- successful byte-exact CCR recovery;
- no cache-hit regression against the control;
- fail-open passthrough when the proxy or compressor errors.

Do not pilot Headroom by compressing `ISSUE_CONTEXT`, plan JSON, review JSON, or
merge instructions.

## Final recommendation

1. **Now:** integrate none. Add token and cache measurement before optimization.
2. **Deferred experiment:** reconsider Graphify in offline shadow mode only
   after the repository or measured exploration cost crosses the stated
   trigger.
3. **First possible production compressor:** Headroom, but only after the
   headless Cursor proxy route is proven and a paired trial passes.
4. **Rejected:** NeuralMind 3.9.0 because its local retrieval missed the key
   implementation file and its ratio uses a naive fixed baseline.
5. **Rejected:** Caveman skill and engine because the skill's recurring prompt
   cost is a poor fit, the engine lacks a Cursor wrapper, its benchmark is not
   publicly reproducible, and the required runtime is BSL-licensed.

This preserves the current correctness-focused Sandcastle prompts and keeps the
pilot reversible. Most importantly, it evaluates total provider usage at held
task quality, not a component's compression ratio against a whole-repository
baseline.
