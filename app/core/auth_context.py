"""
Authoritative user-identity resolution for request handlers.

Historically most routers trusted a spoofable ``x-user-id`` header (defaulting to
"demo-user"), which means any caller could act as any user — a serious hole for a
credit/reward system. This module centralizes identity resolution:

Resolution order:
  1. A valid Firebase ``Authorization: Bearer <idToken>`` — the ``uid`` from the
     verified token is authoritative and cannot be spoofed.
  2. Otherwise the ``x-user-id`` header (legacy / local-dev / tests).

Security posture is controlled by ``settings.require_auth``:
  - False (default): backward compatible. A missing/invalid token falls back to
    ``x-user-id``. This keeps existing tests and any un-migrated flow working.
  - True (recommended for production): a verified Firebase token is REQUIRED; a
    missing/invalid token → HTTP 401, and ``x-user-id`` is ignored for identity.

Routers should depend on ``resolve_user_id`` instead of reading ``x-user-id``
directly, so tightening auth is a one-flag change rather than a per-route rewrite.
"""

from __future__ import annotations

import logging

from fastapi import Header, HTTPException, status
from firebase_admin import auth as firebase_auth

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _verify_bearer(authorization: str | None) -> str | None:
    """Return the uid from a valid Bearer Firebase token, else None."""
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return None
    token = parts[1].strip()
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded.get("uid")
    except Exception as exc:  # noqa: BLE001 - any verification failure is a non-identity
        logger.warning("Firebase token verification failed: %s", exc)
        return None


async def resolve_user_id(
    authorization: str | None = Header(default=None),
    x_user_id: str = Header(default="demo-user"),
) -> str:
    """FastAPI dependency yielding the authoritative user id for the request.

    Prefers a verified Firebase token's uid; falls back to x-user-id unless
    ``require_auth`` is enabled, in which case a valid token is mandatory.
    """
    uid = _verify_bearer(authorization)
    if uid:
        return uid

    settings = get_settings()
    if getattr(settings, "require_auth", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid Firebase ID token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return x_user_id
