import base64
import datetime
import ipaddress
import json
import ssl
import threading
import time
from collections.abc import Collection, Generator, Mapping
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

JWKS_PATH = "/.well-known/jwks.json"
KEY_ID = "local-test-key"


def _base64url_uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode()


def _jwk(
    private_key: rsa.RSAPrivateKey,
    key_id: str,
    *,
    public_key_use: str = "sig",
) -> dict[str, str]:
    public_numbers = private_key.public_key().public_numbers()
    return {
        "kty": "RSA",
        "use": public_key_use,
        "alg": "RS256",
        "kid": key_id,
        "n": _base64url_uint(public_numbers.n),
        "e": _base64url_uint(public_numbers.e),
    }


class _IssuerState:
    def __init__(self, private_key: rsa.RSAPrivateKey) -> None:
        self.keys = {KEY_ID: private_key}
        self.unusable_keys: list[dict[str, str]] = []
        self.request_count = 0
        self.not_modified_count = 0
        self.delay_seconds = 0.0
        self.padding_bytes = 0
        self.raw_document: bytes | None = None

    @property
    def document(self) -> bytes:
        if self.raw_document is not None:
            return self.raw_document
        document: dict[str, object] = {
            "keys": [
                *(
                    _jwk(private_key, key_id)
                    for key_id, private_key in self.keys.items()
                ),
                *self.unusable_keys,
            ]
        }
        if self.padding_bytes:
            document["padding"] = "x" * self.padding_bytes
        return json.dumps(document, sort_keys=True).encode()

    @property
    def etag(self) -> str:
        return f'"keys-{",".join(self.keys)}"'


def _jwks_handler(state: _IssuerState) -> type[BaseHTTPRequestHandler]:
    class JwksHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != JWKS_PATH:
                self.send_error(404)
                return
            state.request_count += 1
            if state.delay_seconds:
                time.sleep(state.delay_seconds)
            if self.headers.get("If-None-Match") == state.etag:
                state.not_modified_count += 1
                self.send_response(304)
                self.end_headers()
                return
            document = state.document
            self.send_response(200)
            self.send_header("Content-Type", "application/jwk-set+json")
            self.send_header("Content-Length", str(len(document)))
            self.send_header("ETag", state.etag)
            self.end_headers()
            self.wfile.write(document)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    return JwksHandler


class LocalOidcIssuer:
    """Deterministic issuer that mints access tokens for its served JWKS."""

    def __init__(
        self,
        *,
        issuer: str,
        private_key: rsa.RSAPrivateKey,
        state: _IssuerState,
        ca_file: Path,
    ) -> None:
        self.issuer = issuer
        self.jwks_uri = f"{issuer}{JWKS_PATH}"
        self.ca_file = ca_file
        self._private_key = private_key
        self._key_id = KEY_ID
        self._state = state

    @property
    def jwks_request_count(self) -> int:
        return self._state.request_count

    @property
    def jwks_not_modified_count(self) -> int:
        return self._state.not_modified_count

    def rotate(self) -> str:
        key_id = f"rotated-key-{len(self._state.keys)}"
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._state.keys[key_id] = private_key
        self._private_key = private_key
        self._key_id = key_id
        return key_id

    def publish_encryption_key(self) -> None:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._state.unusable_keys.append(
            _jwk(private_key, "encryption-key", public_key_use="enc")
        )

    def retire(self, key_id: str) -> None:
        self._state.keys.pop(key_id)

    def delay_jwks_responses(self, seconds: float) -> None:
        self._state.delay_seconds = seconds

    def pad_jwks_document(self, byte_count: int) -> None:
        self._state.padding_bytes = byte_count

    def serve_jwks_document(self, document: bytes) -> None:
        self._state.raw_document = document

    def mint(
        self,
        claims: Mapping[str, object] | None = None,
        *,
        without_claims: Collection[str] = (),
        algorithm: str = "RS256",
        signing_key: rsa.RSAPrivateKey | str | None = None,
        key_id: str | None = None,
        extra_headers: Mapping[str, object] | None = None,
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

        headers: dict[str, object] = {
            "kid": key_id or self._key_id,
            "typ": "JWT",
        }
        if extra_headers is not None:
            headers.update(extra_headers)

        return jwt.encode(
            token_claims,
            signing_key if signing_key is not None else self._private_key,
            algorithm=algorithm,
            headers=headers,
        )


def _write_tls_certificate(directory: Path, private_key: rsa.RSAPrivateKey) -> Path:
    now = datetime.datetime.now(tz=datetime.UTC)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Flash Trips local issuer")]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    certificate_path = directory / "issuer-certificate.pem"
    private_key_path = directory / "issuer-private-key.pem"
    certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    private_key_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return certificate_path


@contextmanager
def serving_local_oidc_issuer() -> Generator[LocalOidcIssuer]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    state = _IssuerState(private_key)
    with TemporaryDirectory() as temporary_directory:
        certificate_path = _write_tls_certificate(
            Path(temporary_directory), private_key
        )
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            _jwks_handler(state),
        )
        tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls_context.load_cert_chain(
            certfile=certificate_path,
            keyfile=Path(temporary_directory) / "issuer-private-key.pem",
        )
        server.socket = tls_context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[0], server.server_address[1]
            yield LocalOidcIssuer(
                issuer=f"https://{host}:{port}",
                private_key=private_key,
                state=state,
                ca_file=certificate_path,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
