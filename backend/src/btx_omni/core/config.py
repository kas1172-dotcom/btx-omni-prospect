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
    monitor_durable_state_enabled: bool = False
    monitor_operator_token: str | None = None
    monitor_stale_after_hours: int = 48
    action_salesperson_token: str = "development-salesperson"
    action_manager_token: str = "development-manager"
    ai_provider: str = "gemini"
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BTX_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    gemini_model: str = "gemini-2.5-flash"
    gemini_mode: str = "developer"
    google_cloud_project: str | None = None
    google_cloud_location: str = "global"
    ai_timeout_seconds: float = 20.0
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
