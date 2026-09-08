"""Resolve external identities to application-owned Planners."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_external_identity"
down_revision: str | None = "0002_planner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "planners",
        sa.Column(
            "access_status",
            sa.String(length=16),
            server_default="Active",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_planners_access_status_values"),
        "planners",
        "access_status IN ('Active', 'Suspended', 'Closed')",
    )
    op.create_table(
        "external_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("issuer", sa.String(length=2048), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("planner_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["planner_id"],
            ["planners.id"],
            name=op.f("fk_external_identities_planner_id_planners"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_identities")),
        sa.UniqueConstraint(
            "issuer",
            "subject",
            name=op.f("uq_external_identities_issuer_subject"),
        ),
    )
    op.create_index(
        op.f("ix_external_identities_planner_id"),
        "external_identities",
        ["planner_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_external_identities_planner_id"),
        table_name="external_identities",
    )
    op.drop_table("external_identities")
    op.drop_constraint(
        op.f("ck_planners_access_status_values"),
        "planners",
        type_="check",
    )
    op.drop_column("planners", "access_status")
