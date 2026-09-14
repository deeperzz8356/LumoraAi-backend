from app.database.fake_store import store


async def get_templates() -> list[dict]:
    try:
        from app.core.firebase import get_firestore_client
        import json
        document = get_firestore_client().collection("template_catalogs").document("v1").get()
        if document.exists:
            catalog = document.to_dict().get("catalog")
            if catalog:
                return json.loads(catalog).get("categories", [])
    except Exception:
        pass
    store.seed()
    return store.templates


async def get_discover_items() -> list[dict]:
    store.seed()
    return store.discover_items
