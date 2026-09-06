# Use normalized PostgreSQL with explicit retention

Flash Trips will use one normalized PostgreSQL database as its relational source of truth rather than reconstructing current state from an event log. One linear migration history will manage logical schemas for identity, planning, execution, Evidence, Approval, handbook, inspection, replay, and security ownership. Cross-schema foreign keys and atomic commits are permitted through the shared unit of work; there are no databases or schemas per Planner.

The Run lifecycle remains `accepted → running ↔ awaiting_approval → succeeded | blocked | failed | cancelled`. Context supersession is `blocked: context_changed`, Planner rejection is `cancelled: planner_rejected`, and `superseded` is not another Run state.

## Storage classes and ownership

Storage has three explicit classes:

- **Immutable canonical records** include complete Plan Revision snapshots and revision-owned records, accepted Evidence, Approval Requests and decisions, Handbook Snapshots and Exports, accepted Run inputs, attempts, Inspection Records, Replay Bundles, and idempotency outcomes.
- **Small mutable controls** include Trip heads and control versions, Run state and leases, Planner Access Status, sessions, and outbox delivery state. Required lifecycle history is also recorded append-only.
- **Disposable execution records** include Execution Checkpoints, proposals, Provisional Selections, rejected Provider Observations, and other transient artefacts. Canonical tables never reference them. Acceptance inserts a new canonical identity with source lineage, validator and policy versions, and an accepted Fingerprint; a transient row is never promoted in place.

A Trip always has a non-null owning Planner. External Identities map to application-owned Planners. Guest Session and Guest Intake Transfer storage are deferred from the invitation-only release and need not exist in its initial schema. If later introduced, Guest Sessions form a separate ownership root and cannot own Trips, revisions, Evidence, Approvals, or handbooks; Guest Intake Transfer atomically copies selected details into a new authenticated Trip Request and marks the transfer consumed without changing ownership of guest records.

Each Plan Revision is a complete immutable normalized snapshot with a sequential Trip-local revision number and base-revision reference. Current truth is not reconstructed from amendment deltas. Composite Trip-scoped references prevent cross-Trip attachment.

Provider Observations are immutable and Run-scoped. Acceptance creates separate immutable Evidence with validator and policy versions, scope, Fingerprint, and source Run. Plan Revisions bind accepted Evidence through immutable snapshot membership. Rejected observations remain Inspection Records or transient Run artefacts.

An Approval Request is immutable and has at most one immutable terminal resolution: approved, rejected, expired, or superseded. Pending means no resolution exists. Later context changes affect derived validity without rewriting the historical request or decision.

Pre-commit planning Approval Requests represent uncommitted proposed results and persist the proposed-result Fingerprint, accepted base Plan Revision, exact Evidence, and policy. They do not reference an uncommitted result as a Plan Revision. Post-commit Handbook delivery Approval Requests represent an already committed Plan Revision and persist that revision plus the exact eligible snapshot inputs. The distinct subjects and bindings are enforced as separate record kinds and typed actions.

Handbook storage separates the immutable snapshot manifest, schema-versioned canonical document, exact format-specific export bytes, checksums, and delivery records. Snapshot Fingerprints deduplicate equivalent output; no mutable `latest handbook` record exists.

Existing superseded Handbook Snapshot bytes remain eligible for explicit historical delivery with a prominent warning. Safety, privacy, ownership, or access revalidation blocks historical byte delivery. Evidence, provider, link, or policy invalidation blocks current delivery and regeneration but does not by itself block otherwise lawful explicit historical delivery.

Idempotency receipts preserve principal, command kind, target, key, canonical request hash, expected revision or control version, resulting status, and frozen response reference for 30 days. They are committed atomically with the bounded mutation or accepted Run. During that period, exact reuse replays the original status and response; another payload conflicts. After 30 days, the response is removed and a minimal non-sensitive tombstone remains for the affected durable record's lifetime. Later reuse returns a typed expired-key conflict and never executes again.

Inspection Records and segment manifests remain append-only. Replay Bundles contain immutable manifests and only allowlisted, lawfully retained, versioned, and hashed fixture artefacts. Verification Replays are separate non-canonical executions linked to the source Run and bundle; they cannot use canonical commit paths, create Approvals, or call live dependencies. Missing lawful material yields `unavailable`.

## Constraints, transactions, and representation

PostgreSQL enforces local structural truth with foreign keys, `NOT NULL`, uniqueness, checks, and composite Trip-scoped references. Cross-record domain validity remains in the deterministic commit coordinator under explicit locks. Workflow triggers and stored procedures are excluded.

