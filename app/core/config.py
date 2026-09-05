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
    cloudflare_api_tokens: str = Field(
        default="",
        validation_alias=AliasChoices("CLOUDFLARE_API_TOKENS", "CLOUDFLARE_API_TOKEN"),
        description="Comma separated list of API tokens for quota rotation"
    )
    cloudflare_account_id: str = Field(
        default="",
        validation_alias=AliasChoices("CLOUDFLARE_ACCOUNT_ID", "cloud-fare-account"),
    )
    pollinations_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("POLLINATIONS_API_KEY"),
    )
    workers_ai_model: str = Field(
        default="@cf/black-forest-labs/flux-1-schnell",
        validation_alias=AliasChoices("WORKERS_AI_MODEL", "workers_ai_model"),
    )

    google_cloud_project: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_CLOUD_PROJECT", "PROJECT_ID", "GCP_PROJECT"),
    )
    google_cloud_location: str = Field(
        default="us-west1",
        validation_alias=AliasChoices("GOOGLE_CLOUD_LOCATION", "REGION", "GCP_LOCATION"),
    )
    google_application_credentials: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GOOGLE_APPLICATION_CREDENTIALS",
            "VERTEX_CREDENTIALS_PATH",
        ),
    )
    image_generation_credentials: str = Field(
        default="",
        validation_alias=AliasChoices("IMAGE_GENERATION_CREDENTIALS"),
    )
    vertex_image_model: str = Field(
        default="imagegeneration@006",
        validation_alias=AliasChoices("VERTEX_IMAGE_MODEL"),
    )
    vertex_video_model: str = Field(
        default="veo-3.1-fast-generate-001",
        validation_alias=AliasChoices("VERTEX_VIDEO_MODEL"),
    )
    vertex_video_output_gcs_uri: str = Field(
        default="",
        validation_alias=AliasChoices("VERTEX_VIDEO_OUTPUT_GCS_URI"),
    )
    vertex_video_poll_seconds: int = Field(default=15, ge=1, le=120)
    vertex_video_poll_attempts: int = Field(default=40, ge=1, le=200)

    # Bug 1: upstream 429 (RESOURCE_EXHAUSTED) handling — bounded exponential
    # backoff + jitter and in-process concurrency limiting. No Redis/Celery/queues
    # (Render FREE plan): state is in-process only.
    upstream_max_retries: int = Field(
        default=4,
        ge=0,
        le=10,
        validation_alias=AliasChoices("UPSTREAM_MAX_RETRIES"),
        description="Max retry attempts on a retriable upstream 429 before honest failure.",
    )
    upstream_backoff_base_seconds: float = Field(
        default=0.5,
        ge=0.0,
        le=30.0,
        validation_alias=AliasChoices("UPSTREAM_BACKOFF_BASE_SECONDS"),
        description="Base delay for exponential backoff on upstream 429.",
    )
    upstream_backoff_max_seconds: float = Field(
        default=20.0,
        ge=0.0,
        le=120.0,
        validation_alias=AliasChoices("UPSTREAM_BACKOFF_MAX_SECONDS"),
        description="Ceiling for a single backoff delay (also caps honored retryDelay).",
    )
    upstream_concurrency_limit: int = Field(
        default=3,
        ge=1,
        le=50,
        validation_alias=AliasChoices("UPSTREAM_CONCURRENCY_LIMIT"),
        description="Max simultaneous Vertex calls guarded by an in-process semaphore.",
    )
    upstream_retry_sleep_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("UPSTREAM_RETRY_SLEEP_ENABLED"),
        description="When False, backoff delays are computed but not slept (fast tests).",
    )
    
    # Video stitching settings
    vertex_video_output_dir: str = Field(
        default="./generated_videos",
        validation_alias=AliasChoices("VERTEX_VIDEO_OUTPUT_DIR"),
        description="Local directory for downloaded video clips and stitched videos"
    )
    vertex_video_stitch_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("VERTEX_VIDEO_STITCH_ENABLED"),
        description="Enable automatic video stitching for long-form content"
    )
    gcs_bucket_name: str = Field(
        default="",
        validation_alias=AliasChoices("GCS_BUCKET_NAME"),
        description="GCS bucket name for video outputs (parsed from GCS URI if not provided)"
    )

    firebase_project_id: str = ""
    firebase_credentials_path: str = ""
    firebase_storage_bucket: str = ""
    fcm_enabled: bool = True
    revenuecat_webhook_auth_key: str = Field(
        default="",
        validation_alias=AliasChoices("REVENUECAT_WEBHOOK_AUTH_KEY"),
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    updates: dict[str, str] = {}
    # Local dev only: default Veo output bucket from Firebase storage when not configured.
    # Never map Firebase credentials or project to Vertex — they are different GCP projects.
    if (
        settings.app_env == "development"
        and not settings.vertex_video_output_gcs_uri
        and settings.firebase_storage_bucket
    ):
        updates["vertex_video_output_gcs_uri"] = (
            f"gs://{settings.firebase_storage_bucket}/veo-outputs"
        )
    return settings.model_copy(update=updates) if updates else settings
