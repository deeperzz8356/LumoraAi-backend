"""
Credit-reward business logic.

Each function validates the request, derives the correct idempotency/period key
from the rules in ``rewards_config``, and delegates the atomic apply to
``rewards_repo``. Every function returns a JSON-serializable dict with a
``status`` field so the router can pass it straight through.

All "already claimed" / "cap reached" outcomes return a structured, non-error
success-shaped response (``status="already_claimed"`` / ``"capped"``) rather than
raising to the client, so the app can show a friendly message without treating
it as a failure.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from app.core.rewards_config import (
    DAILY_RESET_CREDITS,
    EMAIL_LOGIN_CREDITS,
    REFERRAL_CREDITS_PER_INSTALL,
    REFERRAL_MAX_SUCCESSFUL,
    SIGN_UP_BONUS_CREDITS,
    SOCIAL_SHARE_CREDITS,
    SOCIAL_SHARE_PLATFORMS,
    SPIN_PRIZE_WEIGHTS,
    SPIN_PRIZES,
    RewardType,
)
from app.database.firestore_repositories.rewards_repo import (
    ReferralCapReached,
    RewardAlreadyClaimed,
    rewards_repo,
)


# --- period-key helpers -----------------------------------------------------

def _today_key(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d")


def _iso_week_key(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


# --- 1. Daily tasks & engagement -------------------------------------------

def spin_wheel(user_id: str, *, rng: random.Random | None = None) -> dict:
    """Perform the weekly free spin (one per ISO week).

    The prize is chosen from the weighted wheel; a 0-credit outcome ("better
    luck next time") still consumes the week's spin. The week key guarantees at
    most one spin per week even under duplicate requests.
    """
    rand = rng or random
    week_key = f"{RewardType.WEEKLY_SPIN.value}:{_iso_week_key()}"
    prize = rand.choices(SPIN_PRIZES, weights=SPIN_PRIZE_WEIGHTS, k=1)[0]
    try:
        # Even a 0-credit prize must consume the weekly spin, so we still record
        # the claim (amount 0 is a valid apply).
        balance = rewards_repo.claim_once(user_id, week_key, prize)
    except RewardAlreadyClaimed:
        return {
            "status": "already_claimed",
            "reward": RewardType.WEEKLY_SPIN.value,
            "message": "You have already used your free spin this week.",
        }
    return {
        "status": "success",
        "reward": RewardType.WEEKLY_SPIN.value,
        "prize": prize,
        "credits_awarded": prize,
        "balance": balance,
        "message": "Better luck next time!" if prize == 0 else f"You won {prize} credits!",
    }


def claim_daily_reset(user_id: str) -> dict:
    """Award the flat daily credits once per calendar day."""
    day_key = f"{RewardType.DAILY_RESET.value}:{_today_key()}"
    try:
        balance = rewards_repo.claim_once(user_id, day_key, DAILY_RESET_CREDITS)
    except RewardAlreadyClaimed:
        return {
            "status": "already_claimed",
            "reward": RewardType.DAILY_RESET.value,
            "message": "Daily credits already claimed today.",
        }
    return {
        "status": "success",
        "reward": RewardType.DAILY_RESET.value,
        "credits_awarded": DAILY_RESET_CREDITS,
        "balance": balance,
    }


# --- 2. Weekly check-in streak ---------------------------------------------

def claim_check_in(user_id: str) -> dict:
    """Advance the check-in streak and award the day's credits."""
    try:
        result = rewards_repo.claim_check_in(user_id, _today_key())
    except RewardAlreadyClaimed:
        return {
            "status": "already_claimed",
            "reward": RewardType.CHECK_IN.value,
            "message": "You have already checked in today.",
        }
    return {
        "status": "success",
        "reward": RewardType.CHECK_IN.value,
        "streak_day": result["streak_day"],
        "credits_awarded": result["credits_awarded"],
        "balance": result["balance"],
    }


# --- 3. Onboarding & social ------------------------------------------------

def claim_sign_up_bonus(user_id: str) -> dict:
    """One-time sign-up bonus."""
    try:
        balance = rewards_repo.claim_once(user_id, RewardType.SIGN_UP.value, SIGN_UP_BONUS_CREDITS)
    except RewardAlreadyClaimed:
        return {
            "status": "already_claimed",
            "reward": RewardType.SIGN_UP.value,
            "message": "Sign-up bonus already granted.",
        }
    return {
        "status": "success",
        "reward": RewardType.SIGN_UP.value,
        "credits_awarded": SIGN_UP_BONUS_CREDITS,
        "balance": balance,
    }


def claim_email_login(user_id: str) -> dict:
    """One-time email login/verification reward."""
    try:
        balance = rewards_repo.claim_once(user_id, RewardType.EMAIL_LOGIN.value, EMAIL_LOGIN_CREDITS)
    except RewardAlreadyClaimed:
        return {
            "status": "already_claimed",
            "reward": RewardType.EMAIL_LOGIN.value,
            "message": "Email login reward already granted.",
        }
    return {
        "status": "success",
        "reward": RewardType.EMAIL_LOGIN.value,
        "credits_awarded": EMAIL_LOGIN_CREDITS,
        "balance": balance,
    }


def claim_referral(user_id: str, referred_id: str) -> dict:
    """Reward a valid referred install (deduped, capped)."""
    referred_id = (referred_id or "").strip()
    if not referred_id:
        return {"status": "error", "message": "A referred user id is required."}
    if referred_id == user_id:
        return {"status": "error", "message": "You cannot refer yourself."}
    try:
        result = rewards_repo.claim_referral(user_id, referred_id, REFERRAL_CREDITS_PER_INSTALL)
    except RewardAlreadyClaimed:
        return {
            "status": "already_claimed",
            "reward": RewardType.REFERRAL.value,
            "message": "This referral was already counted.",
        }
    except ReferralCapReached:
        return {
            "status": "capped",
            "reward": RewardType.REFERRAL.value,
            "referral_count": REFERRAL_MAX_SUCCESSFUL,
            "message": f"Referral cap reached ({REFERRAL_MAX_SUCCESSFUL} referrals).",
        }
    return {
        "status": "success",
        "reward": RewardType.REFERRAL.value,
        "credits_awarded": result["credits_awarded"],
        "referral_count": result["referral_count"],
        "balance": result["balance"],
    }


def claim_social_share(user_id: str, platform: str, share_id: str) -> dict:
    """Reward a social share, deduplicated per unique share_id.

    `share_id` should be a stable, unique id for the share event supplied by the
    client (so repeated deliveries of the same share do not double-reward). If
    omitted, we fall back to a per-day-per-platform key to avoid unbounded farming.
    """
    platform = (platform or "").strip().lower()
    if platform not in SOCIAL_SHARE_PLATFORMS:
        return {
            "status": "error",
            "message": f"Unsupported share platform '{platform}'.",
        }
    share_id = (share_id or "").strip() or f"{platform}:{_today_key()}"
    claim_key = f"{RewardType.SOCIAL_SHARE.value}:{platform}:{share_id}"
    try:
        balance = rewards_repo.claim_once(user_id, claim_key, SOCIAL_SHARE_CREDITS)
    except RewardAlreadyClaimed:
        return {
            "status": "already_claimed",
            "reward": RewardType.SOCIAL_SHARE.value,
            "message": "This share was already rewarded.",
        }
    return {
        "status": "success",
        "reward": RewardType.SOCIAL_SHARE.value,
        "credits_awarded": SOCIAL_SHARE_CREDITS,
        "balance": balance,
    }
