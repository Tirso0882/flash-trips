from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class JwksFetchPolicy(BaseModel):
    """Versioned resource bounds for retrieving an issuer's signing keys."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    request_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    max_response_bytes: int = Field(default=65_536, ge=1_024, le=1_048_576)
    minimum_refresh_interval_seconds: float = Field(default=30.0, gt=0, le=300)
    cache_ttl_seconds: float = Field(default=300.0, gt=0, le=3_600)

    @model_validator(mode="after")
    def require_refresh_interval_within_cache_ttl(self) -> Self:
        if self.minimum_refresh_interval_seconds > self.cache_ttl_seconds:
            raise ValueError(
                "minimum_refresh_interval_seconds must not exceed cache_ttl_seconds"
            )
        return self


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="forbid",
        frozen=True,
    )

    database_url: SecretStr
    live_call_allowance: Literal[0] = 0

    @model_validator(mode="after")
    def require_postgres_asyncpg(self) -> Self:
        if not self.database_url.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use PostgreSQL with asyncpg")
        return self
