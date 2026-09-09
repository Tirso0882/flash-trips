"""Add Approval Requests and bound Approvals."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_approval"
down_revision: str | None = "0007_plan_revision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        op.f("uq_plan_revisions_id_planner_id"),
        "plan_revisions",
        ["id", "planner_id"],
    )
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("planner_id", sa.Uuid(), nullable=False),
        sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["planner_id"],
            ["planners.id"],
            name=op.f("fk_approval_requests_planner_id_planners"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_revision_id", "planner_id"],
            ["plan_revisions.id", "plan_revisions.planner_id"],
            name=op.f(
                "fk_approval_requests_plan_revision_id_planner_id_plan_revisions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_requests")),
        sa.UniqueConstraint(
            "id",
            "plan_revision_id",
            "planner_id",
            name=op.f("uq_approval_requests_id_plan_revision_id_planner_id"),
        ),
        sa.UniqueConstraint(
            "plan_revision_id",
            name=op.f("uq_approval_requests_plan_revision_id"),
        ),
    )
    for column in ("planner_id", "plan_revision_id"):
        op.create_index(
            op.f(f"ix_approval_requests_{column}"),
            "approval_requests",
            [column],
            unique=False,
        )

    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("planner_id", sa.Uuid(), nullable=False),
        sa.Column("approval_request_id", sa.Uuid(), nullable=False),
        sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["planner_id"],
            ["planners.id"],
            name=op.f("fk_approvals_planner_id_planners"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_revision_id", "planner_id"],
            ["plan_revisions.id", "plan_revisions.planner_id"],
            name=op.f("fk_approvals_plan_revision_id_planner_id_plan_revisions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["approval_request_id", "plan_revision_id", "planner_id"],
            [
                "approval_requests.id",
                "approval_requests.plan_revision_id",
                "approval_requests.planner_id",
            ],
            name=op.f(
                "fk_approvals_approval_request_id_plan_revision_id_planner_id"
                "_approval_requests"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approvals")),
        sa.UniqueConstraint(
            "approval_request_id",
            name=op.f("uq_approvals_approval_request_id"),
        ),
        sa.UniqueConstraint(
            "plan_revision_id",
            name=op.f("uq_approvals_plan_revision_id"),
        ),
    )
    for column in ("planner_id", "approval_request_id", "plan_revision_id"):
        op.create_index(
            op.f(f"ix_approvals_{column}"),
            "approvals",
            [column],
            unique=False,
        )

    op.execute(
        """
        CREATE FUNCTION refuse_immutable_approval_update()
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
    for table in ("approval_requests", "approvals"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_refuse_update
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION refuse_immutable_approval_update()
            """
        )


def downgrade() -> None:
    for table in ("approvals", "approval_requests"):
        op.execute(f"DROP TRIGGER {table}_refuse_update ON {table}")
    op.execute("DROP FUNCTION refuse_immutable_approval_update()")
    op.drop_table("approvals")
    op.drop_table("approval_requests")
    op.drop_constraint(
        op.f("uq_plan_revisions_id_planner_id"),
        "plan_revisions",
        type_="unique",
    )
