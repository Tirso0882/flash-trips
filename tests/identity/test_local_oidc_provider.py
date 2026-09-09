import base64
import hashlib
import ssl
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from httpx import Client

from .local_issuer import LocalOidcIssuer

pytestmark = [
    pytest.mark.enable_socket,
    pytest.mark.allow_hosts(["127.0.0.1"]),
]


def test_local_issuer_completes_a_pkce_browser_authorization(
    local_oidc_issuer: LocalOidcIssuer,
) -> None:
    verifier = "journey-code-verifier"
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    redirect_uri = "http://localhost:4300/api/auth/callback"

    tls = ssl.create_default_context(cafile=str(local_oidc_issuer.ca_file))
    with Client(verify=tls) as client:
        authorization = client.get(
            local_oidc_issuer.authorization_endpoint,
            params={
                "client_id": "journey-client",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "nonce": "journey-nonce",
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "state": "journey-state",
            },
            follow_redirects=False,
        )
        callback = urlparse(authorization.headers["location"])
        code = parse_qs(callback.query)["code"][0]

        tokens = client.post(
            local_oidc_issuer.token_endpoint,
            data={
                "client_id": "journey-client",
                "code": code,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )

    assert authorization.status_code == 302
    assert parse_qs(callback.query)["state"] == ["journey-state"]
    assert tokens.status_code == 200
    body = tokens.json()
    access_claims = jwt.decode(
        body["access_token"],
        options={"verify_signature": False},
    )
    id_claims = jwt.decode(body["id_token"], options={"verify_signature": False})
    assert access_claims["scope"] == "principal:read"
    assert id_claims["nonce"] == "journey-nonce"
