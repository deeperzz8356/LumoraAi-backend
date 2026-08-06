from __future__ import annotations

import base64


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
