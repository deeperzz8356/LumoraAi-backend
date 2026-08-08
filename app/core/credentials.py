from __future__ import annotations

import json
import os
from pathlib import Path

from google.auth import load_credentials_from_file
from google.oauth2 import service_account

_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


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
        f"Credentials file not found: {raw_path!r} (looked under {_BACKEND_ROOT})"
    )


def load_google_credentials(
    *,
    file_path: str = "",
    json_env_name: str = "",
):
    json_payload = os.getenv(json_env_name, "").strip() if json_env_name else ""
    if json_payload:
        try:
            info = json.loads(json_payload)
            return service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
        except Exception:
            credentials, _ = load_credentials_from_file(json_payload, scopes=_SCOPES)
            return credentials

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
