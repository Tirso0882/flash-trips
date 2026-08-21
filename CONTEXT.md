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

**Operator**:
The person authorised to administer invitations and planner access status without thereby gaining ownership of or access to a planner's trips.
_Avoid_: Planner, identity-provider administrator, trip owner

**Invitation**:
A time-bounded, single-recipient offer of eligibility to become a planner, issued and governed by Flash Trips and accepted at most once.
_Avoid_: Identity-provider invitation, access group, reusable signup link

**Guest Session**:
A temporary browser-bound interaction for an unauthenticated visitor's general, non-personalised travel questions that carries no planner identity or trip ownership.
_Avoid_: Guest account, anonymous planner, anonymous trip

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

**Trip**:
A planned leisure journey covering one or more cities for a planner and optional companions.
_Avoid_: Booking, order, itinerary

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

**Handbook Snapshot**:
An immutable trip-handbook artefact bound to one plan revision, evidence snapshot, policy set, and renderer version.
_Avoid_: Latest handbook, mutable report

**Evidence**:
Sourced information supporting a travel claim or choice, bounded by its origin, observed time, and applicable trip scope.
_Avoid_: Context, search result, knowledge

**Revalidation Required**:
A derived condition indicating that a committed plan revision or handbook can no longer support new delivery because relevant inputs, evidence, or policy no longer satisfy current validation.
_Avoid_: Deleted, automatically invalid

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

**Run**:
One durable execution of an accepted planning action, with inspectable progress and exactly one terminal outcome.
_Avoid_: Request, graph invocation, agent call

**Capability**:
A bounded unit of planning work that consumes established trip information and produces one complete, validated planning result or a typed explanation of why it could not do so.
_Avoid_: Agent, graph node, provider integration
