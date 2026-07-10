from fastapi import APIRouter, Header
from app.schemas.generation import ImageGenerateRequest, VideoGenerateRequest, JobResponse
from app.services.generation_service import generate_image, generate_video

router = APIRouter()


@router.post("/image")
async def generate_image_route(body: ImageGenerateRequest, x_user_id: str = Header(default="demo-user")):
    result = await generate_image(x_user_id, body.model_dump())
    return result


@router.post("/video")
async def generate_video_route(body: VideoGenerateRequest, x_user_id: str = Header(default="demo-user")):
    result = await generate_video(x_user_id, body.model_dump())
    return result
