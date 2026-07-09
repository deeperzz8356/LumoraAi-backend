from fastapi import APIRouter, Header
from app.services.subscription_service import get_subscription_status

router = APIRouter()


@router.get("")
async def subscription_route(x_user_id: str = Header(default="demo-user")):
    return await get_subscription_status(x_user_id)
