# Route conversations through typed, scope-bound interactions

Flash Trips will treat conversation as a transport façade over explicit Conversation Scopes and typed handlers, not as an autonomous authority over Trips. Every Turn belongs to `Guest General`, `Authenticated General`, `Trip Intake`, or a `Trip Workspace` bound to one Trip and visible Plan Revision. Neither a model nor conversational text may infer ownership, silently select or switch a Trip, mutate canonical state, approve a decision, or choose a workflow transition.

## Routing

Each Turn has exactly one primary category from this closed taxonomy: greeting or social; general travel question; Trip Request intake contribution; Trip-grounded read-only question; Run status or explanation; Plan Amendment request; Approval response; application command or help; unsupported or high-risk; ambiguous or multi-intent.

Routing follows fixed precedence: validate session and Conversation Scope; recognise signed or structured application actions; apply deterministic protocol rules for pending intake, amendment, Approval Request, clarification, and cancellation interactions; then use a small model only to classify remaining natural-language Turns. The classifier returns typed intent references, uncertainty, and possible secondary intents. Schema-invalid, contradictory, unavailable, or insufficiently confident classification fails closed to one focused Pending Clarification for anything that could affect state.

Multi-intent Turns may be decomposed into typed proposals for explanation, but at most one state-changing interaction proceeds at a time. A read-only answer may accompany a proposed mutation. An Approval response mixed with another intent cannot create an Approval and must return to the exact Approval Request.

## Handler and grounding boundaries

Greetings and application help use deterministic responses where practical. General travel questions may use a small model only over a validated Evidence packet. Trip-grounded questions use canonical Trip and Plan Revision records plus valid Evidence. Intake, amendments, approvals, cancellation, and commands use dedicated typed handlers rather than a general chatbot. Exact reasoning profiles and cost ceilings remain separate model-routing decisions.

Handlers receive minimal category-specific context. Canonical records, the visible Plan Revision, pending requests, and validated Evidence are authoritative; conversation history is untrusted supporting context and is not passed wholesale by default. Handler outputs are typed outcomes containing validated answer content, Evidence references, scope and revision references, clarification needs, and proposed actions. Deterministic application code creates actionable identifiers and controls; model prose cannot manufacture citations, commands, or state transitions.

Externally verifiable travel claims require applicable current Evidence and citations, including safety, health, weather, prices, availability, opening constraints, and routes. Trip-grounded answers identify the visible Plan Revision and distinguish committed facts from current observations. Greetings, clarification prompts, application help, and Run-status descriptions do not require external citations. Missing, stale, contradictory, or out-of-scope Evidence produces a limitation or a typed refresh action, never an answer from model memory.

A grounded question authorises only the route's predeclared read-only lookups within the later model and external-cost policy. It never authorises inventory planning or canonical mutation, and Guest Sessions cannot perform inventory searches. When new validated Evidence contradicts committed information, the Plan Revision remains immutable; deterministic policy may derive `Revalidation Required`, invalidate affected delivery eligibility or approvals, and offer a refresh Run or Plan Amendment.

## Interaction safeguards

Before the first Plan Revision, confirmed corrections refine the Trip Request. Afterwards, a requested change is interpreted as an untrusted Amendment Proposal bound to one base revision. The proposal shows each typed change, downstream impact, invalidation, and unresolved ambiguity. One cohesive proposal may contain multiple atomic changes, but Planner confirmation through a bound action is required before it becomes one Plan Amendment and may start a mutating Run. A structured form may supply confirmation directly.

An Amendment Proposal expires when its base revision changes and is never silently rebased or partially applied. Revising an unconfirmed proposal creates a new fingerprint and supersedes the previous proposal. An active mutating Run prevents another amendment from being confirmed or queued; any captured intent must be reinterpreted against the visible revision after that Run terminates. An undo request creates a new Amendment Proposal restoring selected earlier values rather than rolling back or deleting revisions.

Free-text agreement, rejection, cancellation, or dismissal never creates an authoritative action. Approval and rejection require a bound action identifying the exact Approval Request and reviewed fingerprint. Conditional approval is not Approval. Only one state-changing decision interaction is presented at a time per Trip; canonical Approval Requests are exposed in deterministic order. Requesting changes first closes the exact Approval Request, then begins a separately confirmed amendment flow.

Natural language may propose starting, opening, or switching a Trip, but the transition requires explicit confirmation. Similarly, a bound action may dismiss a Pending Clarification or unconfirmed proposal, while cancellation of an active Run requires confirmation bound to that Run and never deletes the Trip or rolls back a Plan Revision. Guest conversation content remains non-authoritative after sign-in and must be explicitly confirmed into Trip Intake.

Unsupported booking, payment, cancellation, reservation, disruption, immigration, legal, medical, and other high-risk requests return a typed boundary response and supported alternatives without invoking a planning workflow. Imminent-safety language uses deterministic escalation content and official emergency sources while stating that Flash Trips is not an emergency service.

Classification, retrieval, validation, and generation failures return a typed failure with safe recovery actions. They cannot emit uncited factual claims, partially validated actions, or mutations. Detailed transport contracts and idempotency, trace storage, model and provider budgets, security controls, and interaction presentation remain owned by their dedicated architecture decisions.
