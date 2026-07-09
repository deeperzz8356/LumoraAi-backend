# Lumora AI Backend

FastAPI backend for Lumora AI, organized as a normalized `/api/v1` REST service.

## Architecture

The Cloudflare Workers AI redesign plan lives in [docs/cloudflare-workers-ai-architecture.md](docs/cloudflare-workers-ai-architecture.md).

## Structure

- `app/routers` - thin API routers
- `app/services` - business logic and fake/demo implementations
- `app/schemas` - Pydantic request/response schemas
- `app/models` - data models if needed
- `app/database` - fake store and future repository layer
- `app/core` - config and Firebase integration
- `app/middleware` - cross-cutting middleware
- `app/utils` - helper utilities
- `app/workers` - background jobs and queues
- `tests` - backend tests

## Active API Prefix

All endpoints are mounted under:

`/api/v1`

## Example Endpoints

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/guest`
- `GET /api/v1/users`
- `POST /api/v1/images/generate`
- `GET /api/v1/images/{id}`
- `GET /api/v1/images/history`
- `POST /api/v1/images/regenerate`
- `DELETE /api/v1/images/{id}`
- `POST /api/v1/images/share`
- `POST /api/v1/generation/image` (legacy demo route)
- `POST /api/v1/generation/video`
- `GET /api/v1/templates`
- `GET /api/v1/discover`
- `GET /api/v1/history`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/retry`
- `GET /api/v1/notifications`
- `GET /api/v1/profile`
- `GET /api/v1/settings`
- `GET /api/v1/subscriptions`
- `GET /api/v1/credits`
- `POST /api/v1/credits`
- `POST /api/v1/upload`

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Notes

- Firebase auth, Firestore, and Storage are kept as the target backend infrastructure.
- RevenueCat and billing are intentionally removed for now and replaced with service interfaces.
- Demo responses are implemented so the Android app can develop against the API before real AI integration.
