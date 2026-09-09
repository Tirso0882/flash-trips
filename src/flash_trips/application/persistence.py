from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from flash_trips.kernel.evidence import EvidenceReference


class PlannerAccessStatus(StrEnum):
    ACTIVE = "Active"
    SUSPENDED = "Suspended"
    CLOSED = "Closed"


@dataclass(frozen=True, slots=True)
class PlannerPrincipal:
    """Application authority for one Planner's records."""

    planner_id: UUID


@dataclass(frozen=True, slots=True)
class PlannerRecord:
    """The stable application-owned identity of a Planner."""

    id: UUID
    access_status: PlannerAccessStatus = PlannerAccessStatus.ACTIVE


class PlannerRepository(Protocol):
    async def add(self, planner: PlannerRecord) -> None: ...

    async def get(self, planner_id: UUID) -> PlannerRecord | None: ...


@dataclass(frozen=True, slots=True)
class TripStayRecord:
    """One ordered city stay in a Trip Structure."""

    id: UUID
    city: str
    starts_on: date
    ends_on: date
    nights: int


@dataclass(frozen=True, slots=True)
class TripStructureRecord:
    """The ordered, multi-city-ready structure of a Trip."""

    stays: tuple[TripStayRecord, ...]


@dataclass(frozen=True, slots=True)
class TripRecord:
    """A private Trip owned by one Planner."""

    id: UUID
    planner_id: UUID
    structure: TripStructureRecord


class TripRepository(Protocol):
    async def add(self, trip: TripRecord) -> None: ...

    async def get(self, trip_id: UUID) -> TripRecord | None: ...

    async def list(self) -> list[TripRecord]: ...


class RunTerminalStatus(StrEnum):
    SUCCEEDED = "Succeeded"
    BLOCKED = "Blocked"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


@dataclass(frozen=True, slots=True)
class RunTerminalOutcome:
    status: RunTerminalStatus
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class RunRecord:
    """One durable execution with at most one terminal outcome."""

    id: UUID
    planner_id: UUID
    trip_id: UUID
    terminal_outcome: RunTerminalOutcome | None = None


class ActiveRunExistsError(RuntimeError):
    def __init__(self, active_run_id: UUID) -> None:
        super().__init__("An active mutating Run already exists for this Trip")
        self.active_run_id = active_run_id


class TerminalOutcomeAlreadyRecordedError(RuntimeError):
    pass


class RunNotFoundError(LookupError):
    pass


class RunRepository(Protocol):
    async def add(self, run: RunRecord) -> None: ...

    async def get(self, run_id: UUID) -> RunRecord | None: ...

    async def record_terminal(
        self,
        run_id: UUID,
        outcome: RunTerminalOutcome,
    ) -> RunRecord: ...


class PlanClaimKind(StrEnum):
    TRAVEL_READINESS = "travel_readiness"


@dataclass(frozen=True, slots=True)
class PlanClaimRecord:
    """One evidence-backed claim in a complete Plan Revision."""

    id: UUID
    kind: PlanClaimKind
    text: str
    evidence_reference: EvidenceReference
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class PlanRevisionRecord:
    """One complete immutable version of a Travel Plan."""

    id: UUID
    planner_id: UUID
    trip_id: UUID
    run_id: UUID
    revision_number: int
    base_revision_id: UUID | None
    claims: tuple[PlanClaimRecord, ...]


class PlanRevisionRepository(Protocol):
    """Commit-only access to immutable Plan Revisions."""

    async def commit(self, revision: PlanRevisionRecord) -> PlanRevisionRecord: ...

    async def get_current(self, trip_id: UUID) -> PlanRevisionRecord | None: ...


@dataclass(frozen=True, slots=True)
class ApprovalRequestRecord:
    """One immutable decision presented for an exact Plan Revision."""

    id: UUID
    planner_id: UUID
    plan_revision_id: UUID


@dataclass(frozen=True, slots=True)
class BoundApprovalAction:
    """A typed Approval action bound to its request and subject."""

    approval_request_id: UUID
    plan_revision_id: UUID


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    """A Planner's recorded Approval of one exact request and revision."""

    id: UUID
    planner_id: UUID
    approval_request_id: UUID
    plan_revision_id: UUID


class ApprovalNotFoundError(LookupError):
    pass


class ApprovalAlreadyRecordedError(RuntimeError):
    pass


class ApprovalRepository(Protocol):
    async def present(self, request: ApprovalRequestRecord) -> None: ...

    async def get_request(
        self,
        plan_revision_id: UUID,
    ) -> ApprovalRequestRecord | None: ...

    async def approve(self, action: BoundApprovalAction) -> ApprovalRecord: ...

    async def get_approval(
        self,
        plan_revision_id: UUID,
    ) -> ApprovalRecord | None: ...


class UnitOfWork(Protocol):
    @property
    def approvals(self) -> ApprovalRepository: ...

    @property
    def planners(self) -> PlannerRepository: ...

    @property
    def trips(self) -> TripRepository: ...

    @property
    def runs(self) -> RunRepository: ...

    @property
    def plan_revisions(self) -> PlanRevisionRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self, principal: PlannerPrincipal) -> UnitOfWork: ...
