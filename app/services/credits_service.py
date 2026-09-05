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
