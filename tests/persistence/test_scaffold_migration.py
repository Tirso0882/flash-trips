import os
import subprocess
import sys

import psycopg
import pytest
from sqlalchemy import text

from flash_trips.adapters.postgres import PostgresDatabase


def database_url(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        pytest.skip(f"{name} is required for real PostgreSQL tests")
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest.mark.persistence
@pytest.mark.enable_socket
def test_empty_database_upgrades_and_runtime_role_has_no_ddl_authority() -> None:
    migration_url = database_url("MIGRATION_DATABASE_URL")
    runtime_url = database_url("DATABASE_URL")

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env={**os.environ, "MIGRATION_DATABASE_URL": migration_url},
    )

    with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT version_num FROM alembic_version")
        assert cursor.fetchone() == ("0001_scaffold",)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute("CREATE TABLE forbidden_runtime_ddl (id integer)")


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_runtime_database_connects_through_transaction_interface() -> None:
    runtime_url = os.environ.get("DATABASE_URL")
    if runtime_url is None:
        pytest.skip("DATABASE_URL is required for real PostgreSQL tests")

    database = PostgresDatabase(runtime_url)
    try:
        async with database.transaction() as connection:
            result = await connection.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
    finally:
        await database.close()
