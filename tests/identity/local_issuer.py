import base64
import json
import threading
import time
from collections.abc import Collection, Generator, Mapping
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

JWKS_PATH = "/.well-known/jwks.json"
KEY_ID = "local-test-key"


def _base64url_uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode()


def _jwks_document(private_key: rsa.RSAPrivateKey) -> bytes:
    public_numbers = private_key.public_key().public_numbers()
    return json.dumps(
        {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": KEY_ID,
                    "n": _base64url_uint(public_numbers.n),
                    "e": _base64url_uint(public_numbers.e),
                }
            ]
        }
    ).encode()


def _jwks_handler(document: bytes) -> type[BaseHTTPRequestHandler]:
    class JwksHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != JWKS_PATH:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/jwk-set+json")
            self.send_header("Content-Length", str(len(document)))
            self.end_headers()
            self.wfile.write(document)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    return JwksHandler


class LocalOidcIssuer:
    """Deterministic issuer that mints access tokens for its served JWKS."""

    def __init__(self, *, issuer: str, private_key: rsa.RSAPrivateKey) -> None:
        self.issuer = issuer
        self.jwks_uri = f"{issuer}{JWKS_PATH}"
        self._private_key = private_key

    def mint(
        self,
        claims: Mapping[str, object] | None = None,
        *,
        without_claims: Collection[str] = (),
        algorithm: str = "RS256",
        signing_key: rsa.RSAPrivateKey | str | None = None,
    ) -> str:
        now = int(time.time())
        token_claims: dict[str, object] = {
            "iss": self.issuer,
            "sub": "local-subject",
            "aud": "flash-trips-api",
            "iat": now,
            "nbf": now - 1,
            "exp": now + 300,
            "scope": "principal:read",
        }
        if claims is not None:
            token_claims.update(claims)
        for claim in without_claims:
            token_claims.pop(claim, None)

        return jwt.encode(
            token_claims,
            signing_key if signing_key is not None else self._private_key,
            algorithm=algorithm,
            headers={"kid": KEY_ID},
        )


@contextmanager
def serving_local_oidc_issuer() -> Generator[LocalOidcIssuer]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        _jwks_handler(_jwks_document(private_key)),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[0], server.server_address[1]
        yield LocalOidcIssuer(
            issuer=f"http://{host}:{port}",
            private_key=private_key,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
