import json

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from flash_trips.adapters.config import (
    ExternalIdentityAllowlistEntry,
    JwksFetchPolicy,
    RuntimeSettings,
)
from flash_trips.composition import create_runtime_app


def runtime_values() -> dict[str, object]:
    return {
        "database_url": (
            "postgresql+asyncpg://flash_trips_runtime:private@db/flash_trips"
        ),
        "external_identity_allowlist": [
            {
                "issuer": "https://issuer.example",
                "subject": "allowed-subject",
            }
        ],
        "live_call_allowance": 0,
    }


def test_runtime_settings_do_not_reveal_database_credentials() -> None:
    settings = RuntimeSettings.model_validate(runtime_values())

    assert "private" not in repr(settings)
    assert "allowed-subject" not in repr(settings)
    assert settings.database_url.get_secret_value().startswith("postgresql+asyncpg://")


def test_scaffold_rejects_live_call_authority() -> None:
    values = runtime_values()
    values["live_call_allowance"] = 1
    with pytest.raises(ValidationError):
        RuntimeSettings.model_validate(values)


@pytest.mark.parametrize(
    "entries",
    [
        [],
        [
            {"issuer": "https://issuer.example", "subject": "first"},
            {"issuer": "https://issuer.example", "subject": "second"},
        ],
    ],
)
def test_runtime_settings_require_exactly_one_external_identity(
    entries: list[dict[str, str]],
) -> None:
    values = runtime_values()
    values["external_identity_allowlist"] = entries

    with pytest.raises(ValidationError):
        RuntimeSettings.model_validate(values)


@pytest.mark.parametrize("field", ["issuer", "subject"])
def test_allowlist_rejects_blank_identity_parts(field: str) -> None:
    values = {"issuer": "https://issuer.example", "subject": "allowed-subject"}
    values[field] = " "

    with pytest.raises(ValidationError):
        ExternalIdentityAllowlistEntry.model_validate(values)


def set_documented_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://runtime:private@db/flash_trips",
    )
    monkeypatch.setenv(
        "EXTERNAL_IDENTITY_ALLOWLIST",
        json.dumps([{"issuer": "https://issuer.example", "subject": "allowed"}]),
    )
    monkeypatch.setenv("LIVE_CALL_ALLOWANCE", "0")


def test_documented_environment_starts_with_its_one_allowlisted_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_documented_environment(monkeypatch)

    settings = RuntimeSettings.from_environment()

    (entry,) = settings.external_identity_allowlist
    assert entry.issuer == "https://issuer.example"
    assert entry.subject.get_secret_value() == "allowed"
    assert settings.live_call_allowance == 0


@pytest.mark.asyncio
async def test_runtime_application_composes_from_the_documented_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_documented_environment(monkeypatch)

    transport = ASGITransport(app=create_runtime_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/status")

    assert response.status_code == 200


def test_environment_startup_rejects_live_call_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_documented_environment(monkeypatch)
    monkeypatch.setenv("LIVE_CALL_ALLOWANCE", "1")

    with pytest.raises(ValidationError):
        RuntimeSettings.from_environment()


def test_environment_startup_rejects_more_than_one_allowlisted_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_documented_environment(monkeypatch)
    monkeypatch.setenv(
        "EXTERNAL_IDENTITY_ALLOWLIST",
        json.dumps(
            [
                {"issuer": "https://issuer.example", "subject": "first"},
                {"issuer": "https://issuer.example", "subject": "second"},
            ]
        ),
    )

    with pytest.raises(ValidationError):
        RuntimeSettings.from_environment()


def test_jwks_fetch_policy_is_versioned_and_rejects_an_unbounded_refresh_rate() -> None:
    assert JwksFetchPolicy().version == 1

    with pytest.raises(ValidationError):
        JwksFetchPolicy(
            minimum_refresh_interval_seconds=60,
            cache_ttl_seconds=30,
        )
