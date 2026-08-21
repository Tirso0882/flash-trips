# Flash Trips

Flash Trips helps a planner turn a leisure-travel request into an evidence-backed travel plan and an approved trip handbook. It recommends and explains travel options but does not currently book, pay for, cancel, or manage reservations.

## Language

**Planner**:
The person who owns a trip-planning interaction and approves the resulting travel plan for themselves and any companions.
_Avoid_: User, customer, lead traveller

**External Identity**:
A provider-authenticated identity associated with a planner through a stable issuer and subject, never through email equality alone.
_Avoid_: Planner, email identity, login account

**Planner Access Status**:
The application-owned condition that determines whether a planner remains eligible to use authenticated Flash Trips services after accepting an invitation.
_Avoid_: Invitation status, identity-provider status, account status

**Access Recovery Review**:
A bounded review of security-sensitive actions after suspected identity or session compromise that must complete before planning mutations, Approvals, and handbook access resume.
_Avoid_: Revalidation Required, rollback, audit log

**Protective Access Hold**:
A temporary application-owned restriction triggered by strong compromise or abuse signals that revokes active sessions and blocks sensitive operations pending recent authentication or Operator review.
_Avoid_: Planner Access Status, rate limit, permanent suspension

**Security Audit Record**:
An immutable, minimised account of an identity, authorisation, administration, disclosure, recovery, or deletion event, kept separate from Trip content and execution inspection.
_Avoid_: Inspection Record, operational log, Trip history

**Security Incident**:
A suspected or confirmed event threatening confidentiality, integrity, or authorised availability that requires bounded containment, investigation, recovery, and closure.
_Avoid_: Failed Run, ordinary provider outage, support request

**Deletion Receipt**:
A non-identifying record that a bounded privacy deletion completed without retaining the personal data or ownership relationship that was removed.
_Avoid_: Archived record, retained profile, data export

**Operator**:
The person authorised to administer invitations and planner access status without thereby gaining ownership of or access to a planner's trips.
_Avoid_: Planner, identity-provider administrator, trip owner

**Invitation**:
A time-bounded, single-recipient offer of eligibility to become a planner, issued and governed by Flash Trips and accepted at most once.
_Avoid_: Identity-provider invitation, access group, reusable signup link

**Guest Session**:
A temporary browser-bound interaction for an unauthenticated visitor's general, non-personalised travel questions that carries no planner identity or trip ownership.
_Avoid_: Guest account, anonymous planner, anonymous trip

**Guest Intake Transfer**:
A one-time, authenticated, planner-confirmed conversion of selected guest-provided travel details into a new Trip Request without transferring authority from the guest transcript.
_Avoid_: Guest claim, automatic migration, account merge

**Conversation Scope**:
The explicit boundary for a Turn: Guest General, Authenticated General, Trip Intake, or one Trip Workspace bound to its visible Plan Revision.
_Avoid_: Chat mode, inferred trip context, conversation memory

**Turn**:
A single Planner or guest input together with its validated classification and typed conversational outcome within one Conversation Scope.
_Avoid_: Prompt, message blob, agent step

**Pending Clarification**:
A temporary, scope-bound request for the Planner to resolve one ambiguous Turn without granting authority to change a Trip or approve a decision.
_Avoid_: Follow-up chat, assumed intent, implicit confirmation

**Planner Profile**:
The minimal service information and reusable preferences associated with a planner, distinct from any individual trip request or optional marketing information.
_Avoid_: User profile, trip request, marketing profile

**Companion**:
A traveller included in the planner's trip who does not independently own or edit the plan.
_Avoid_: User, collaborator, account member

**Companion Travel Constraint**:
A minimal typed requirement relevant to planning for a companion, recorded without an underlying medical, religious, legal, or other private explanation.
_Avoid_: Companion profile, diagnosis, personal history

**Trip**:
A planned leisure journey covering one or more cities for a planner and optional companions.
_Avoid_: Booking, order, itinerary

