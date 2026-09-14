"""Global Remote Config tool policy. Charges always use this server snapshot."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
from threading import Lock

from fastapi import HTTPException

DEFAULT_COSTS = {
    "text_to_image": 1, "image_to_image": 1, "logo": 1, "avatar": 1,
    "text_to_video": 5, "image_to_video": 5, "promo_video": 5,
    "background_removal": 1, "background_replace": 1,
    "photo_enhance": 0, "compress": 0,
}
ALIASES = {"image_generation": "text_to_image", "video_generation": "text_to_video"}
_lock = Lock()
_tools = {key: {"enabled": True, "credit_cost": cost} for key, cost in DEFAULT_COSTS.items()}
_cache = Path(os.getenv("TOOL_POLICY_CACHE", ".cache/tool-policy.json"))
logger = logging.getLogger(__name__)


def snapshot() -> dict:
    with _lock:
        tools = {key: dict(value) for key, value in _tools.items()}
    revision = hashlib.sha256(json.dumps(tools, sort_keys=True).encode()).hexdigest()[:20]
    return {"revision": revision, "tools": tools}


def apply_parameters(parameters: dict) -> dict:
    """Invalid or conditionally-priced values retain their last valid value."""
    with _lock:
        for tool, current in _tools.items():
            for suffix, field in (("enabled", "enabled"), ("credit_cost", "credit_cost")):
                parameter = parameters.get(f"tool_{tool}_{suffix}", {})
                if parameter.get("conditionalValues"):
                    continue
                value = parameter.get("defaultValue", {}).get("value")
                if field == "enabled" and str(value).lower() in ("true", "false"):
                    current[field] = str(value).lower() == "true"
                elif field == "credit_cost" and isinstance(value, str) and value.isascii() and value.isdecimal():
                    cost = int(value)
                    if cost <= 100000:
                        current[field] = cost
    return snapshot()


def refresh() -> None:
    """Read the published client template with server credentials, never client amounts."""
    try:
        from app.core.firebase import initialize_firebase_app
        from google.auth.transport.requests import AuthorizedSession
        app = initialize_firebase_app()
        with AuthorizedSession(app.credential.get_credential()) as session:
            response = session.get(
                f"https://firebaseremoteconfig.googleapis.com/v1/projects/{app.project_id}/remoteConfig",
                timeout=15,
            )
            response.raise_for_status()
            parameters = response.json().get("parameters", {})
        policy = apply_parameters(parameters)
        _cache.parent.mkdir(parents=True, exist_ok=True)
        temporary = _cache.with_suffix(".tmp")
        temporary.write_text(json.dumps(policy), encoding="utf-8")
        temporary.replace(_cache)
    except Exception as exc:
        logger.warning("Tool policy refresh unavailable (%s); retaining last valid policy", type(exc).__name__)


def restore_cache() -> None:
    try:
        saved = json.loads(_cache.read_text(encoding="utf-8"))["tools"]
        parameters = {}
        for tool, values in saved.items():
            for key, value in values.items():
                parameters[f"tool_{tool}_{key}"] = {"defaultValue": {"value": str(value).lower()}}
        apply_parameters(parameters)
    except (OSError, ValueError, KeyError, TypeError):
        pass


async def refresh_loop() -> None:
    while True:
        await asyncio.to_thread(refresh)
        await asyncio.sleep(45)


def authorize(tool: str, expected_revision: str | None, *, allowed: set[str] | None = None) -> int:
    tool = ALIASES.get(tool, tool)
    policy = snapshot()
    entry = policy["tools"].get(tool)
    if entry is None or (allowed is not None and tool not in allowed):
        raise HTTPException(400, detail="Unknown tool for this operation.")
    if not entry["enabled"]:
        raise HTTPException(503, detail="Temporarily unavailable.")
    # Legacy apps can run only at their original price. They must update before
    # using remotely changed prices, including a newly free operation.
    stale = expected_revision != policy["revision"] if expected_revision else entry["credit_cost"] != DEFAULT_COSTS[tool]
    if stale:
        raise HTTPException(409, detail="Tool settings changed. Review the updated price and try again.")
    return entry["credit_cost"]
