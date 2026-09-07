from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
