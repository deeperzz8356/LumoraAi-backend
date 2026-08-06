from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.services.credits_service import get_credits, add_credits

router = APIRouter()


class AddCreditsRequest(BaseModel):
    amount: int = 5


@router.get("")
async def credits_route(x_user_id: str = Header(default="demo-user")):
    return await get_credits(x_user_id)


@router.post("")
async def add_credits_route(body: AddCreditsRequest | None = None, x_user_id: str = Header(default="demo-user")):
    amount = (body.amount if body else 5)
    return await add_credits(x_user_id, amount)
