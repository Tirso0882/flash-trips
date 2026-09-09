import os
import subprocess
import sys
from uuid import UUID

import psycopg
import pytest

from flash_trips.adapters.postgres import (
    PostgresDatabase,
    PostgresExternalIdentityRepositoryFactory,
    PostgresUnitOfWorkFactory,
)
from flash_trips.application.identity import (
    AllowedExternalIdentity,
    ResolvePlanner,
)
from flash_trips.application.persistence import (
    PlannerAccessStatus,
    PlannerPrincipal,
    PlannerRecord,
    UnitOfWorkFactory,
)
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal
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

    assert heads == ["0007_plan_revision (head)"]
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
            assert cursor.fetchone() == ("0007_plan_revision",)
            cursor.execute("SELECT to_regclass('public.planners')")
            assert cursor.fetchone() == ("planners",)
            cursor.execute("SELECT to_regclass('public.external_identities')")
            assert cursor.fetchone() == ("external_identities",)
            cursor.execute("SELECT to_regclass('public.application_sessions')")
            assert cursor.fetchone() == ("application_sessions",)
            cursor.execute("SELECT to_regclass('public.trips')")
            assert cursor.fetchone() == ("trips",)
            cursor.execute("SELECT to_regclass('public.trip_structures')")
            assert cursor.fetchone() == ("trip_structures",)
            cursor.execute("SELECT to_regclass('public.runs')")
            assert cursor.fetchone() == ("runs",)
            cursor.execute("SELECT to_regclass('public.plan_revisions')")
            assert cursor.fetchone() == ("plan_revisions",)
            cursor.execute("SELECT to_regclass('public.plan_claims')")
            assert cursor.fetchone() == ("plan_claims",)

        run_alembic("downgrade", "0006_run")
        with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.plan_revisions')")
            assert cursor.fetchone() == (None,)
            cursor.execute("SELECT to_regclass('public.plan_claims')")
            assert cursor.fetchone() == (None,)

        run_alembic("downgrade", "0005_trip")
        with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.runs')")
            assert cursor.fetchone() == (None,)

        run_alembic("downgrade", "0004_application_session")
        with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.trips')")
            assert cursor.fetchone() == (None,)
            cursor.execute("SELECT to_regclass('public.trip_structures')")
            assert cursor.fetchone() == (None,)

        run_alembic("downgrade", "0003_external_identity")
        with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.application_sessions')")
            assert cursor.fetchone() == (None,)

        run_alembic("downgrade", "0002_planner")
        with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT version_num FROM alembic_version")
            assert cursor.fetchone() == ("0002_planner",)
            cursor.execute("SELECT to_regclass('public.external_identities')")
            assert cursor.fetchone() == (None,)
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'planners' AND column_name = 'access_status'
                """
            )
            assert cursor.fetchone() is None

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


def insert_external_identity(
    runtime_url: str,
    *,
    planner_id: UUID,
    issuer: str,
    subject: str,
) -> None:
    with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO external_identities (id, issuer, subject, planner_id)
            VALUES (%s, %s, %s, %s)
            """,
            (uuid7(), issuer, subject, planner_id),
        )


@pytest.mark.persistence
@pytest.mark.enable_socket
def test_external_identity_enforces_exact_pair_uniqueness_and_planner_reference(
    migrated_database: None,
) -> None:
    runtime_url = psycopg_url("DATABASE_URL")
    planner_id = uuid7()
    issuer = f"https://issuer.example/{planner_id}"
    subject = f"subject-{planner_id}"
    with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO planners (id, access_status) VALUES (%s, 'Active')",
            (planner_id,),
        )
        cursor.execute(
            """
            INSERT INTO external_identities (id, issuer, subject, planner_id)
            VALUES (%s, %s, %s, %s)
            """,
            (uuid7(), issuer, subject, planner_id),
        )

    with pytest.raises(psycopg.errors.UniqueViolation):
        insert_external_identity(
            runtime_url,
            planner_id=planner_id,
            issuer=issuer,
            subject=subject,
        )

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        insert_external_identity(
            runtime_url,
            planner_id=uuid7(),
            issuer="https://other-issuer.example",
            subject="subject",
        )


