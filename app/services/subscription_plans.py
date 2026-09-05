from typing import Any


PLAN_CATALOG: list[dict[str, Any]] = [
    {
        "code": "free",
        "name": "Free",
        "price_usd": 0.0,
        "monthly_credits": 0,
        "signup_bonus_credits": 7,
        "video_credits": 0,
        "features": [
            "7 free trial credits on signup",
            "Basic templates",
            "Community support",
        ],
        "is_popular": False,
    },
    {
        # Matches Play/RevenueCat product id "pro_monthly".
        "code": "pro_monthly",
        "name": "Pro Monthly",
        "price_usd": 19.99,
        "monthly_credits": 500,
        "signup_bonus_credits": 0,
        "video_credits": 20,
        "features": [
            "500 credits per month",
            "HD image generation",
            "Standard queue priority",
        ],
        "is_popular": False,
    },
    {
        # Matches Play/RevenueCat product id "pro_annual".
        "code": "pro_annual",
        "name": "Pro Annual",
        "price_usd": 149.99,
        "monthly_credits": 500,
        "signup_bonus_credits": 0,
        "video_credits": 20,
        "features": [
            "500 credits per month (billed yearly)",
            "HD image & video",
            "Priority queue",
        ],
        "is_popular": True,
    },
    {
        # Matches Play/RevenueCat product id "elite_pro".
        "code": "elite_pro",
        "name": "Elite Pro",
        "price_usd": 499.99,
        "monthly_credits": 5000,
        "signup_bonus_credits": 0,
        "video_credits": 200,
        "features": [
            "5000 credits per month",
            "8K rendering",
            "Instant queue",
            "Concierge support",
        ],
        "is_popular": False,
    },
]


def get_plan_catalog() -> dict[str, Any]:
    return {
        "status": "success",
        "currency": "USD",
        "plans": PLAN_CATALOG,
    }


def get_plan_by_code(code: str) -> dict[str, Any] | None:
    return next((plan for plan in PLAN_CATALOG if plan["code"] == code), None)
