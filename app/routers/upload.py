from fastapi import APIRouter, Header
from app.services.upload_service import create_upload_ticket

router = APIRouter()


@router.post("")
async def upload_route(filename: str | None = None, x_user_id: str = Header(default="demo-user")):
    return await create_upload_ticket(x_user_id, filename)
