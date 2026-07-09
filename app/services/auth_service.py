from app.database.fake_store import store


async def login(email: str, password: str) -> dict:
    user_id = f"user_{abs(hash(email)) % 10000:04d}"
    store.ensure_user(user_id)
    return {"access_token": f"demo-token-{user_id}", "user_id": user_id}


async def guest_login(device_id: str | None = None) -> dict:
    suffix = abs(hash(device_id or "guest")) % 10000
    user_id = f"guest_{suffix:04d}"
    store.ensure_user(user_id)
    return {"access_token": f"guest-token-{user_id}", "user_id": user_id}
