from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from flash_trips.application.persistence import PlannerPrincipal
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal

from .repositories import (
    PostgresApprovalRepository,
    PostgresExternalIdentityRepository,
    PostgresPlannerRepository,
    PostgresPlanRevisionRepository,
    PostgresRunRepository,
    PostgresTripRepository,
)


class PostgresDatabase:
    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("PostgreSQL with the asyncpg driver is required")
        self._engine: AsyncEngine = create_async_engine(
            database_url,
            pool_pre_ping=True,
        )

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncConnection]:
        async with self._engine.begin() as connection:
            yield connection

    async def close(self) -> None:
        await self._engine.dispose()


class PostgresUnitOfWorkFactory:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def __call__(self, principal: PlannerPrincipal) -> "PostgresUnitOfWork":
        return PostgresUnitOfWork(self._database, principal)


class PostgresExternalIdentityRepositoryFactory:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def __call__(
        self, principal: AuthenticatedPrincipal
    ) -> PostgresExternalIdentityRepository:
        return PostgresExternalIdentityRepository(
            self._database.transaction,
            principal,
        )


class PostgresUnitOfWork:
    def __init__(
        self,
        database: PostgresDatabase,
        principal: PlannerPrincipal,
    ) -> None:
        self._database = database
        self._principal = principal
        self._transaction: AbstractAsyncContextManager[AsyncConnection] | None = None
        self._approvals: PostgresApprovalRepository | None = None
        self._planners: PostgresPlannerRepository | None = None
        self._plan_revisions: PostgresPlanRevisionRepository | None = None
        self._runs: PostgresRunRepository | None = None
        self._trips: PostgresTripRepository | None = None

    @property
    def approvals(self) -> PostgresApprovalRepository:
        if self._approvals is None:
            raise RuntimeError("Unit of work has not been entered")
        return self._approvals

    @property
    def planners(self) -> PostgresPlannerRepository:
        if self._planners is None:
            raise RuntimeError("Unit of work has not been entered")
        return self._planners

    @property
    def trips(self) -> PostgresTripRepository:
        if self._trips is None:
            raise RuntimeError("Unit of work has not been entered")
        return self._trips

    @property
    def runs(self) -> PostgresRunRepository:
        if self._runs is None:
            raise RuntimeError("Unit of work has not been entered")
        return self._runs

    @property
    def plan_revisions(self) -> PostgresPlanRevisionRepository:
        if self._plan_revisions is None:
            raise RuntimeError("Unit of work has not been entered")
        return self._plan_revisions

    async def __aenter__(self) -> Self:
        transaction = self._database.transaction()
        connection = await transaction.__aenter__()
        self._transaction = transaction
        self._approvals = PostgresApprovalRepository(connection, self._principal)
        self._planners = PostgresPlannerRepository(connection, self._principal)
        self._plan_revisions = PostgresPlanRevisionRepository(
            connection, self._principal
        )
        self._runs = PostgresRunRepository(connection, self._principal)
        self._trips = PostgresTripRepository(connection, self._principal)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        transaction = self._transaction
        if transaction is None:
            raise RuntimeError("Unit of work has not been entered")
        await transaction.__aexit__(exc_type, exc_value, traceback)
