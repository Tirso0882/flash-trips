from uuid import UUID

import pytest
from httpx import AsyncClient

from tests.contract.test_http_run import (
    OTHER_PLANNER_ID,
    MemoryUnitOfWorkFactory,
    create_trip,
    run_client,
)


async def create_revision_and_request(
    client: AsyncClient,
) -> tuple[str, dict[str, object]]:
    trip_id = await create_trip(client)
    started = await client.post(f"/api/v1/trips/{trip_id}/runs")
    assert started.status_code == 202
    request = await client.get(f"/api/v1/trips/{trip_id}/approval-request")
    assert request.status_code == 200
    return trip_id, request.json()


@pytest.mark.asyncio
async def test_bound_action_approves_the_exact_presented_plan_revision() -> None:
    store = MemoryUnitOfWorkFactory()
    async with run_client(store) as client:
        _trip_id, presented = await create_revision_and_request(client)
        response = await client.post(
            "/api/v1/approvals",
            json={
                "approval_request_id": presented["id"],
                "plan_revision_id": presented["plan_revision_id"],
            },
        )

    assert response.status_code == 201
    assert response.json()["approval_request_id"] == presented["id"]
    assert response.json()["plan_revision_id"] == presented["plan_revision_id"]
    assert store.approvals[0].planner_id != OTHER_PLANNER_ID


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"approval_request_id": "01991e28-1d65-7000-8000-000000000099"},
        {"plan_revision_id": "01991e28-1d65-7000-8000-000000000099"},
        {
            "approval_request_id": "01991e28-1d65-7000-8000-000000000099",
            "plan_revision_id": "01991e28-1d65-7000-8000-000000000098",
            "text": "yes",
        },
        {"text": "yes, approve it"},
    ],
)
async def test_free_text_or_an_unbound_action_cannot_approve(
    payload: dict[str, str],
) -> None:
    store = MemoryUnitOfWorkFactory()
    async with run_client(store) as client:
        response = await client.post("/api/v1/approvals", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
    assert store.approvals == []


@pytest.mark.asyncio
async def test_mismatched_or_foreign_binding_is_indistinguishable_from_missing() -> (
    None
):
    store = MemoryUnitOfWorkFactory()
    async with run_client(store) as client:
        _trip_id, presented = await create_revision_and_request(client)
        mismatched = await client.post(
            "/api/v1/approvals",
            json={
                "approval_request_id": presented["id"],
                "plan_revision_id": "01991e28-1d65-7000-8000-000000000099",
            },
        )
        foreign = await client.post(
            "/api/v1/approvals",
            headers={"Authorization": "Bearer other"},
            json={
                "approval_request_id": presented["id"],
                "plan_revision_id": presented["plan_revision_id"],
            },
        )

    assert mismatched.status_code == foreign.status_code == 404
    assert mismatched.json()["code"] == foreign.json()["code"] == "approval_not_found"
    assert set(mismatched.json()) == set(foreign.json())
    assert store.approvals == []


@pytest.mark.asyncio
async def test_approval_request_and_recorded_approval_are_principal_scoped() -> None:
    store = MemoryUnitOfWorkFactory()
    async with run_client(store) as client:
        trip_id, presented = await create_revision_and_request(client)
        approved = await client.post(
            "/api/v1/approvals",
            json={
                "approval_request_id": presented["id"],
                "plan_revision_id": presented["plan_revision_id"],
            },
        )
        owner = await client.get(f"/api/v1/trips/{trip_id}/approval-request")
        foreign = await client.get(
            f"/api/v1/trips/{trip_id}/approval-request",
            headers={"Authorization": "Bearer other"},
        )

    assert approved.status_code == 201
    assert owner.status_code == 200
    assert owner.json()["approval_id"] == approved.json()["id"]
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "approval_not_found"


@pytest.mark.asyncio
async def test_approving_twice_is_refused() -> None:
    store = MemoryUnitOfWorkFactory()
    async with run_client(store) as client:
        _trip_id, presented = await create_revision_and_request(client)
        action = {
            "approval_request_id": presented["id"],
            "plan_revision_id": presented["plan_revision_id"],
        }
        first = await client.post("/api/v1/approvals", json=action)
        second = await client.post("/api/v1/approvals", json=action)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["code"] == "approval_already_recorded"
    assert len(store.approvals) == 1
    assert UUID(first.json()["id"]) == store.approvals[0].id
