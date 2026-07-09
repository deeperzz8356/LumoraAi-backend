from fastapi import APIRouter, Header
from app.services.profile_service import get_profile

router = APIRouter()


@router.get("")
async def profile_route(x_user_id: str = Header(default="demo-user")):
    return await get_profile(x_user_id)
