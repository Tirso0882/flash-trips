import os
import subprocess
import sys
from datetime import UTC, date, datetime
from uuid import UUID

import psycopg
import pytest

from flash_trips.adapters.postgres import PostgresDatabase, PostgresUnitOfWorkFactory
from flash_trips.application import (
    ApprovalAlreadyRecordedError,
    ApprovalNotFoundError,
    ApprovalRequestRecord,
    BoundApprovalAction,
    PlanClaimKind,
    PlanClaimRecord,
    PlannerPrincipal,
    PlannerRecord,
    PlanRevisionRecord,
    RunRecord,
    RunTerminalOutcome,
    RunTerminalStatus,
    TripRecord,
    TripStayRecord,
    TripStructureRecord,
    UnitOfWorkFactory,
)
from flash_trips.kernel import EvidenceReference
from flash_trips.kernel.identifiers import uuid7


def required_url(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        pytest.skip(f"{name} is required for real PostgreSQL tests")
    return value


@pytest.fixture(scope="module", autouse=True)
def migrated_database() -> None:
    migration_url = required_url("MIGRATION_DATABASE_URL").replace(
        "postgresql+asyncpg://",
        "postgresql://",
        1,
    )
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "MIGRATION_DATABASE_URL": migration_url},
    )
    assert result.returncode == 0, result.stdout + result.stderr


async def add_planner_trip_and_revision(
    unit_of_work_factory: UnitOfWorkFactory,
    planner_id: UUID,
) -> tuple[TripRecord, PlanRevisionRecord]:
    principal = PlannerPrincipal(planner_id)
    trip = TripRecord(
        id=uuid7(),
        planner_id=planner_id,
        structure=TripStructureRecord(
            stays=(
                TripStayRecord(
                    id=uuid7(),
                    city="Lisbon",
                    starts_on=date(2026, 10, 4),
                    ends_on=date(2026, 10, 7),
                    nights=3,
                ),
            )
        ),
    )
    run = RunRecord(id=uuid7(), planner_id=planner_id, trip_id=trip.id)
    revision = PlanRevisionRecord(
        id=uuid7(),
        planner_id=planner_id,
        trip_id=trip.id,
        run_id=run.id,
        revision_number=1,
        base_revision_id=None,
        claims=(
            PlanClaimRecord(
                id=uuid7(),
                kind=PlanClaimKind.TRAVEL_READINESS,
                text="No fixture concerns were found.",
                evidence_reference=EvidenceReference("fixture:lisbon:v1"),
                observed_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
            ),
        ),
    )
    async with unit_of_work_factory(principal) as unit_of_work:
        await unit_of_work.planners.add(PlannerRecord(id=planner_id))
        await unit_of_work.trips.add(trip)
        await unit_of_work.runs.add(run)
        await unit_of_work.plan_revisions.commit(revision)
    return trip, revision


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_records_approval_against_the_exact_request_and_revision() -> None:
    planner_id = uuid7()
    principal = PlannerPrincipal(planner_id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        _trip, revision = await add_planner_trip_and_revision(factory, planner_id)
        request = ApprovalRequestRecord(uuid7(), planner_id, revision.id)
        action = BoundApprovalAction(request.id, revision.id)
        async with factory(principal) as unit_of_work:
            await unit_of_work.approvals.present(request)
            approval = await unit_of_work.approvals.approve(action)

        assert approval.planner_id == planner_id
        assert approval.approval_request_id == request.id
        assert approval.plan_revision_id == revision.id
        async with factory(principal) as unit_of_work:
            assert await unit_of_work.approvals.get_request(revision.id) == request
            assert await unit_of_work.approvals.get_approval(revision.id) == approval
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_refuses_mismatched_and_foreign_approval_bindings() -> None:
    owner_id = uuid7()
    other_id = uuid7()
    database = PostgresDatabase(required_url("DATABASE_URL"))
    factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        _trip, revision = await add_planner_trip_and_revision(factory, owner_id)
        request = ApprovalRequestRecord(uuid7(), owner_id, revision.id)
        async with factory(PlannerPrincipal(owner_id)) as unit_of_work:
            await unit_of_work.approvals.present(request)

        for principal, action in (
            (
                PlannerPrincipal(owner_id),
                BoundApprovalAction(request.id, uuid7()),
            ),
            (
                PlannerPrincipal(other_id),
                BoundApprovalAction(request.id, revision.id),
            ),
        ):
            with pytest.raises(ApprovalNotFoundError):
                async with factory(principal) as unit_of_work:
                    await unit_of_work.approvals.approve(action)
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_refuses_approval_of_a_superseded_plan_revision() -> None:
    planner_id = uuid7()
    principal = PlannerPrincipal(planner_id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        trip, first = await add_planner_trip_and_revision(factory, planner_id)
        first_request = ApprovalRequestRecord(uuid7(), planner_id, first.id)
        async with factory(principal) as unit_of_work:
            await unit_of_work.approvals.present(first_request)
            await unit_of_work.runs.record_terminal(
                first.run_id,
                RunTerminalOutcome(
                    RunTerminalStatus.SUCCEEDED,
                    "fixture_complete",
                    "First revision committed.",
                ),
            )
        second_run = RunRecord(uuid7(), planner_id, trip.id)
        second = PlanRevisionRecord(
            id=uuid7(),
            planner_id=planner_id,
            trip_id=trip.id,
            run_id=second_run.id,
            revision_number=2,
            base_revision_id=first.id,
            claims=(
                PlanClaimRecord(
                    id=uuid7(),
                    kind=first.claims[0].kind,
                    text=first.claims[0].text,
                    evidence_reference=first.claims[0].evidence_reference,
                    observed_at=first.claims[0].observed_at,
                ),
            ),
        )
        async with factory(principal) as unit_of_work:
            await unit_of_work.runs.add(second_run)
            await unit_of_work.plan_revisions.commit(second)

        with pytest.raises(ApprovalNotFoundError):
            async with factory(principal) as unit_of_work:
                await unit_of_work.approvals.approve(
                    BoundApprovalAction(first_request.id, first.id)
                )
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_refuses_a_second_approval() -> None:
    planner_id = uuid7()
    principal = PlannerPrincipal(planner_id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        _trip, revision = await add_planner_trip_and_revision(factory, planner_id)
        request = ApprovalRequestRecord(uuid7(), planner_id, revision.id)
        action = BoundApprovalAction(request.id, revision.id)
        async with factory(principal) as unit_of_work:
            await unit_of_work.approvals.present(request)
            await unit_of_work.approvals.approve(action)

        with pytest.raises(ApprovalAlreadyRecordedError):
            async with factory(principal) as unit_of_work:
                await unit_of_work.approvals.approve(action)
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_presented_approval_request_is_immutable() -> None:
    planner_id = uuid7()
    principal = PlannerPrincipal(planner_id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        _trip, revision = await add_planner_trip_and_revision(factory, planner_id)
        request = ApprovalRequestRecord(uuid7(), planner_id, revision.id)
        async with factory(principal) as unit_of_work:
            await unit_of_work.approvals.present(request)

        runtime_url = required_url("DATABASE_URL").replace(
            "postgresql+asyncpg://",
            "postgresql://",
            1,
        )
        with (
            psycopg.connect(runtime_url) as connection,
            connection.cursor() as cursor,
            pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState),
        ):
            cursor.execute(
                "UPDATE approval_requests SET plan_revision_id = %s WHERE id = %s",
                (uuid7(), request.id),
            )
    finally:
        await database.close()
