from typing import Annotated

from fastapi import APIRouter, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from flash_trips.adapters.http.problems import ProblemResponse
from flash_trips.application import AccessTokenVerificationError, AccessTokenVerifier

_REQUIRED_SCOPE = "principal:read"
_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="Bearer access token",
)


class AuthenticatedPrincipalResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    issuer: str
    subject: str
    scopes: tuple[str, ...]


def _unauthenticated() -> HTTPException:
    return HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})


def principal_router(access_token_verifier: AccessTokenVerifier) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def authenticated_principal(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Security(_bearer),
        ],
    ) -> AuthenticatedPrincipalResponse:
        if credentials is None:
            raise _unauthenticated()

        try:
            principal = access_token_verifier.verify(credentials.credentials)
        except AccessTokenVerificationError:
            raise _unauthenticated() from None

        if _REQUIRED_SCOPE not in principal.scopes:
            raise HTTPException(status_code=403)

        return AuthenticatedPrincipalResponse(
            issuer=principal.issuer,
            subject=principal.subject,
            scopes=tuple(sorted(principal.scopes)),
        )

    router.add_api_route(
        "/authenticated-principal",
        authenticated_principal,
        methods=["GET"],
        response_model=AuthenticatedPrincipalResponse,
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
