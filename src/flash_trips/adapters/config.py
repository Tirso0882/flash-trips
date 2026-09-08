from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
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


class ExternalIdentityAllowlistEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    issuer: str = Field(min_length=1, max_length=2_048)
    subject: SecretStr = Field(min_length=1, max_length=255)

    @field_validator("issuer")
    @classmethod
    def require_non_blank_issuer(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("external identity values must not be blank")
        return value

    @field_validator("subject")
    @classmethod
    def require_non_blank_subject(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("external identity values must not be blank")
        return value


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="forbid",
        frozen=True,
    )

    database_url: SecretStr
    external_identity_allowlist: tuple[ExternalIdentityAllowlistEntry, ...] = Field(
        min_length=1,
        max_length=1,
    )
    live_call_allowance: Literal[0] = 0

    @field_validator("live_call_allowance", mode="before")
    @classmethod
    def read_allowance_from_text(cls, value: object) -> object:
        # The environment always presents this setting as text, and a literal
        # type accepts no string form of its value.
        if isinstance(value, str):
            return int(value)
        return value

    @model_validator(mode="after")
    def require_postgres_asyncpg(self) -> Self:
        if not self.database_url.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use PostgreSQL with asyncpg")
        return self

    @classmethod
    def from_environment(cls) -> Self:
        # Pyright reads the generated constructor and cannot see that
        # pydantic-settings fills every field from the environment.
        return cls()  # pyright: ignore[reportCallIssue]
