from uuid import UUID

import pytest

from tests.contract.test_http_run import (
    PLANNER_ID,
    MemoryUnitOfWorkFactory,
    create_trip,
    run_client,
)


@pytest.mark.asyncio
async def test_current_plan_revision_query_identifies_exact_revision() -> None:
    store = MemoryUnitOfWorkFactory()
    async with run_client(store) as client:
        trip_id = await create_trip(client)
        started = await client.post(f"/api/v1/trips/{trip_id}/runs")
        response = await client.get(
            f"/api/v1/trips/{trip_id}/plan-revision",
        )

    assert started.status_code == 202
    assert response.status_code == 200
    assert response.json() == {
        "id": str(store.plan_revisions[0].id),
        "trip_id": trip_id,
        "run_id": started.json()["id"],
        "revision_number": 1,
        "base_revision_id": None,
        "claims": [
            {
                "id": str(store.plan_revisions[0].claims[0].id),
                "kind": "travel_readiness",
                "text": "No fixture Travel Readiness concerns were found for Lisbon.",
                "evidence_reference": ("evaluation-fixture:travel-readiness-lisbon-v1"),
                "observed_at": "2026-09-08T12:00:00Z",
            }
        ],
    }
    assert UUID(response.json()["id"]) == store.plan_revisions[0].id
    assert store.plan_revisions[0].planner_id == PLANNER_ID


@pytest.mark.asyncio
async def test_current_plan_revision_query_is_principal_scoped() -> None:
    store = MemoryUnitOfWorkFactory()
    async with run_client(store) as client:
        trip_id = await create_trip(client)
        await client.post(f"/api/v1/trips/{trip_id}/runs")
        response = await client.get(
            f"/api/v1/trips/{trip_id}/plan-revision",
            headers={"Authorization": "Bearer other"},
        )

    assert response.status_code == 404
    assert response.json()["code"] == "plan_revision_not_found"
