from fastapi import APIRouter, Header

from app.schemas.images import ImageGenerateRequest, ImageGenerateResponse
from app.services.image_service import generate_text_to_image

router = APIRouter()


@router.post("/generate", response_model=ImageGenerateResponse)
async def images_generate_route(body: ImageGenerateRequest, x_user_id: str = Header(default="demo-user")):
    result = await generate_text_to_image(x_user_id, body)
    return ImageGenerateResponse(
        jobId=result["id"],
        queuePosition=result["queuePosition"],
        progress=result["progress"],
        model=result["model"],
        imageUrl=result["imageUrl"],
        mimeType=result["mimeType"],
    )
