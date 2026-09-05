from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from fastapi import HTTPException
from app.core.auth_context import resolve_user_id
from app.services.credits_service import get_credits, add_credits, deduct_credits_for_action

router = APIRouter()


class AddCreditsRequest(BaseModel):
    amount: int = 5
    # Bug 4 (idempotency): client sends a stable key per logical credits/add
    # event (Task 3.4). Duplicate deliveries carrying the same key apply once.
    idempotency_key: str | None = None


class DeductCreditsRequest(BaseModel):
    # The client names the billable ACTION; the server prices it. This charges
    # credits for on-device actions (e.g. background removal) that do not flow
    # through a generation endpoint.
    action: str


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


@router.post("/deduct")
async def deduct_credits_route(
    body: DeductCreditsRequest,
    user_id: str = Depends(resolve_user_id),
):
    """Charge the server-defined cost for a named billable action.

    402 when the balance is insufficient; 400 for an unknown action.
    """
    result = await deduct_credits_for_action(user_id, body.action)
    if result.get("status") == "insufficient":
        raise HTTPException(status_code=402, detail="Insufficient credits.")
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "Bad request"))
    return result
