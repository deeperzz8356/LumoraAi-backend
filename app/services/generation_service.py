import logging
import os

from app.core.config import get_settings
from app.database.firestore_repositories.credit_repo import credit_repo
from app.database.firestore_repositories.analytics_repo import analytics_repo
from app.database.firestore_repositories.generations_repo import generations_repo
from app.providers.media_utils import encode_data_url
from app.providers.vertex_ai_provider import VertexAIProvider
from app.providers.vertex_ai_video_provider import VertexAIVideoProvider
from app.schemas.images import ImageGenerateRequest
from app.utils.upstream_rate_limit import (
    UpstreamRateLimitError,
    call_with_retry,
)

logger = logging.getLogger(__name__)

image_provider = VertexAIProvider()
video_provider = VertexAIVideoProvider()


def _has_confirmed_output(result: dict) -> bool:
    """confirmedOutput(X): a generation is counted only when it produced real,
    extractable output — a non-error status AND an actual media URL.

    Bug 4 (Requirements 2.13, 2.16): the generation counter must increment only
    for confirmed outputs, not on a bare 200 OK. A swallowed/rate-limited 429 or
    any error result (now surfaced honestly by Task 3.3) is NOT a confirmed
    output and must not be counted.
    """
    if not isinstance(result, dict):
        return False
    if result.get("status") == "error":
        return False
    return bool(result.get("video_url") or result.get("image_url"))


async def _call_upstream_with_retry(func):
    """Run an upstream Vertex call with bounded 429 retry/backoff + concurrency.

    Bug 1 (isBugCondition1): honors Vertex's retryDelay with bounded exponential
    backoff + jitter, caps concurrency via an in-process semaphore, and raises
    UpstreamRateLimitError (http_status in {429, 503}) when retries are
    exhausted so the router can surface an honest failure.
    """
    settings = get_settings()
    # Never sleep for real seconds inside the test suite: keep contract tests fast
    # and deterministic. Backoff delays are still computed, just not slept.
    sleep_enabled = settings.upstream_retry_sleep_enabled and not os.environ.get(
        "PYTEST_CURRENT_TEST"
    )
    return await call_with_retry(
        func,
        max_retries=settings.upstream_max_retries,
        base_seconds=settings.upstream_backoff_base_seconds,
        max_seconds=settings.upstream_backoff_max_seconds,
        concurrency_limit=settings.upstream_concurrency_limit,
        sleep_enabled=sleep_enabled,
    )


