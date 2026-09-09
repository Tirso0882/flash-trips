"""Add immutable Handbook Snapshots and recorded Deliveries."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_handbook"
down_revision: str | None = "0008_approval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        op.f("uq_approvals_id_plan_revision_id_planner_id"),
        "approvals",
        ["id", "plan_revision_id", "planner_id"],
    )
    op.create_table(
        "handbook_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("planner_id", sa.Uuid(), nullable=False),
        sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
        sa.Column("approval_id", sa.Uuid(), nullable=False),
        sa.Column("document_schema_version", sa.Integer(), nullable=False),
        sa.Column("export_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "document_schema_version > 0",
            name=op.f("ck_handbook_snapshots_schema_version_positive"),
        ),
        sa.CheckConstraint(
            "octet_length(checksum) = 64",
            name=op.f("ck_handbook_snapshots_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["planner_id"],
            ["planners.id"],
            name=op.f("fk_handbook_snapshots_planner_id_planners"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_revision_id", "planner_id"],
            ["plan_revisions.id", "plan_revisions.planner_id"],
            name=op.f(
                "fk_handbook_snapshots_plan_revision_id_planner_id_plan_revisions"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["approval_id", "plan_revision_id", "planner_id"],
            ["approvals.id", "approvals.plan_revision_id", "approvals.planner_id"],
            name=op.f(
                "fk_handbook_snapshots_approval_id_plan_revision_id_planner_id_approvals"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_handbook_snapshots")),
        sa.UniqueConstraint(
            "id",
            "planner_id",
            name=op.f("uq_handbook_snapshots_id_planner_id"),
        ),
        sa.UniqueConstraint(
            "plan_revision_id",
            name=op.f("uq_handbook_snapshots_plan_revision_id"),
        ),
    )
    for column in ("planner_id", "plan_revision_id", "approval_id"):
        op.create_index(
            op.f(f"ix_handbook_snapshots_{column}"),
            "handbook_snapshots",
            [column],
            unique=False,
        )

    op.create_table(
        "handbook_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("planner_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("export_format", sa.String(length=16), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "export_format IN ('html')",
            name=op.f("ck_handbook_deliveries_export_format_values"),
        ),
        sa.CheckConstraint(
            "octet_length(checksum) = 64",
            name=op.f("ck_handbook_deliveries_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["planner_id"],
            ["planners.id"],
            name=op.f("fk_handbook_deliveries_planner_id_planners"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "planner_id"],
            ["handbook_snapshots.id", "handbook_snapshots.planner_id"],
            name=op.f(
                "fk_handbook_deliveries_snapshot_id_planner_id_handbook_snapshots"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_handbook_deliveries")),
    )
    for column in ("planner_id", "snapshot_id"):
        op.create_index(
            op.f(f"ix_handbook_deliveries_{column}"),
            "handbook_deliveries",
            [column],
            unique=False,
        )

    op.execute(
        """
        CREATE FUNCTION refuse_immutable_handbook_update()
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
    for table in ("handbook_snapshots", "handbook_deliveries"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_refuse_update
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION refuse_immutable_handbook_update()
            """
        )


def downgrade() -> None:
    for table in ("handbook_deliveries", "handbook_snapshots"):
        op.execute(f"DROP TRIGGER {table}_refuse_update ON {table}")
    op.execute("DROP FUNCTION refuse_immutable_handbook_update()")
    op.drop_table("handbook_deliveries")
    op.drop_table("handbook_snapshots")
    op.drop_constraint(
        op.f("uq_approvals_id_plan_revision_id_planner_id"),
        "approvals",
        type_="unique",
    )
