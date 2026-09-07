from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from flash_trips.application.persistence import PlannerPrincipal, PlannerRecord

from .models import PlannerModel


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
            insert(PlannerModel).values(id=planner.id),
        )

    async def get(self, planner_id: UUID) -> PlannerRecord | None:
        result = await self._connection.execute(
            select(PlannerModel.id).where(
                PlannerModel.id == planner_id,
                PlannerModel.id == self._principal.planner_id,
            ),
        )
        stored_id = result.scalar_one_or_none()
        if stored_id is None:
            return None
        return PlannerRecord(id=stored_id)
