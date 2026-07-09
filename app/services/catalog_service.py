from app.database.fake_store import store


async def get_templates() -> list[dict]:
    store.seed()
    return store.templates


async def get_discover_items() -> list[dict]:
    store.seed()
    return store.discover_items
