from app.database.fake_store import store


async def list_notifications() -> list[dict]:
    store.seed()
    return store.notifications
