from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    MetaData,
    String,
    UniqueConstraint,
    Uuid,
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
