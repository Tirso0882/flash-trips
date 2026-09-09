from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from flash_trips.adapters.http.problems import ProblemResponse
from flash_trips.application import (
    AccessTokenVerificationError,
    AccessTokenVerifier,
    PlannerPrincipal,
    PlannerResolver,
)

_REQUIRED_SCOPE = "principal:read"
_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="Bearer access token",
)


class PlannerPrincipalResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    planner_id: UUID


def _unauthenticated() -> HTTPException:
    return HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})


def authenticated_planner(
    access_token_verifier: AccessTokenVerifier,
    planner_resolver: PlannerResolver,
) -> Callable[..., Awaitable[PlannerPrincipal]]:
    async def resolve(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Security(_bearer),
        ],
    ) -> PlannerPrincipal:
        if credentials is None:
            raise _unauthenticated()

        try:
            principal = access_token_verifier.verify(credentials.credentials)
        except AccessTokenVerificationError:
            raise _unauthenticated() from None

        if _REQUIRED_SCOPE not in principal.scopes:
            raise HTTPException(status_code=403)

        planner = await planner_resolver.resolve(principal)
        if planner is None:
            raise _unauthenticated()

        return planner

    return resolve


def principal_router(
    access_token_verifier: AccessTokenVerifier,
    planner_resolver: PlannerResolver,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    planner = authenticated_planner(access_token_verifier, planner_resolver)

    async def authenticated_principal(
        principal: Annotated[PlannerPrincipal, Security(planner)],
    ) -> PlannerPrincipalResponse:
        return PlannerPrincipalResponse(planner_id=principal.planner_id)

    router.add_api_route(
        "/authenticated-principal",
        authenticated_principal,
        methods=["GET"],
        response_model=PlannerPrincipalResponse,
        operation_id="getAuthenticatedPrincipal",
        responses={
            401: {
                "description": "Unauthorized",
                "model": ProblemResponse,
                "content": {"application/problem+json": {}},
            },
            403: {
                "description": "Forbidden",
                "model": ProblemResponse,
                "content": {"application/problem+json": {}},
            },
        },
    )
    return router
