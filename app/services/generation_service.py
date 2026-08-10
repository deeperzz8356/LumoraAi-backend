import logging

from app.database.firestore_repositories.credit_repo import credit_repo
from app.database.firestore_repositories.analytics_repo import analytics_repo
from app.providers.media_utils import encode_data_url
from app.providers.vertex_ai_provider import VertexAIProvider
from app.providers.vertex_ai_video_provider import VertexAIVideoProvider
from app.schemas.images import ImageGenerateRequest

logger = logging.getLogger(__name__)

image_provider = VertexAIProvider()
video_provider = VertexAIVideoProvider()


async def generate_image(user_id: str, payload: dict, *, developer_mode: bool = False) -> dict:
    request_obj = ImageGenerateRequest(**payload)
    if request_obj.style:
        request_obj.prompt = f"{request_obj.prompt}, in {request_obj.style} style"

    if not developer_mode and not credit_repo.deduct_credits(user_id, amount=1):
        return {"status": "error", "message": "Insufficient credits to generate image"}

    try:
        generated = await image_provider.generate_image(request_obj)
    except Exception as exc:
        # Best-effort refund so a provider failure does not permanently burn the credit.
        try:
            credit_repo.add_credits(user_id, amount=1)
        except Exception:
            pass
        return {"status": "error", "message": f"Vertex AI image generation failed: {exc}"}

    image_url = encode_data_url(generated.image_bytes, generated.mime_type)

    analytics_repo.log_generation(
        user_id=user_id,
        feature=f"text_to_image_style_{request_obj.style}" if request_obj.style else "text_to_image",
        provider="vertex-ai",
        prompt=request_obj.prompt,
    )

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
        generated = await video_provider.generate_single_video(payload)
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

    analytics_repo.log_generation(
        user_id=user_id,
        feature="text_to_video",
        provider=generated.get("provider", "vertex-ai"),
        prompt=prompt,
    )

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
