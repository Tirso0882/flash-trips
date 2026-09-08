"""Store revocable application sessions without recoverable identifiers."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_application_session"
down_revision: str | None = "0003_external_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("planner_id", sa.Uuid(), nullable=False),
        sa.Column("identifier_digest", sa.LargeBinary(), nullable=False),
        sa.Column("csrf_digest", sa.LargeBinary(), nullable=False),
        sa.Column("access_token_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("access_token_iv", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "octet_length(identifier_digest) = 32",
            name=op.f("ck_application_sessions_identifier_digest_length"),
        ),
        sa.CheckConstraint(
            "octet_length(csrf_digest) = 32",
            name=op.f("ck_application_sessions_csrf_digest_length"),
        ),
        sa.CheckConstraint(
            "octet_length(access_token_iv) = 12",
            name=op.f("ck_application_sessions_access_token_iv_length"),
        ),
        sa.CheckConstraint(
            "last_seen_at >= created_at",
            name=op.f("ck_application_sessions_last_seen_after_creation"),
        ),
        sa.CheckConstraint(
            "idle_expires_at > last_seen_at",
            name=op.f("ck_application_sessions_idle_expiry_after_last_seen"),
        ),
        sa.CheckConstraint(
            "absolute_expires_at > created_at",
            name=op.f("ck_application_sessions_absolute_expiry_after_creation"),
        ),
        sa.ForeignKeyConstraint(
            ["planner_id"],
            ["planners.id"],
            name=op.f("fk_application_sessions_planner_id_planners"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_sessions")),
        sa.UniqueConstraint(
            "identifier_digest",
            name=op.f("uq_application_sessions_identifier_digest"),
        ),
    )
    op.create_index(
        op.f("ix_application_sessions_planner_id"),
        "application_sessions",
        ["planner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_application_sessions_absolute_expires_at"),
        "application_sessions",
        ["absolute_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_application_sessions_absolute_expires_at"),
        table_name="application_sessions",
    )
    op.drop_index(
        op.f("ix_application_sessions_planner_id"),
        table_name="application_sessions",
    )
    op.drop_table("application_sessions")
