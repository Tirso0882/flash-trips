"""Add principal-owned Runs with sealed terminal outcomes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_run"
down_revision: str | None = "0005_trip"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("planner_id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("terminal_status", sa.String(length=16), nullable=True),
        sa.Column("terminal_code", sa.String(length=100), nullable=True),
        sa.Column("terminal_detail", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "terminal_status IS NULL OR "
            "terminal_status IN ('Succeeded', 'Blocked', 'Failed', 'Cancelled')",
            name=op.f("ck_runs_terminal_status_values"),
        ),
        sa.CheckConstraint(
            "(terminal_status IS NULL AND terminal_code IS NULL "
            "AND terminal_detail IS NULL) OR "
            "(terminal_status IS NOT NULL AND terminal_code IS NOT NULL "
            "AND terminal_detail IS NOT NULL)",
            name=op.f("ck_runs_terminal_outcome_complete"),
        ),
        sa.ForeignKeyConstraint(
            ["planner_id"],
            ["planners.id"],
            name=op.f("fk_runs_planner_id_planners"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id", "planner_id"],
            ["trips.id", "trips.planner_id"],
            name=op.f("fk_runs_trip_id_planner_id_trips"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
    )
    op.create_index(
        op.f("ix_runs_planner_id"),
        "runs",
        ["planner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_runs_trip_id"),
        "runs",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        "uq_runs_active_trip",
        "runs",
        ["trip_id"],
        unique=True,
        postgresql_where=sa.text("terminal_status IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_runs_active_trip", table_name="runs")
    op.drop_index(op.f("ix_runs_trip_id"), table_name="runs")
    op.drop_index(op.f("ix_runs_planner_id"), table_name="runs")
    op.drop_table("runs")
