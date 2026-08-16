from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BTX Omni Prospect"
    environment: str = "development"
    api_prefix: str = "/api"
    data_mode: str = "SAMPLE"

    database_url: str = (
        "postgresql+psycopg://"
        "btx_omni:btx_omni_dev@localhost:5432/btx_omni"
    )

    model_config = SettingsConfigDict(
        env_prefix="BTX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
