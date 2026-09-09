from dataclasses import dataclass
from datetime import date
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

from .persistence import (
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
                await unit_of_work.plan_revisions.commit(
                    PlanRevisionRecord(
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
                )
            return await unit_of_work.runs.record_terminal(run.id, terminal_outcome)

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

    def _unit_of_work(self, principal: PlannerPrincipal) -> UnitOfWork:
        if self._unit_of_work_factory is None:
            raise RuntimeError("Trip persistence is not configured")
        return self._unit_of_work_factory(principal)
