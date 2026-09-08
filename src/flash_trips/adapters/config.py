from typing import Literal, Self
from uuid import UUID

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
    flash_trips_oidc_client_id: str | None = None
    flash_trips_oidc_issuer: str | None = None
    flash_trips_oidc_tenant_id: str | None = None
    flash_trips_oidc_tenant_subdomain: str | None = None

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
        oidc_values = (
            self.flash_trips_oidc_client_id,
            self.flash_trips_oidc_issuer,
            self.flash_trips_oidc_tenant_id,
            self.flash_trips_oidc_tenant_subdomain,
        )
        if any(value is not None for value in oidc_values):
            if any(value is None or not value.strip() for value in oidc_values):
                raise ValueError("OIDC verifier configuration must be complete")
            tenant_id_value = self.flash_trips_oidc_tenant_id
            subdomain = self.flash_trips_oidc_tenant_subdomain
            issuer = self.flash_trips_oidc_issuer
            if tenant_id_value is None or subdomain is None or issuer is None:
                raise ValueError("OIDC verifier configuration must be complete")
            tenant_id = str(UUID(tenant_id_value))
            if issuer != f"https://{tenant_id}.ciamlogin.com/{tenant_id}/v2.0":
                raise ValueError("OIDC issuer must be the exact external tenant issuer")
        return self

    @property
    def oidc_is_configured(self) -> bool:
        return self.flash_trips_oidc_issuer is not None

    @property
    def oidc_jwks_uri(self) -> str:
        if self.flash_trips_oidc_tenant_subdomain is None:
            raise ValueError("OIDC verifier is not configured")
        subdomain = self.flash_trips_oidc_tenant_subdomain
        return (
            f"https://{subdomain}.ciamlogin.com/"
            f"{subdomain}.onmicrosoft.com/discovery/v2.0/keys"
        )

    @classmethod
    def from_environment(cls) -> Self:
        # Pyright reads the generated constructor and cannot see that
        # pydantic-settings fills every field from the environment.
        return cls()  # pyright: ignore[reportCallIssue]
