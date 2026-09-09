"""Add immutable evidence-backed Plan Revisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_plan_revision"
down_revision: str | None = "0006_run"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        op.f("uq_runs_id_trip_id_planner_id"),
        "runs",
        ["id", "trip_id", "planner_id"],
    )
    op.create_table(
        "plan_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("planner_id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("base_revision_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "revision_number > 0",
            name=op.f("ck_plan_revisions_revision_number_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["planner_id"],
            ["planners.id"],
            name=op.f("fk_plan_revisions_planner_id_planners"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "trip_id", "planner_id"],
            ["runs.id", "runs.trip_id", "runs.planner_id"],
            name=op.f("fk_plan_revisions_run_id_trip_id_planner_id_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id", "planner_id"],
            ["trips.id", "trips.planner_id"],
            name=op.f("fk_plan_revisions_trip_id_planner_id_trips"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_revisions")),
        sa.UniqueConstraint(
            "id",
            "trip_id",
            "planner_id",
            name=op.f("uq_plan_revisions_id_trip_id_planner_id"),
        ),
        sa.UniqueConstraint(
            "trip_id",
            "revision_number",
            name=op.f("uq_plan_revisions_trip_id_revision_number"),
        ),
        sa.UniqueConstraint("run_id", name=op.f("uq_plan_revisions_run_id")),
    )
    op.create_foreign_key(
        op.f("fk_plan_revisions_base_revision_id_trip_id_planner_id_plan_revisions"),
        "plan_revisions",
        "plan_revisions",
        ["base_revision_id", "trip_id", "planner_id"],
        ["id", "trip_id", "planner_id"],
        ondelete="RESTRICT",
    )
    for column in ("planner_id", "trip_id", "run_id", "base_revision_id"):
        op.create_index(
            op.f(f"ix_plan_revisions_{column}"),
            "plan_revisions",
            [column],
            unique=False,
        )
    op.add_column(
        "trips",
        sa.Column("current_plan_revision_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_trips_current_plan_revision_id_id_planner_id_plan_revisions"),
        "trips",
        "plan_revisions",
        ["current_plan_revision_id", "id", "planner_id"],
        ["id", "trip_id", "planner_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_trips_current_plan_revision_id"),
        "trips",
        ["current_plan_revision_id"],
        unique=False,
    )

    op.create_table(
        "plan_claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("planner_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=100), nullable=False),
        sa.Column("text", sa.String(length=2000), nullable=False),
        sa.Column("evidence_reference", sa.String(length=500), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('travel_readiness')",
            name=op.f("ck_plan_claims_kind_values"),
        ),
        sa.ForeignKeyConstraint(
            ["planner_id"],
            ["planners.id"],
            name=op.f("fk_plan_claims_planner_id_planners"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_revision_id", "trip_id", "planner_id"],
            [
                "plan_revisions.id",
                "plan_revisions.trip_id",
                "plan_revisions.planner_id",
            ],
            name=op.f(
                "fk_plan_claims_plan_revision_id_trip_id_planner_id_plan_revisions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_claims")),
    )
    for column in ("plan_revision_id", "trip_id", "planner_id"):
        op.create_index(
            op.f(f"ix_plan_claims_{column}"),
            "plan_claims",
            [column],
            unique=False,
        )

    op.execute(
        """
        CREATE FUNCTION refuse_immutable_plan_update()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION '% is immutable', TG_TABLE_NAME
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    for table in ("plan_revisions", "plan_claims"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_refuse_update
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION refuse_immutable_plan_update()
            """
        )


def downgrade() -> None:
    for table in ("plan_claims", "plan_revisions"):
        op.execute(f"DROP TRIGGER {table}_refuse_update ON {table}")
    op.execute("DROP FUNCTION refuse_immutable_plan_update()")
    op.execute("DROP INDEX IF EXISTS ix_trips_current_plan_revision_id")
    op.execute(
        """
        ALTER TABLE trips
        DROP CONSTRAINT IF EXISTS
            fk_trips_current_plan_revision_id_id_planner_id_plan_revisions
        """
    )
    op.execute("ALTER TABLE trips DROP COLUMN IF EXISTS current_plan_revision_id")
    op.drop_table("plan_claims")
    op.drop_table("plan_revisions")
    op.execute(
        """
        ALTER TABLE runs
        DROP CONSTRAINT IF EXISTS uq_runs_id_trip_id_planner_id
        """
    )
