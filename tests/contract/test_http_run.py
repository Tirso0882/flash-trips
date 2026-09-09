from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from types import TracebackType
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from flash_trips.adapters.service_status import StaticServiceStatus
from flash_trips.application import (
    ActiveRunExistsError,
    ApprovalAlreadyRecordedError,
    ApprovalNotFoundError,
    ApprovalRecord,
    ApprovalRepository,
    ApprovalRequestRecord,
    BoundApprovalAction,
    HandbookDeliveryRecord,
    HandbookExportFormat,
    HandbookRepository,
    HandbookSnapshotRecord,
    NewTripStay,
    PlannerPrincipal,
    PlannerRecord,
    PlannerRepository,
    PlanRevisionRecord,
    PlanRevisionRepository,
    RunRecord,
    RunRepository,
    RunTerminalOutcome,
    RunTerminalStatus,
    TerminalOutcomeAlreadyRecordedError,
    TripPlanning,
    TripRecord,
    TripRepository,
    UnitOfWork,
)
from flash_trips.capabilities.travel_readiness import (
    FixtureTravelReadinessCapability,
    TravelReadinessAssessment,
    TravelReadinessInput,
    TravelReadinessRefusalReason,
    TravelReadinessResult,
)
from flash_trips.composition import create_app
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal
from flash_trips.kernel.capability import (
    Capability,
    CapabilityComplete,
    CapabilityRefusal,
)
from flash_trips.kernel.identifiers import uuid7

PLANNER_ID = UUID("01991e28-1d65-7000-8000-000000000001")
OTHER_PLANNER_ID = UUID("01991e28-1d65-7000-8000-000000000002")


@dataclass(frozen=True, slots=True)
class FakeAccessTokenVerifier:
    def verify(self, access_token: str) -> AuthenticatedPrincipal:
        planner = OTHER_PLANNER_ID if access_token.endswith("other") else PLANNER_ID
        return AuthenticatedPrincipal(
            issuer="https://issuer.example",
            subject=str(planner),
            scopes=frozenset({"principal:read"}),
        )


@dataclass(frozen=True, slots=True)
class FakePlannerResolver:
    async def resolve(self, principal: AuthenticatedPrincipal) -> PlannerPrincipal:
        return PlannerPrincipal(planner_id=UUID(principal.subject))


@dataclass(slots=True)
class MemoryTripRepository:
    principal: PlannerPrincipal
    records: list[TripRecord]

    async def add(self, trip: TripRecord) -> None:
        self.records.append(trip)

    async def get(self, trip_id: UUID) -> TripRecord | None:
        return next(
            (
                trip
                for trip in self.records
                if trip.id == trip_id and trip.planner_id == self.principal.planner_id
            ),
            None,
        )

    async def list(self) -> list[TripRecord]:
        return [
            trip
            for trip in self.records
            if trip.planner_id == self.principal.planner_id
        ]


@dataclass(slots=True)
class MemoryRunRepository:
    principal: PlannerPrincipal
    records: list[RunRecord]

    async def add(self, run: RunRecord) -> None:
        active = next(
            (
                record
                for record in self.records
                if record.trip_id == run.trip_id
                and record.terminal_outcome is None
                and record.planner_id == self.principal.planner_id
            ),
            None,
        )
        if active is not None:
            raise ActiveRunExistsError(active.id)
        self.records.append(run)

    async def get(self, run_id: UUID) -> RunRecord | None:
        return next(
            (
                run
                for run in self.records
                if run.id == run_id and run.planner_id == self.principal.planner_id
            ),
            None,
        )

    async def record_terminal(
        self,
        run_id: UUID,
        outcome: RunTerminalOutcome,
    ) -> RunRecord:
        run = await self.get(run_id)
        if run is None:
            raise LookupError(run_id)
        if run.terminal_outcome is not None:
            raise TerminalOutcomeAlreadyRecordedError(run_id)
        completed = RunRecord(
            id=run.id,
            planner_id=run.planner_id,
            trip_id=run.trip_id,
            terminal_outcome=outcome,
        )
        self.records[self.records.index(run)] = completed
        return completed


