"""
Credit-reward endpoints.

All routes are keyed off the authenticated user's id (x-user-id header, matching
the existing credits router convention). Each returns the structured dict from
the service layer; "already claimed" / "capped" outcomes are returned as 200
with a descriptive status so the client can show a friendly message.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth_context import resolve_user_id
from app.services import rewards_service

router = APIRouter()


class ReferralRequest(BaseModel):
    referred_id: str


class SocialShareRequest(BaseModel):
    platform: str
    share_id: str | None = None


@router.post("/spin")
async def spin_route(user_id: str = Depends(resolve_user_id)):
    return rewards_service.spin_wheel(user_id)


@router.post("/daily-reset")
async def daily_reset_route(user_id: str = Depends(resolve_user_id)):
    return rewards_service.claim_daily_reset(user_id)


@router.post("/check-in")
async def check_in_route(user_id: str = Depends(resolve_user_id)):
    return rewards_service.claim_check_in(user_id)


@router.post("/sign-up-bonus")
async def sign_up_bonus_route(user_id: str = Depends(resolve_user_id)):
    return rewards_service.claim_sign_up_bonus(user_id)


@router.post("/email-login")
async def email_login_route(user_id: str = Depends(resolve_user_id)):
    return rewards_service.claim_email_login(user_id)


@router.post("/referral")
async def referral_route(
    body: ReferralRequest,
    user_id: str = Depends(resolve_user_id),
):
    return rewards_service.claim_referral(user_id, body.referred_id)


@router.post("/social-share")
async def social_share_route(
    body: SocialShareRequest,
    user_id: str = Depends(resolve_user_id),
):
    return rewards_service.claim_social_share(user_id, body.platform, body.share_id)
