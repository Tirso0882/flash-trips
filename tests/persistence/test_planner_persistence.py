import os
import subprocess
import sys

import psycopg
import pytest

from flash_trips.adapters.postgres import PostgresDatabase, PostgresUnitOfWorkFactory
from flash_trips.application.persistence import (
    PlannerPrincipal,
    PlannerRecord,
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


def psycopg_url(name: str) -> str:
    return required_url(name).replace("postgresql+asyncpg://", "postgresql://", 1)


def run_alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
    migration_url = psycopg_url("MIGRATION_DATABASE_URL")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "MIGRATION_DATABASE_URL": migration_url},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture
def migrated_database() -> None:
    run_alembic("upgrade", "head")


@pytest.mark.persistence
@pytest.mark.enable_socket
def test_migration_history_has_one_head_that_matches_the_mapped_models(
    migrated_database: None,
) -> None:
    heads = run_alembic("heads").stdout.strip().splitlines()

    assert heads == ["0002_planner (head)"]
    run_alembic("check")


@pytest.mark.persistence
@pytest.mark.enable_socket
def test_planner_table_appears_on_upgrade_and_is_removed_on_rollback() -> None:
    runtime_url = psycopg_url("DATABASE_URL")

    run_alembic("downgrade", "base")
    try:
        run_alembic("upgrade", "0001_scaffold")
        with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT version_num FROM alembic_version")
            assert cursor.fetchone() == ("0001_scaffold",)
            cursor.execute("SELECT to_regclass('public.planners')")
            assert cursor.fetchone() == (None,)

        run_alembic("upgrade", "head")
        with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT version_num FROM alembic_version")
            assert cursor.fetchone() == ("0002_planner",)
            cursor.execute("SELECT to_regclass('public.planners')")
            assert cursor.fetchone() == ("planners",)

        run_alembic("downgrade", "0001_scaffold")
        with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT version_num FROM alembic_version")
            assert cursor.fetchone() == ("0001_scaffold",)
            cursor.execute("SELECT to_regclass('public.planners')")
            assert cursor.fetchone() == (None,)
    finally:
        run_alembic("upgrade", "head")


@pytest.mark.persistence
@pytest.mark.enable_socket
def test_runtime_role_cannot_create_tables(migrated_database: None) -> None:
    runtime_url = psycopg_url("DATABASE_URL")

    with (
        psycopg.connect(runtime_url) as connection,
        connection.cursor() as cursor,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        cursor.execute("CREATE TABLE forbidden_runtime_ddl (id integer)")


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_principal_scoped_repository_inserts_and_reads_planner(
    migrated_database: None,
) -> None:
    planner = PlannerRecord(id=uuid7())
    principal = PlannerPrincipal(planner_id=planner.id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        async with unit_of_work_factory(principal) as unit_of_work:
            await unit_of_work.planners.add(planner)

        async with unit_of_work_factory(principal) as unit_of_work:
            assert await unit_of_work.planners.get(planner.id) == planner
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_repository_denies_planners_outside_its_principal(
    migrated_database: None,
) -> None:
    planner = PlannerRecord(id=uuid7())
    owner = PlannerPrincipal(planner_id=planner.id)
    other = PlannerPrincipal(planner_id=uuid7())
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        async with unit_of_work_factory(owner) as unit_of_work:
            await unit_of_work.planners.add(planner)

        async with unit_of_work_factory(other) as unit_of_work:
            with pytest.raises(ValueError, match="principal"):
                await unit_of_work.planners.add(planner)
            assert await unit_of_work.planners.get(planner.id) is None
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_unit_of_work_rolls_back_on_failure(migrated_database: None) -> None:
    planner = PlannerRecord(id=uuid7())
    principal = PlannerPrincipal(planner_id=planner.id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    unit_of_work_factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        with pytest.raises(ExpectedRollback):
            async with unit_of_work_factory(principal) as unit_of_work:
                await unit_of_work.planners.add(planner)
                raise ExpectedRollback

        async with unit_of_work_factory(principal) as unit_of_work:
            assert await unit_of_work.planners.get(planner.id) is None
    finally:
        await database.close()
