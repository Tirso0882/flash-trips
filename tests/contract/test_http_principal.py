from collections.abc import Mapping
from dataclasses import dataclass, fields
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient, Response

from flash_trips.application import (
    AccessTokenVerificationError,
    AllowedExternalIdentity,
    PlannerAccessStatus,
    PlannerPrincipal,
    PlannerRecord,
    ResolvePlanner,
)
from flash_trips.composition import create_app
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal

ALLOWED_ISSUER = "https://issuer.example"
ALLOWED_SUBJECT = "allowed-subject"


@dataclass(frozen=True, slots=True)
class FakeAccessTokenVerifier:
    principal: AuthenticatedPrincipal

    def verify(self, access_token: str) -> AuthenticatedPrincipal:
        if "unverifiable" in access_token:
            raise AccessTokenVerificationError
        return self.principal


@dataclass(frozen=True, slots=True)
class FakePlannerResolver:
    result: PlannerPrincipal | None

    async def resolve(
        self, principal: AuthenticatedPrincipal
    ) -> PlannerPrincipal | None:
        del principal
        return self.result


@dataclass(frozen=True, slots=True)
class FakeExternalIdentityRepository:
    planner: PlannerRecord | None

    async def resolve(self) -> PlannerRecord | None:
        return self.planner


@dataclass(frozen=True, slots=True)
class FakeExternalIdentities:
    """Stored External Identities keyed by their exact issuer and subject."""

    planners: Mapping[tuple[str, str], PlannerRecord]

    def __call__(
        self, principal: AuthenticatedPrincipal
    ) -> FakeExternalIdentityRepository:
        return FakeExternalIdentityRepository(
            self.planners.get((principal.issuer, principal.subject))
        )


async def get_principal_with_stored_planner(planner: PlannerRecord | None) -> Response:
    """Call the protected route when the allowlisted token finds `planner`."""
    verifier = FakeAccessTokenVerifier(
        AuthenticatedPrincipal(
            issuer=ALLOWED_ISSUER,
            subject=ALLOWED_SUBJECT,
            scopes=frozenset({"principal:read"}),
        )
    )
    stored = {} if planner is None else {(ALLOWED_ISSUER, ALLOWED_SUBJECT): planner}
    resolver = ResolvePlanner(
        FakeExternalIdentities(stored),
        AllowedExternalIdentity(issuer=ALLOWED_ISSUER, subject=ALLOWED_SUBJECT),
    )
    transport = ASGITransport(
        app=create_app(access_token_verifier=verifier, planner_resolver=resolver)
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(
            "/api/v1/authenticated-principal",
            headers={"Authorization": "Bearer valid-access-token"},
        )


def refusal(response: Response) -> object:
    problem = response.json()
    problem.pop("request_id")
    return (
        response.status_code,
        response.headers["content-type"],
        response.headers["www-authenticate"],
        problem,
    )


def test_authenticated_principal_contains_only_provider_neutral_identity() -> None:
    assert [field.name for field in fields(AuthenticatedPrincipal)] == [
        "issuer",
        "subject",
        "scopes",
    ]


@pytest.mark.asyncio
async def test_default_composition_fails_closed_without_a_configured_verifier() -> None:
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/authenticated-principal",
            headers={"Authorization": "Bearer unconfigured-access-token"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_returns_the_redacted_principal() -> None:
    planner_id = UUID("01991e28-1d65-7000-8000-000000000001")
    verifier = FakeAccessTokenVerifier(
        AuthenticatedPrincipal(
            issuer="https://issuer.example",
            subject="external-subject",
            scopes=frozenset({"principal:read", "trips:read"}),
        )
    )
    resolver = FakePlannerResolver(PlannerPrincipal(planner_id=planner_id))
    transport = ASGITransport(
        app=create_app(
            access_token_verifier=verifier,
            planner_resolver=resolver,
        )
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/authenticated-principal",
            headers={"Authorization": "Bearer valid-access-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"planner_id": str(planner_id)}


@pytest.mark.asyncio
async def test_unknown_external_identity_receives_the_authentication_refusal() -> None:
    verifier = FakeAccessTokenVerifier(
        AuthenticatedPrincipal(
            issuer="https://issuer.example",
            subject="unknown-subject",
            scopes=frozenset({"principal:read"}),
        )
    )
    transport = ASGITransport(
        app=create_app(
            access_token_verifier=verifier,
            planner_resolver=FakePlannerResolver(None),
        )
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/authenticated-principal",
            headers={"Authorization": "Bearer valid-but-unknown-token"},
        )

    problem = response.json()
    problem.pop("request_id")
    assert response.status_code == 401
    assert problem["code"] == "authentication_required"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "authorization",
    [None, "Basic credentials", "Bearer", "Bearer unverifiable-token"],
)
async def test_missing_malformed_and_unverifiable_tokens_are_indistinguishable(
    authorization: str | None,
) -> None:
    verifier = FakeAccessTokenVerifier(
        AuthenticatedPrincipal(
            issuer="https://issuer.example",
            subject="external-subject",
            scopes=frozenset({"principal:read"}),
        )
    )
    transport = ASGITransport(app=create_app(access_token_verifier=verifier))
    headers = {} if authorization is None else {"Authorization": authorization}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/authenticated-principal",
            headers=headers,
        )

    problem = response.json()
    problem.pop("request_id")
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["www-authenticate"] == "Bearer"
    assert problem == {
        "type": "https://flash-trips.example/problems/authentication-required",
        "title": "Unauthorized",
        "status": 401,
        "detail": "Authentication is required.",
        "code": "authentication_required",
        "retryable": False,
    }


@pytest.mark.asyncio
async def test_principal_without_required_scope_receives_a_safe_forbidden_problem() -> (
    None
):
    verifier = FakeAccessTokenVerifier(
        AuthenticatedPrincipal(
            issuer="https://issuer.example",
            subject="external-subject",
            scopes=frozenset({"private-provider-scope"}),
        )
    )
    transport = ASGITransport(app=create_app(access_token_verifier=verifier))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/authenticated-principal",
            headers={"Authorization": "Bearer valid-access-token"},
        )

    problem = response.json()
    problem.pop("request_id")
    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert "private-provider-scope" not in response.text
    assert problem == {
        "type": "https://flash-trips.example/problems/access-denied",
        "title": "Forbidden",
        "status": 403,
        "detail": "Access is denied.",
        "code": "access_denied",
        "retryable": False,
    }


@pytest.mark.asyncio
async def test_allowlisted_identity_reaches_only_its_own_active_planner() -> None:
    planner_id = UUID("01991e28-1d65-7000-8000-000000000002")
    response = await get_principal_with_stored_planner(
        PlannerRecord(id=planner_id, access_status=PlannerAccessStatus.ACTIVE)
    )

    assert response.status_code == 200
    assert response.json() == {"planner_id": str(planner_id)}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "access_status",
    [PlannerAccessStatus.SUSPENDED, PlannerAccessStatus.CLOSED],
)
async def test_blocked_access_status_refusal_matches_the_unknown_identity_refusal(
    access_status: PlannerAccessStatus,
) -> None:
    blocked = await get_principal_with_stored_planner(
        PlannerRecord(
            id=UUID("01991e28-1d65-7000-8000-000000000003"),
            access_status=access_status,
        )
    )
    unknown = await get_principal_with_stored_planner(None)

    assert blocked.status_code == 401
    assert refusal(blocked) == refusal(unknown)
