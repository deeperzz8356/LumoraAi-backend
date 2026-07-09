from fastapi import APIRouter, Header
from app.services.credits_service import get_credits, add_credits

router = APIRouter()


@router.get("")
async def credits_route(x_user_id: str = Header(default="demo-user")):
    return await get_credits(x_user_id)


@router.post("")
async def add_credits_route(amount: int = 5, x_user_id: str = Header(default="demo-user")):
    return await add_credits(x_user_id, amount)