async def generate_image(user_id: str, payload: dict, *, developer_mode: bool = False) -> dict:
    request_obj = ImageGenerateRequest(**payload)
    if request_obj.style:
        request_obj.prompt = f"{request_obj.prompt}, in {request_obj.style} style"

    if not developer_mode and not credit_repo.deduct_credits(user_id, amount=1):
        return {"status": "error", "message": "Insufficient credits to generate image"}

    try:
        generated = await _call_upstream_with_retry(
            lambda: image_provider.generate_image(request_obj)
        )
    except UpstreamRateLimitError as exc:
        # Bug 1: upstream 429 persisted after bounded retries. Refund and surface
        # an HONEST failure (http_status in {429, 503}) — never a 200-with-no-output.
        try:
            credit_repo.add_credits(user_id, amount=1)
        except Exception:
            pass
        return {
            "status": "error",
            "message": f"Image generation rate limited upstream: {exc}",
            "http_status": exc.http_status,
        }
    except Exception as exc:
        # Best-effort refund so a provider failure does not permanently burn the credit.
        try:
            credit_repo.add_credits(user_id, amount=1)
        except Exception:
            pass
        return {"status": "error", "message": f"Vertex AI image generation failed: {exc}"}

    image_url = encode_data_url(generated.image_bytes, generated.mime_type)

    # Bug 4 (isBugCondition4, generation half): count the generation ONLY when a
    # confirmed output exists (image_url present), never on a bare 200 OK. A
    # swallowed/rate-limited failure now returns early above (honest {429,503})
    # and never reaches this line, so the counter reflects confirmed outputs only.
    if _has_confirmed_output({"status": "success", "image_url": image_url}):
        analytics_repo.log_generation(
            user_id=user_id,
            feature=f"text_to_image_style_{request_obj.style}" if request_obj.style else "text_to_image",
            provider="vertex-ai",
            prompt=request_obj.prompt,
        )
        # Persist to the `generations` collection so GET /generation/history
        # (which reads that collection) reflects real generations, and so
        # find_cached_image can reuse prior outputs. Best-effort: a failure here
        # must not fail the generation the user already paid for.
        try:
            generations_repo.save_generation(
                user_id=user_id,
                prompt=request_obj.prompt,
                style=request_obj.style or "",
                image_url=image_url,
                provider="vertex-ai",
                model=generated.model,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to persist image generation history: %s", exc)

    return {
        "status": "success",
        "image_url": image_url,
        "model": generated.model,
        "provider": "vertex-ai",
    }


async def generate_video(user_id: str, payload: dict, *, developer_mode: bool = False) -> dict:
    """Generate a single 8-second video."""
    # Single video generation is cheaper (5 credits)
    if not developer_mode and not credit_repo.deduct_credits(user_id, amount=5):
        return {"status": "error", "message": "Insufficient credits to generate video"}

    prompt = payload.get("prompt", "")

    try:
        generated = await _call_upstream_with_retry(
            lambda: video_provider.generate_single_video(payload)
        )
    except UpstreamRateLimitError as exc:
        # Bug 1: upstream 429 persisted after bounded retries. Refund and surface
        # an HONEST failure (http_status in {429, 503}) — never a 200-with-no-output.
        try:
            credit_repo.add_credits(user_id, amount=5)
        except Exception:
            pass
        return {
            "status": "error",
            "message": f"Video generation rate limited upstream: {exc}",
            "http_status": exc.http_status,
        }
    except Exception as exc:
        try:
            credit_repo.add_credits(user_id, amount=5)
        except Exception:
            pass
        return {"status": "error", "message": f"Video generation failed: {exc}"}

    if generated.get("status") == "error":
        try:
            credit_repo.add_credits(user_id, amount=5)
        except Exception:
            pass
        return {
            "status": "error",
            "message": generated.get("message", "Video generation failed"),
        }

    # Bug 4 (isBugCondition4, generation half): count the generation ONLY when a
    # confirmed output exists (video_url present), never on a bare 200 OK. Honest
    # upstream failures ({429,503}) and error results return early above and never
    # reach this line, so the counter reflects confirmed outputs only.
    if _has_confirmed_output(generated):
        analytics_repo.log_generation(
            user_id=user_id,
            feature="text_to_video",
            provider=generated.get("provider", "vertex-ai"),
            prompt=prompt,
        )
        # Persist so GET /generation/history reflects real videos. The history
        # doc reuses image_url as the media URL column (the client reads that
        # field for both media types). Best-effort.
        try:
            generations_repo.save_generation(
                user_id=user_id,
                prompt=prompt,
                style=payload.get("style") or "",
                image_url=generated["video_url"],
                provider=generated.get("provider", "vertex-ai"),
                model=generated.get("model") or "",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to persist video generation history: %s", exc)

    return {
        "status": "success",
        "video_url": generated["video_url"],
        "local_path": generated.get("local_path"),
        "model": generated.get("model"),
        "duration": generated.get("duration"),
        "provider": generated.get("provider", "vertex-ai"),
    }


async def generate_long_form_video(
    user_id: str,
    base_prompt: str,
    duration_seconds: int = 180,
    style: str = "cinematic",
) -> dict:
    """
    Generate a long-form video (3 minutes) by batch-generating and stitching clips.
    
    Cost: ~5 credits per 8-second clip (23 clips for 3 minutes = ~115 credits)
    """
    from app.core.config import get_settings
    
    settings = get_settings()
    num_scenes = (duration_seconds // 8) + 1
    
    # Estimate credits needed (5 per scene + overhead)
    credits_needed = num_scenes * 5 + 10
    
    if not credit_repo.deduct_credits(user_id, amount=credits_needed):
        return {
            "status": "error",
            "message": f"Insufficient credits (need {credits_needed}, for {num_scenes} scenes)"
        }

    try:
        generated = await video_provider.generate_long_form_video(
            base_prompt=base_prompt,
            duration_seconds=duration_seconds,
            style=style,
        )
    except Exception as exc:
        try:
            credit_repo.add_credits(user_id, amount=credits_needed)
        except Exception:
            pass
        logger.error(f"Long-form video generation failed: {exc}")
        return {"status": "error", "message": f"Long-form video generation failed: {exc}"}

    if generated.get("status") == "error":
        try:
            credit_repo.add_credits(user_id, amount=credits_needed)
        except Exception:
            pass
        return {
            "status": "error",
            "message": generated.get("message", "Video generation failed"),
        }

    analytics_repo.log_generation(
        user_id=user_id,
        feature="text_to_video_long_form",
        provider=generated.get("provider", "vertex-ai"),
        prompt=base_prompt,
    )

    return {
        "status": "success",
        "video_url": generated["video_url"],
        "local_path": generated.get("local_path"),
        "model": generated.get("model"),
        "duration": generated.get("duration"),
        "total_scenes": generated.get("total_scenes"),
        "failed_scenes": generated.get("failed_scenes", 0),
        "provider": generated.get("provider", "vertex-ai"),
    }
