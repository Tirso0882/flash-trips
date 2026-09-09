import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import pytest
from httpx import AsyncClient, Response

from tests.contract.test_http_approval import create_revision_and_request
from tests.security.conftest import TwoPlannerFixture

MISSING_ID = "01991e28-1d65-7000-8000-000000000099"
REQUEST_ID_BYTES = re.compile(rb'"request_id":"[0-9a-f-]{36}"')


@dataclass(frozen=True, slots=True)
class JourneyStations:
    trip_id: str
    run_id: str
    plan_revision_id: str
    approval_request_id: str
    handbook_snapshot_id: str


async def complete_journey(client: AsyncClient) -> JourneyStations:
    trip_id, approval_request = await create_revision_and_request(client)
    plan_revision_response = await client.get(f"/api/v1/trips/{trip_id}/plan-revision")
    approved = await client.post(
        "/api/v1/approvals",
        json={
            "approval_request_id": approval_request["id"],
            "plan_revision_id": approval_request["plan_revision_id"],
        },
    )
    assert approved.status_code == 201
    handbook = await client.post(f"/api/v1/trips/{trip_id}/handbook-snapshots")
    assert handbook.status_code == 201
    return JourneyStations(
        trip_id=trip_id,
        run_id=str(plan_revision_response.json()["run_id"]),
        plan_revision_id=str(approval_request["plan_revision_id"]),
        approval_request_id=str(approval_request["id"]),
        handbook_snapshot_id=str(handbook.json()["id"]),
    )


def problem_bytes(response: Response) -> bytes:
    normalized, replacements = REQUEST_ID_BYTES.subn(
        b'"request_id":"<request-id>"', response.content
    )
    assert replacements == 1
    return normalized


StationRequest = Callable[
    [AsyncClient, JourneyStations, dict[str, str]], Awaitable[Response]
]


@dataclass(frozen=True, slots=True)
class ProtectedStation:
    name: str
    request: StationRequest


PROTECTED_STATIONS = (
    ProtectedStation(
        "Trip read",
        lambda client, stations, headers: client.get(
            f"/api/v1/trips/{stations.trip_id}", headers=headers
        ),
    ),
    ProtectedStation(
        "Trip list",
        lambda client, _stations, headers: client.get("/api/v1/trips", headers=headers),
    ),
    ProtectedStation(
        "Run start",
        lambda client, stations, headers: client.post(
            f"/api/v1/trips/{stations.trip_id}/runs", headers=headers
        ),
    ),
    ProtectedStation(
        "Run read",
        lambda client, stations, headers: client.get(
            f"/api/v1/runs/{stations.run_id}", headers=headers
        ),
    ),
    ProtectedStation(
        "Plan Revision read",
        lambda client, stations, headers: client.get(
            f"/api/v1/trips/{stations.trip_id}/plan-revision", headers=headers
        ),
    ),
    ProtectedStation(
        "Approval Request read",
        lambda client, stations, headers: client.get(
            f"/api/v1/trips/{stations.trip_id}/approval-request", headers=headers
        ),
    ),
    ProtectedStation(
        "Approval action",
        lambda client, stations, headers: client.post(
            "/api/v1/approvals",
            headers=headers,
            json={
                "approval_request_id": stations.approval_request_id,
                "plan_revision_id": stations.plan_revision_id,
            },
        ),
    ),
    ProtectedStation(
        "Handbook compilation",
        lambda client, stations, headers: client.post(
            f"/api/v1/trips/{stations.trip_id}/handbook-snapshots",
            headers=headers,
        ),
    ),
    ProtectedStation(
        "Handbook download",
        lambda client, stations, headers: client.get(
            f"/api/v1/handbook-snapshots/{stations.handbook_snapshot_id}/export",
            headers=headers,
        ),
    ),
)

