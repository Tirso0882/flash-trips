import base64
import datetime
import hashlib
import ipaddress
import json
import secrets
import ssl
import threading
import time
from collections.abc import Collection, Generator, Mapping
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlencode, urlparse

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
        self.authorization_codes: dict[str, dict[str, str]] = {}
        self.issuer = ""
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
            request = urlparse(self.path)
            if request.path == "/.well-known/openid-configuration":
                self._write_json(
                    {
                        "authorization_endpoint": f"{state.issuer}/authorize",
                        "issuer": state.issuer,
                        "jwks_uri": f"{state.issuer}{JWKS_PATH}",
                        "token_endpoint": f"{state.issuer}/token",
                    }
                )
                return
            if request.path == "/authorize":
                self._authorize(parse_qs(request.query))
                return
            if request.path != JWKS_PATH:
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

        def do_POST(self) -> None:
            if self.path != "/token":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_error(400)
                return
            if length <= 0 or length > 16_384:
                self.send_error(400)
                return
            form = parse_qs(self.rfile.read(length).decode())
            code = _single_value(form, "code")
            authorization = (
                state.authorization_codes.pop(code, None) if code is not None else None
            )
            verifier = _single_value(form, "code_verifier")
            if (
                authorization is None
                or verifier is None
                or _single_value(form, "grant_type") != "authorization_code"
                or _single_value(form, "client_id") != authorization["client_id"]
                or _single_value(form, "redirect_uri") != authorization["redirect_uri"]
                or _code_challenge(verifier) != authorization["code_challenge"]
            ):
                self._write_json({"error": "invalid_grant"}, status=400)
                return

            now = int(time.time())
            common = {
                "iss": state.issuer,
                "sub": "local-subject",
                "iat": now,
                "nbf": now - 1,
                "exp": now + 300,
            }
            headers = {"kid": KEY_ID, "typ": "JWT"}
            access_token = jwt.encode(
                {
                    **common,
                    "aud": authorization["client_id"],
                    "scope": "principal:read",
                },
                state.keys[KEY_ID],
                algorithm="RS256",
                headers=headers,
            )
            id_token = jwt.encode(
                {
                    **common,
                    "aud": authorization["client_id"],
                    "nonce": authorization["nonce"],
                },
                state.keys[KEY_ID],
                algorithm="RS256",
                headers=headers,
            )
            self._write_json(
                {
                    "access_token": access_token,
                    "id_token": id_token,
                    "token_type": "Bearer",
                }
            )

        def _authorize(self, query: Mapping[str, list[str]]) -> None:
            required = {
                name: _single_value(query, name)
                for name in (
                    "client_id",
                    "code_challenge",
                    "nonce",
                    "redirect_uri",
                    "state",
                )
            }
            if (
                any(value is None for value in required.values())
                or _single_value(query, "code_challenge_method") != "S256"
                or _single_value(query, "response_type") != "code"
            ):
                self.send_error(400)
                return
            authorization = {
                name: value for name, value in required.items() if value is not None
            }
            code = secrets.token_urlsafe(32)
            state.authorization_codes[code] = authorization
            separator = "&" if "?" in authorization["redirect_uri"] else "?"
            location = (
                f"{authorization['redirect_uri']}{separator}"
                f"{urlencode({'code': code, 'state': authorization['state']})}"
            )
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()

        def _write_json(
            self, payload: Mapping[str, object], *, status: int = 200
        ) -> None:
            document = json.dumps(payload, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(document)))
            self.end_headers()
            self.wfile.write(document)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    return JwksHandler


def _single_value(values: Mapping[str, list[str]], name: str) -> str | None:
    entries = values.get(name)
    return entries[0] if entries is not None and len(entries) == 1 else None


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


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
        self.authorization_endpoint = f"{issuer}/authorize"
        self.discovery_endpoint = f"{issuer}/.well-known/openid-configuration"
        self.jwks_uri = f"{issuer}{JWKS_PATH}"
        self.token_endpoint = f"{issuer}/token"
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
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
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
        server.daemon_threads = True
        tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls_context.load_cert_chain(
            certfile=certificate_path,
            keyfile=Path(temporary_directory) / "issuer-private-key.pem",
        )
        server.socket = tls_context.wrap_socket(server.socket, server_side=True)
        host, port = server.server_address[0], server.server_address[1]
        state.issuer = f"https://{host}:{port}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield LocalOidcIssuer(
                issuer=state.issuer,
                private_key=private_key,
                state=state,
                ca_file=certificate_path,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
