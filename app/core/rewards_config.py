"""
Single source of truth for the Lumora credit-reward rules.

Centralizing every amount, cap, and cadence here (instead of scattering magic
numbers across services) keeps the reward system auditable and makes rule
changes a one-file edit. The service and repository layers read from here.

Reward catalogue (as specified by product):

1. Daily tasks & engagement
   - Weekly free spin: 1 spin/week (resets weekly). Prize wheel yields one of
     {50, 25, 10, 2, 0}. 0 == "Better luck next time".
   - Daily app reset: 2 free credits per calendar day on opening the app.

2. Weekly check-in streak (resets to Day 1 after Day 7)
   - Day 1: 1, Day 2: 1, Day 3: 2, Day 4: 2, Day 5: 3, Day 6: 4, Day 7: 5.

3. Onboarding & social
   - Sign-up bonus: 2 credits, one-time on account creation.
   - Email login/verification: 1 credit (one-time).
   - Referral: 5 credits per valid referred install, capped at 5 referrals.
   - Social share: 3 credits per share (IG story, YT shorts, etc.).
"""

from __future__ import annotations

from enum import Enum


class RewardType(str, Enum):
    """Stable identifiers for each reward source (also used as event prefixes)."""

    WEEKLY_SPIN = "weekly_spin"
    DAILY_RESET = "daily_reset"
    CHECK_IN = "check_in"
    SIGN_UP = "sign_up"
    EMAIL_LOGIN = "email_login"
    REFERRAL = "referral"
    SOCIAL_SHARE = "social_share"


# --- 1. Daily tasks & engagement -------------------------------------------

# Weekly free spin: one spin per ISO week. Each prize is a possible outcome of
# the wheel; 0 credits is a valid ("better luck next time") result.
SPIN_PRIZES: tuple[int, ...] = (50, 25, 10, 2, 0)
# Optional weights so the wheel is not uniform (bigger prizes are rarer). The
# order matches SPIN_PRIZES. Weights need not sum to 1; they are normalized.
SPIN_PRIZE_WEIGHTS: tuple[float, ...] = (0.02, 0.08, 0.20, 0.40, 0.30)
SPINS_PER_WEEK = 1

# Daily app-open reset: flat credits once per calendar day.
DAILY_RESET_CREDITS = 2


# --- 2. Weekly check-in streak ---------------------------------------------

# Credits by streak day (1-indexed). After day 7 the streak wraps back to day 1.
CHECK_IN_STREAK_CREDITS: dict[int, int] = {
    1: 1,
    2: 1,
    3: 2,
    4: 2,
    5: 3,
    6: 4,
    7: 5,
}
CHECK_IN_STREAK_LENGTH = 7


def check_in_credits_for_day(day: int) -> int:
    """Credits for a given 1..7 streak day (raises for out-of-range)."""
    if day not in CHECK_IN_STREAK_CREDITS:
        raise ValueError(f"check-in day must be 1..{CHECK_IN_STREAK_LENGTH}, got {day}")
    return CHECK_IN_STREAK_CREDITS[day]


# --- 3. Onboarding & social ------------------------------------------------

SIGN_UP_BONUS_CREDITS = 2
EMAIL_LOGIN_CREDITS = 1

REFERRAL_CREDITS_PER_INSTALL = 5
REFERRAL_MAX_SUCCESSFUL = 5  # hard cap on rewarded referrals

SOCIAL_SHARE_CREDITS = 3
# Platforms accepted for a share reward. Kept permissive but validated so the
# client cannot invent arbitrary sources.
SOCIAL_SHARE_PLATFORMS: frozenset[str] = frozenset(
    {"instagram_story", "instagram_post", "youtube_shorts", "tiktok", "facebook", "x", "whatsapp"}
)
