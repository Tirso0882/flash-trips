from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from flash_trips.application.persistence import (
    PlannerAccessStatus,
    PlannerPrincipal,
    PlannerRecord,
)
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal

from .models import ExternalIdentityModel, PlannerModel


class PostgresPlannerRepository:
    def __init__(
        self,
        connection: AsyncConnection,
        principal: PlannerPrincipal,
    ) -> None:
        self._connection = connection
        self._principal = principal

    async def add(self, planner: PlannerRecord) -> None:
        if planner.id != self._principal.planner_id:
            raise ValueError("Planner does not match the repository principal")
        await self._connection.execute(
            insert(PlannerModel).values(
                id=planner.id,
                access_status=planner.access_status.value,
            ),
        )

    async def get(self, planner_id: UUID) -> PlannerRecord | None:
        result = await self._connection.execute(
            select(PlannerModel.id, PlannerModel.access_status).where(
                PlannerModel.id == planner_id,
                PlannerModel.id == self._principal.planner_id,
            ),
        )
        row = result.one_or_none()
        if row is None:
            return None
        return PlannerRecord(
            id=row.id,
            access_status=PlannerAccessStatus(row.access_status),
        )


class PostgresExternalIdentityRepository:
    def __init__(
        self,
        transaction: Callable[[], AbstractAsyncContextManager[AsyncConnection]],
        principal: AuthenticatedPrincipal,
    ) -> None:
        self._transaction = transaction
        self._principal = principal

    async def resolve(self) -> PlannerRecord | None:
        async with self._transaction() as connection:
            result = await connection.execute(
                select(PlannerModel.id, PlannerModel.access_status)
                .join(
                    ExternalIdentityModel,
                    ExternalIdentityModel.planner_id == PlannerModel.id,
                )
                .where(
                    ExternalIdentityModel.issuer == self._principal.issuer,
                    ExternalIdentityModel.subject == self._principal.subject,
                )
            )
            row = result.one_or_none()
        if row is None:
            return None
        return PlannerRecord(
            id=row.id,
            access_status=PlannerAccessStatus(row.access_status),
        )
