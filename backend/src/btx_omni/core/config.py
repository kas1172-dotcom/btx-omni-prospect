from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    app_name: str = "BTX Omni Prospect"
    environment: str = "development"
    api_prefix: str = "/api"
    data_mode: str = "SAMPLE"
    frontend_origins: str = "http://localhost:5173"
    session_ttl_seconds: int = 1800
    session_cookie_name: str = "btx_poc_session"
    monitor_mode: str = "disabled"
    monitor_durable_state_enabled: bool = False
    monitor_operator_token: str | None = None
    monitor_stale_after_hours: int = 48
    monitor_worker_sources: str = (
        "sam_gov,usaspending,federal_register,sec_edgar,nasa,fda_openfda"
    )
    monitor_source_record_limit: int = 25
    monitor_source_target_limit: int = 25
    monitor_worker_max_seconds: float = 240
    monitor_source_min_start_seconds: float = 2.0
    # SAM NAICS filtering remains opt-in until BTX verifies the target codes.
    # An empty list deliberately means the bounded date query is unclassified.
    monitor_sam_naics: str = ""
    monitor_sam_naics_verification_state: str = "PENDING_VERIFICATION"
    monitor_brief_synthesis_cap: int = 3
    monitor_brief_auth_retry_seconds: int = 3600
    monitor_brief_timeout_retry_seconds: int = 300
    monitor_brief_quota_retry_seconds: int = 21600
    monitor_brief_unavailable_retry_seconds: int = 900
    federal_procurement_fixture_mode: bool = False
    monitor_schedule_configured: bool = False
    action_salesperson_token: str = "development-salesperson"
    action_manager_token: str = "development-manager"
    ai_provider: str = "gemini"
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "BTX_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"
        ),
    )
    gemini_model: str = "gemini-2.5-flash"
    gemini_mode: str = "developer"
    google_cloud_project: str | None = None
    google_cloud_location: str = "global"
    ai_timeout_seconds: float = 20.0
    sam_api_key: str | None = None
    # SEC requires an organization/contact identifying User-Agent.  Never use a
    # plausible-looking default contact as a production identity.
    sec_user_agent: str | None = None

    database_url: str = Field(
        default=("postgresql+psycopg://btx_omni:btx_omni_dev@localhost:5432/btx_omni"),
        validation_alias=AliasChoices("BTX_DATABASE_URL", "DATABASE_URL"),
    )

    model_config = SettingsConfigDict(
        env_prefix="BTX_",
        env_file=BACKEND_ENV_FILE,
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
