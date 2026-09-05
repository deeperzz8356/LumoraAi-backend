from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from app.core.auth_context import resolve_user_id
from app.core.dev_mode import is_developer_mode_header
# Reuse the SAME request schema as POST /generation/video so the two video
# endpoints share one contract (previously this route used a smaller, diverging
# inline model with duration=8 vs 10 and no style/source_image/motion/camera).
from app.schemas.generation import VideoGenerateRequest
from app.services.generation_service import generate_video, generate_long_form_video

router = APIRouter()


class LongFormVideoRequest(BaseModel):
    """Long-form video generation request."""
    prompt: str
    duration_seconds: int = 180
    style: str = "cinematic"


@router.post("/generate")
async def videos_generate_route(
    body: VideoGenerateRequest,
    user_id: str = Depends(resolve_user_id),
    x_developer_mode: str | None = Header(default=None),
):
    """Generate a single video. Alias of POST /generation/video (same contract)."""
    return await generate_video(
        user_id,
        body.model_dump(),
        developer_mode=is_developer_mode_header(x_developer_mode),
    )


@router.post("/generate/long-form")
async def videos_generate_long_form_route(
    body: LongFormVideoRequest,
    user_id: str = Depends(resolve_user_id),
):
    """
    Generate a long-form video (3 minutes by default) by batch-generating
    and stitching multiple 8-second clips.
    
    Note: This will consume ~5 credits per 8-second scene.
    For a 3-minute (180s) video, expect ~23 scenes = ~115 credits.
    """
    return await generate_long_form_video(
        user_id,
        body.prompt,
        body.duration_seconds,
        body.style,
    )
