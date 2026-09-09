from dataclasses import dataclass, field
from types import TracebackType
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from flash_trips.application import (
    ActiveRunExistsError,
    PlannerPrincipal,
    PlannerRecord,
    PlannerRepository,
    RunRecord,
    RunRepository,
    RunTerminalOutcome,
    TerminalOutcomeAlreadyRecordedError,
    TripRecord,
    TripRepository,
    UnitOfWork,
)
from flash_trips.composition import create_app
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal
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
    planners: PlannerRepository = field(init=False)
    trips: TripRepository = field(init=False)
    runs: RunRepository = field(init=False)

    def __post_init__(self) -> None:
        self.planners = UnusedPlannerRepository()
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
    trips: list[TripRecord] = field(default_factory=list[TripRecord])
    runs: list[RunRecord] = field(default_factory=list[RunRecord])

    def __call__(self, principal: PlannerPrincipal) -> UnitOfWork:
        return MemoryUnitOfWork(principal, self)


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
