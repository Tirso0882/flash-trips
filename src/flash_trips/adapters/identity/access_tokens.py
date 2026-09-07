import json
from collections.abc import Collection

import jwt

from flash_trips.application import AccessTokenVerificationError
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal


class JwtAccessTokenVerifier:
    """Verify provider-neutral access tokens against an issuer's JWKS."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_uri: str,
        allowed_algorithms: Collection[str],
        required_scope: str,
    ) -> None:
        algorithms = tuple(allowed_algorithms)
        if not algorithms:
            raise ValueError("allowed_algorithms must not be empty")
        self._issuer = issuer
        self._audience = audience
        self._allowed_algorithms = algorithms
        self._required_scope = required_scope
        self._jwks_client = jwt.PyJWKClient(jwks_uri)

    def verify(self, access_token: str) -> AuthenticatedPrincipal:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(access_token)
            claims: dict[str, object] = jwt.decode(
                access_token,
                signing_key.key,
                algorithms=self._allowed_algorithms,
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": ["iss", "sub", "aud", "exp", "nbf", "scope"],
                    "strict_aud": True,
                },
            )
        # PyJWT raises a bare JSON error rather than a PyJWTError when the
        # issuer serves a JWKS document that is not valid JSON.
        except (jwt.PyJWTError, json.JSONDecodeError) as error:
            raise AccessTokenVerificationError from error

        subject = claims["sub"]
        scope_claim = claims["scope"]
        if not isinstance(subject, str) or not subject:
            raise AccessTokenVerificationError
        if not isinstance(scope_claim, str):
            raise AccessTokenVerificationError
        scopes = frozenset(scope_claim.split())
        if self._required_scope not in scopes:
            raise AccessTokenVerificationError

        return AuthenticatedPrincipal(
            issuer=self._issuer,
            subject=subject,
            scopes=scopes,
        )


class RejectingAccessTokenVerifier:
    """Fail-closed verifier used until a configured verifier is composed."""

    def verify(self, access_token: str) -> AuthenticatedPrincipal:
        del access_token
        raise AccessTokenVerificationError
