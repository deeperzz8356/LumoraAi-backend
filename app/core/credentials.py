from __future__ import annotations

import json
import os
from pathlib import Path

from google.auth import load_credentials_from_file
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as UserCredentials

_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)
_BACKEND_ROOT = Path(__file__).resolve().parents[2]

_JSON_ENV_VARS = (
    "GOOGLE_APPLICATION_CREDENTIALS_JSON",
    "IMAGE_GENERATION_CREDENTIALS_JSON",
)
_VERTEX_CREDENTIALS_TMP = Path(
    os.environ.get("VERTEX_CREDENTIALS_TMP", "/tmp/lumora-vertex-credentials.json")
)


def resolve_credentials_path(raw_path: str) -> str:
    path = Path(raw_path)
    if path.is_file():
        return str(path.resolve())
    candidate = _BACKEND_ROOT / raw_path
    if candidate.is_file():
        return str(candidate.resolve())
    candidate = _BACKEND_ROOT / Path(raw_path).name
    if candidate.is_file():
        return str(candidate.resolve())
    raise FileNotFoundError(
        f"Vertex AI credentials file not found: {raw_path!r} (looked under {_BACKEND_ROOT})"
    )


def credentials_file_exists(raw_path: str) -> bool:
    if not raw_path:
        return False
    try:
        resolve_credentials_path(raw_path)
        return True
    except FileNotFoundError:
        return False


def _load_credentials_from_json_payload(json_payload: str):
    info = json.loads(json_payload)
    if info.get("type") == "service_account":
        return service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    if info.get("type") == "authorized_user":
        return UserCredentials.from_authorized_user_info(info, scopes=_SCOPES)
    credentials, _ = load_credentials_from_file(json_payload, scopes=_SCOPES)
    return credentials


def load_google_credentials(
    *,
    file_path: str = "",
    json_env_name: str = "",
):
    json_payload = os.getenv(json_env_name, "").strip() if json_env_name else ""
    if json_payload:
        return _load_credentials_from_json_payload(json_payload)

    if file_path:
        resolved = resolve_credentials_path(file_path)
        try:
            return service_account.Credentials.from_service_account_file(
                resolved,
                scopes=_SCOPES,
            )
        except Exception:
            credentials, _ = load_credentials_from_file(resolved, scopes=_SCOPES)
            return credentials

    raise RuntimeError(
        f"Missing Google credentials. Set {json_env_name or 'a credentials JSON env var'} "
        "or provide a credentials file path."
    )


def load_vertex_credentials(*, file_path: str = ""):
    """Load Vertex credentials — JSON env vars always win over file paths."""
    for env_name in _JSON_ENV_VARS:
        if os.getenv(env_name, "").strip():
            return load_google_credentials(file_path="", json_env_name=env_name)

    if file_path and credentials_file_exists(file_path):
        return load_google_credentials(file_path=file_path, json_env_name="")

    raise RuntimeError(
        "Vertex AI credentials not found on the server. "
        "On Render, set GOOGLE_APPLICATION_CREDENTIALS_JSON to the full JSON content "
        "(paste nano-banana-sa.json or application_default_credentials.json). "
        "Remove GOOGLE_APPLICATION_CREDENTIALS and FIREBASE_CREDENTIALS_PATH "
        "if they point to local files like ./firebase-credentials.json."
    )


def _is_vertex_credential_path(raw_path: str) -> bool:
    """Firebase SA files must never be used for Vertex AI."""
    if not raw_path:
        return False
    name = Path(raw_path).name.lower()
    if "firebase" in name:
        return False
    return credentials_file_exists(raw_path)


def ensure_vertex_credentials_env() -> None:
    """
    Prepare credentials for Render and other container hosts.

    - Writes JSON env vars to a temp file so ADC-based libraries work.
    - Clears stale GOOGLE_APPLICATION_CREDENTIALS paths that do not exist on disk.
    """
    for env_name in _JSON_ENV_VARS:
        payload = os.getenv(env_name, "").strip()
        if payload.startswith("{"):
            _VERTEX_CREDENTIALS_TMP.write_text(payload, encoding="utf-8")
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_VERTEX_CREDENTIALS_TMP)
            return

    raw = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if raw and not credentials_file_exists(raw):
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)


def load_vertex_credentials_from_settings():
    from app.core.config import get_settings

    ensure_vertex_credentials_env()
    settings = get_settings()
    file_path = next(
        (
            path
            for path in (
                settings.google_application_credentials,
                settings.image_generation_credentials,
            )
            if _is_vertex_credential_path(path)
        ),
        "",
    )
    return load_vertex_credentials(file_path=file_path)