@dataclass(slots=True)
class MemoryPlanRevisionRepository:
    principal: PlannerPrincipal
    records: list[PlanRevisionRecord]
    fail_commit: bool = False

    async def commit(self, revision: PlanRevisionRecord) -> PlanRevisionRecord:
        if self.fail_commit:
            raise RuntimeError("sensitive commit failure")
        self.records.append(revision)
        return revision

    async def get_current(self, trip_id: UUID) -> PlanRevisionRecord | None:
        matches = [
            revision
            for revision in self.records
            if revision.trip_id == trip_id
            and revision.planner_id == self.principal.planner_id
        ]
        return max(matches, key=lambda item: item.revision_number, default=None)

    async def get_current_for_id(
        self,
        plan_revision_id: UUID,
    ) -> PlanRevisionRecord | None:
        revision = next(
            (
                item
                for item in self.records
                if item.id == plan_revision_id
                and item.planner_id == self.principal.planner_id
            ),
            None,
        )
        if revision is None:
            return None
        current = await self.get_current(revision.trip_id)
        return revision if current is not None and current.id == revision.id else None


@dataclass(slots=True)
class MemoryApprovalRepository:
    principal: PlannerPrincipal
    store: "MemoryUnitOfWorkFactory"

    async def present(self, request: ApprovalRequestRecord) -> None:
        if self.store.failure_stage == "approval":
            raise RuntimeError("sensitive presentation failure")
        self.store.approval_requests.append(request)

    async def get_request(
        self,
        plan_revision_id: UUID,
    ) -> ApprovalRequestRecord | None:
        return next(
            (
                request
                for request in self.store.approval_requests
                if request.plan_revision_id == plan_revision_id
                and request.planner_id == self.principal.planner_id
            ),
            None,
        )

    async def approve(self, action: BoundApprovalAction) -> ApprovalRecord:
        request = await self.get_request(action.plan_revision_id)
        revision = await MemoryPlanRevisionRepository(
            self.principal,
            self.store.plan_revisions,
        ).get_current_for_id(action.plan_revision_id)
        if (
            request is None
            or request.id != action.approval_request_id
            or revision is None
        ):
            raise ApprovalNotFoundError(action.approval_request_id)
        if await self.get_approval(action.plan_revision_id) is not None:
            raise ApprovalAlreadyRecordedError(action.approval_request_id)
        approval = ApprovalRecord(
            id=uuid7(),
            planner_id=self.principal.planner_id,
            approval_request_id=action.approval_request_id,
            plan_revision_id=action.plan_revision_id,
        )
        self.store.approvals.append(approval)
        return approval

    async def get_approval(self, plan_revision_id: UUID) -> ApprovalRecord | None:
        return next(
            (
                approval
                for approval in self.store.approvals
                if approval.plan_revision_id == plan_revision_id
                and approval.planner_id == self.principal.planner_id
            ),
            None,
        )


@dataclass(slots=True)
class MemoryHandbookRepository:
    principal: PlannerPrincipal
    store: "MemoryUnitOfWorkFactory"

    async def get_for_revision(
        self,
        plan_revision_id: UUID,
    ) -> HandbookSnapshotRecord | None:
        return next(
            (
                snapshot
                for snapshot in self.store.handbook_snapshots
                if snapshot.plan_revision_id == plan_revision_id
                and snapshot.planner_id == self.principal.planner_id
            ),
            None,
        )

    async def add(
        self,
        snapshot: HandbookSnapshotRecord,
    ) -> HandbookSnapshotRecord:
        self.store.handbook_snapshots.append(snapshot)
        return snapshot

    async def deliver(
        self,
        snapshot_id: UUID,
        delivered_at: datetime,
    ) -> tuple[HandbookSnapshotRecord, HandbookDeliveryRecord] | None:
        snapshot = next(
            (
                item
                for item in self.store.handbook_snapshots
                if item.id == snapshot_id
                and item.planner_id == self.principal.planner_id
            ),
            None,
        )
        if snapshot is None:
            return None
        delivery = HandbookDeliveryRecord(
            id=uuid7(),
            planner_id=self.principal.planner_id,
            snapshot_id=snapshot.id,
            export_format=HandbookExportFormat.HTML,
            checksum=snapshot.checksum,
            delivered_at=delivered_at,
        )
        self.store.handbook_deliveries.append(delivery)
        return snapshot, delivery


