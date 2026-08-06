"""
Nano-banana Service Account Provider for Image Generation.
Uses Gemini 2.0 Flash or other available models for image generation.
Authenticates with nano-banana-sa.json service account.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from google.oauth2 import service_account
from google.auth import load_credentials_from_file

from app.core.config import get_settings
from app.services.ai_provider import GeneratedImage
from app.schemas.images import ImageGenerateRequest

logger = logging.getLogger(__name__)

_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _resolve_credentials_path(raw_path: str) -> str:
    """Resolve credentials file path."""
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


def _build_nano_banana_client() -> genai.Client:
    """Build client using nano-banana-sa.json service account."""
    settings = get_settings()
    if not settings.google_cloud_project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT not configured")

    credentials = None
    creds_path_to_use = settings.image_generation_credentials

    if creds_path_to_use:
        creds_path = _resolve_credentials_path(creds_path_to_use)
        try:
            # Load as service account
            credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=_SCOPES,
            )
            logger.info(f"✅ Loaded nano-banana service account: {creds_path}")
        except Exception as e:
            # Fallback to ADC format
            logger.info(f"Not a service account file, trying ADC format: {e}")
            credentials, _ = load_credentials_from_file(creds_path, scopes=_SCOPES)

    return genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
        credentials=credentials,
    )


class NanoBananaProvider:
    """Image generation using nano-banana-sa.json service account."""

    def __init__(self):
        self.client = _build_nano_banana_client()
        self.model = "gemini-2.0-flash"  # Default model

    async def generate_image(self, request: ImageGenerateRequest) -> GeneratedImage:
        """Generate image using Gemini 2.0 Flash with nano-banana credentials."""
        settings = get_settings()
        
        logger.info(f"[nano-banana] Generating image with model: {self.model}")
        logger.info(f"[nano-banana] Prompt: {request.prompt[:60]}...")

        try:
            # Use Gemini to generate image
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=[
                    f"Generate an image based on this prompt: {request.prompt}"
                ],
            )

            # Extract generated content
            if response and response.content:
                # Try to get image bytes if available
                for part in response.content.parts:
                    if hasattr(part, 'blob') and hasattr(part.blob, 'mime_type') and part.blob.mime_type.startswith('image/'):
                        logger.info(f"[nano-banana] ✅ Image generated successfully")
                        return GeneratedImage(
                            image_bytes=part.blob.data,
                            mime_type=part.blob.mime_type or "image/png",
                            model=self.model,
                        )

            # If no blob, try to get text response
            if response and response.text:
                logger.info(f"[nano-banana] Got text response, trying to extract image...")
                logger.info(f"Response: {response.text[:100]}")

            logger.warning(f"[nano-banana] Response didn't contain image blob")
            raise RuntimeError("No image data in response")

        except Exception as e:
            logger.error(f"[nano-banana] ❌ Generation failed: {type(e).__name__}: {str(e)[:100]}")
            raise

    async def generate_image_legacy(self, request: ImageGenerateRequest) -> GeneratedImage:
        """Alternative: Use vision model to describe and create image."""
        settings = get_settings()
        
        logger.info(f"[nano-banana-vision] Attempting image generation...")

        try:
            # Create a vision prompt
            response = await self.client.aio.models.generate_content(
                model="gemini-1.5-flash-vision",
                contents=[
                    types.Content(
                        parts=[
                            types.Part.from_text(
                                f"Create an image based on this description: {request.prompt}"
                            )
                        ]
                    )
                ],
            )

            if response and response.content:
                for part in response.content.parts:
                    if hasattr(part, 'blob'):
                        return GeneratedImage(
                            image_bytes=part.blob.data,
                            mime_type=part.blob.mime_type or "image/png",
                            model="gemini-1.5-flash-vision",
                        )

            raise RuntimeError("No image in response")

        except Exception as e:
            logger.error(f"[nano-banana-vision] Failed: {e}")
            raise
