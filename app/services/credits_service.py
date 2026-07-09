from app.database.fake_store import store


async def get_credits(user_id: str) -> dict:
    store.ensure_user(user_id)
    return {"status": "success", "balance": store.credits.get(user_id, 0)}


async def add_credits(user_id: str, amount: int) -> dict:
    store.ensure_user(user_id)
    store.credits[user_id] = store.credits.get(user_id, 0) + amount
    return {"status": "success", "balance": store.credits[user_id]}
