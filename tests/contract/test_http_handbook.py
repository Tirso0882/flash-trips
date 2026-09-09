import pytest

from tests.contract.test_http_approval import create_revision_and_request
from tests.contract.test_http_run import MemoryUnitOfWorkFactory, run_client


async def compile_approved_handbook(
    store: MemoryUnitOfWorkFactory,
) -> tuple[str, str]:
    async with run_client(store) as client:
        trip_id, request = await create_revision_and_request(client)
        approved = await client.post(
            "/api/v1/approvals",
            json={
                "approval_request_id": request["id"],
                "plan_revision_id": request["plan_revision_id"],
            },
        )
        assert approved.status_code == 201
        compiled = await client.post(f"/api/v1/trips/{trip_id}/handbook-snapshots")
    assert compiled.status_code == 201
    assert compiled.json()["plan_revision_id"] == request["plan_revision_id"]
    assert compiled.json()["approval_id"] == approved.json()["id"]
    assert compiled.json()["format"] == "html"
    return trip_id, compiled.json()["id"]


@pytest.mark.asyncio
async def test_download_is_deterministic_and_records_delivery() -> None:
    store = MemoryUnitOfWorkFactory()
    _trip_id, snapshot_id = await compile_approved_handbook(store)

    async with run_client(store) as client:
        first = await client.get(f"/api/v1/handbook-snapshots/{snapshot_id}/export")
        second = await client.get(f"/api/v1/handbook-snapshots/{snapshot_id}/export")

    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert first.headers["content-type"] == "text/html; charset=utf-8"
    assert first.headers["content-disposition"].startswith("attachment;")
    assert b"Trip Handbook" in first.content
    assert len(store.handbook_deliveries) == 2
    assert store.handbook_deliveries[0].snapshot_id == store.handbook_snapshots[0].id
    assert store.approvals[0].id != store.handbook_deliveries[0].id


@pytest.mark.asyncio
async def test_revision_without_approval_cannot_compile_a_snapshot() -> None:
    store = MemoryUnitOfWorkFactory()
    async with run_client(store) as client:
        trip_id, _request = await create_revision_and_request(client)
        response = await client.post(f"/api/v1/trips/{trip_id}/handbook-snapshots")

    assert response.status_code == 409
    assert response.json()["code"] == "handbook_not_eligible"
    assert store.handbook_snapshots == []


@pytest.mark.asyncio
async def test_foreign_and_missing_snapshot_downloads_are_indistinguishable() -> None:
    store = MemoryUnitOfWorkFactory()
    _trip_id, snapshot_id = await compile_approved_handbook(store)

    async with run_client(store) as client:
        foreign = await client.get(
            f"/api/v1/handbook-snapshots/{snapshot_id}/export",
            headers={"Authorization": "Bearer other"},
        )
        missing = await client.get(
            "/api/v1/handbook-snapshots/01991e28-1d65-7000-8000-000000000099/export"
        )
        unauthenticated = await client.get(
            f"/api/v1/handbook-snapshots/{snapshot_id}/export",
            headers={"Authorization": ""},
        )

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json()["code"] == missing.json()["code"] == "handbook_not_found"
    assert set(foreign.json()) == set(missing.json())
    assert unauthenticated.status_code == 401
    assert store.handbook_deliveries == []
