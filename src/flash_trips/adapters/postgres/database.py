from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from flash_trips.application.persistence import PlannerPrincipal

from .repositories import PostgresPlannerRepository


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


class PostgresUnitOfWork:
    def __init__(
        self,
        database: PostgresDatabase,
        principal: PlannerPrincipal,
    ) -> None:
        self._database = database
        self._principal = principal
        self._transaction: AbstractAsyncContextManager[AsyncConnection] | None = None
        self._planners: PostgresPlannerRepository | None = None

    @property
    def planners(self) -> PostgresPlannerRepository:
        if self._planners is None:
            raise RuntimeError("Unit of work has not been entered")
        return self._planners

    async def __aenter__(self) -> Self:
        transaction = self._database.transaction()
        connection = await transaction.__aenter__()
        self._transaction = transaction
        self._planners = PostgresPlannerRepository(connection, self._principal)
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
