"""Create the application-owned Planner record."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_planner"
down_revision: str | None = "0001_scaffold"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "planners",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_planners")),
    )


def downgrade() -> None:
    op.drop_table("planners")
