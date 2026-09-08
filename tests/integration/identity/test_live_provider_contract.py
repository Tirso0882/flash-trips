import logging

import pytest
from pydantic import ValidationError

from flash_trips.adapters.config import RuntimeSettings
from flash_trips.adapters.identity import JwtAccessTokenVerifier
from flash_trips.application import AccessTokenVerificationError


def _runtime_values() -> dict[str, object]:
    tenant_id = "01991e28-1d65-7000-8000-000000000001"
    return {
        "database_url": (
            "postgresql+asyncpg://flash_trips_runtime:private@db/flash_trips"
        ),
        "external_identity_allowlist": [
            {
                "issuer": f"https://{tenant_id}.ciamlogin.com/{tenant_id}/v2.0",
                "subject": "disposable-planner",
            }
        ],
        "flash_trips_oidc_client_id": "01991e28-1d65-7000-8000-000000000002",
        "flash_trips_oidc_issuer": (
            f"https://{tenant_id}.ciamlogin.com/{tenant_id}/v2.0"
        ),
        "flash_trips_oidc_tenant_id": tenant_id,
        "flash_trips_oidc_tenant_subdomain": "flashtrips",
        "live_call_allowance": 0,
    }


def test_live_provider_configuration_uses_the_exact_tenant_boundary() -> None:
    settings = RuntimeSettings.model_validate(_runtime_values())

    assert settings.oidc_is_configured
    assert (
        settings.oidc_jwks_uri == "https://flashtrips.ciamlogin.com/"
        "flashtrips.onmicrosoft.com/discovery/v2.0/keys"
    )

    values = _runtime_values()
    values["flash_trips_oidc_issuer"] = "https://other.example/v2.0"
    with pytest.raises(ValidationError):
        RuntimeSettings.model_validate(values)


def test_provider_token_canary_never_reaches_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    canary = "authorization-code-and-token-canary"
    verifier = JwtAccessTokenVerifier(
        issuer="https://flashtrips.ciamlogin.com/tenant/v2.0",
        audience="flash-trips-api",
        jwks_uri=(
            "https://flashtrips.ciamlogin.com/"
            "flashtrips.onmicrosoft.com/discovery/v2.0/keys"
        ),
        allowed_algorithms=("RS256",),
        required_scope="principal:read",
    )

    with caplog.at_level(logging.DEBUG), pytest.raises(AccessTokenVerificationError):
        verifier.verify(canary)

    assert canary not in caplog.text
