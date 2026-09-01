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
        "code": "starter",
        "name": "Starter",
        "price_usd": 4.99,
        "monthly_credits": 50,
        "signup_bonus_credits": 0,
        "video_credits": 2,
        "features": [
            "50 image credits per month",
            "2 video generations per month",
            "Priority queue",
        ],
        "is_popular": True,
    },
    {
        "code": "pro",
        "name": "Pro",
        "price_usd": 14.99,
        "monthly_credits": 250,
        "signup_bonus_credits": 0,
        "video_credits": 10,
        "features": [
            "250 image credits per month",
            "10 video generations per month",
            "Early access to new models",
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
