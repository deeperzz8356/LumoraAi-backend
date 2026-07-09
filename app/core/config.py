from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_prefix: str = "/api/v1"
    allowed_origins: list[str] = ["http://localhost:8081", "exp://localhost:8081"]

    cloudflare_api_token: str = Field(
        default="",
        validation_alias=AliasChoices("CLOUDFLARE_API_TOKEN", "cloud-fare-api"),
    )
    cloudflare_account_id: str = Field(
        default="",
        validation_alias=AliasChoices("CLOUDFLARE_ACCOUNT_ID", "cloud-fare-account"),
    )
    workers_ai_model: str = Field(
        default="@cf/black-forest-labs/flux-1-schnell",
        validation_alias=AliasChoices("WORKERS_AI_MODEL", "workers_ai_model"),
    )

    firebase_project_id: str = ""
    firebase_credentials_path: str = ""
    firebase_storage_bucket: str = ""
    fcm_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
