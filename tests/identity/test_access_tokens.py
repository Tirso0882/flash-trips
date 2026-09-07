import time

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

from flash_trips.adapters.identity import JwtAccessTokenVerifier
from flash_trips.application import AccessTokenVerificationError
from flash_trips.composition import create_app

from .local_issuer import LocalOidcIssuer

# The JWKS document is served in process; only that loopback listener is
# exempt from the suite-wide socket ban, and pytest-socket restores the ban
# after every test.
pytestmark = [
    pytest.mark.enable_socket,
    pytest.mark.allow_hosts(["127.0.0.1"]),
]


def _verifier_under_test(issuer: LocalOidcIssuer) -> JwtAccessTokenVerifier:
    return JwtAccessTokenVerifier(
        issuer=issuer.issuer,
        audience="flash-trips-api",
        jwks_uri=issuer.jwks_uri,
        allowed_algorithms=("RS256",),
        required_scope="principal:read",
    )


@pytest.mark.asyncio
async def test_signed_access_token_establishes_the_endpoint_principal(
    local_oidc_issuer: LocalOidcIssuer,
) -> None:
    token = local_oidc_issuer.mint(
        {
            "sub": "signed-token-subject",
            "planner_id": "attacker-selected-planner",
            "email": "attacker@example.test",
            "roles": ["operator"],
            "scope": "trips:read principal:read",
        }
    )
    app = create_app(access_token_verifier=_verifier_under_test(local_oidc_issuer))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/authenticated-principal",
            params={
                "planner_id": "request-selected-planner",
                "email": "request@example.test",
                "roles": "operator",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Planner-Id": "header-selected-planner",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "issuer": local_oidc_issuer.issuer,
        "subject": "signed-token-subject",
        "scopes": ["principal:read", "trips:read"],
    }


@pytest.mark.parametrize(
    ("claims", "without_claims"),
    [
        ({"iss": "https://wrong-issuer.example"}, ()),
        ({"aud": "another-api"}, ()),
        ({"aud": ["flash-trips-api", "another-api"]}, ()),
        ({"exp": int(time.time()) - 60}, ()),
        ({"nbf": int(time.time()) + 60}, ()),
        ({"scope": "trips:read"}, ()),
        ({"scope": ["principal:read"]}, ()),
        ({"sub": ""}, ()),
        ({"sub": 12345}, ()),
        ({}, ("iss",)),
        ({}, ("sub",)),
        ({}, ("aud",)),
        ({}, ("exp",)),
        ({}, ("nbf",)),
        ({}, ("scope",)),
    ],
    ids=[
        "wrong-issuer",
        "wrong-audience",
        "audience-shared-with-another-api",
        "expired",
        "not-yet-valid",
        "missing-required-scope",
        "non-string-scope",
        "empty-subject",
        "non-string-subject",
        "missing-issuer",
        "missing-subject",
        "missing-audience",
        "missing-expiry",
        "missing-not-before",
        "missing-scope",
    ],
)
def test_verifier_rejects_tokens_outside_the_access_token_contract(
    local_oidc_issuer: LocalOidcIssuer,
    claims: dict[str, object],
    without_claims: tuple[str, ...],
) -> None:
    token = local_oidc_issuer.mint(claims, without_claims=without_claims)

    with pytest.raises(AccessTokenVerificationError):
        _verifier_under_test(local_oidc_issuer).verify(token)


def test_verifier_rejects_an_algorithm_outside_the_allowlist(
    local_oidc_issuer: LocalOidcIssuer,
) -> None:
    token = local_oidc_issuer.mint(
        algorithm="HS256",
        signing_key="symmetric-secret-that-is-longer-than-32-bytes",
    )

    with pytest.raises(AccessTokenVerificationError):
        _verifier_under_test(local_oidc_issuer).verify(token)


def test_verifier_rejects_a_signature_from_an_unpublished_key(
    local_oidc_issuer: LocalOidcIssuer,
) -> None:
    unpublished_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = local_oidc_issuer.mint(signing_key=unpublished_key)

    with pytest.raises(AccessTokenVerificationError):
        _verifier_under_test(local_oidc_issuer).verify(token)
