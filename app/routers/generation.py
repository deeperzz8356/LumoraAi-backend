from fastapi import APIRouter, Header
from app.core.dev_mode import is_developer_mode_header
from app.schemas.generation import VideoGenerateRequest, JobResponse
from app.schemas.images import ImageGenerateRequest
from app.services.generation_service import generate_image, generate_video

router = APIRouter()


@router.post("/image")
async def generate_image_route(
    body: ImageGenerateRequest,
    x_user_id: str = Header(default="demo-user"),
    x_developer_mode: str | None = Header(default=None),
):
    result = await generate_image(
        x_user_id,
        body.model_dump(),
        developer_mode=is_developer_mode_header(x_developer_mode),
    )
    return result


@router.post("/video")
async def generate_video_route(
    body: VideoGenerateRequest,
    x_user_id: str = Header(default="demo-user"),
    x_developer_mode: str | None = Header(default=None),
):
    result = await generate_video(
        x_user_id,
        body.model_dump(),
        developer_mode=is_developer_mode_header(x_developer_mode),
    )
    return result


@router.get("/history")
async def get_generation_history(x_user_id: str = Header(default="demo-user")):
    from app.database.firestore_repositories.generations_repo import generations_repo
    history = generations_repo.get_user_generations(user_id=x_user_id)
    return {"status": "success", "data": history}
