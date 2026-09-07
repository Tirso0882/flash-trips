from dataclasses import dataclass, fields

import pytest
from httpx import ASGITransport, AsyncClient

from flash_trips.application import AccessTokenVerificationError
from flash_trips.composition import create_app
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal


@dataclass(frozen=True, slots=True)
class FakeAccessTokenVerifier:
    principal: AuthenticatedPrincipal

    def verify(self, access_token: str) -> AuthenticatedPrincipal:
        if "unverifiable" in access_token:
            raise AccessTokenVerificationError
        return self.principal


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
    verifier = FakeAccessTokenVerifier(
        AuthenticatedPrincipal(
            issuer="https://issuer.example",
            subject="external-subject",
            scopes=frozenset({"principal:read", "trips:read"}),
        )
    )
    transport = ASGITransport(app=create_app(access_token_verifier=verifier))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/authenticated-principal",
            headers={"Authorization": "Bearer valid-access-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "issuer": "https://issuer.example",
        "subject": "external-subject",
        "scopes": ["principal:read", "trips:read"],
    }


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
