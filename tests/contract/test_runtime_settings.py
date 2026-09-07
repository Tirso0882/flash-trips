import pytest
from pydantic import ValidationError

from flash_trips.adapters.config import JwksFetchPolicy, RuntimeSettings


def test_runtime_settings_do_not_reveal_database_credentials() -> None:
    settings = RuntimeSettings.model_validate(
        {
            "database_url": (
                "postgresql+asyncpg://flash_trips_runtime:private@db/flash_trips"
            ),
            "live_call_allowance": 0,
        }
    )

    assert "private" not in repr(settings)
    assert settings.database_url.get_secret_value().startswith("postgresql+asyncpg://")


def test_scaffold_rejects_live_call_authority() -> None:
    with pytest.raises(ValidationError):
        RuntimeSettings.model_validate(
            {
                "database_url": ("postgresql+asyncpg://runtime:private@db/flash_trips"),
                "live_call_allowance": 1,
            }
        )


def test_jwks_fetch_policy_is_versioned_and_rejects_an_unbounded_refresh_rate() -> None:
    assert JwksFetchPolicy().version == 1

    with pytest.raises(ValidationError):
        JwksFetchPolicy(
            minimum_refresh_interval_seconds=60,
            cache_ttl_seconds=30,
        )
