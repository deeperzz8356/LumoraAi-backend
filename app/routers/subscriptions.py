from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth_context import resolve_user_id
from app.services.subscription_plans import get_plan_catalog
from app.services.subscription_service import get_subscription_status, activate_subscription

router = APIRouter()


class SubscribeRequest(BaseModel):
    planCode: str


@router.get("")
async def subscription_route(user_id: str = Depends(resolve_user_id)):
    return await get_subscription_status(user_id)


@router.get("/plans")
async def subscription_plans_route():
    return get_plan_catalog()


@router.post("/activate")
async def activate_subscription_route(body: SubscribeRequest, user_id: str = Depends(resolve_user_id)):
    try:
        return await activate_subscription(user_id, body.planCode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
