from fastapi import APIRouter, Header
from app.database.fake_store import store

router = APIRouter()


@router.get("")
async def users_route(x_user_id: str = Header(default="demo-user")):
    store.ensure_user(x_user_id)
    return {"status": "success", "data": store.users[x_user_id]}
