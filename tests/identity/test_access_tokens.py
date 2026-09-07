import time

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

from flash_trips.adapters.config import JwksFetchPolicy
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


def _verifier_under_test(
    issuer: LocalOidcIssuer,
    *,
    policy: JwksFetchPolicy | None = None,
) -> JwtAccessTokenVerifier:
    return JwtAccessTokenVerifier(
        issuer=issuer.issuer,
        audience="flash-trips-api",
        jwks_uri=issuer.jwks_uri,
        allowed_algorithms=("RS256",),
        required_scope="principal:read",
        jwks_policy=policy,
        tls_ca_file=issuer.ca_file,
    )


def test_verifier_refuses_plaintext_jwks_retrieval() -> None:
    with pytest.raises(ValueError, match="JWKS URI must use HTTPS"):
        JwtAccessTokenVerifier(
            issuer="https://issuer.example",
            audience="flash-trips-api",
            jwks_uri="http://issuer.example/.well-known/jwks.json",
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "wrong-issuer",
        "wrong-audience",
        "another-api",
        "id-token",
        "algorithm-none",
        "symmetric-key-substitution",
        "expired",
        "tampered-signature",
    ],
)
async def test_catastrophic_token_cases_return_the_same_authentication_problem(
    local_oidc_issuer: LocalOidcIssuer,
    case: str,
) -> None:
    if case == "wrong-issuer":
        token = local_oidc_issuer.mint({"iss": "https://wrong-issuer.example"})
    elif case == "wrong-audience":
        token = local_oidc_issuer.mint({"aud": "unexpected-audience"})
    elif case == "another-api":
        token = local_oidc_issuer.mint({"aud": ["flash-trips-api", "another-api"]})
    elif case == "id-token":
        # Minted at the API audience with a scope claim, so only the ID-token
        # claims can reject it.
        token = local_oidc_issuer.mint(
            {"nonce": "local-id-token-nonce", "at_hash": "local-access-token-hash"}
        )
    elif case == "algorithm-none":
        token = local_oidc_issuer.mint(algorithm="none", signing_key="")
    elif case == "symmetric-key-substitution":
        token = local_oidc_issuer.mint(
            algorithm="HS256",
            signing_key="symmetric-secret-that-is-longer-than-32-bytes",
        )
    elif case == "expired":
        token = local_oidc_issuer.mint({"exp": int(time.time()) - 60})
    else:
        valid_token = local_oidc_issuer.mint()
        encoded_header, encoded_payload, signature = valid_token.split(".")
        replacement = "A" if signature[0] != "A" else "B"
        token = f"{encoded_header}.{encoded_payload}.{replacement}{signature[1:]}"

    app = create_app(access_token_verifier=_verifier_under_test(local_oidc_issuer))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/authenticated-principal",
            headers={"Authorization": f"Bearer {token}"},
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
        ({"nonce": "local-id-token-nonce"}, ()),
        ({"at_hash": "local-access-token-hash"}, ()),
        ({"c_hash": "local-code-hash"}, ()),
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
        "id-token-nonce",
        "id-token-access-token-hash",
        "id-token-code-hash",
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
    verifier = _verifier_under_test(local_oidc_issuer)
    verifier.verify(local_oidc_issuer.mint())
    requests_before_unknown_key = local_oidc_issuer.jwks_request_count
    unpublished_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = local_oidc_issuer.mint(
        signing_key=unpublished_key,
        key_id="caller-selected-unknown-key",
    )

    with pytest.raises(AccessTokenVerificationError):
        verifier.verify(token)

    assert local_oidc_issuer.jwks_request_count == requests_before_unknown_key


