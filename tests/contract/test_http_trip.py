from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Self, cast
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient, Response

from flash_trips.application import (
    PlannerPrincipal,
    PlannerRecord,
    PlannerRepository,
    PlanRevisionRecord,
    PlanRevisionRepository,
    RunRecord,
    RunRepository,
    RunTerminalOutcome,
    TripRecord,
    TripRepository,
    UnitOfWork,
)
from flash_trips.composition import create_app
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal

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
        if trip.planner_id != self.principal.planner_id:
            raise ValueError("Trip does not match the repository principal")
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


@dataclass(frozen=True, slots=True)
class UnusedPlannerRepository:
    async def add(self, planner: PlannerRecord) -> None:
        del planner

    async def get(self, planner_id: UUID) -> PlannerRecord | None:
        del planner_id
        return None


@dataclass(frozen=True, slots=True)
class UnusedRunRepository:
    async def add(self, run: RunRecord) -> None:
        del run

    async def get(self, run_id: UUID) -> RunRecord | None:
        del run_id
        return None

    async def record_terminal(
        self,
        run_id: UUID,
        outcome: RunTerminalOutcome,
    ) -> RunRecord:
        del run_id, outcome
        raise AssertionError("Run persistence is not used by Trip HTTP tests")


@dataclass(frozen=True, slots=True)
class UnusedPlanRevisionRepository:
    async def commit(self, revision: PlanRevisionRecord) -> PlanRevisionRecord:
        del revision
        raise AssertionError("Plan persistence is not used by Trip HTTP tests")

    async def get_current(self, trip_id: UUID) -> PlanRevisionRecord | None:
        del trip_id
        return None


@dataclass(slots=True)
class MemoryUnitOfWork:
    principal: PlannerPrincipal
    records: list[TripRecord]
    planners: PlannerRepository = field(init=False)
    plan_revisions: PlanRevisionRepository = field(init=False)
    runs: RunRepository = field(init=False)
    trips: TripRepository = field(init=False)

    def __post_init__(self) -> None:
        self.planners = UnusedPlannerRepository()
        self.plan_revisions = UnusedPlanRevisionRepository()
        self.runs = UnusedRunRepository()
        self.trips = MemoryTripRepository(self.principal, self.records)

    async def __aenter__(self) -> Self:
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
    records: list[TripRecord] = field(default_factory=list[TripRecord])

    def __call__(self, principal: PlannerPrincipal) -> UnitOfWork:
        return MemoryUnitOfWork(principal, self.records)


def trip_client(
    unit_of_work_factory: MemoryUnitOfWorkFactory,
) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(
            app=create_app(
                access_token_verifier=FakeAccessTokenVerifier(),
                planner_resolver=FakePlannerResolver(),
                unit_of_work_factory=unit_of_work_factory,
            )
        ),
        base_url="http://test",
        headers={"Authorization": "Bearer owner-token"},
    )


def trip_input(city: str = "Lisbon") -> dict[str, Any]:
    return {
        "structure": {
            "stays": [
                {
                    "city": city,
                    "starts_on": "2026-10-04",
                    "ends_on": "2026-10-07",
                    "nights": 3,
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_create_list_and_reopen_a_private_trip() -> None:
    store = MemoryUnitOfWorkFactory()
    async with trip_client(store) as client:
        created = await client.post("/api/v1/trips", json=trip_input())
        trip_id = created.json()["id"]
        listed = await client.get("/api/v1/trips")
        reopened = await client.get(f"/api/v1/trips/{trip_id}")

    assert created.status_code == 201
    assert created.headers["location"] == f"/api/v1/trips/{trip_id}"
    assert listed.status_code == 200
    assert listed.json() == {"items": [created.json()]}
    assert reopened.status_code == 200
    assert reopened.json() == created.json()
    assert "planner_id" not in created.text


@pytest.mark.asyncio
async def test_create_rejects_a_multi_city_structure_at_the_http_policy() -> None:
    store = MemoryUnitOfWorkFactory()
    request = trip_input()
    structure = cast(dict[str, Any], request["structure"])
    stays = cast(list[dict[str, object]], structure["stays"])
    stays.append(
        {
            "city": "Porto",
            "starts_on": "2026-10-07",
            "ends_on": "2026-10-09",
            "nights": 2,
        }
    )

    async with trip_client(store) as client:
        response = await client.post("/api/v1/trips", json=request)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "unsupported_structure"
    assert store.records == []


@pytest.mark.asyncio
async def test_invalid_trip_identifier_uses_the_problem_contract() -> None:
    async with trip_client(MemoryUnitOfWorkFactory()) as client:
        response = await client.get("/api/v1/trips/not-a-uuid")

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "invalid_request"


def refusal(response: Response) -> tuple[int, str, dict[str, object]]:
    problem = response.json()
    problem.pop("request_id")
    return response.status_code, response.headers["content-type"], problem


@pytest.mark.asyncio
async def test_foreign_and_nonexistent_trip_identifiers_are_indistinguishable() -> None:
    store = MemoryUnitOfWorkFactory()
    async with trip_client(store) as owner:
        created = await owner.post("/api/v1/trips", json=trip_input())
        trip_id = created.json()["id"]
        missing = await owner.get("/api/v1/trips/01991e28-1d65-7000-8000-000000000099")
        foreign = await owner.get(
            f"/api/v1/trips/{trip_id}",
            headers={"Authorization": "Bearer planner-other"},
        )

    assert refusal(foreign) == refusal(missing)
    assert refusal(foreign) == (
        404,
        "application/problem+json",
        {
            "type": "https://flash-trips.example/problems/trip-not-found",
            "title": "Not Found",
            "status": 404,
            "detail": "The Trip was not found.",
            "code": "trip_not_found",
            "retryable": False,
        },
    )
