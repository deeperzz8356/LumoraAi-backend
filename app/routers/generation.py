from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from app.core.auth_context import resolve_user_id
from app.core.dev_mode import is_developer_mode_header
from app.schemas.generation import VideoGenerateRequest, JobResponse
from app.schemas.images import ImageGenerateRequest
from app.services.generation_service import generate_image, generate_video

router = APIRouter()


def _honest_failure_status(result: dict) -> int | None:
    """Return an HTTP failure status (in {429, 503}) if the service marked the
    result as a retriable upstream rate-limit failure (Bug 1). Otherwise None so
    the response stays HTTP 200 (preservation of success and non-retriable errors).
    """
    hint = result.get("http_status") or result.get("status_code")
    if hint in (429, 503):
        return hint
    return None


@router.post("/image")
async def generate_image_route(
    body: ImageGenerateRequest,
    user_id: str = Depends(resolve_user_id),
    x_developer_mode: str | None = Header(default=None),
):
    result = await generate_image(
        user_id,
        body.model_dump(),
        developer_mode=is_developer_mode_header(x_developer_mode),
    )
    status = _honest_failure_status(result)
    if status is not None:
        return JSONResponse(status_code=status, content=result)
    return result


@router.post("/video")
async def generate_video_route(
    body: VideoGenerateRequest,
    user_id: str = Depends(resolve_user_id),
    x_developer_mode: str | None = Header(default=None),
):
    result = await generate_video(
        user_id,
        body.model_dump(),
        developer_mode=is_developer_mode_header(x_developer_mode),
    )
    status = _honest_failure_status(result)
    if status is not None:
        # Bug 1: an exhausted upstream 429 must be an honest HTTP failure
        # (429/503), never HTTP 200 with no output.
        return JSONResponse(status_code=status, content=result)
    return result


@router.get("/history")
async def get_generation_history(user_id: str = Depends(resolve_user_id)):
    from app.database.firestore_repositories.generations_repo import generations_repo
    history = generations_repo.get_user_generations(user_id=user_id)
    return {"status": "success", "data": history}
