from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.database.firestore_repositories.user_repo import user_repo
from app.services.subscription_plans import get_plan_by_code


class BillingService:
    def __init__(self) -> None:
        self.user_repo = user_repo

    def apply_signup_bonus(self, user_id: str) -> int:
        plan = get_plan_by_code("free")
        if not plan:
            return 0

        bonus = int(plan.get("signup_bonus_credits", 0))
        if bonus <= 0:
            return 0

        user_data = self.user_repo.get_user(user_id) or {}
        if user_data.get("signup_bonus_granted"):
            return 0

        self.user_repo.collection.document(user_id).set(
            {
                "signup_bonus_granted": True,
                "credits": (user_data.get("credits") or 0) + bonus,
            },
            merge=True,
        )
        return bonus

    def get_subscription_status(self, user_id: str) -> dict[str, Any]:
        user_data = self.user_repo.get_user(user_id) or {}
        plan_code = user_data.get("subscription_plan") or "free"
        plan = get_plan_by_code(plan_code) or get_plan_by_code("free")
        if not plan:
            plan = {"code": "free", "name": "Free", "price_usd": 0.0}

        active = bool(user_data.get("subscription_active"))
        if active:
            expires_at = user_data.get("subscription_expires_at")
            if expires_at:
                try:
                    active = datetime.fromisoformat(expires_at) > datetime.now(timezone.utc)
                except ValueError:
                    active = False

        return {
            "status": "success",
            "userId": user_id,
            "plan": plan_code,
            "planName": plan["name"],
            "active": active,
            "priceUsd": plan.get("price_usd", 0.0),
            "monthlyCredits": plan.get("monthly_credits", 0),
            "videoCredits": plan.get("video_credits", 0),
        }

    def activate_subscription(self, user_id: str, plan_code: str) -> dict[str, Any]:
        plan = get_plan_by_code(plan_code)
        if not plan:
            raise ValueError("Unknown plan")

        expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        self.user_repo.collection.document(user_id).set(
            {
                "subscription_plan": plan_code,
                "subscription_active": True,
                "subscription_expires_at": expires_at,
                "credits": (self.user_repo.get_user(user_id) or {}).get("credits", 0) + plan.get("monthly_credits", 0),
            },
            merge=True,
        )
        return self.get_subscription_status(user_id)


billing_service = BillingService()
