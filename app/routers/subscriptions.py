from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services.subscription_plans import get_plan_catalog
from app.services.subscription_service import get_subscription_status, activate_subscription

router = APIRouter()


class SubscribeRequest(BaseModel):
    planCode: str


@router.get("")
async def subscription_route(x_user_id: str = Header(default="demo-user")):
    return await get_subscription_status(x_user_id)


@router.get("/plans")
async def subscription_plans_route():
    return get_plan_catalog()


@router.post("/activate")
async def activate_subscription_route(body: SubscribeRequest, x_user_id: str = Header(default="demo-user")):
    try:
        return await activate_subscription(x_user_id, body.planCode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
