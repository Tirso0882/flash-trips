"""Add principal-owned Trips and ordered Trip Structure stays."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_trip"
down_revision: str | None = "0004_application_session"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trips",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("planner_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["planner_id"],
            ["planners.id"],
            name=op.f("fk_trips_planner_id_planners"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trips")),
        sa.UniqueConstraint(
            "id",
            "planner_id",
            name=op.f("uq_trips_id_planner_id"),
        ),
    )
    op.create_index(
        op.f("ix_trips_planner_id"),
        "trips",
        ["planner_id"],
        unique=False,
    )
    op.create_table(
        "trip_structures",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("planner_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("city", sa.String(length=200), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("nights", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "ends_on >= starts_on",
            name=op.f("ck_trip_structures_dates_ordered"),
        ),
        sa.CheckConstraint(
            "nights >= 0",
            name=op.f("ck_trip_structures_nights_nonnegative"),
        ),
        sa.CheckConstraint(
            "position >= 0",
            name=op.f("ck_trip_structures_position_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["trip_id", "planner_id"],
            ["trips.id", "trips.planner_id"],
            name=op.f("fk_trip_structures_trip_id_planner_id_trips"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_structures")),
        sa.UniqueConstraint(
            "trip_id",
            "position",
            name=op.f("uq_trip_structures_trip_id_position"),
        ),
    )
    op.create_index(
        op.f("ix_trip_structures_planner_id"),
        "trip_structures",
        ["planner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trip_structures_trip_id"),
        "trip_structures",
        ["trip_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_trip_structures_trip_id"),
        table_name="trip_structures",
    )
    op.drop_index(
        op.f("ix_trip_structures_planner_id"),
        table_name="trip_structures",
    )
    op.drop_table("trip_structures")
    op.drop_index(op.f("ix_trips_planner_id"), table_name="trips")
    op.drop_table("trips")
