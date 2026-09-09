from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from flash_trips.capabilities.travel_readiness import (
    TravelReadinessInput,
    TravelReadinessRefusalReason,
    TravelReadinessResult,
)
from flash_trips.kernel.capability import (
    Capability,
    CapabilityComplete,
)
from flash_trips.kernel.identifiers import uuid7
from flash_trips.kernel.service_status import ServiceStatus
from flash_trips.platform.handbook import (
    HandbookClaim,
    compile_document,
    render_html,
)

from .persistence import (
    ApprovalRecord,
    ApprovalRequestRecord,
    BoundApprovalAction,
    HandbookNotEligibleError,
    HandbookNotFoundError,
    HandbookSnapshotRecord,
    PlanClaimKind,
    PlanClaimRecord,
    PlannerPrincipal,
    PlanRevisionRecord,
    RunRecord,
    RunTerminalOutcome,
    RunTerminalStatus,
    TripRecord,
    TripStayRecord,
    TripStructureRecord,
    UnitOfWork,
    UnitOfWorkFactory,
)
from .ports import ServiceStatusPort

# SKELETON_REPLACEMENT: issue 204 (FT-03) deepens this thin Trip station.
# SKELETON_REPLACEMENT: issue 216 (FT-14) deepens this thin Plan Revision station.
# SKELETON_REPLACEMENT: issue 200 (FT-21) deepens this thin Approval station.
# SKELETON_REPLACEMENT: issue 220 (FT-22) deepens this thin Handbook station.
# SKELETON_REPLACEMENT: issue 224 (FT-24) deepens this thin Handbook delivery.

_FAILED_RUN_OUTCOME = RunTerminalOutcome(
    status=RunTerminalStatus.FAILED,
    code="application_failure",
    detail="The Run failed before completion.",
)


class UnsupportedTripStructureError(ValueError):
    """The requested structure is valid data but unsupported by current policy."""


class TripNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class NewTripStay:
    city: str
    starts_on: date
    ends_on: date
    nights: int


