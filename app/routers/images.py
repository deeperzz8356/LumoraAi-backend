from fastapi import APIRouter, Header
import uuid

from app.schemas.images import ImageGenerateRequest, ImageGenerateResponse
from app.services.generation_service import generate_image

router = APIRouter()


@router.post("/generate", response_model=ImageGenerateResponse)
async def images_generate_route(body: ImageGenerateRequest, x_user_id: str = Header(default="demo-user")):
    """
    Generate an image using gemini-2.5-flash-image model.
    
    Costs 1 credit per image.
    Uses modern Vertex AI unified SDK pattern (generate_content with response_modalities).
    """
    result = await generate_image(x_user_id, body.model_dump())
    
    if result.get("status") == "error":
        # Return error response
        return ImageGenerateResponse(
            status="error",
            jobId=str(uuid.uuid4()),
            queuePosition=0,
            progress=0,
            model=body.model or "gemini-2.5-flash-image",
            imageUrl="",
            mimeType="image/png",
        )
    
    return ImageGenerateResponse(
        status="success",
        jobId=str(uuid.uuid4()),
        queuePosition=1,
        progress=100,
        model=result.get("model", "gemini-2.5-flash-image"),
        imageUrl=result.get("image_url", ""),
        mimeType=result.get("mime_type", "image/png"),
    )
