from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from app.core.auth_context import resolve_user_id
from app.services.credits_service import get_credits, add_credits

router = APIRouter()


class AddCreditsRequest(BaseModel):
    amount: int = 5
    # Bug 4 (idempotency): client sends a stable key per logical credits/add
    # event (Task 3.4). Duplicate deliveries carrying the same key apply once.
    idempotency_key: str | None = None


@router.get("")
async def credits_route(user_id: str = Depends(resolve_user_id)):
    return await get_credits(user_id)


@router.post("")
async def add_credits_route(
    body: AddCreditsRequest | None = None,
    user_id: str = Depends(resolve_user_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    amount = (body.amount if body else 5)
    key = (body.idempotency_key if body and body.idempotency_key else idempotency_key)
    return await add_credits(user_id, amount, idempotency_key=key)


@router.post("/add")
async def add_credits_alias_route(
    body: AddCreditsRequest | None = None,
    user_id: str = Depends(resolve_user_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    amount = (body.amount if body else 5)
    key = (body.idempotency_key if body and body.idempotency_key else idempotency_key)
    return await add_credits(user_id, amount, idempotency_key=key)
