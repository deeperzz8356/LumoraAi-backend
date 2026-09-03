from app.database.fake_store import store
import re


USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")


async def get_profile(user_id: str) -> dict:
    store.ensure_user(user_id)
    return {"status": "success", "profile": store.profiles[user_id]}


async def update_profile(user_id: str, payload: dict) -> dict:
    store.ensure_user(user_id)
    profile = store.profiles[user_id]
    username = payload.get("username")
    if username is not None:
        clean_username = username.strip().removeprefix("@").lower()
        if not USERNAME_RE.match(clean_username):
            raise ValueError("Username must be 3-30 characters and contain only letters, numbers, dots, or underscores.")
        for owner_id, existing in store.profiles.items():
            existing_username = str(existing.get("username", "")).lower()
            if owner_id != user_id and existing_username == clean_username:
                raise KeyError("Username is already taken.")
        profile["username"] = clean_username

    for source_key, target_key in {
        "displayName": "displayName",
        "bio": "bio",
        "location": "location",
        "avatarUrl": "avatarUrl",
    }.items():
        if source_key in payload:
            profile[target_key] = str(payload.get(source_key) or "").strip()

    return {"status": "success", "profile": profile}
