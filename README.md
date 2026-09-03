# Google Play verification service

This service is the trusted boundary for Play purchases. The Android client
never supplies a credit amount. Configure:

```text
FIREBASE_SERVICE_ACCOUNT_JSON=/secrets/firebase-admin.json
PLAY_SERVICE_ACCOUNT_JSON=/secrets/play-publisher.json
PLAY_PACKAGE_NAME=com.deep.lumoraai
PLAY_PRODUCT_CATALOG_JSON={"credits_starter":{"kind":"inapp","credits":50},"credits_creator":{"kind":"inapp","credits":150},"credits_studio":{"kind":"inapp","credits":500},"pro_monthly":{"kind":"subs","entitlement":"pro"},"pro_annual":{"kind":"subs","entitlement":"pro"},"elite_pro":{"kind":"subs","entitlement":"elite"}}
DATABASE_PATH=./billing.sqlite3
```

Run with `uvicorn app.main:app`. `POST /api/v1/billing/google-play/verify`
requires a Firebase ID token (`Authorization: Bearer <firebase-id-token>`) and accepts only
`product_id` and `purchase_token`. Google Play Developer API verification,
catalog mapping, and a unique purchase-token transaction provide idempotency.
The Android client acknowledges/consumes only after this endpoint returns
success. Subscription verification also requires the requested product ID to
match a Google `lineItems` entry and stores expiry/auto-renew state.
Deploy behind TLS and never expose service-account files. The endpoint is safe
to retry: one-time purchases are credited once per purchase token, while
subscription retries refresh expiry, auto-renew, and active/canceled state.
Run the included tests with `python -m pytest -q`. A production container is
provided in `backend/Dockerfile`; mount credentials read-only and inject the
three configuration values through your secret manager, not an image layer.

For a production deployment, put the service behind an authenticated TLS
reverse proxy, restrict the service account to the Play Android Publisher
permissions it needs, and back up `DATABASE_PATH` (or replace SQLite with a
transactional shared database before running multiple replicas).
