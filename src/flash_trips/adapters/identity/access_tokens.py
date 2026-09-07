import json
import re
import ssl
import threading
import time
from collections.abc import Collection
from http.client import HTTPException, HTTPSConnection
from pathlib import Path
from urllib.parse import SplitResult, urlsplit

import jwt

from flash_trips.adapters.config import JwksFetchPolicy
from flash_trips.application import AccessTokenVerificationError
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal

_ASYMMETRIC_SIGNING_ALGORITHMS = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    }
)
_MAX_KEY_ID_LENGTH = 128
# RFC 9110 entity-tag characters, bounded so nothing unexpected from the issuer
# reaches the If-None-Match request header.
_ETAG_PATTERN = re.compile(r'\A(?:W/)?"[\x21\x23-\x7e]{1,128}"\Z')

# ID tokens authenticate an end user to a client, never a caller to this API.
# These claims only ever appear in one, so their presence identifies the token
# as an ID token regardless of the audience it was minted for.
_ID_TOKEN_ONLY_CLAIMS = frozenset({"nonce", "at_hash", "c_hash"})


class _SigningKeyUnavailable(Exception):
    """No published signing key could be established for a key identifier."""


class _BoundedJwksCache:
    def __init__(
        self,
        *,
        jwks_uri: SplitResult,
        policy: JwksFetchPolicy,
        tls_ca_file: Path | None,
    ) -> None:
        tls_context = ssl.create_default_context(
            cafile=None if tls_ca_file is None else str(tls_ca_file)
        )

        host = jwks_uri.hostname
        if host is None:
            raise ValueError("JWKS URI must include a host")

        self._host = host
        self._port = jwks_uri.port
        self._path = jwks_uri.path or "/"
        if jwks_uri.query:
            self._path = f"{self._path}?{jwks_uri.query}"
        self._policy = policy
        self._tls_context = tls_context
        self._keys: dict[str, jwt.PyJWK] = {}
        self._etag: str | None = None
        self._last_attempt = float("-inf")
        self._last_checked = float("-inf")
        self._lock = threading.Lock()

    def get(self, key_id: str) -> jwt.PyJWK:
        with self._lock:
            now = time.monotonic()
            if not self._keys or (
                now - self._last_checked >= self._policy.cache_ttl_seconds
            ):
                self._refresh_within_rate_limit(now)

            signing_key = self._keys.get(key_id)
            if signing_key is not None:
                return signing_key

            # An unknown key identifier may prompt at most one refresh per
            # interval, so a caller-chosen identifier cannot pace the fetches.
            self._refresh_within_rate_limit(now)
            signing_key = self._keys.get(key_id)
            if signing_key is not None:
                return signing_key

        raise _SigningKeyUnavailable

    def _refresh_within_rate_limit(self, now: float) -> None:
        # Every refresh path is rate limited, including an expired cache and a
        # failing issuer, and the attempt is recorded before the request so a
        # failure cannot be retried faster than a success.
        if now - self._last_attempt < self._policy.minimum_refresh_interval_seconds:
            return
        self._last_attempt = now
        document, etag = self._fetch()
        if document is not None:
            self._keys = self._parse(document)
            self._etag = etag
        self._last_checked = now

    def _fetch(self) -> tuple[bytes | None, str | None]:
        headers = {
            "Accept": "application/jwk-set+json, application/json",
            "User-Agent": "flash-trips-jwks/1",
        }
        if self._etag is not None:
            headers["If-None-Match"] = self._etag

        connection = HTTPSConnection(
            self._host,
            port=self._port,
            timeout=self._policy.request_timeout_seconds,
            context=self._tls_context,
        )
        try:
            connection.request("GET", self._path, headers=headers)
            response = connection.getresponse()
            if response.status == 304 and self._etag is not None:
                return None, self._etag
            if response.status != 200:
                raise _SigningKeyUnavailable
            content_type = response.headers.get_content_type()
            if content_type not in {"application/jwk-set+json", "application/json"}:
                raise _SigningKeyUnavailable
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except ValueError as error:
                    raise _SigningKeyUnavailable from error
                if (
                    declared_length < 0
                    or declared_length > self._policy.max_response_bytes
                ):
                    raise _SigningKeyUnavailable
            document = response.read(self._policy.max_response_bytes + 1)
            if len(document) > self._policy.max_response_bytes:
                raise _SigningKeyUnavailable
            return document, self._usable_etag(response.headers.get("ETag"))
        except (HTTPException, OSError, TimeoutError) as error:
            raise _SigningKeyUnavailable from error
        finally:
            connection.close()

    @staticmethod
    def _usable_etag(etag: str | None) -> str | None:
        if etag is None or _ETAG_PATTERN.fullmatch(etag) is None:
            return None
        return etag

    @staticmethod
    def _parse(document: bytes) -> dict[str, jwt.PyJWK]:
        try:
            jwk_set = jwt.PyJWKSet.from_json(document.decode("utf-8"))
        except (
            AttributeError,
            TypeError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            jwt.PyJWTError,
        ) as error:
            raise _SigningKeyUnavailable from error

        keys: dict[str, jwt.PyJWK] = {}
        for key in jwk_set.keys:
            key_id = key.key_id
            # A published key the application cannot use is skipped rather than
            # invalidating the document, so an encryption key alongside the
            # signing keys cannot deny every verification.
            if (
                not isinstance(key_id, str)
                or not key_id
                or len(key_id) > _MAX_KEY_ID_LENGTH
                or key.public_key_use not in {None, "sig"}
            ):
                continue
            if key_id in keys:
                # A repeated key identifier makes key selection ambiguous.
                raise _SigningKeyUnavailable
            keys[key_id] = key
        if not keys:
            raise _SigningKeyUnavailable
        return keys


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
        jwks_policy: JwksFetchPolicy | None = None,
        tls_ca_file: Path | None = None,
    ) -> None:
        algorithms = tuple(allowed_algorithms)
        if not algorithms:
            raise ValueError("allowed_algorithms must not be empty")
        if not frozenset(algorithms) <= _ASYMMETRIC_SIGNING_ALGORITHMS:
            raise ValueError(
                "allowed_algorithms must contain only asymmetric algorithms"
            )
        parsed_jwks_uri = urlsplit(jwks_uri)
        if parsed_jwks_uri.scheme != "https":
            raise ValueError("JWKS URI must use HTTPS")
        if (
            parsed_jwks_uri.hostname is None
            or parsed_jwks_uri.username is not None
            or parsed_jwks_uri.password is not None
            or parsed_jwks_uri.fragment
        ):
            raise ValueError("JWKS URI must be an absolute URL without credentials")
        self._issuer = issuer
        self._audience = audience
        self._allowed_algorithms = algorithms
        self._required_scope = required_scope
        self._jwks_cache = _BoundedJwksCache(
            jwks_uri=parsed_jwks_uri,
            policy=jwks_policy or JwksFetchPolicy(),
            tls_ca_file=tls_ca_file,
        )

    def verify(self, access_token: str) -> AuthenticatedPrincipal:
        try:
            header = jwt.get_unverified_header(access_token)
            algorithm = header.get("alg")
            key_id = header.get("kid")
            if (
                not isinstance(algorithm, str)
                or algorithm not in self._allowed_algorithms
                or not isinstance(key_id, str)
                or not key_id
                or len(key_id) > _MAX_KEY_ID_LENGTH
            ):
                raise AccessTokenVerificationError
            signing_key = self._jwks_cache.get(key_id)
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
        except (jwt.PyJWTError, _SigningKeyUnavailable) as error:
            raise AccessTokenVerificationError from error

        if not _ID_TOKEN_ONLY_CLAIMS.isdisjoint(claims):
            raise AccessTokenVerificationError

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
