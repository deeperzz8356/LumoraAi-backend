from app.database.firestore_repositories.credit_repo import credit_repo


async def get_credits(user_id: str) -> dict:
    balance = credit_repo.get_credits(user_id)
    return {"status": "success", "balance": balance}


async def add_credits(user_id: str, amount: int, idempotency_key: str | None = None) -> dict:
    # Bug 4: apply each logical credits/add at most once per idempotency key,
    # persisted in Firestore so it survives restarts/cold starts. When no key is
    # supplied, behavior is preserved (non-idempotent add).
    balance = credit_repo.add_credits_idempotent(
        user_id, amount, idempotency_key=idempotency_key
    )
    return {"status": "success", "balance": balance}


# Server-priced action costs. The client names the ACTION; the server decides the
# cost so the amount can never be spoofed. On-device actions (e.g. background
# removal via a third-party API) use this to charge credits authoritatively.
ACTION_COSTS: dict[str, int] = {
    "background_removal": 1,
    "background_replace": 1,
    "image_generation": 1,
    "video_generation": 5,
    "promo_video": 5,
}


async def deduct_credits_for_action(user_id: str, action: str) -> dict:
    """Deduct the server-defined cost for a named action.

    Returns {"status":"success","balance":int,"cost":int} on success, or
    {"status":"error","message":...} when the action is unknown or the user has
    insufficient credits (HTTP layer maps insufficient to 402).
    """
    cost = ACTION_COSTS.get(action)
    if cost is None:
        return {"status": "error", "message": f"Unknown billable action '{action}'."}
    if not credit_repo.deduct_credits(user_id, amount=cost):
        return {"status": "insufficient", "message": "Insufficient credits.", "cost": cost}
    balance = credit_repo.get_credits(user_id)
    return {"status": "success", "balance": balance, "cost": cost}
