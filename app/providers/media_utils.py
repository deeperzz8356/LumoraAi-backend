from __future__ import annotations

import base64
import logging
import re

logger = logging.getLogger(__name__)

_VEO_MODEL_ALIASES: dict[str, str] = {
    "veo-1 ultra": "veo-3.1-generate-001",
    "veo-1": "veo-3.1-generate-001",
    "veo ultra": "veo-3.1-generate-001",
    "fastdraft": "veo-3.1-fast-generate-001",
    "fast draft": "veo-3.1-fast-generate-001",
    "veo fast": "veo-3.1-fast-generate-001",
}

_VALID_VEO_MODEL = re.compile(r"^veo-[\w.-]+$", re.IGNORECASE)


def encode_data_url(data: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def decode_base64_payload(value: str) -> bytes:
    if "," in value and value.startswith("data:"):
        value = value.split(",", 1)[1]
    return base64.b64decode(value)


def closest_aspect_ratio(width: int, height: int) -> str:
    if height <= 0:
        return "1:1"
    ratio = width / height
    candidates = {
        "1:1": 1.0,
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
    }
    return min(candidates.items(), key=lambda item: abs(item[1] - ratio))[0]


def clamp_veo_duration(seconds: int, model: str) -> int:
    """Map requested duration to a Veo-supported value."""
    allowed = (4, 6, 8) if "veo-3" in model else (5, 6, 7, 8)
    return min(allowed, key=lambda value: abs(value - max(1, seconds)))


# Style values that mean "no style / default output" and must NOT inject a
# style directive into the prompt (preservation req 3.13). Compared
# case-insensitively.
_DEFAULT_STYLE_SENTINELS = {"", "default", "none", "standard"}


def is_default_style(style: str | None) -> bool:
    """Return True when ``style`` represents the default/unstyled selection.

    A default style must leave the prompt unchanged so unstyled output is
    preserved (Bug 5 preservation, req 3.13).
    """
    if not style:
        return True
    return style.strip().lower() in _DEFAULT_STYLE_SENTINELS


def apply_style_directive(prompt: str, style: str | None) -> str:
    """Map a UI-selected ``style`` onto the Vertex request as a prompt directive.

    Veo's ``GenerateVideosConfig`` exposes no native ``style`` parameter, so the
    style is carried through as an explicit directive appended to the prompt so
    the generated video visibly reflects the selection (Bug 5, req 2.18/2.19).
    When no style (or the default sentinel) is selected the prompt is returned
    unchanged (preservation req 3.13).
    """
    if is_default_style(style):
        return prompt
    directive = f"in {style.strip()} style"
    base = (prompt or "").strip()
    if not base:
        return directive
    # Avoid double-appending if the caller already included the directive.
    if directive.lower() in base.lower():
        return base
    return f"{base}, {directive}"


def resolve_veo_model(model: str | None, default: str) -> str:
    """Map UI labels and aliases to a Vertex AI Veo model id."""
    if not model or not model.strip():
        return default

    candidate = model.strip()
    alias = _VEO_MODEL_ALIASES.get(candidate.lower())
    if alias:
        logger.info("Resolved video model alias %r -> %r", candidate, alias)
        return alias

    if _VALID_VEO_MODEL.match(candidate):
        return candidate

    logger.warning("Unknown video model %r; using default %r", candidate, default)
    return default