**Sensitive Trip Data**:
Private personal information associated with a trip, especially combinations of dates, locations, companions, budgets, and constraints that may reveal a person's movements or circumstances.
_Avoid_: Public destination information, general travel question, Provider Observation

**Trip Request**:
The planner's stated goals, constraints, and requested planning services for a trip.
_Avoid_: Prompt, query, requirements blob

**Trip Structure**:
The validated allocation of a trip's dates, cities, stays, and nights.
_Avoid_: Trip skeleton, trip layout

**Travel Plan**:
The validated, evidence-backed representation of the trip's proposed and approved choices, constraints, and schedule.
_Avoid_: Agent output, response, itinerary

**Plan Amendment**:
A planner-confirmed typed request to change an existing travel plan without silently replacing its established facts or decisions.
_Avoid_: Edit, overwrite, prompt correction

**Amendment Proposal**:
An untrusted typed interpretation of a requested travel-plan change presented to the planner for review before it can become a plan amendment.
_Avoid_: Plan Amendment, accepted edit

**Plan Revision**:
An identifiable version of a travel plan resulting from validated planning work or a validated plan amendment.
_Avoid_: Chat response, draft blob, saved output

**Trip Handbook**:
The delivery artefact derived from an approved travel plan for the planner to use during the trip.
_Avoid_: AI response, report, itinerary

**Handbook Document**:
The schema-versioned, format-neutral semantic content compiled from an eligible plan revision for deterministic handbook rendering.
_Avoid_: JSON handbook, renderer output, mutable report

**Handbook Snapshot**:
An immutable trip-handbook artefact bound to one plan revision, its exact qualifying approvals, evidence snapshot, policy set, and compilation and rendering versions.
_Avoid_: Latest handbook, mutable report

**Handbook Export**:
An immutable format-specific projection of a handbook snapshot delivered for offline use without becoming authoritative planning input.
_Avoid_: Editable handbook, source document, plan import

**Handbook Delivery**:
An authorised retrieval of one handbook export by the owning planner, recorded for audit without constituting approval or proof that the export was opened.
_Avoid_: Handbook approval, view confirmation, public share

**Evidence**:
Sourced information supporting a travel claim or choice, bounded by its origin, observed time, and applicable trip scope.
_Avoid_: Context, search result, knowledge

**Revalidation Required**:
A derived condition indicating that a committed plan revision or handbook can no longer support new delivery because relevant inputs, evidence, or policy no longer satisfy current validation.
_Avoid_: Deleted, automatically invalid

**Provider Market Profile**:
A versioned statement of the bounded roles, markets, modes, date horizons, and currencies for which an external provider is eligible to serve a capability.
_Avoid_: Global support, assumed coverage, provider availability

**Reasoning Profile**:
A versioned purpose-specific contract that deterministically bounds which model-backed interpretation or proposal may run, with what inputs, tools, resource limits, and validation obligations.
_Avoid_: Model size, agent role, self-selected model

**Provider Observation**:
A source-specific, time-bounded external result received from a travel or information provider before domain validation establishes whether it may support a travel plan.
_Avoid_: Provider result, raw fact, recommendation

**Candidate**:
A provider observation that has passed the applicable identity, scope, freshness, eligibility, and evidence checks for possible use in a travel plan.
_Avoid_: Search result, option, recommendation

**Selection Proposal**:
An untrusted, model-ranked suggestion containing only eligible candidates for deterministic evaluation.
_Avoid_: Selection, recommendation result

**Provisional Selection**:
A candidate accepted for budget and feasibility evaluation within a run but not yet committed to a plan revision.
_Avoid_: Selection, confirmed choice

**Plan Portfolio**:
A run-local combination of provisional selections evaluated together for budget coverage and itinerary feasibility.
_Avoid_: Travel Plan, Plan Revision, committed plan

**Selection**:
A validated travel choice committed within a plan revision.
_Avoid_: Candidate, model choice, search result

**Travel Readiness**:
The evidence-backed assessment of destination safety advisories, health notices, and weather risks that may affect a trip, excluding personalised immigration, legal, or medical advice.
_Avoid_: Safety agent, readiness subagent

