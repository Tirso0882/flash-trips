from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from flash_trips.application.persistence import PlannerAccessStatus

CONSTRAINT_NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class PostgresBase(DeclarativeBase):
    metadata = MetaData(naming_convention=CONSTRAINT_NAMING_CONVENTION)


class PlannerModel(PostgresBase):
    __tablename__ = "planners"
    __table_args__ = (
        CheckConstraint(
            "access_status IN ('Active', 'Suspended', 'Closed')",
            name="access_status_values",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    access_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=PlannerAccessStatus.ACTIVE.value,
    )


class TripModel(PostgresBase):
    __tablename__ = "trips"
    __table_args__ = (UniqueConstraint("id", "planner_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    planner_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("planners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class TripStructureModel(PostgresBase):
    __tablename__ = "trip_structures"
    __table_args__ = (
        CheckConstraint("position >= 0", name="position_nonnegative"),
        CheckConstraint("ends_on >= starts_on", name="dates_ordered"),
        CheckConstraint("nights >= 0", name="nights_nonnegative"),
        ForeignKeyConstraint(
            ["trip_id", "planner_id"],
            ["trips.id", "trips.planner_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("trip_id", "position"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    trip_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    planner_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    city: Mapped[str] = mapped_column(String(200), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    nights: Mapped[int] = mapped_column(Integer, nullable=False)


class RunModel(PostgresBase):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(
            "terminal_status IS NULL OR "
            "terminal_status IN ('Succeeded', 'Blocked', 'Failed', 'Cancelled')",
            name="terminal_status_values",
        ),
        CheckConstraint(
            "(terminal_status IS NULL AND terminal_code IS NULL "
            "AND terminal_detail IS NULL) OR "
            "(terminal_status IS NOT NULL AND terminal_code IS NOT NULL "
            "AND terminal_detail IS NOT NULL)",
            name="terminal_outcome_complete",
        ),
        ForeignKeyConstraint(
            ["trip_id", "planner_id"],
            ["trips.id", "trips.planner_id"],
            ondelete="CASCADE",
        ),
        Index(
            "uq_runs_active_trip",
            "trip_id",
            unique=True,
            postgresql_where=text("terminal_status IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    planner_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("planners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trip_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    terminal_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    terminal_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    terminal_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ExternalIdentityModel(PostgresBase):
    __tablename__ = "external_identities"
    __table_args__ = (UniqueConstraint("issuer", "subject"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    issuer: Mapped[str] = mapped_column(String(2048), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    planner_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("planners.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


class ApplicationSessionModel(PostgresBase):
    __tablename__ = "application_sessions"
    __table_args__ = (
        CheckConstraint(
            "octet_length(identifier_digest) = 32",
            name="identifier_digest_length",
        ),
        CheckConstraint("octet_length(csrf_digest) = 32", name="csrf_digest_length"),
        CheckConstraint(
            "octet_length(access_token_iv) = 12",
            name="access_token_iv_length",
        ),
        CheckConstraint("last_seen_at >= created_at", name="last_seen_after_creation"),
        CheckConstraint(
            "idle_expires_at > last_seen_at",
            name="idle_expiry_after_last_seen",
        ),
        CheckConstraint(
            "absolute_expires_at > created_at",
            name="absolute_expiry_after_creation",
        ),
        UniqueConstraint("identifier_digest"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    planner_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("planners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    identifier_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    csrf_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    access_token_ciphertext: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )
    access_token_iv: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    idle_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    absolute_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
