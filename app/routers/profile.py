from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth_context import resolve_user_id
from app.services.profile_service import get_profile, update_profile

router = APIRouter()


class ProfileUpdateRequest(BaseModel):
    displayName: str | None = None
    username: str | None = None
    bio: str | None = None
    location: str | None = None
    avatarUrl: str | None = None


@router.get("")
async def profile_route(user_id: str = Depends(resolve_user_id)):
    return await get_profile(user_id)


@router.put("")
async def update_profile_route(body: ProfileUpdateRequest, user_id: str = Depends(resolve_user_id)):
    try:
        return await update_profile(user_id, body.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
