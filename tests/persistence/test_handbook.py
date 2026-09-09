import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

import psycopg
import pytest

from flash_trips.adapters.postgres import PostgresDatabase, PostgresUnitOfWorkFactory
from flash_trips.application import (
    ApprovalRecord,
    ApprovalRequestRecord,
    BoundApprovalAction,
    HandbookNotEligibleError,
    HandbookSnapshotRecord,
    PlanClaimKind,
    PlanClaimRecord,
    PlannerPrincipal,
    PlannerRecord,
    PlanRevisionRecord,
    RunRecord,
    TripRecord,
    TripStayRecord,
    TripStructureRecord,
    UnitOfWorkFactory,
)
from flash_trips.kernel import EvidenceReference
from flash_trips.kernel.identifiers import uuid7
from flash_trips.platform.handbook import HandbookClaim, compile_document, render_html


def required_url(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        pytest.skip(f"{name} is required for real PostgreSQL tests")
    return value


def render_revision(revision: PlanRevisionRecord) -> bytes:
    return render_html(
        compile_document(
            plan_revision_id=str(revision.id),
            revision_number=revision.revision_number,
            claims=tuple(
                HandbookClaim(
                    text=claim.text,
                    evidence_reference=claim.evidence_reference.value,
                    observed_at=claim.observed_at,
                )
                for claim in revision.claims
            ),
        )
    )


@pytest.fixture(scope="module", autouse=True)
def migrated_database() -> None:
    migration_url = required_url("MIGRATION_DATABASE_URL").replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "MIGRATION_DATABASE_URL": migration_url},
    )
    assert result.returncode == 0, result.stdout + result.stderr


async def approved_revision(
    factory: UnitOfWorkFactory,
    planner_id: UUID,
) -> tuple[PlannerPrincipal, PlanRevisionRecord, ApprovalRecord]:
    principal = PlannerPrincipal(planner_id)
    _trip, revision = await add_planner_trip_and_revision(factory, principal.planner_id)
    request = ApprovalRequestRecord(uuid7(), principal.planner_id, revision.id)
    async with factory(principal) as unit_of_work:
        await unit_of_work.approvals.present(request)
        approval = await unit_of_work.approvals.approve(
            BoundApprovalAction(request.id, revision.id)
        )
    return principal, revision, approval


async def add_planner_trip_and_revision(
    factory: UnitOfWorkFactory,
    planner_id: UUID,
) -> tuple[TripRecord, PlanRevisionRecord]:
    principal = PlannerPrincipal(planner_id)
    trip = TripRecord(
        id=uuid7(),
        planner_id=planner_id,
        structure=TripStructureRecord(
            stays=(
                TripStayRecord(
                    id=uuid7(),
                    city="Lisbon",
                    starts_on=date(2026, 10, 4),
                    ends_on=date(2026, 10, 7),
                    nights=3,
                ),
            )
        ),
    )
    run = RunRecord(id=uuid7(), planner_id=planner_id, trip_id=trip.id)
    revision = PlanRevisionRecord(
        id=uuid7(),
        planner_id=planner_id,
        trip_id=trip.id,
        run_id=run.id,
        revision_number=1,
        base_revision_id=None,
        claims=(
            PlanClaimRecord(
                id=uuid7(),
                kind=PlanClaimKind.TRAVEL_READINESS,
                text="No fixture concerns were found.",
                evidence_reference=EvidenceReference("fixture:lisbon:v1"),
                observed_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
            ),
        ),
    )
    async with factory(principal) as unit_of_work:
        await unit_of_work.planners.add(PlannerRecord(id=planner_id))
        await unit_of_work.trips.add(trip)
        await unit_of_work.runs.add(run)
        await unit_of_work.plan_revisions.commit(revision)
    return trip, revision


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_refuses_snapshot_without_a_qualifying_approval() -> None:
    planner_id = uuid7()
    principal = PlannerPrincipal(planner_id)
    database = PostgresDatabase(required_url("DATABASE_URL"))
    factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        _trip, revision = await add_planner_trip_and_revision(factory, planner_id)
        export = render_revision(revision)
        snapshot = HandbookSnapshotRecord.create(
            planner_id=planner_id,
            plan_revision_id=revision.id,
            approval_id=uuid7(),
            document_schema_version=1,
            export_bytes=export,
        )
        with pytest.raises(HandbookNotEligibleError):
            async with factory(principal) as unit_of_work:
                await unit_of_work.handbooks.add(snapshot)
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.persistence
@pytest.mark.enable_socket
async def test_snapshot_is_immutable_and_each_retrieval_records_delivery() -> None:
    planner_id = uuid7()
    database = PostgresDatabase(required_url("DATABASE_URL"))
    factory: UnitOfWorkFactory = PostgresUnitOfWorkFactory(database)
    try:
        principal, revision, approval = await approved_revision(factory, planner_id)
        export = render_revision(revision)
        snapshot = HandbookSnapshotRecord.create(
            planner_id=principal.planner_id,
            plan_revision_id=revision.id,
            approval_id=approval.id,
            document_schema_version=1,
            export_bytes=export,
        )
        async with factory(principal) as unit_of_work:
            assert await unit_of_work.handbooks.add(snapshot) == snapshot
            retry = HandbookSnapshotRecord.create(
                planner_id=principal.planner_id,
                plan_revision_id=revision.id,
                approval_id=approval.id,
                document_schema_version=1,
                export_bytes=export,
            )
            assert await unit_of_work.handbooks.add(retry) == snapshot
            delivered = await unit_of_work.handbooks.deliver(
                snapshot.id, datetime(2026, 9, 9, 12, tzinfo=UTC)
            )

        assert delivered is not None
        served, delivery = delivered
        assert served.export_bytes == export
        assert delivery.snapshot_id == snapshot.id
        assert delivery.planner_id == principal.planner_id
        assert delivery.checksum == snapshot.checksum
        assert not hasattr(delivery, "opened_at")
        assert not hasattr(delivery, "approval_id")

        runtime_url = required_url("DATABASE_URL").replace(
            "postgresql+asyncpg://", "postgresql://", 1
        )
        with (
            psycopg.connect(runtime_url) as connection,
            connection.cursor() as cursor,
            pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState),
        ):
            cursor.execute(
                "UPDATE handbook_snapshots SET export_bytes = %s WHERE id = %s",
                (replace(snapshot, export_bytes=b"changed").export_bytes, snapshot.id),
            )
    finally:
        await database.close()
