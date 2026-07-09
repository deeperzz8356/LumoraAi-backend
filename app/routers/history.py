from fastapi import APIRouter, Header
from app.database.fake_store import store

router = APIRouter()


@router.get("")
async def history_route(x_user_id: str = Header(default="demo-user")):
    store.ensure_user(x_user_id)
    return {"status": "success", "items": [item for item in store.history if item.get("userId") == x_user_id]}
