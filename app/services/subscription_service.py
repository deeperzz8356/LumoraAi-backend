async def get_subscription_status(user_id: str) -> dict:
    return {"status": "success", "userId": user_id, "plan": "free", "active": False}