PROBLEM_STATIONS: tuple[tuple[str, int, StationRequest, StationRequest], ...] = (
    (
        "Trip read",
        404,
        lambda client, stations, headers: client.get(
            f"/api/v1/trips/{stations.trip_id}", headers=headers
        ),
        lambda client, _stations, headers: client.get(
            f"/api/v1/trips/{MISSING_ID}", headers=headers
        ),
    ),
    (
        "Run start",
        404,
        lambda client, stations, headers: client.post(
            f"/api/v1/trips/{stations.trip_id}/runs", headers=headers
        ),
        lambda client, _stations, headers: client.post(
            f"/api/v1/trips/{MISSING_ID}/runs", headers=headers
        ),
    ),
    (
        "Run read",
        404,
        lambda client, stations, headers: client.get(
            f"/api/v1/runs/{stations.run_id}", headers=headers
        ),
        lambda client, _stations, headers: client.get(
            f"/api/v1/runs/{MISSING_ID}", headers=headers
        ),
    ),
    (
        "Plan Revision read",
        404,
        lambda client, stations, headers: client.get(
            f"/api/v1/trips/{stations.trip_id}/plan-revision", headers=headers
        ),
        lambda client, _stations, headers: client.get(
            f"/api/v1/trips/{MISSING_ID}/plan-revision", headers=headers
        ),
    ),
    (
        "Approval Request read",
        404,
        lambda client, stations, headers: client.get(
            f"/api/v1/trips/{stations.trip_id}/approval-request", headers=headers
        ),
        lambda client, _stations, headers: client.get(
            f"/api/v1/trips/{MISSING_ID}/approval-request", headers=headers
        ),
    ),
    (
        "Approval action",
        404,
        lambda client, stations, headers: client.post(
            "/api/v1/approvals",
            headers=headers,
            json={
                "approval_request_id": stations.approval_request_id,
                "plan_revision_id": stations.plan_revision_id,
            },
        ),
        lambda client, _stations, headers: client.post(
            "/api/v1/approvals",
            headers=headers,
            json={
                "approval_request_id": MISSING_ID,
                "plan_revision_id": MISSING_ID,
            },
        ),
    ),
    (
        "Handbook compilation",
        409,
        lambda client, stations, headers: client.post(
            f"/api/v1/trips/{stations.trip_id}/handbook-snapshots",
            headers=headers,
        ),
        lambda client, _stations, headers: client.post(
            f"/api/v1/trips/{MISSING_ID}/handbook-snapshots", headers=headers
        ),
    ),
    (
        "Handbook download",
        404,
        lambda client, stations, headers: client.get(
            f"/api/v1/handbook-snapshots/{stations.handbook_snapshot_id}/export",
            headers=headers,
        ),
        lambda client, _stations, headers: client.get(
            f"/api/v1/handbook-snapshots/{MISSING_ID}/export", headers=headers
        ),
    ),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "station", PROTECTED_STATIONS, ids=lambda station: station.name
)
async def test_unauthenticated_caller_is_denied_at_every_station(
    two_planners: TwoPlannerFixture,
    station: ProtectedStation,
) -> None:
    stations = await complete_journey(two_planners.client)

    response = await station.request(
        two_planners.client, stations, {"Authorization": ""}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "station", PROTECTED_STATIONS, ids=lambda station: station.name
)
async def test_operator_credentials_cannot_reach_planner_stations(
    two_planners: TwoPlannerFixture,
    station: ProtectedStation,
) -> None:
    stations = await complete_journey(two_planners.client)

    response = await station.request(
        two_planners.client, stations, two_planners.operator_headers
    )

    assert response.status_code == 403
    assert response.json()["code"] == "access_denied"


@pytest.mark.asyncio
async def test_second_planner_cannot_list_the_owners_trip(
    two_planners: TwoPlannerFixture,
) -> None:
    stations = await complete_journey(two_planners.client)

    response = await two_planners.client.get(
        "/api/v1/trips", headers=two_planners.other_headers
    )

    assert response.status_code == 200
    assert response.json() == {"items": []}
    assert stations.trip_id not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "expected_status", "foreign_request", "missing_request"),
    PROBLEM_STATIONS,
)
async def test_foreign_and_nonexistent_resources_have_identical_problem_documents(
    two_planners: TwoPlannerFixture,
    name: str,
    expected_status: int,
    foreign_request: StationRequest,
    missing_request: StationRequest,
) -> None:
    del name
    stations = await complete_journey(two_planners.client)

    foreign = await foreign_request(
        two_planners.client, stations, two_planners.other_headers
    )
    missing = await missing_request(
        two_planners.client, stations, two_planners.other_headers
    )

    assert foreign.status_code == missing.status_code == expected_status
    assert foreign.headers["content-type"] == missing.headers["content-type"]
    assert problem_bytes(foreign) == problem_bytes(missing)
