import os
import subprocess
import sys
from datetime import UTC, date, datetime
from uuid import UUID

import psycopg
import pytest
from sqlalchemy.exc import IntegrityError

from flash_trips.adapters.postgres import PostgresDatabase, PostgresUnitOfWorkFactory
from flash_trips.application import (
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


@pytest.fixture(scope="module")
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


async def add_trip_and_run(
    unit_of_work_factory: UnitOfWorkFactory,
    planner_id: UUID,
) -> tuple[TripRecord, RunRecord]:
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
    async with unit_of_work_factory(
        PlannerPrincipal(planner_id=planner_id)
    ) as unit_of_work:
        await unit_of_work.planners.add(PlannerRecord(id=planner_id))
        await unit_of_work.trips.add(trip)
        await unit_of_work.runs.add(run)
    return trip, run


def revision_for(
    planner_id: UUID,
    trip: TripRecord,
    run: RunRecord,
) -> PlanRevisionRecord:
    return PlanRevisionRecord(
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


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_commits_one_complete_plan_revision_and_reads_it_as_current(
    migrated_database: None,
) -> None:
    planner_id = uuid7()
    principal = PlannerPrincipal(planner_id=planner_id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        trip, run = await add_trip_and_run(unit_of_work_factory, planner_id)
        revision = revision_for(planner_id, trip, run)

        async with unit_of_work_factory(principal) as unit_of_work:
            committed = await unit_of_work.plan_revisions.commit(revision)

        assert committed == revision
        async with unit_of_work_factory(principal) as unit_of_work:
            assert await unit_of_work.plan_revisions.get_current(trip.id) == revision
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_fault_during_claim_insert_leaves_no_partial_revision(
    migrated_database: None,
) -> None:
    planner_id = uuid7()
    principal = PlannerPrincipal(planner_id=planner_id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        trip, run = await add_trip_and_run(unit_of_work_factory, planner_id)
        revision = revision_for(planner_id, trip, run)
        duplicate = PlanRevisionRecord(
            id=revision.id,
            planner_id=revision.planner_id,
            trip_id=revision.trip_id,
            run_id=revision.run_id,
            revision_number=revision.revision_number,
            base_revision_id=revision.base_revision_id,
            claims=(revision.claims[0], revision.claims[0]),
        )

        with pytest.raises(IntegrityError):
            async with unit_of_work_factory(principal) as unit_of_work:
                await unit_of_work.plan_revisions.commit(duplicate)

        async with unit_of_work_factory(principal) as unit_of_work:
            assert await unit_of_work.plan_revisions.get_current(trip.id) is None
            assert await unit_of_work.runs.get(run.id) == run
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_one_run_cannot_commit_a_second_plan_revision(
    migrated_database: None,
) -> None:
    planner_id = uuid7()
    principal = PlannerPrincipal(planner_id=planner_id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        trip, run = await add_trip_and_run(unit_of_work_factory, planner_id)
        first = revision_for(planner_id, trip, run)
        second = PlanRevisionRecord(
            id=uuid7(),
            planner_id=planner_id,
            trip_id=trip.id,
            run_id=run.id,
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
        async with unit_of_work_factory(principal) as unit_of_work:
            await unit_of_work.plan_revisions.commit(first)

        with pytest.raises(IntegrityError):
            async with unit_of_work_factory(principal) as unit_of_work:
                await unit_of_work.plan_revisions.commit(second)

        async with unit_of_work_factory(principal) as unit_of_work:
            assert await unit_of_work.plan_revisions.get_current(trip.id) == first
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_previous_revision_remains_current_until_new_revision_commits(
    migrated_database: None,
) -> None:
    planner_id = uuid7()
    principal = PlannerPrincipal(planner_id=planner_id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        trip, first_run = await add_trip_and_run(unit_of_work_factory, planner_id)
        first = revision_for(planner_id, trip, first_run)
        async with unit_of_work_factory(principal) as unit_of_work:
            await unit_of_work.plan_revisions.commit(first)
            await unit_of_work.runs.record_terminal(
                first_run.id,
                RunTerminalOutcome(
                    status=RunTerminalStatus.SUCCEEDED,
                    code="fixture_complete",
                    detail="First revision committed.",
                ),
            )

        second_run = RunRecord(id=uuid7(), planner_id=planner_id, trip_id=trip.id)
        async with unit_of_work_factory(principal) as unit_of_work:
            await unit_of_work.runs.add(second_run)
        async with unit_of_work_factory(principal) as unit_of_work:
            assert await unit_of_work.plan_revisions.get_current(trip.id) == first

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
        async with unit_of_work_factory(principal) as unit_of_work:
            await unit_of_work.plan_revisions.commit(second)
        async with unit_of_work_factory(principal) as unit_of_work:
            assert await unit_of_work.plan_revisions.get_current(trip.id) == second
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_schema_refuses_updates_to_committed_revisions_and_claims(
    migrated_database: None,
) -> None:
    planner_id = uuid7()
    principal = PlannerPrincipal(planner_id=planner_id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        trip, run = await add_trip_and_run(unit_of_work_factory, planner_id)
        revision = revision_for(planner_id, trip, run)
        async with unit_of_work_factory(principal) as unit_of_work:
            await unit_of_work.plan_revisions.commit(revision)

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
                "UPDATE plan_revisions SET revision_number = 2 WHERE id = %s",
                (revision.id,),
            )
        with (
            psycopg.connect(runtime_url) as connection,
            connection.cursor() as cursor,
            pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState),
        ):
            cursor.execute(
                "UPDATE plan_claims SET text = 'changed' WHERE id = %s",
                (revision.claims[0].id,),
            )
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_schema_refuses_a_run_from_another_trip_or_planner(
    migrated_database: None,
) -> None:
    owner_id = uuid7()
    other_id = uuid7()
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        owner_trip, _owner_run = await add_trip_and_run(unit_of_work_factory, owner_id)
        _other_trip, other_run = await add_trip_and_run(unit_of_work_factory, other_id)
        runtime_url = required_url("DATABASE_URL").replace(
            "postgresql+asyncpg://",
            "postgresql://",
            1,
        )
        with (
            psycopg.connect(runtime_url) as connection,
            connection.cursor() as cursor,
            pytest.raises(psycopg.errors.ForeignKeyViolation),
        ):
            cursor.execute(
                """
                INSERT INTO plan_revisions (
                    id, planner_id, trip_id, run_id, revision_number
                ) VALUES (%s, %s, %s, %s, 1)
                """,
                (uuid7(), owner_id, owner_trip.id, other_run.id),
            )
    finally:
        await database.close()