@dataclass(frozen=True, slots=True)
class UnusedPlannerRepository:
    async def add(self, planner: PlannerRecord) -> None:
        del planner

    async def get(self, planner_id: UUID) -> PlannerRecord | None:
        del planner_id
        return None


@dataclass(slots=True)
class MemoryUnitOfWork:
    principal: PlannerPrincipal
    store: "MemoryUnitOfWorkFactory"
    approvals: ApprovalRepository = field(init=False)
    handbooks: HandbookRepository = field(init=False)
    planners: PlannerRepository = field(init=False)
    plan_revisions: PlanRevisionRepository = field(init=False)
    trips: TripRepository = field(init=False)
    runs: RunRepository = field(init=False)

    def __post_init__(self) -> None:
        self.approvals = MemoryApprovalRepository(self.principal, self.store)
        self.handbooks = MemoryHandbookRepository(self.principal, self.store)
        self.planners = UnusedPlannerRepository()
        self.plan_revisions = MemoryPlanRevisionRepository(
            self.principal,
            self.store.plan_revisions,
            fail_commit=self.store.failure_stage == "revision",
        )
        self.trips = MemoryTripRepository(self.principal, self.store.trips)
        self.runs = MemoryRunRepository(self.principal, self.store.runs)

    async def __aenter__(self) -> "MemoryUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback


@dataclass(slots=True)
class MemoryUnitOfWorkFactory:
    failure_stage: str | None = None
    approval_requests: list[ApprovalRequestRecord] = field(
        default_factory=list[ApprovalRequestRecord]
    )
    approvals: list[ApprovalRecord] = field(default_factory=list[ApprovalRecord])
    handbook_deliveries: list[HandbookDeliveryRecord] = field(
        default_factory=list[HandbookDeliveryRecord]
    )
    handbook_snapshots: list[HandbookSnapshotRecord] = field(
        default_factory=list[HandbookSnapshotRecord]
    )
    plan_revisions: list[PlanRevisionRecord] = field(
        default_factory=list[PlanRevisionRecord]
    )
    trips: list[TripRecord] = field(default_factory=list[TripRecord])
    runs: list[RunRecord] = field(default_factory=list[RunRecord])

    def __call__(self, principal: PlannerPrincipal) -> UnitOfWork:
        return MemoryUnitOfWork(principal, self)


class ExplodingTravelReadiness(
    Capability[
        TravelReadinessInput,
        TravelReadinessResult,
        TravelReadinessRefusalReason,
    ]
):
    async def execute(
        self,
        capability_input: TravelReadinessInput,
    ) -> (
        CapabilityComplete[TravelReadinessResult]
        | CapabilityRefusal[TravelReadinessRefusalReason]
    ):
        del capability_input
        raise RuntimeError("sensitive capability failure")


class EvidenceFreeTravelReadiness(
    Capability[
        TravelReadinessInput,
        TravelReadinessResult,
        TravelReadinessRefusalReason,
    ]
):
    async def execute(
        self,
        capability_input: TravelReadinessInput,
    ) -> (
        CapabilityComplete[TravelReadinessResult]
        | CapabilityRefusal[TravelReadinessRefusalReason]
    ):
        del capability_input
        return CapabilityComplete(
            value=TravelReadinessResult(
                fixture_id="evidence-free",
                assessment=TravelReadinessAssessment.READY,
                summary="Sensitive unsupported result",
                observed_at=datetime.now(UTC),
                evidence_references=(),
            )
        )


