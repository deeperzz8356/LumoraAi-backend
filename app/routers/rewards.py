"""
Credit-reward endpoints.

All routes are keyed off the authenticated user's id (x-user-id header, matching
the existing credits router convention). Each returns the structured dict from
the service layer; "already claimed" / "capped" outcomes are returned as 200
with a descriptive status so the client can show a friendly message.
"""

from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.services import rewards_service

router = APIRouter()


class ReferralRequest(BaseModel):
    referred_id: str


class SocialShareRequest(BaseModel):
    platform: str
    share_id: str | None = None


@router.post("/spin")
async def spin_route(x_user_id: str = Header(default="demo-user")):
    return rewards_service.spin_wheel(x_user_id)


@router.post("/daily-reset")
async def daily_reset_route(x_user_id: str = Header(default="demo-user")):
    return rewards_service.claim_daily_reset(x_user_id)


@router.post("/check-in")
async def check_in_route(x_user_id: str = Header(default="demo-user")):
    return rewards_service.claim_check_in(x_user_id)


@router.post("/sign-up-bonus")
async def sign_up_bonus_route(x_user_id: str = Header(default="demo-user")):
    return rewards_service.claim_sign_up_bonus(x_user_id)


@router.post("/email-login")
async def email_login_route(x_user_id: str = Header(default="demo-user")):
    return rewards_service.claim_email_login(x_user_id)


@router.post("/referral")
async def referral_route(
    body: ReferralRequest,
    x_user_id: str = Header(default="demo-user"),
):
    return rewards_service.claim_referral(x_user_id, body.referred_id)


@router.post("/social-share")
async def social_share_route(
    body: SocialShareRequest,
    x_user_id: str = Header(default="demo-user"),
):
    return rewards_service.claim_social_share(x_user_id, body.platform, body.share_id)