@pytest.mark.persistence
@pytest.mark.enable_socket
def test_planner_access_status_rejects_values_outside_the_closed_set(
    migrated_database: None,
) -> None:
    with (
        psycopg.connect(psycopg_url("DATABASE_URL")) as connection,
        connection.cursor() as cursor,
        pytest.raises(psycopg.errors.CheckViolation),
    ):
        cursor.execute(
            "INSERT INTO planners (id, access_status) VALUES (%s, 'Unknown')",
            (uuid7(),),
        )


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
@pytest.mark.parametrize(
    ("issuer", "subject", "access_status", "expected"),
    [
        ("matching", "matching", PlannerAccessStatus.ACTIVE, True),
        ("matching", "different", PlannerAccessStatus.ACTIVE, False),
        ("different", "matching", PlannerAccessStatus.ACTIVE, False),
        ("matching", "matching", PlannerAccessStatus.SUSPENDED, False),
        ("matching", "matching", PlannerAccessStatus.CLOSED, False),
    ],
)
async def test_exact_identity_resolution_requires_active_planner(
    migrated_database: None,
    issuer: str,
    subject: str,
    access_status: PlannerAccessStatus,
    expected: bool,
) -> None:
    runtime_url = psycopg_url("DATABASE_URL")
    planner_id = uuid7()
    stored_issuer = f"https://issuer.example/{planner_id}"
    stored_subject = f"allowed-{planner_id}"
    with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO planners (id, access_status) VALUES (%s, %s)",
            (planner_id, access_status.value),
        )
        cursor.execute(
            """
            INSERT INTO external_identities (id, issuer, subject, planner_id)
            VALUES (%s, %s, %s, %s)
            """,
            (uuid7(), stored_issuer, stored_subject, planner_id),
        )

    database = PostgresDatabase(required_url("DATABASE_URL"))
    resolver = ResolvePlanner(
        PostgresExternalIdentityRepositoryFactory(database),
        AllowedExternalIdentity(
            issuer=stored_issuer,
            subject=stored_subject,
        ),
    )
    try:
        resolved = await resolver.resolve(
            AuthenticatedPrincipal(
                issuer=(
                    stored_issuer
                    if issuer == "matching"
                    else "https://different-issuer.example"
                ),
                subject=stored_subject
                if subject == "matching"
                else "different-subject",
                scopes=frozenset({"principal:read"}),
            )
        )
    finally:
        await database.close()

    assert (resolved is not None) is expected
    if resolved is not None:
        assert resolved.planner_id == planner_id


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_second_planner_identifier_cannot_resolve_first_planner(
    migrated_database: None,
) -> None:
    runtime_url = psycopg_url("DATABASE_URL")
    first_planner_id = uuid7()
    second_planner_id = uuid7()
    issuer = f"https://issuer.example/{first_planner_id}"
    first_subject = f"first-{first_planner_id}"
    second_subject = f"second-{second_planner_id}"
    with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO planners (id, access_status) VALUES (%s, 'Active')",
            [(first_planner_id,), (second_planner_id,)],
        )
        cursor.executemany(
            """
            INSERT INTO external_identities (id, issuer, subject, planner_id)
            VALUES (%s, %s, %s, %s)
            """,
            [
                (uuid7(), issuer, first_subject, first_planner_id),
                (uuid7(), issuer, second_subject, second_planner_id),
            ],
        )

    database = PostgresDatabase(required_url("DATABASE_URL"))
    resolver = ResolvePlanner(
        PostgresExternalIdentityRepositoryFactory(database),
        AllowedExternalIdentity(
            issuer=issuer,
            subject=second_subject,
        ),
    )
    try:
        resolved = await resolver.resolve(
            AuthenticatedPrincipal(
                issuer=issuer,
                subject=second_subject,
                scopes=frozenset({"principal:read"}),
            )
        )
    finally:
        await database.close()

    assert resolved == PlannerPrincipal(planner_id=second_planner_id)
    assert resolved != PlannerPrincipal(planner_id=first_planner_id)


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_allowlisted_identity_without_a_database_mapping_fails_closed(
    migrated_database: None,
) -> None:
    identity = AllowedExternalIdentity(
        issuer=f"https://issuer.example/{uuid7()}",
        subject=f"unknown-{uuid7()}",
    )
    database = PostgresDatabase(required_url("DATABASE_URL"))
    resolver = ResolvePlanner(
        PostgresExternalIdentityRepositoryFactory(database),
        identity,
    )
    try:
        resolved = await resolver.resolve(
            AuthenticatedPrincipal(
                issuer=identity.issuer,
                subject=identity.subject,
                scopes=frozenset({"principal:read"}),
            )
        )
    finally:
        await database.close()

    assert resolved is None
