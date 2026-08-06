from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.services.generation_service import generate_video, generate_long_form_video

router = APIRouter()


class VideoGenerateRequest(BaseModel):
    """Single video generation request."""
    prompt: str
    duration: int = 8
    aspect_ratio: str = "16:9"
    model: str = None


class LongFormVideoRequest(BaseModel):
    """Long-form video generation request."""
    prompt: str
    duration_seconds: int = 180
    style: str = "cinematic"


@router.post("/generate")
async def videos_generate_route(
    body: VideoGenerateRequest,
    x_user_id: str = Header(default="demo-user")
):
    """Generate a single 8-second video."""
    return await generate_video(x_user_id, body.model_dump())


@router.post("/generate/long-form")
async def videos_generate_long_form_route(
    body: LongFormVideoRequest,
    x_user_id: str = Header(default="demo-user")
):
    """
    Generate a long-form video (3 minutes by default) by batch-generating
    and stitching multiple 8-second clips.
    
    Note: This will consume ~5 credits per 8-second scene.
    For a 3-minute (180s) video, expect ~23 scenes = ~115 credits.
    """
    return await generate_long_form_video(
        x_user_id,
        body.prompt,
        body.duration_seconds,
        body.style,
    )
