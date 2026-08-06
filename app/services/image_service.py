from __future__ import annotations

import logging
from app.database.firestore_repositories.credit_repo import credit_repo
from app.database.firestore_repositories.analytics_repo import analytics_repo
from app.providers.media_utils import encode_data_url
from app.providers.vertex_ai_provider import VertexAIProvider
from app.schemas.images import ImageGenerateRequest

logger = logging.getLogger(__name__)

# Global provider instance
image_provider = VertexAIProvider()


async def generate_text_to_image(user_id: str, payload: ImageGenerateRequest) -> dict:
    """
    Generate image using gemini-2.5-flash-image via Vertex AI.
    
    Uses modern unified SDK pattern (generate_content with response_modalities).
    Integrates with credit system and analytics.
    
    Cost: 1 credit per image
    """
    request_obj = ImageGenerateRequest(**payload) if isinstance(payload, dict) else payload
    
    # Enhance prompt with style if provided
    if request_obj.style:
        request_obj.prompt = f"{request_obj.prompt}, in {request_obj.style} style"

    # Deduct 1 credit for image generation
    if not credit_repo.deduct_credits(user_id, amount=1):
        logger.warning(f"User {user_id} insufficient credits for image generation")
        return {"status": "error", "message": "Insufficient credits to generate image"}

    try:
        logger.info(f"🎨 Generating image for user {user_id}: {request_obj.prompt[:50]}...")
        generated = await image_provider.generate_image(request_obj)
        logger.info(f"✅ Image generated successfully: {generated.model}")
    except Exception as exc:
        logger.error(f"❌ Image generation failed: {exc}")
        # Refund credit on failure
        try:
            credit_repo.add_credits(user_id, amount=1)
            logger.info(f"💰 Refunded 1 credit to user {user_id}")
        except Exception as refund_error:
            logger.error(f"Failed to refund credit: {refund_error}")
        return {"status": "error", "message": f"Image generation failed: {str(exc)[:100]}"}

    # Encode image as data URL
    image_url = encode_data_url(generated.image_bytes, generated.mime_type)

    # Log analytics
    try:
        analytics_repo.log_generation(
            user_id=user_id,
            feature=f"text_to_image_style_{request_obj.style}" if request_obj.style else "text_to_image",
            provider="vertex-ai",
            prompt=request_obj.prompt,
        )
    except Exception as analytics_error:
        logger.warning(f"Failed to log analytics: {analytics_error}")

    logger.info(f"✅ Image generation complete for user {user_id}")
    return {
        "status": "success",
        "image_url": image_url,
        "model": generated.model,
        "provider": "vertex-ai",
    }
