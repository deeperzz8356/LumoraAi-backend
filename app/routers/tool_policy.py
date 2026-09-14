from fastapi import APIRouter
from app.services.tool_policy import snapshot

router = APIRouter()


@router.get("")
async def tool_policy_route():
    return snapshot()
