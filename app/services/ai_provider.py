from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.schemas.images import ImageGenerateRequest


@dataclass(slots=True)
class GeneratedImage:
    image_bytes: bytes
    mime_type: str
    model: str


class AIProvider(Protocol):
    async def generate_image(self, request: ImageGenerateRequest) -> GeneratedImage:
        raise NotImplementedError
