import os
import subprocess
import sys
from datetime import date
from uuid import UUID

import pytest

from flash_trips.adapters.postgres import PostgresDatabase, PostgresUnitOfWorkFactory
from flash_trips.application import (
    PlannerPrincipal,
    TripRecord,
    TripStayRecord,
    TripStructureRecord,
    UnitOfWorkFactory,
)
from flash_trips.kernel.identifiers import uuid7


class ExpectedRollback(Exception):
    pass


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


async def add_planner(
    unit_of_work_factory: UnitOfWorkFactory,
    planner_id: UUID,
) -> None:
    from flash_trips.application import PlannerRecord

    async with unit_of_work_factory(
        PlannerPrincipal(planner_id=planner_id)
    ) as unit_of_work:
        await unit_of_work.planners.add(PlannerRecord(id=planner_id))


def trip_for(planner_id: UUID, *, stays: tuple[TripStayRecord, ...]) -> TripRecord:
    return TripRecord(
        id=uuid7(),
        planner_id=planner_id,
        structure=TripStructureRecord(stays=stays),
    )


def stay(
    city: str,
    starts_on: date,
    ends_on: date,
    nights: int,
) -> TripStayRecord:
    return TripStayRecord(
        id=uuid7(),
        city=city,
        starts_on=starts_on,
        ends_on=ends_on,
        nights=nights,
    )


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_trip_repository_is_principal_scoped(
    migrated_database: None,
) -> None:
    owner_id = uuid7()
    other_id = uuid7()
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    owned = trip_for(
        owner_id,
        stays=(stay("Lisbon", date(2026, 10, 4), date(2026, 10, 7), 3),),
    )
    try:
        await add_planner(unit_of_work_factory, owner_id)
        await add_planner(unit_of_work_factory, other_id)
        async with unit_of_work_factory(
            PlannerPrincipal(planner_id=owner_id)
        ) as unit_of_work:
            await unit_of_work.trips.add(owned)

        async with unit_of_work_factory(
            PlannerPrincipal(planner_id=owner_id)
        ) as unit_of_work:
            assert await unit_of_work.trips.get(owned.id) == owned
            assert await unit_of_work.trips.list() == [owned]

        async with unit_of_work_factory(
            PlannerPrincipal(planner_id=other_id)
        ) as unit_of_work:
            assert await unit_of_work.trips.get(owned.id) is None
            assert await unit_of_work.trips.list() == []
            with pytest.raises(ValueError, match="principal"):
                await unit_of_work.trips.add(owned)
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_trip_structure_round_trips_two_ordered_stays(
    migrated_database: None,
) -> None:
    planner_id = uuid7()
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    multi_city = trip_for(
        planner_id,
        stays=(
            stay("Lisbon", date(2026, 10, 4), date(2026, 10, 7), 3),
            stay("Porto", date(2026, 10, 7), date(2026, 10, 9), 2),
        ),
    )
    try:
        await add_planner(unit_of_work_factory, planner_id)
        async with unit_of_work_factory(
            PlannerPrincipal(planner_id=planner_id)
        ) as unit_of_work:
            await unit_of_work.trips.add(multi_city)

        async with unit_of_work_factory(
            PlannerPrincipal(planner_id=planner_id)
        ) as unit_of_work:
            assert await unit_of_work.trips.get(multi_city.id) == multi_city
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_trip_write_rolls_back_with_the_unit_of_work(
    migrated_database: None,
) -> None:
    planner_id = uuid7()
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    owned = trip_for(
        planner_id,
        stays=(stay("Lisbon", date(2026, 10, 4), date(2026, 10, 7), 3),),
    )
    try:
        await add_planner(unit_of_work_factory, planner_id)
        with pytest.raises(ExpectedRollback):
            async with unit_of_work_factory(
                PlannerPrincipal(planner_id=planner_id)
            ) as unit_of_work:
                await unit_of_work.trips.add(owned)
                raise ExpectedRollback

        async with unit_of_work_factory(
            PlannerPrincipal(planner_id=planner_id)
        ) as unit_of_work:
            assert await unit_of_work.trips.get(owned.id) is None
    finally:
        await database.close()
