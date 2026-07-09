from fastapi import APIRouter
from app.services.notification_service import list_notifications

router = APIRouter()


@router.get("")
async def notifications_route():
    return {"status": "success", "items": await list_notifications()}