Canonical mutations use `READ COMMITTED` plus `SELECT … FOR UPDATE` on the relevant Trip, Run, and Approval records. A partial unique index enforces one active mutating Run per Trip. Executors claim work through leases and `FOR UPDATE SKIP LOCKED`; advisory locks are unnecessary. Provider or model calls and checkpoint writes never hold canonical transactions open.

UUIDv7 values use `uuid`; system time uses `timestamptz`; travel time uses `date`, local `time`, and validated IANA-zone text. Money uses bounded `numeric` plus ISO currency and never floating point. Hashes use length-checked `bytea`; closed states use text with explicit checks; exact exports use `bytea`. PostgreSQL enum types are excluded so closed states remain explicitly migratable.

Invariant-bearing ownership, identities, relationships, states, money, dates, Fingerprints, and versions use relational columns. JSONB is limited to bounded immutable documents, adapter artefacts, diagnostics, and disposable checkpoints. Every structured payload carries schema name, major and minor versions, canonicalisation version, and content hash. Additive changes use minor versions and semantic breaks use major versions. Readers or upcasters remain available for every retained version; historical Evidence, inspection, replay, and handbook payloads are never rewritten. Unrestricted raw model and provider payloads are not retained.

## Migrations, access, and indexes

The modular monolith uses one linear Alembic history. Changes are classified as expand, restartable bounded backfill, or contract. The current schema supports the current and immediately previous application images so binary rollback remains possible. Migrations run as an explicit deployment step, never at application startup. Concurrent index creation is an explicit non-transactional step. Production rejects multiple migration heads, unknown schema versions, and incompatible application and schema combinations. Backup restoration is disaster recovery rather than routine schema rollback.

Each environment has separate migration-owner and runtime roles. Runtime receives necessary DML but no DDL, ownership, replication, or bypass privilege. Cross-module transactions preclude module-specific credentials initially. Operators and other humans receive no routine production database access.

Indexes cover every foreign-key access path and accepted ownership, revision, active-Run, executable-lease, Approval-expiry, Evidence-Fingerprint, handbook-Fingerprint, idempotency, Run-event, outbox, and retention query. Speculative indexes and JSONB GIN indexes are excluded until measurements justify them. Initial tables are not partitioned; measured volume, vacuum behaviour, or deletion cost must justify partitioning.

## Retention, deletion, and restoration

Trips are automatically deleted 24 months after the later of travel completion and meaningful Planner activity, with advance warning, unless the Planner explicitly deletes the Trip sooner. Closing Planner access begins a 30-day deletion grace period; explicit privacy deletion bypasses it.

Initial retention limits are:

- If the deferred Guest surface is introduced, Guest content follows the accepted 24-hour inactivity and seven-day absolute limits; transferred content is purged within 24 hours.
- Checkpoints remain while resumable and for seven days after a terminal Run.
- Unaccepted observations and transient Run artefacts remain for 30 days.
- Exact idempotency status and response receipts remain for 30 days after completion; minimal non-sensitive key tombstones remain for the affected durable record's lifetime. Delivered outbox rows remain for seven days.
- Expired sessions and Invitation contact data remain for 30 days.
- Runs, public events, Inspection Records, accepted Evidence, Approvals, revisions, Replay material, and handbooks follow their owning Trip, subject to lawful fixture-retention limits.
- Minimized Security Audit Records remain for one year, subject to earlier removal of identifiable links when privacy deletion requires it.

Deletion immediately denies access and marks the ownership root `deletion_pending`, then an idempotent job hard-deletes the sensitive graph. Cascades apply only within clearly owned aggregates and `RESTRICT` applies across ownership roots. Completion requires orphan verification and creates only a non-identifying Deletion Receipt. Ordinary soft deletion is not privacy deletion.

There is no informal Operator legal-hold feature. Any future preservation duty requires a separately reviewed decision and cannot be inferred from Operator authority.

Production keeps 35 days of point-in-time recovery; non-production keeps seven days and never receives production data. Deletion commands also enter a restricted append-only Azure Blob ledger outside the database restore boundary. It contains only HMAC-derived Planner or Trip identifiers, deletion scope, timestamp, and Key Vault key version—never email or external identity subjects—and remains for 42 days. A restored database is scrubbed against this ledger and verified before serving traffic.

## Conformance

Persistence tests use real PostgreSQL rather than SQLite. They cover every constraint and immutable-table rule; concurrent Run acceptance, Approval, commit, cancellation, lease recovery, and idempotent replay; migration from every supported schema and rollback to the previous image; retention and hard deletion; orphan detection; backup restoration and deletion-ledger replay; checkpoint-to-canonical isolation; and byte-for-byte preservation of historical Handbook Exports and immutable Plan Revision history across upgrades.