def test_verifier_refreshes_for_rotation_and_drops_retired_keys(
    local_oidc_issuer: LocalOidcIssuer,
) -> None:
    policy = JwksFetchPolicy(
        minimum_refresh_interval_seconds=0.2,
        cache_ttl_seconds=0.2,
    )
    verifier = _verifier_under_test(local_oidc_issuer, policy=policy)
    original_token = local_oidc_issuer.mint()
    verifier.verify(original_token)

    local_oidc_issuer.rotate()
    rotated_token = local_oidc_issuer.mint()
    with pytest.raises(AccessTokenVerificationError):
        verifier.verify(rotated_token)
    assert local_oidc_issuer.jwks_request_count == 1

    time.sleep(0.21)
    verifier.verify(rotated_token)
    local_oidc_issuer.retire("local-test-key")
    time.sleep(0.21)

    with pytest.raises(AccessTokenVerificationError):
        verifier.verify(original_token)


def test_unchanged_jwks_version_extends_the_cached_key_lifetime(
    local_oidc_issuer: LocalOidcIssuer,
) -> None:
    policy = JwksFetchPolicy(
        minimum_refresh_interval_seconds=0.05,
        cache_ttl_seconds=0.05,
    )
    verifier = _verifier_under_test(local_oidc_issuer, policy=policy)
    token = local_oidc_issuer.mint()
    verifier.verify(token)
    time.sleep(0.06)

    verifier.verify(token)

    assert local_oidc_issuer.jwks_not_modified_count == 1


def test_jwks_fetch_is_bounded_by_response_size(
    local_oidc_issuer: LocalOidcIssuer,
) -> None:
    local_oidc_issuer.pad_jwks_document(2_000)
    verifier = _verifier_under_test(
        local_oidc_issuer,
        policy=JwksFetchPolicy(max_response_bytes=1_024),
    )

    with pytest.raises(AccessTokenVerificationError):
        verifier.verify(local_oidc_issuer.mint())


def test_malformed_jwks_fails_closed(
    local_oidc_issuer: LocalOidcIssuer,
) -> None:
    local_oidc_issuer.serve_jwks_document(b'["not", "a", "jwk-set"]')

    with pytest.raises(AccessTokenVerificationError):
        _verifier_under_test(local_oidc_issuer).verify(local_oidc_issuer.mint())


def test_a_failing_issuer_is_not_refetched_faster_than_the_refresh_interval(
    local_oidc_issuer: LocalOidcIssuer,
) -> None:
    local_oidc_issuer.serve_jwks_document(b'["not", "a", "jwk-set"]')
    verifier = _verifier_under_test(local_oidc_issuer)
    token = local_oidc_issuer.mint()

    for _ in range(5):
        with pytest.raises(AccessTokenVerificationError):
            verifier.verify(token)

    assert local_oidc_issuer.jwks_request_count == 1


def test_an_unusable_published_key_does_not_invalidate_the_signing_keys(
    local_oidc_issuer: LocalOidcIssuer,
) -> None:
    local_oidc_issuer.publish_encryption_key()

    principal = _verifier_under_test(local_oidc_issuer).verify(local_oidc_issuer.mint())

    assert principal.subject == "local-subject"


def test_jwks_fetch_is_bounded_by_timeout(
    local_oidc_issuer: LocalOidcIssuer,
) -> None:
    local_oidc_issuer.delay_jwks_responses(0.2)
    verifier = _verifier_under_test(
        local_oidc_issuer,
        policy=JwksFetchPolicy(request_timeout_seconds=0.05),
    )
    started = time.monotonic()

    with pytest.raises(AccessTokenVerificationError):
        verifier.verify(local_oidc_issuer.mint())

    assert time.monotonic() - started < 0.5


def test_token_headers_cannot_select_the_jwks_destination(
    local_oidc_issuer: LocalOidcIssuer,
) -> None:
    token = local_oidc_issuer.mint(
        extra_headers={
            "jku": "http://127.0.0.1/caller-selected-jwks",
            "x5u": "http://127.0.0.1/caller-selected-certificate",
        }
    )

    principal = _verifier_under_test(local_oidc_issuer).verify(token)

    assert principal.subject == "local-subject"
    assert local_oidc_issuer.jwks_request_count == 1
