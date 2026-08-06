from app.services.billing_service import billing_service


async def get_subscription_status(user_id: str) -> dict:
    return billing_service.get_subscription_status(user_id)


async def activate_subscription(user_id: str, plan_code: str) -> dict:
    return billing_service.activate_subscription(user_id, plan_code)