**Advisory Authority**:
An official government or public-health source explicitly selected for a planner or companion whose audience-specific travel advice remains distinct from global, regional, and other authorities.
_Avoid_: Inferred nationality, default country, universal advisory

**Route Measurement**:
Evidence-backed travel distance and duration between two trip locations for a stated mode and observation time.
_Avoid_: Route guess, model estimate

**Budget Assessment**:
The deterministic account of known and unknown trip costs, currency conversion, coverage, contingency, and the verdict against the planner's target budget.
_Avoid_: Model budget, price estimate

**Target Budget**:
The planner's preferred spending level, which a proposed travel plan may exceed only after explicit disclosure and approval.
_Avoid_: Hard ceiling, guaranteed total

**Hard Budget Limit**:
An explicit spending ceiling that a proposed travel plan cannot exceed without a new plan amendment.
_Avoid_: Target Budget, preference

**External Cost Budget**:
A versioned hard allowance for chargeable model and provider work, enforced independently of the planner's trip spending limits.
_Avoid_: Target Budget, Hard Budget Limit, provider quota

**Feasibility Conflict**:
A typed explanation of why provisional selections cannot satisfy the fixed trip structure, timing, route, opening, or budget constraints.
_Avoid_: Model concern, planning failure

**Constraint Relaxation**:
A typed planner-authorised change that loosens a stated trip preference or constraint after bounded planning cannot produce a valid plan portfolio.
_Avoid_: Silent fallback, automatic compromise

**Approval**:
A planner's recorded decision on a specific proposed change, warning, budget, travel plan, or handbook delivery, bound to the exact revision and facts reviewed.
_Avoid_: Confirmation message, conversational yes

**Approval Request**:
The immutable, bounded decision presented to the planner, identifying the exact revision, evidence, warning, or proposed result to approve or reject.
_Avoid_: Prompt for confirmation, chat question

**Paid Execution Authorization**:
An Operator-controlled, purpose-bound allowance for non-product live model or provider calls, limited by environment, providers, maximum spend, and expiry.
_Avoid_: Approval, Planner consent, unlimited API access

**Run**:
One durable execution of an accepted planning action, with inspectable progress and exactly one terminal outcome.
_Avoid_: Request, graph invocation, agent call

**Fingerprint**:
A deterministic identity binding the exact inputs, dependencies, Evidence, policies, schemas, and implementation versions relevant to a decision, reuse claim, or Approval.
_Avoid_: Record identifier, integrity digest, timestamp

**Execution Checkpoint**:
A durable record of resumable workflow progress that cannot become or override canonical Trip state.
_Avoid_: Approval Gate, Plan Revision, workflow truth

**Approval Gate**:
A workflow pause requiring a Planner decision bound to the exact Approval Request before the Run may proceed.
_Avoid_: Execution Checkpoint, confirmation prompt, free-text agreement

**Inspection Record**:
An immutable, typed account of how a Turn or Run was routed, evaluated, progressed, and brought to an outcome, exposed only through audience-appropriate redacted views.
_Avoid_: Debug log, raw transcript, telemetry span

**Run Reconstruction**:
A read-only explanation of a historical Run derived from its inspection records without executing dependencies or changing canonical state.
_Avoid_: Replay, retry, resume

**Verification Replay**:
A linked, non-canonical execution over recorded logical inputs and frozen or mocked dependency responses that either reproduces the original bound implementation exactly or compares a candidate implementation semantically without mutating canonical state.
_Avoid_: Live rerun, retry, resume, output reuse

**Replay Bundle**:
The access-controlled recorded inputs, dependency responses, versions, and integrity references sufficient to perform a lawful Verification Replay of a Turn or Run.
_Avoid_: Raw trace, live provider refresh, canonical state

**Capability**:
A bounded unit of planning work that consumes established trip information and produces one complete, validated planning result or a typed explanation of why it could not do so.
_Avoid_: Agent, graph node, provider integration
