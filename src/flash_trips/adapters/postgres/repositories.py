from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.elements import ColumnElement

from flash_trips.application.persistence import (
    ActiveRunExistsError,
    PlannerAccessStatus,
    PlannerPrincipal,
    PlannerRecord,
    RunNotFoundError,
    RunRecord,
    RunTerminalOutcome,
    RunTerminalStatus,
    TerminalOutcomeAlreadyRecordedError,
    TripRecord,
    TripStayRecord,
    TripStructureRecord,
)
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal

from .models import (
    ExternalIdentityModel,
    PlannerModel,
    RunModel,
    TripModel,
    TripStructureModel,
)


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


class PostgresTripRepository:
    def __init__(
        self,
        connection: AsyncConnection,
        principal: PlannerPrincipal,
    ) -> None:
        self._connection = connection
        self._principal = principal

    async def add(self, trip: TripRecord) -> None:
        if trip.planner_id != self._principal.planner_id:
            raise ValueError("Trip does not match the repository principal")
        await self._connection.execute(
            insert(TripModel).values(
                id=trip.id,
                planner_id=self._principal.planner_id,
            )
        )
        if trip.structure.stays:
            await self._connection.execute(
                insert(TripStructureModel),
                [
                    {
                        "id": stay.id,
                        "trip_id": trip.id,
                        "planner_id": self._principal.planner_id,
                        "position": position,
                        "city": stay.city,
                        "starts_on": stay.starts_on,
                        "ends_on": stay.ends_on,
                        "nights": stay.nights,
                    }
                    for position, stay in enumerate(trip.structure.stays)
                ],
            )

    async def get(self, trip_id: UUID) -> TripRecord | None:
        records = await self._read(TripModel.id == trip_id)
        return records[0] if records else None

    async def list(self) -> list[TripRecord]:
        return await self._read()

    async def _read(
        self,
        condition: ColumnElement[bool] | None = None,
    ) -> list[TripRecord]:
        statement = (
            select(
                TripModel.id.label("trip_id"),
                TripModel.planner_id,
                TripStructureModel.id.label("stay_id"),
                TripStructureModel.city,
                TripStructureModel.starts_on,
                TripStructureModel.ends_on,
                TripStructureModel.nights,
            )
            .join(
                TripStructureModel,
                (TripStructureModel.trip_id == TripModel.id)
                & (TripStructureModel.planner_id == TripModel.planner_id),
            )
            .where(
                TripModel.planner_id == self._principal.planner_id,
                TripStructureModel.planner_id == self._principal.planner_id,
            )
            .order_by(TripModel.id, TripStructureModel.position)
        )
        if condition is not None:
            statement = statement.where(condition)
        rows = (await self._connection.execute(statement)).all()
        trips: list[TripRecord] = []
        for row in rows:
            if not trips or trips[-1].id != row.trip_id:
                trips.append(
                    TripRecord(
                        id=row.trip_id,
                        planner_id=row.planner_id,
                        structure=TripStructureRecord(stays=()),
                    )
                )
            current = trips[-1]
            trips[-1] = TripRecord(
                id=current.id,
                planner_id=current.planner_id,
                structure=TripStructureRecord(
                    stays=(
                        *current.structure.stays,
                        TripStayRecord(
                            id=row.stay_id,
                            city=row.city,
                            starts_on=row.starts_on,
                            ends_on=row.ends_on,
                            nights=row.nights,
                        ),
                    )
                ),
            )
        return trips


class PostgresRunRepository:
    def __init__(
        self,
        connection: AsyncConnection,
        principal: PlannerPrincipal,
    ) -> None:
        self._connection = connection
        self._principal = principal

    async def add(self, run: RunRecord) -> None:
        if run.planner_id != self._principal.planner_id:
            raise ValueError("Run does not match the repository principal")
        inserted = await self._connection.execute(
            postgres_insert(RunModel)
            .values(
                id=run.id,
                planner_id=self._principal.planner_id,
                trip_id=run.trip_id,
                terminal_status=(
                    run.terminal_outcome.status.value
                    if run.terminal_outcome is not None
                    else None
                ),
                terminal_code=(
                    run.terminal_outcome.code
                    if run.terminal_outcome is not None
                    else None
                ),
                terminal_detail=(
                    run.terminal_outcome.detail
                    if run.terminal_outcome is not None
                    else None
                ),
            )
            .on_conflict_do_nothing(
                index_elements=[RunModel.trip_id],
                index_where=RunModel.terminal_status.is_(None),
            )
            .returning(RunModel.id)
        )
        if inserted.scalar_one_or_none() is not None:
            return
        active_run_id = (
            await self._connection.execute(
                select(RunModel.id).where(
                    RunModel.planner_id == self._principal.planner_id,
                    RunModel.trip_id == run.trip_id,
                    RunModel.terminal_status.is_(None),
                )
            )
        ).scalar_one()
        raise ActiveRunExistsError(active_run_id)

    async def get(self, run_id: UUID) -> RunRecord | None:
        result = await self._connection.execute(
            select(
                RunModel.id,
                RunModel.planner_id,
                RunModel.trip_id,
                RunModel.terminal_status,
                RunModel.terminal_code,
                RunModel.terminal_detail,
            ).where(
                RunModel.id == run_id,
                RunModel.planner_id == self._principal.planner_id,
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        outcome = None
        if row.terminal_status is not None:
            outcome = RunTerminalOutcome(
                status=RunTerminalStatus(row.terminal_status),
                code=row.terminal_code,
                detail=row.terminal_detail,
            )
        return RunRecord(
            id=row.id,
            planner_id=row.planner_id,
            trip_id=row.trip_id,
            terminal_outcome=outcome,
        )

    async def record_terminal(
        self,
        run_id: UUID,
        outcome: RunTerminalOutcome,
    ) -> RunRecord:
        result = await self._connection.execute(
            update(RunModel)
            .where(
                RunModel.id == run_id,
                RunModel.planner_id == self._principal.planner_id,
                RunModel.terminal_status.is_(None),
            )
            .values(
                terminal_status=outcome.status.value,
                terminal_code=outcome.code,
                terminal_detail=outcome.detail,
            )
            .returning(RunModel.trip_id)
        )
        trip_id = result.scalar_one_or_none()
        if trip_id is not None:
            return RunRecord(
                id=run_id,
                planner_id=self._principal.planner_id,
                trip_id=trip_id,
                terminal_outcome=outcome,
            )
        existing = await self.get(run_id)
        if existing is None:
            raise RunNotFoundError(run_id)
        raise TerminalOutcomeAlreadyRecordedError(run_id)


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
