# Use a capability-oriented modular monolith

Flash Trips will begin as a capability-oriented modular monolith with ports and adapters at genuine external seams. A deep `TripPlanning` module exposes submission, replayable observation, and authoritative reads; a chat-facing transport adapter presents convenient conversation operations; an internal compile-time capability registry declares dependencies and invalidation; and a separate read-only `RunInspector` explains execution. LangGraph is private workflow machinery for branching, parallel work, retries, and approval interruption, while PostgreSQL Plan Revisions, Evidence, approvals, and Trip Handbook snapshots remain canonical application records and graph checkpoints contain execution progress only.

## Considered Options

- An agent-centric LangGraph supergraph was rejected because it would make orchestration topology, graph state, and agent implementation part of the product architecture and repeat Wanderlisted's concentration of responsibilities.
- Distributed agent microservices were rejected because the invitation-only stage does not justify distributed consistency, message ordering, operational, and debugging costs.
- A conversation-only application interface was rejected as the canonical seam because it would couple the planning core to one user experience, though the transport adapter may provide that façade.

## Consequences

Flash Trips is initially deployed as one backend application, with a worker added only when operational evidence requires it. Its authoritative capability modules are Trip Request, Trip Structure, Air Travel, Accommodation, Dining, Activities, Ground Transport, Travel Readiness, Budget, Itinerary, and Plan Assembly. Dining and Activities remain separate even where they reuse non-authoritative place types, normalisation utilities, or provider adapters. Plan Assembly owns run-local portfolios, deterministic constraint feedback, and bounded repair; it does not own provider search, money, route measurement, or schedule feasibility.

Evidence Ledger, Approval, Route Measurement, Workflow Compiler and executor, Reasoning Runtime, RunInspector, and Handbook Compiler are supporting modules with narrower authority. Provider adapters retrieve and normalise typed observations; capability modules decide eligibility, freshness, scope, and Evidence sufficiency. Models may rank or explain validated candidates, but deterministic policy accepts or rejects every proposed selection. No module becomes a separate service merely because it uses a model or appears as a graph step.
