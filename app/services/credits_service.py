from app.database.firestore_repositories.credit_repo import credit_repo


async def get_credits(user_id: str) -> dict:
    balance = credit_repo.get_credits(user_id)
    return {"status": "success", "balance": balance}


async def add_credits(user_id: str, amount: int) -> dict:
    balance = credit_repo.add_credits(user_id, amount)
    return {"status": "success", "balance": balance}
