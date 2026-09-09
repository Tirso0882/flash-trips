import asyncio
import os
import subprocess
import sys
from datetime import date
from uuid import UUID

import pytest

from flash_trips.adapters.postgres import PostgresDatabase, PostgresUnitOfWorkFactory
from flash_trips.application import (
    ActiveRunExistsError,
    PlannerPrincipal,
    PlannerRecord,
    RunRecord,
    RunTerminalOutcome,
    RunTerminalStatus,
    TerminalOutcomeAlreadyRecordedError,
    TripRecord,
    TripStayRecord,
    TripStructureRecord,
    UnitOfWorkFactory,
)
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


async def add_trip(
    unit_of_work_factory: UnitOfWorkFactory,
    planner_id: UUID,
) -> TripRecord:
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
    async with unit_of_work_factory(
        PlannerPrincipal(planner_id=planner_id)
    ) as unit_of_work:
        await unit_of_work.planners.add(PlannerRecord(id=planner_id))
        await unit_of_work.trips.add(trip)
    return trip


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_run_records_one_terminal_outcome_without_overwrite(
    migrated_database: None,
) -> None:
    planner_id = uuid7()
    principal = PlannerPrincipal(planner_id=planner_id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    run = RunRecord(id=uuid7(), planner_id=planner_id, trip_id=uuid7())
    first = RunTerminalOutcome(
        status=RunTerminalStatus.SUCCEEDED,
        code="fixture_complete",
        detail="The fixture Capability completed.",
    )
    second = RunTerminalOutcome(
        status=RunTerminalStatus.BLOCKED,
        code="late_refusal",
        detail="This outcome must not replace the first.",
    )
    try:
        trip = await add_trip(unit_of_work_factory, planner_id)
        run = RunRecord(id=run.id, planner_id=planner_id, trip_id=trip.id)
        async with unit_of_work_factory(principal) as unit_of_work:
            await unit_of_work.runs.add(run)
            completed = await unit_of_work.runs.record_terminal(run.id, first)
        assert completed.terminal_outcome == first

        async with unit_of_work_factory(principal) as unit_of_work:
            with pytest.raises(TerminalOutcomeAlreadyRecordedError):
                await unit_of_work.runs.record_terminal(run.id, second)

        async with unit_of_work_factory(principal) as unit_of_work:
            assert await unit_of_work.runs.get(run.id) == RunRecord(
                id=run.id,
                planner_id=planner_id,
                trip_id=trip.id,
                terminal_outcome=first,
            )
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_only_one_active_mutating_run_exists_per_trip(
    migrated_database: None,
) -> None:
    planner_id = uuid7()
    principal = PlannerPrincipal(planner_id=planner_id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        trip = await add_trip(unit_of_work_factory, planner_id)
        active = RunRecord(id=uuid7(), planner_id=planner_id, trip_id=trip.id)
        competing = RunRecord(id=uuid7(), planner_id=planner_id, trip_id=trip.id)

        async def add_run(run: RunRecord) -> None:
            async with unit_of_work_factory(principal) as unit_of_work:
                await unit_of_work.runs.add(run)

        attempts = await asyncio.gather(
            add_run(active),
            add_run(competing),
            return_exceptions=True,
        )
        refusals = [
            attempt for attempt in attempts if isinstance(attempt, ActiveRunExistsError)
        ]

        assert sum(attempt is None for attempt in attempts) == 1
        assert len(refusals) == 1
        persisted_id = refusals[0].active_run_id
        refused_id = active.id if persisted_id == competing.id else competing.id
        async with unit_of_work_factory(principal) as unit_of_work:
            assert await unit_of_work.runs.get(persisted_id) is not None
            assert await unit_of_work.runs.get(refused_id) is None
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_run_repository_is_principal_scoped(
    migrated_database: None,
) -> None:
    owner_id = uuid7()
    other_id = uuid7()
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        trip = await add_trip(unit_of_work_factory, owner_id)
        await add_trip(unit_of_work_factory, other_id)
        run = RunRecord(id=uuid7(), planner_id=owner_id, trip_id=trip.id)
        async with unit_of_work_factory(
            PlannerPrincipal(planner_id=owner_id)
        ) as unit_of_work:
            await unit_of_work.runs.add(run)

        async with unit_of_work_factory(
            PlannerPrincipal(planner_id=other_id)
        ) as unit_of_work:
            assert await unit_of_work.runs.get(run.id) is None
            with pytest.raises(ValueError, match="principal"):
                await unit_of_work.runs.add(run)
    finally:
        await database.close()
