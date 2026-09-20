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
    release_sha: str = ""
    release_tree: str = ""
    release_worktree: str = "unknown"
    frontend_origins: str = "http://localhost:5173"
    session_ttl_seconds: int = 1800
    session_cookie_name: str = "btx_poc_session"
    omni_tenant_id: str | None = Field(default=None, validation_alias="OMNI_TENANT_ID")
    hosted_demo_access_bypass: bool = False
    monitor_mode: str = "disabled"
    monitor_durable_state_enabled: bool = False
    commercial_durable_state_enabled: bool = False
    market_refresh_enabled: bool = False
    monitor_operator_token: str | None = None
    monitor_stale_after_hours: int = 48
    monitor_worker_sources: str = (
        "sam_gov,usaspending,federal_register,sec_edgar,nasa,fda_openfda"
    )
    monitor_source_record_limit: int = Field(default=25, ge=1, le=100)
    monitor_sam_request_budget: int = Field(default=8, ge=1, le=100)
    monitor_sam_page_size: int = Field(default=100, ge=1, le=1000)
    monitor_sam_overlap_days: int = Field(default=3, ge=1, le=30)
    monitor_sam_backfill_days: int = Field(default=365, ge=1, le=365)
    monitor_sam_collection_mode: str = "incremental"
    monitor_usaspending_request_budget: int = Field(default=4, ge=1, le=50)
    monitor_usaspending_page_size: int = Field(default=25, ge=1, le=100)
    monitor_public_lookback_days: int = Field(default=14, ge=1, le=60)
    monitor_document_fetch_cap: int = Field(default=2, ge=0, le=5)
    monitor_research_cap: int = Field(default=2, ge=0, le=3)
    monitor_source_target_limit: int = 25
    monitor_worker_max_seconds: float = Field(default=240, gt=0, le=900)
    monitor_source_min_start_seconds: float = Field(default=2.0, gt=0, le=60)
    # SAM NAICS filtering remains opt-in until the governed BTX market taxonomy
    # has been reviewed for this environment. An empty list deliberately means
    # the bounded date query is unclassified.
    monitor_sam_naics: str = ""
    monitor_sam_naics_verification_state: str = "PENDING_VERIFICATION"
    monitor_brief_synthesis_cap: int = Field(default=3, ge=0, le=10)
    monitor_technical_decomposition_cap: int = Field(default=2, ge=0, le=5)
    monitor_entity_candidate_resolution_cap: int = Field(default=3, ge=0, le=10)
    monitor_brief_auth_retry_seconds: int = 3600
    monitor_brief_timeout_retry_seconds: int = 300
    monitor_brief_quota_retry_seconds: int = 21600
    monitor_brief_unavailable_retry_seconds: int = 900
    federal_procurement_fixture_mode: bool = False
    monitor_schedule_configured: bool = False
    action_salesperson_token: str = "development-salesperson"
    action_manager_token: str = "development-manager"
    # Server-only JSON map: stable user ID -> SHA-256 of a high-entropy access code.
    user_access_code_hashes: dict[str, str] = Field(default_factory=dict, repr=False)
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
    ai_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    ai_daily_environment_calls: int = Field(default=1000, ge=1, le=10000)
    ai_daily_actor_calls: int = Field(default=400, ge=1, le=10000)
    ai_concurrent_environment_calls: int = Field(default=2, ge=1, le=8)
    ai_concurrent_actor_calls: int = Field(default=1, ge=1, le=8)
    sam_api_key: str | None = None
    # Commerce's official content API uses a data.gov API key. Keeping this
    # separate from SAM prevents accidental cross-provider credential use.
    commerce_api_key: str | None = None
    # DEFAULT is a small reviewed official-feed cohort. Operators may replace
    # it with explicit JSON entries; [] deliberately disables a registry.
    monitor_company_feed_registry: str = "DEFAULT"
    monitor_state_source_registry: str = "[]"
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

    @field_validator("user_access_code_hashes")
    @classmethod
    def validate_user_codes(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not key.strip() or key != key.strip() or key.startswith("shared-access")
               or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest)
               for key, digest in value.items()):
            raise ValueError("Invalid server access-code mapping")
        if len(set(value.values())) != len(value):
            raise ValueError("Access codes must identify exactly one user")
        return value

    @property
    def hosted_demo_access_bypass_enabled(self) -> bool:
        """Allow automatic sessions only for an explicitly configured SAMPLE demo."""
        return (
            self.hosted_demo_access_bypass
            and self.environment.casefold() == "production"
            and self.data_mode.upper() == "SAMPLE"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
