from app.database.fake_store import store


async def get_profile(user_id: str) -> dict:
    store.ensure_user(user_id)
    return {"status": "success", "profile": store.profiles[user_id]}
