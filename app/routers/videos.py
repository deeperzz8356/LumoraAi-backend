from fastapi import APIRouter, Header
from app.services.generation_service import generate_video

router = APIRouter()


@router.post("/generate")
async def videos_generate_route(prompt: str, x_user_id: str = Header(default="demo-user")):
    return await generate_video(x_user_id, {"prompt": prompt})
