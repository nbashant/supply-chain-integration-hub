from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )

    app_name: str = "Supply Chain Integration Hub"
    app_environment: Literal["local", "test", "production"] = "local"
    app_log_level: str = "INFO"
    database_url: str = Field(
        default=(
            "postgresql+psycopg://supply_chain:"
            "local-development-only@127.0.0.1:5432/supply_chain_hub"
        ),
    )
    redis_url: str = "redis://127.0.0.1:6379/0"
    object_storage_endpoint: str = "http://127.0.0.1:8333"
    object_storage_access_key: str = "supply-chain-local"
    object_storage_secret_key: str = "local-object-storage-only"
    object_storage_bucket: str = "supply-chain-data"
    object_storage_region: str = "us-east-1"
    partner_api_token: str = "local-partner-token-change-me"
    allowed_hosts: str = "127.0.0.1,localhost,testserver,api"
    import_max_attempts: int = Field(default=3, ge=1, le=10)
    import_retry_base_seconds: int = Field(default=2, ge=1, le=300)
    import_retry_max_seconds: int = Field(default=60, ge=1, le=3600)
    import_lease_seconds: int = Field(default=300, ge=30, le=3600)
    import_redispatch_seconds: int = Field(default=60, ge=10, le=3600)

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @model_validator(mode="after")
    def reject_production_placeholders(self) -> "Settings":
        if self.app_environment == "production" and self.partner_api_token == (
            "local-partner-token-change-me"
        ):
            raise ValueError("PARTNER_API_TOKEN must be changed in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