def run_client(store: MemoryUnitOfWorkFactory) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(
            app=create_app(
                access_token_verifier=FakeAccessTokenVerifier(),
                planner_resolver=FakePlannerResolver(),
                unit_of_work_factory=store,
            )
        ),
        base_url="http://test",
        headers={"Authorization": "Bearer owner-token"},
    )


async def create_trip(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/trips",
        json={
            "structure": {
                "stays": [
                    {
                        "city": "Lisbon",
                        "starts_on": "2026-10-04",
                        "ends_on": "2026-10-07",
                        "nights": 3,
                    }
                ]
            }
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_start_run_and_read_its_terminal_status() -> None:
    store = MemoryUnitOfWorkFactory()
    async with run_client(store) as client:
        trip_id = await create_trip(client)
        started = await client.post(f"/api/v1/trips/{trip_id}/runs")
        read = await client.get(started.headers["location"])

    assert started.status_code == 202
    assert read.status_code == 200
    assert started.json() == read.json()
    assert read.json()["trip_id"] == trip_id
    assert read.json()["status"] == "Succeeded"
    assert read.json()["terminal_outcome"]["code"] == "fixture_complete"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_stage", "capability", "message"),
    (
        pytest.param(
            None,
            None,
            "Travel Readiness Capability is not configured",
            id="missing-capability",
        ),
        pytest.param(
            None,
            ExplodingTravelReadiness(),
            "sensitive capability failure",
            id="capability-execution",
        ),
        pytest.param(
            None,
            EvidenceFreeTravelReadiness(),
            "must reference Evidence",
            id="evidence-validation",
        ),
        pytest.param(
            "revision",
            FixtureTravelReadinessCapability(),
            "sensitive commit failure",
            id="plan-revision-commit",
        ),
        pytest.param(
            "approval",
            FixtureTravelReadinessCapability(),
            "sensitive presentation failure",
            id="approval-request-presentation",
        ),
    ),
)
async def test_application_failure_records_one_safe_failed_terminal_outcome(
    failure_stage: str | None,
    capability: Capability[
        TravelReadinessInput,
        TravelReadinessResult,
        TravelReadinessRefusalReason,
    ]
    | None,
    message: str,
) -> None:
    store = MemoryUnitOfWorkFactory(failure_stage=failure_stage)
    principal = PlannerPrincipal(planner_id=PLANNER_ID)
    planning = TripPlanning(StaticServiceStatus(), store, capability)
    trip = await planning.create_trip(
        principal,
        (
            NewTripStay(
                city="Lisbon",
                starts_on=date(2026, 10, 4),
                ends_on=date(2026, 10, 7),
                nights=3,
            ),
        ),
    )

    with pytest.raises(RuntimeError, match=message):
        await planning.start_run(principal, trip.id)

    assert len(store.runs) == 1
    outcome = store.runs[0].terminal_outcome
    assert outcome is not None
    assert outcome == RunTerminalOutcome(
        status=RunTerminalStatus.FAILED,
        code="application_failure",
        detail="The Run failed before completion.",
    )
    assert "sensitive" not in outcome.detail


@pytest.mark.asyncio
async def test_second_active_run_is_a_typed_problem_with_the_active_reference() -> None:
    store = MemoryUnitOfWorkFactory()
    async with run_client(store) as client:
        trip_id = await create_trip(client)
        active_run_id = uuid7()
        store.runs.append(
            RunRecord(
                id=active_run_id,
                planner_id=PLANNER_ID,
                trip_id=UUID(trip_id),
            )
        )
        response = await client.post(f"/api/v1/trips/{trip_id}/runs")

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "active_run_exists"
    assert response.json()["run_id"] == str(active_run_id)
