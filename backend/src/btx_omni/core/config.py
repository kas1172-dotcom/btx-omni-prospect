from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BTX Omni Prospect"
    environment: str = "development"
    api_prefix: str = "/api"
    data_mode: str = "SAMPLE"
    frontend_origins: str = "http://localhost:5173"
    monitor_mode: str = "disabled"
    ai_provider: str = "anthropic"
    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BTX_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
    )
    anthropic_model: str = "claude-sonnet-5"
    sam_api_key: str | None = None

    database_url: str = Field(
        default=(
            "postgresql+psycopg://"
            "btx_omni:btx_omni_dev@localhost:5432/btx_omni"
        ),
        validation_alias=AliasChoices("BTX_DATABASE_URL", "DATABASE_URL"),
    )

    model_config = SettingsConfigDict(
        env_prefix="BTX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Force platform PostgreSQL URLs onto the project's psycopg v3 dialect."""
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
