from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.core.credentials import load_vertex_credentials_from_settings
from app.providers.media_utils import (
    clamp_veo_duration,
    closest_aspect_ratio,
    decode_base64_payload,
    encode_data_url,
)
from app.schemas.images import ImageGenerateRequest
from app.services.ai_provider import GeneratedImage

logger = logging.getLogger(__name__)


@lru_cache
def _build_client() -> genai.Client:
    settings = get_settings()
    if not settings.google_cloud_project:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT is not configured. Set it in backend/.env to use Vertex AI."
        )

    credentials = load_vertex_credentials_from_settings()

    return genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
        credentials=credentials,
    )


def _build_image_client() -> genai.Client:
    """Build dedicated client for image generation."""
    settings = get_settings()
    if not settings.google_cloud_project:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT is not configured. Set it in backend/.env to use Vertex AI."
        )

    credentials = load_vertex_credentials_from_settings()
    logger.info("Loaded image generation credentials from env or file")

    return genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
        credentials=credentials,
    )


class VertexAIProvider:
    """Image (Imagen) and video (Veo) generation via Vertex AI / Google Gen AI SDK."""

    async def generate_image(self, request: ImageGenerateRequest) -> GeneratedImage:
        """
        Generate image using Gemini 2.5 Flash Image via Vertex AI.
        
        Uses generate_content() with response_modalities=["IMAGE"] instead of deprecated 
        generate_images() method, following the Vertex AI unified SDK pattern.
        """
        settings = get_settings()
        # Use gemini-2.5-flash-image as the default model (configurable via settings)
        model = request.model or "gemini-2.5-flash-image"
        aspect_ratio = closest_aspect_ratio(request.width, request.height)

        # Build image config for generate_content
        image_config_kwargs: dict[str, Any] = {
            "aspect_ratio": aspect_ratio,
        }
        
        # GenerateContentConfig for image generation via gemini-2.5-flash-image
        config_kwargs: dict[str, Any] = {
            "response_modalities": ["IMAGE"],
            "image_config": types.ImageConfig(**image_config_kwargs),
        }

        contents: list[Any] = [request.prompt]
        if request.source_image_b64:
            image_bytes = decode_base64_payload(request.source_image_b64)
            contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))

        # Use dedicated image generation client
        client = _build_image_client()
        
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as e:
            logger.error(f"generate_content failed: {e}")
            raise RuntimeError(f"Vertex AI image generation failed: {str(e)[:100]}")

        # Extract image from response
        if not response.candidates:
            raise RuntimeError("Vertex AI returned no response candidates")

        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            raise RuntimeError("Vertex AI returned no content parts")

        # Find the image part in the response
        image_bytes = None
        for part in candidate.content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                # Extract image bytes from inline_data
                image_bytes = part.inline_data.data
                break

        if not image_bytes:
            raise RuntimeError("Vertex AI response contains no image data")

        mime_type = "image/png"
        return GeneratedImage(
            image_bytes=image_bytes,
            mime_type=mime_type,
            model=model,
        )

    async def generate_video(self, payload: dict) -> dict:
        settings = get_settings()
        model = payload.get("model") or settings.vertex_video_model
        prompt = payload.get("prompt") or ""
        aspect_ratio = payload.get("aspect_ratio") or "16:9"
        duration = clamp_veo_duration(int(payload.get("duration") or 8), model)

        source_image = None
        source_b64 = payload.get("source_image_b64")
        if source_b64:
            image_bytes = decode_base64_payload(source_b64)
            source_image = types.Image(image_bytes=image_bytes, mime_type="image/png")

        config_kwargs: dict[str, Any] = {
            "number_of_videos": 1,
            "aspect_ratio": aspect_ratio,
            "duration_seconds": duration,
            "person_generation": "allow_adult",
        }
        if settings.vertex_video_output_gcs_uri:
            config_kwargs["output_gcs_uri"] = settings.vertex_video_output_gcs_uri.rstrip("/") + "/"

        client = _build_client()
        operation = await client.aio.models.generate_videos(
            model=model,
            prompt=prompt,
            image=source_image,
            config=types.GenerateVideosConfig(**config_kwargs),
        )

        operation = await self._poll_video_operation(client, operation)
        if operation.error:
            raise RuntimeError(f"Vertex AI Veo failed: {operation.error}")

        result = operation.result or operation.response
        videos = getattr(result, "generated_videos", None) if result else None
        if not videos:
            raise RuntimeError("Vertex AI Veo returned no videos")

        video = videos[0].video
        if not video:
            raise RuntimeError("Vertex AI Veo response missing video payload")

        if video.video_bytes:
            mime_type = video.mime_type or "video/mp4"
            return {
                "status": "success",
                "video_url": encode_data_url(video.video_bytes, mime_type),
                "model": model,
                "provider": "vertex-ai",
            }

        if video.uri:
            return {
                "status": "success",
                "video_url": video.uri,
                "model": model,
                "provider": "vertex-ai",
            }

        raise RuntimeError("Vertex AI Veo response had neither video bytes nor URI")

    async def _poll_video_operation(self, client: genai.Client, operation: Any):
        settings = get_settings()
        attempts = max(1, settings.vertex_video_poll_attempts)
        delay = max(1, settings.vertex_video_poll_seconds)

        for _ in range(attempts):
            if operation.done:
                return operation
            await asyncio.sleep(delay)
            operation = await client.aio.operations.get(operation)

        raise TimeoutError(
            f"Vertex AI Veo timed out after {attempts * delay}s waiting for video generation"
        )