class TripPlanning:
    """Typed application interface for Flash Trips use cases."""

    def __init__(
        self,
        service_status: ServiceStatusPort,
        unit_of_work_factory: UnitOfWorkFactory | None = None,
        travel_readiness: Capability[
            TravelReadinessInput,
            TravelReadinessResult,
            TravelReadinessRefusalReason,
        ]
        | None = None,
    ) -> None:
        self._service_status = service_status
        self._unit_of_work_factory = unit_of_work_factory
        self._travel_readiness = travel_readiness

    def service_status(self) -> ServiceStatus:
        return self._service_status.read()

    async def create_trip(
        self,
        principal: PlannerPrincipal,
        stays: tuple[NewTripStay, ...],
    ) -> TripRecord:
        if len(stays) != 1:
            raise UnsupportedTripStructureError(
                "The current Trip policy requires exactly one city stay"
            )
        trip = TripRecord(
            id=uuid7(),
            planner_id=principal.planner_id,
            structure=TripStructureRecord(
                stays=tuple(
                    TripStayRecord(
                        id=uuid7(),
                        city=stay.city,
                        starts_on=stay.starts_on,
                        ends_on=stay.ends_on,
                        nights=stay.nights,
                    )
                    for stay in stays
                )
            ),
        )
        async with self._unit_of_work(principal) as unit_of_work:
            await unit_of_work.trips.add(trip)
        return trip

    async def list_trips(self, principal: PlannerPrincipal) -> list[TripRecord]:
        async with self._unit_of_work(principal) as unit_of_work:
            return await unit_of_work.trips.list()

    async def get_trip(
        self,
        principal: PlannerPrincipal,
        trip_id: UUID,
    ) -> TripRecord | None:
        async with self._unit_of_work(principal) as unit_of_work:
            return await unit_of_work.trips.get(trip_id)

    async def start_run(
        self,
        principal: PlannerPrincipal,
        trip_id: UUID,
    ) -> RunRecord:
        async with self._unit_of_work(principal) as unit_of_work:
            trip = await unit_of_work.trips.get(trip_id)
            if trip is None:
                raise TripNotFoundError(trip_id)
            run = RunRecord(
                id=uuid7(),
                planner_id=principal.planner_id,
                trip_id=trip.id,
            )
            await unit_of_work.runs.add(run)

        try:
            capability = self._travel_readiness
            if capability is None:
                raise RuntimeError("Travel Readiness Capability is not configured")
            capability_outcome = await capability.execute(
                TravelReadinessInput(
                    cities=tuple(stay.city for stay in trip.structure.stays),
                )
            )
            if isinstance(capability_outcome, CapabilityComplete):
                if not capability_outcome.value.evidence_references:
                    raise RuntimeError(
                        "A completed Capability result must reference Evidence"
                    )
                terminal_outcome = RunTerminalOutcome(
                    status=RunTerminalStatus.SUCCEEDED,
                    code="fixture_complete",
                    detail=capability_outcome.value.summary,
                )
            else:
                terminal_outcome = RunTerminalOutcome(
                    status=RunTerminalStatus.BLOCKED,
                    code=capability_outcome.reason.value,
                    detail=capability_outcome.detail,
                )
            async with self._unit_of_work(principal) as unit_of_work:
                if isinstance(capability_outcome, CapabilityComplete):
                    current = await unit_of_work.plan_revisions.get_current(trip.id)
                    result = capability_outcome.value
                    revision = PlanRevisionRecord(
                        id=uuid7(),
                        planner_id=principal.planner_id,
                        trip_id=trip.id,
                        run_id=run.id,
                        revision_number=(
                            current.revision_number + 1 if current is not None else 1
                        ),
                        base_revision_id=current.id if current is not None else None,
                        claims=(
                            PlanClaimRecord(
                                id=uuid7(),
                                kind=PlanClaimKind.TRAVEL_READINESS,
                                text=result.summary,
                                evidence_reference=result.evidence_references[0],
                                observed_at=result.observed_at,
                            ),
                        ),
                    )
                    await unit_of_work.plan_revisions.commit(revision)
                    await unit_of_work.approvals.present(
                        ApprovalRequestRecord(
                            id=uuid7(),
                            planner_id=principal.planner_id,
                            plan_revision_id=revision.id,
                        )
                    )
                return await unit_of_work.runs.record_terminal(run.id, terminal_outcome)
        except Exception:
            # The original application failure remains the public behavior.
            with suppress(Exception):
                await self._record_failed_run(principal, run.id)
            raise

    async def get_run(
        self,
        principal: PlannerPrincipal,
        run_id: UUID,
    ) -> RunRecord | None:
        async with self._unit_of_work(principal) as unit_of_work:
            return await unit_of_work.runs.get(run_id)

    async def get_current_plan_revision(
        self,
        principal: PlannerPrincipal,
        trip_id: UUID,
    ) -> PlanRevisionRecord | None:
        async with self._unit_of_work(principal) as unit_of_work:
            return await unit_of_work.plan_revisions.get_current(trip_id)

    async def get_current_approval_request(
        self,
        principal: PlannerPrincipal,
        trip_id: UUID,
    ) -> ApprovalRequestRecord | None:
        async with self._unit_of_work(principal) as unit_of_work:
            revision = await unit_of_work.plan_revisions.get_current(trip_id)
            if revision is None:
                return None
            return await unit_of_work.approvals.get_request(revision.id)

    async def approve_plan_revision(
        self,
        principal: PlannerPrincipal,
        action: BoundApprovalAction,
    ) -> ApprovalRecord:
        async with self._unit_of_work(principal) as unit_of_work:
            return await unit_of_work.approvals.approve(action)

    async def get_approval_for_plan_revision(
        self,
        principal: PlannerPrincipal,
        plan_revision_id: UUID,
    ) -> ApprovalRecord | None:
        async with self._unit_of_work(principal) as unit_of_work:
            return await unit_of_work.approvals.get_approval(plan_revision_id)

    async def compile_current_handbook(
        self,
        principal: PlannerPrincipal,
        trip_id: UUID,
    ) -> HandbookSnapshotRecord:
        async with self._unit_of_work(principal) as unit_of_work:
            revision = await unit_of_work.plan_revisions.get_current(trip_id)
            if revision is None:
                raise HandbookNotEligibleError(trip_id)
            approval = await unit_of_work.approvals.get_approval(revision.id)
            if approval is None:
                raise HandbookNotEligibleError(revision.id)
            existing = await unit_of_work.handbooks.get_for_revision(revision.id)
            if existing is not None:
                return existing
            document = compile_document(
                plan_revision_id=str(revision.id),
                revision_number=revision.revision_number,
                claims=tuple(
                    HandbookClaim(
                        text=claim.text,
                        evidence_reference=claim.evidence_reference.value,
                        observed_at=claim.observed_at,
                    )
                    for claim in revision.claims
                ),
            )
            return await unit_of_work.handbooks.add(
                HandbookSnapshotRecord.create(
                    planner_id=principal.planner_id,
                    plan_revision_id=revision.id,
                    approval_id=approval.id,
                    document_schema_version=document.schema_version,
                    export_bytes=render_html(document),
                )
            )

    async def download_handbook(
        self,
        principal: PlannerPrincipal,
        snapshot_id: UUID,
    ) -> HandbookSnapshotRecord:
        async with self._unit_of_work(principal) as unit_of_work:
            delivery = await unit_of_work.handbooks.deliver(
                snapshot_id,
                datetime.now(UTC),
            )
            if delivery is None:
                raise HandbookNotFoundError(snapshot_id)
            snapshot, _record = delivery
            return snapshot

    def _unit_of_work(self, principal: PlannerPrincipal) -> UnitOfWork:
        if self._unit_of_work_factory is None:
            raise RuntimeError("Trip persistence is not configured")
        return self._unit_of_work_factory(principal)

    async def _record_failed_run(
        self,
        principal: PlannerPrincipal,
        run_id: UUID,
    ) -> None:
        async with self._unit_of_work(principal) as unit_of_work:
            await unit_of_work.runs.record_terminal(run_id, _FAILED_RUN_OUTCOME)
