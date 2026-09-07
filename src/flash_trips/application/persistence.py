from dataclasses import dataclass
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PlannerPrincipal:
    """Application authority for one Planner's records."""

    planner_id: UUID


@dataclass(frozen=True, slots=True)
class PlannerRecord:
    """The stable application-owned identity of a Planner."""

    id: UUID


class PlannerRepository(Protocol):
    async def add(self, planner: PlannerRecord) -> None: ...

    async def get(self, planner_id: UUID) -> PlannerRecord | None: ...


class UnitOfWork(Protocol):
    @property
    def planners(self) -> PlannerRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self, principal: PlannerPrincipal) -> UnitOfWork: ...
