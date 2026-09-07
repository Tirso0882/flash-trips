import pytest
from pydantic import ValidationError

from flash_trips.adapters.config import RuntimeSettings


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
