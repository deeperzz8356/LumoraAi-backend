"""
Tests for resolve_user_id: authoritative identity resolution.

Verifies:
- A valid Firebase Bearer token's uid takes precedence over x-user-id.
- Without a token, x-user-id is used when require_auth is False (backward compat).
- With require_auth True, a missing/invalid token is rejected (401).
"""

import asyncio
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.core import auth_context


def _run(coro):
    return asyncio.run(coro)


def test_token_uid_takes_precedence_over_header():
    with patch.object(auth_context, "_verify_bearer", return_value="real-uid"):
        uid = _run(auth_context.resolve_user_id(authorization="Bearer x", x_user_id="spoofed"))
    assert uid == "real-uid"


def test_falls_back_to_header_when_no_token_and_auth_not_required():
    fake_settings = type("S", (), {"require_auth": False})()
    with patch.object(auth_context, "_verify_bearer", return_value=None), \
            patch.object(auth_context, "get_settings", return_value=fake_settings):
        uid = _run(auth_context.resolve_user_id(authorization=None, x_user_id="header-uid"))
    assert uid == "header-uid"


def test_rejects_when_auth_required_and_no_valid_token():
    fake_settings = type("S", (), {"require_auth": True})()
    with patch.object(auth_context, "_verify_bearer", return_value=None), \
            patch.object(auth_context, "get_settings", return_value=fake_settings):
        with pytest.raises(HTTPException) as exc:
            _run(auth_context.resolve_user_id(authorization=None, x_user_id="header-uid"))
    assert exc.value.status_code == 401
