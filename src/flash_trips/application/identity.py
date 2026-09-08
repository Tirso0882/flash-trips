from dataclasses import dataclass
from typing import Protocol

from flash_trips.application.persistence import (
    PlannerAccessStatus,
    PlannerPrincipal,
    PlannerRecord,
)
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal


@dataclass(frozen=True, slots=True)
class AllowedExternalIdentity:
    issuer: str
    subject: str


class ExternalIdentityRepository(Protocol):
    async def resolve(self) -> PlannerRecord | None: ...


class ExternalIdentityRepositoryFactory(Protocol):
    def __call__(
        self, principal: AuthenticatedPrincipal
    ) -> ExternalIdentityRepository: ...


class PlannerResolver(Protocol):
    async def resolve(
        self, principal: AuthenticatedPrincipal
    ) -> PlannerPrincipal | None: ...


class ResolvePlanner:
    def __init__(
        self,
        repositories: ExternalIdentityRepositoryFactory,
        allowed_identity: AllowedExternalIdentity,
    ) -> None:
        self._repositories = repositories
        self._allowed_identity = allowed_identity

    async def resolve(
        self, principal: AuthenticatedPrincipal
    ) -> PlannerPrincipal | None:
        if (
            principal.issuer != self._allowed_identity.issuer
            or principal.subject != self._allowed_identity.subject
        ):
            return None

        planner = await self._repositories(principal).resolve()
        if planner is None or planner.access_status is not PlannerAccessStatus.ACTIVE:
            return None
        return PlannerPrincipal(planner_id=planner.id)


class RejectingPlannerResolver:
    async def resolve(
        self, principal: AuthenticatedPrincipal
    ) -> PlannerPrincipal | None:
        del principal
        return None
