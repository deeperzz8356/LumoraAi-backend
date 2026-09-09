from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    types = None

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
    if not GENAI_AVAILABLE:
        raise RuntimeError("google-generativeai package not available")
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
    if not GENAI_AVAILABLE:
        raise RuntimeError("google-generativeai package not available")
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


def _extract_vertex_image_bytes(response: Any) -> tuple[bytes, str] | None:
    """Return the first image payload from common Gen AI response shapes."""
    def normalize_bytes(value: Any) -> bytes | None:
        if isinstance(value, bytes):
            return value
        if isinstance(value, str) and value.strip():
            return decode_base64_payload(value)
        return None

    candidates = list(getattr(response, "candidates", None) or [])
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = list(getattr(content, "parts", None) or [])
        for part in parts:
            for attr_name in ("inline_data", "inlineData", "blob"):
                payload = getattr(part, attr_name, None)
                data = getattr(payload, "data", None)
                image_bytes = normalize_bytes(data)
                if image_bytes:
                    mime_type = getattr(payload, "mime_type", None) or getattr(payload, "mimeType", None) or "image/png"
                    return image_bytes, mime_type
            text = getattr(part, "text", None)
            if isinstance(text, str) and text.startswith("data:image/"):
                return decode_base64_payload(text), text.split(";", 1)[0].removeprefix("data:")

    for attr_name in ("generated_images", "images"):
        images = list(getattr(response, attr_name, None) or [])
        for image in images:
            data = getattr(image, "image_bytes", None) or getattr(image, "bytes_base64_encoded", None)
            image_bytes = normalize_bytes(data)
            if image_bytes:
                return image_bytes, getattr(image, "mime_type", None) or "image/png"

    return None


def _describe_empty_vertex_image_response(response: Any) -> str:
    candidates = list(getattr(response, "candidates", None) or [])
    if not candidates:
        return "Image generation returned no candidates. Please try again."

    candidate = candidates[0]
    finish_reason = getattr(candidate, "finish_reason", None) or getattr(candidate, "finishReason", None)
    safety = getattr(candidate, "safety_ratings", None) or getattr(candidate, "safetyRatings", None)
    if finish_reason:
        reason = str(finish_reason).split(".")[-1].lower().replace("_", " ")
        if "safety" in reason or "block" in reason:
            return "Image generation was blocked by the provider safety filters. Please adjust the prompt and try again."
        return f"Image generation finished without an image ({reason}). Please adjust the prompt and try again."
    if safety:
        return "Image generation returned no image, possibly due to provider safety filters. Please adjust the prompt and try again."
    return "Image generation returned no image. Please adjust the prompt or try again."


class VertexAIProvider:
    """Image (Imagen) and video (Veo) generation via Vertex AI / Google Gen AI SDK."""

    async def generate_image(self, request: ImageGenerateRequest) -> GeneratedImage:
        """
        Generate image using Gemini 2.5 Flash Image via Vertex AI.
        
        Uses generate_content() with response_modalities=["IMAGE"] instead of deprecated 
        generate_images() method, following the Vertex AI unified SDK pattern.
        """
        if not GENAI_AVAILABLE:
            raise RuntimeError("Vertex AI provider requires google-generativeai package")
        
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
        # Collect every reference image: the multi-image list takes precedence,
        # falling back to the single legacy field. Up to 3 references are passed
        # to Gemini together so the output is conditioned on all of them.
        reference_images = list(request.source_images_b64 or [])
        if not reference_images and request.source_image_b64:
            reference_images = [request.source_image_b64]
        for encoded in reference_images[:3]:
            if not encoded:
                continue
            image_bytes = decode_base64_payload(encoded)
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

        extracted = _extract_vertex_image_bytes(response)
        if extracted is None:
            logger.warning("Vertex image response had no usable image payload: %r", response)
            raise RuntimeError(_describe_empty_vertex_image_response(response))

        image_bytes, mime_type = extracted
        return GeneratedImage(
            image_bytes=image_bytes,
            mime_type=mime_type,
            model=model,
        )

    async def generate_video(self, payload: dict) -> dict:
        if not GENAI_AVAILABLE:
            raise RuntimeError("Vertex AI provider requires google-generativeai package")
            
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

    async def _poll_video_operation(self, client: Any, operation: Any):
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
