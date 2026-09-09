from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.elements import ColumnElement

from flash_trips.application.persistence import (
    ActiveRunExistsError,
    ApprovalAlreadyRecordedError,
    ApprovalNotFoundError,
    ApprovalRecord,
    ApprovalRequestRecord,
    BoundApprovalAction,
    HandbookDeliveryRecord,
    HandbookExportFormat,
    HandbookNotEligibleError,
    HandbookSnapshotRecord,
    PlanClaimKind,
    PlanClaimRecord,
    PlannerAccessStatus,
    PlannerPrincipal,
    PlannerRecord,
    PlanRevisionRecord,
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
from flash_trips.kernel.evidence import EvidenceReference
from flash_trips.kernel.identifiers import uuid7

from .models import (
    ApprovalModel,
    ApprovalRequestModel,
    ExternalIdentityModel,
    HandbookDeliveryModel,
    HandbookSnapshotModel,
    PlanClaimModel,
    PlannerModel,
    PlanRevisionModel,
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


class PostgresPlanRevisionRepository:
    def __init__(
        self,
        connection: AsyncConnection,
        principal: PlannerPrincipal,
    ) -> None:
        self._connection = connection
        self._principal = principal

    async def commit(self, revision: PlanRevisionRecord) -> PlanRevisionRecord:
        if revision.planner_id != self._principal.planner_id:
            raise ValueError("Plan Revision does not match the repository principal")
        if not revision.claims:
            raise ValueError("A Plan Revision must contain at least one claim")

        trip = (
            await self._connection.execute(
                select(TripModel.id, TripModel.current_plan_revision_id)
                .where(
                    TripModel.id == revision.trip_id,
                    TripModel.planner_id == self._principal.planner_id,
                )
                .with_for_update()
            )
        ).one_or_none()
        if trip is None:
            raise ValueError("Trip does not match the repository principal")
        run_id = (
            await self._connection.execute(
                select(RunModel.id)
                .where(
                    RunModel.id == revision.run_id,
                    RunModel.trip_id == revision.trip_id,
                    RunModel.planner_id == self._principal.planner_id,
                    RunModel.terminal_status.is_(None),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if run_id is None:
            raise ValueError("Run is not active for this Trip")

        current = (
            await self._get(revision.trip_id, trip.current_plan_revision_id)
            if trip.current_plan_revision_id is not None
            else None
        )
        expected_base = current.id if current is not None else None
        expected_number = current.revision_number + 1 if current is not None else 1
        if (
            revision.base_revision_id != expected_base
            or revision.revision_number != expected_number
        ):
            raise ValueError("Plan Revision does not extend the current revision")

        await self._connection.execute(
            insert(PlanRevisionModel).values(
                id=revision.id,
                planner_id=self._principal.planner_id,
                trip_id=revision.trip_id,
                run_id=revision.run_id,
                revision_number=revision.revision_number,
                base_revision_id=revision.base_revision_id,
            )
        )
        await self._connection.execute(
            insert(PlanClaimModel),
            [
                {
                    "id": claim.id,
                    "plan_revision_id": revision.id,
                    "trip_id": revision.trip_id,
                    "planner_id": self._principal.planner_id,
                    "kind": claim.kind.value,
                    "text": claim.text,
                    "evidence_reference": claim.evidence_reference.value,
                    "observed_at": claim.observed_at,
                }
                for claim in revision.claims
            ],
        )
        await self._connection.execute(
            update(TripModel)
            .where(
                TripModel.id == revision.trip_id,
                TripModel.planner_id == self._principal.planner_id,
                TripModel.current_plan_revision_id == revision.base_revision_id,
            )
            .values(current_plan_revision_id=revision.id)
        )
        return revision

    async def get_current(self, trip_id: UUID) -> PlanRevisionRecord | None:
        revision_id = (
            await self._connection.execute(
                select(TripModel.current_plan_revision_id).where(
                    TripModel.id == trip_id,
                    TripModel.planner_id == self._principal.planner_id,
                )
            )
        ).scalar_one_or_none()
        if revision_id is None:
            return None
        return await self._get(trip_id, revision_id)

    async def _get(
        self,
        trip_id: UUID,
        revision_id: UUID,
    ) -> PlanRevisionRecord | None:
        revision = (
            await self._connection.execute(
                select(
                    PlanRevisionModel.id,
                    PlanRevisionModel.planner_id,
                    PlanRevisionModel.trip_id,
                    PlanRevisionModel.run_id,
                    PlanRevisionModel.revision_number,
                    PlanRevisionModel.base_revision_id,
                ).where(
                    PlanRevisionModel.id == revision_id,
                    PlanRevisionModel.trip_id == trip_id,
                    PlanRevisionModel.planner_id == self._principal.planner_id,
                )
            )
        ).one_or_none()
        if revision is None:
            return None
        claims = (
            await self._connection.execute(
                select(
                    PlanClaimModel.id,
                    PlanClaimModel.kind,
                    PlanClaimModel.text,
                    PlanClaimModel.evidence_reference,
                    PlanClaimModel.observed_at,
                )
                .where(
                    PlanClaimModel.plan_revision_id == revision.id,
                    PlanClaimModel.planner_id == self._principal.planner_id,
                )
                .order_by(PlanClaimModel.id)
            )
        ).all()
        return PlanRevisionRecord(
            id=revision.id,
            planner_id=revision.planner_id,
            trip_id=revision.trip_id,
            run_id=revision.run_id,
            revision_number=revision.revision_number,
            base_revision_id=revision.base_revision_id,
            claims=tuple(
                PlanClaimRecord(
                    id=claim.id,
                    kind=PlanClaimKind(claim.kind),
                    text=claim.text,
                    evidence_reference=EvidenceReference(claim.evidence_reference),
                    observed_at=claim.observed_at,
                )
                for claim in claims
            ),
        )


class PostgresApprovalRepository:
    def __init__(
        self,
        connection: AsyncConnection,
        principal: PlannerPrincipal,
    ) -> None:
        self._connection = connection
        self._principal = principal

    async def present(self, request: ApprovalRequestRecord) -> None:
        if request.planner_id != self._principal.planner_id:
            raise ValueError("Approval Request does not match the repository principal")
        current_revision = (
            await self._connection.execute(
                select(PlanRevisionModel.id)
                .join(
                    TripModel,
                    (TripModel.id == PlanRevisionModel.trip_id)
                    & (TripModel.planner_id == PlanRevisionModel.planner_id),
                )
                .where(
                    PlanRevisionModel.id == request.plan_revision_id,
                    PlanRevisionModel.planner_id == self._principal.planner_id,
                    TripModel.current_plan_revision_id == PlanRevisionModel.id,
                )
            )
        ).scalar_one_or_none()
        if current_revision is None:
            raise ValueError("Plan Revision does not match the repository principal")
        await self._connection.execute(
            insert(ApprovalRequestModel).values(
                id=request.id,
                planner_id=self._principal.planner_id,
                plan_revision_id=request.plan_revision_id,
            )
        )

    async def get_request(
        self,
        plan_revision_id: UUID,
    ) -> ApprovalRequestRecord | None:
        row = (
            await self._connection.execute(
                select(
                    ApprovalRequestModel.id,
                    ApprovalRequestModel.planner_id,
                    ApprovalRequestModel.plan_revision_id,
                ).where(
                    ApprovalRequestModel.plan_revision_id == plan_revision_id,
                    ApprovalRequestModel.planner_id == self._principal.planner_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return ApprovalRequestRecord(
            id=row.id,
            planner_id=row.planner_id,
            plan_revision_id=row.plan_revision_id,
        )

    async def approve(self, action: BoundApprovalAction) -> ApprovalRecord:
        request_id = (
            await self._connection.execute(
                select(ApprovalRequestModel.id)
                .join(
                    PlanRevisionModel,
                    (PlanRevisionModel.id == ApprovalRequestModel.plan_revision_id)
                    & (PlanRevisionModel.planner_id == ApprovalRequestModel.planner_id),
                )
                .join(
                    TripModel,
                    (TripModel.id == PlanRevisionModel.trip_id)
                    & (TripModel.planner_id == PlanRevisionModel.planner_id),
                )
                .where(
                    ApprovalRequestModel.id == action.approval_request_id,
                    ApprovalRequestModel.plan_revision_id == action.plan_revision_id,
                    ApprovalRequestModel.planner_id == self._principal.planner_id,
                    TripModel.current_plan_revision_id == action.plan_revision_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if request_id is None:
            raise ApprovalNotFoundError(action.approval_request_id)

        approval = ApprovalRecord(
            id=uuid7(),
            planner_id=self._principal.planner_id,
            approval_request_id=action.approval_request_id,
            plan_revision_id=action.plan_revision_id,
        )
        inserted = await self._connection.execute(
            postgres_insert(ApprovalModel)
            .values(
                id=approval.id,
                planner_id=approval.planner_id,
                approval_request_id=approval.approval_request_id,
                plan_revision_id=approval.plan_revision_id,
            )
            .on_conflict_do_nothing(index_elements=[ApprovalModel.approval_request_id])
            .returning(ApprovalModel.id)
        )
        if inserted.scalar_one_or_none() is None:
            raise ApprovalAlreadyRecordedError(action.approval_request_id)
        return approval

    async def get_approval(self, plan_revision_id: UUID) -> ApprovalRecord | None:
        row = (
            await self._connection.execute(
                select(
                    ApprovalModel.id,
                    ApprovalModel.planner_id,
                    ApprovalModel.approval_request_id,
                    ApprovalModel.plan_revision_id,
                ).where(
                    ApprovalModel.plan_revision_id == plan_revision_id,
                    ApprovalModel.planner_id == self._principal.planner_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return ApprovalRecord(
            id=row.id,
            planner_id=row.planner_id,
            approval_request_id=row.approval_request_id,
            plan_revision_id=row.plan_revision_id,
        )


class PostgresHandbookRepository:
    def __init__(
        self,
        connection: AsyncConnection,
        principal: PlannerPrincipal,
    ) -> None:
        self._connection = connection
        self._principal = principal

    async def get_for_revision(
        self,
        plan_revision_id: UUID,
    ) -> HandbookSnapshotRecord | None:
        return await self._get(plan_revision_id, by_revision=True)

    async def add(
        self,
        snapshot: HandbookSnapshotRecord,
    ) -> HandbookSnapshotRecord:
        if snapshot.planner_id != self._principal.planner_id:
            raise HandbookNotEligibleError(snapshot.plan_revision_id)
        qualifying_approval = (
            await self._connection.execute(
                select(ApprovalModel.id)
                .join(
                    PlanRevisionModel,
                    (PlanRevisionModel.id == ApprovalModel.plan_revision_id)
                    & (PlanRevisionModel.planner_id == ApprovalModel.planner_id),
                )
                .join(
                    TripModel,
                    (TripModel.id == PlanRevisionModel.trip_id)
                    & (TripModel.planner_id == PlanRevisionModel.planner_id),
                )
                .where(
                    ApprovalModel.id == snapshot.approval_id,
                    ApprovalModel.plan_revision_id == snapshot.plan_revision_id,
                    ApprovalModel.planner_id == self._principal.planner_id,
                    TripModel.current_plan_revision_id == snapshot.plan_revision_id,
                )
            )
        ).scalar_one_or_none()
        if qualifying_approval is None:
            raise HandbookNotEligibleError(snapshot.plan_revision_id)

        inserted = await self._connection.execute(
            postgres_insert(HandbookSnapshotModel)
            .values(
                id=snapshot.id,
                planner_id=self._principal.planner_id,
                plan_revision_id=snapshot.plan_revision_id,
                approval_id=snapshot.approval_id,
                document_schema_version=snapshot.document_schema_version,
                export_bytes=snapshot.export_bytes,
                checksum=snapshot.checksum,
            )
            .on_conflict_do_nothing(
                index_elements=[HandbookSnapshotModel.plan_revision_id]
            )
            .returning(HandbookSnapshotModel.id)
        )
        if inserted.scalar_one_or_none() is not None:
            return snapshot
        existing = await self.get_for_revision(snapshot.plan_revision_id)
        if existing is None or (
            existing.approval_id != snapshot.approval_id
            or existing.document_schema_version != snapshot.document_schema_version
            or existing.export_bytes != snapshot.export_bytes
            or existing.checksum != snapshot.checksum
        ):
            raise HandbookNotEligibleError(snapshot.plan_revision_id)
        return existing

    async def deliver(
        self,
        snapshot_id: UUID,
        delivered_at: datetime,
    ) -> tuple[HandbookSnapshotRecord, HandbookDeliveryRecord] | None:
        snapshot = await self._get(snapshot_id)
        if snapshot is None:
            return None
        delivery = HandbookDeliveryRecord(
            id=uuid7(),
            planner_id=self._principal.planner_id,
            snapshot_id=snapshot.id,
            export_format=HandbookExportFormat.HTML,
            checksum=snapshot.checksum,
            delivered_at=delivered_at,
        )
        await self._connection.execute(
            insert(HandbookDeliveryModel).values(
                id=delivery.id,
                planner_id=delivery.planner_id,
                snapshot_id=delivery.snapshot_id,
                export_format=delivery.export_format.value,
                checksum=delivery.checksum,
                delivered_at=delivery.delivered_at,
            )
        )
        return snapshot, delivery

    async def _get(
        self,
        identifier: UUID,
        *,
        by_revision: bool = False,
    ) -> HandbookSnapshotRecord | None:
        identifier_column = (
            HandbookSnapshotModel.plan_revision_id
            if by_revision
            else HandbookSnapshotModel.id
        )
        row = (
            await self._connection.execute(
                select(
                    HandbookSnapshotModel.id,
                    HandbookSnapshotModel.planner_id,
                    HandbookSnapshotModel.plan_revision_id,
                    HandbookSnapshotModel.approval_id,
                    HandbookSnapshotModel.document_schema_version,
                    HandbookSnapshotModel.export_bytes,
                    HandbookSnapshotModel.checksum,
                ).where(
                    identifier_column == identifier,
                    HandbookSnapshotModel.planner_id == self._principal.planner_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return HandbookSnapshotRecord(
            id=row.id,
            planner_id=row.planner_id,
            plan_revision_id=row.plan_revision_id,
            approval_id=row.approval_id,
            document_schema_version=row.document_schema_version,
            export_bytes=row.export_bytes,
            checksum=row.checksum,
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
