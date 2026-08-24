from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.credentials import ensure_vertex_credentials_env
from app.core.firebase import initialize_firebase_app
from app.routers import auth, users, generation, images, videos, templates, notifications, profile, settings, subscriptions, credits, upload, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_vertex_credentials_env()
    initialize_firebase_app()
    yield


def create_app() -> FastAPI:
    app_settings = get_settings()
    app = FastAPI(
        title="Lumora AI API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if app_settings.app_env == "development" else None,
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = app_settings.api_prefix
    app.include_router(auth.router, prefix=f"{prefix}/auth", tags=["auth"])
    app.include_router(users.router, prefix=f"{prefix}/users", tags=["users"])
    app.include_router(generation.router, prefix=f"{prefix}/generation", tags=["generation"])
    app.include_router(images.router, prefix=f"{prefix}/images", tags=["images"])
    app.include_router(videos.router, prefix=f"{prefix}/videos", tags=["videos"])
    app.include_router(templates.router, prefix=f"{prefix}/templates", tags=["templates"])
    app.include_router(notifications.router, prefix=f"{prefix}/notifications", tags=["notifications"])
    app.include_router(profile.router, prefix=f"{prefix}/profile", tags=["profile"])
    app.include_router(settings.router, prefix=f"{prefix}/settings", tags=["settings"])
    app.include_router(subscriptions.router, prefix=f"{prefix}/subscriptions", tags=["subscriptions"])
    app.include_router(credits.router, prefix=f"{prefix}/credits", tags=["credits"])
    app.include_router(upload.router, prefix=f"{prefix}/upload", tags=["upload"])
    app.include_router(webhooks.router, prefix=f"{prefix}/webhooks", tags=["webhooks"])

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
