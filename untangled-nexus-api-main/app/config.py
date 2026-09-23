from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = ""
    mongodb_db: str = "untangled_its"
    session_expiry_hours: int = Field(default=8, ge=1, le=168)
    max_document_bytes: int = Field(default=8 * 1024 * 1024, ge=1, le=8 * 1024 * 1024)
    sick_leave_document_required: bool = True
    port: int = 10000
    frontend_url: str = "*"
    node_env: str = "production"
    dashboard_cache_ms: int = 15_000
    mongodb_max_pool_size: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
