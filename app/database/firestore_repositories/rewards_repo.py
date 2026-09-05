"""
Durable, transactional persistence for credit rewards.

Every claim is applied inside a single Firestore transaction that (a) checks the
appropriate guard (period key, one-time flag, streak state, or referral count),
(b) updates the user's credit balance, and (c) records the claim — atomically,
so concurrent duplicate deliveries cannot double-apply. All state lives in
Firestore (durable across Render cold starts; no in-memory-only state, no Redis).

Guard shapes under users/{uid}:
- reward_claims/{claim_key}  — generic one-time / per-period claim marker.
- rewards (map on the user doc) — streak state and referral counters.
"""

from __future__ import annotations

from datetime import datetime, timezone

from firebase_admin import firestore

from app.core.firebase import get_firestore_client
from app.core.rewards_config import (
    CHECK_IN_STREAK_LENGTH,
    REFERRAL_MAX_SUCCESSFUL,
    check_in_credits_for_day,
)

STARTER_CREDITS = 7


class RewardAlreadyClaimed(Exception):
    """A one-time / per-period reward was already claimed for this key."""


class ReferralCapReached(Exception):
    """The user has already reached the maximum rewarded referrals."""


class RewardsRepository:
    def __init__(self):
        self.db = get_firestore_client()
        self.collection = self.db.collection("users")

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _balance_of(snapshot) -> int:
        if not snapshot.exists:
            return STARTER_CREDITS
        return snapshot.to_dict().get("credits", STARTER_CREDITS)

    # -- generic one-time / per-period claim --------------------------------

    def claim_once(self, user_id: str, claim_key: str, amount: int) -> int:
        """Apply `amount` credits at most once per (user, claim_key).

        `claim_key` encodes the period/uniqueness, e.g.:
          - "daily_reset:2026-02-14"     (per calendar day)
          - "weekly_spin:2026-W07"       (per ISO week)
          - "sign_up"                    (one-time, ever)
          - "email_login"                (one-time, ever)
          - "social_share:<share_id>"    (per unique share event)

        Raises RewardAlreadyClaimed if the key was already used.
        Returns the new balance.
        """
        user_ref = self.collection.document(user_id)
        claim_ref = user_ref.collection("reward_claims").document(claim_key)

        @firestore.transactional
        def apply(transaction, uref, cref):
            # Reads before writes (Firestore requirement).
            claim_snap = cref.get(transaction=transaction)
            user_snap = uref.get(transaction=transaction)
            if claim_snap.exists:
                raise RewardAlreadyClaimed(claim_key)

            current = self._balance_of(user_snap)
            new_balance = current + amount
            if not user_snap.exists:
                transaction.set(uref, {"credits": new_balance}, merge=True)
            else:
                transaction.update(uref, {"credits": new_balance})
            transaction.set(
                cref,
                {
                    "amount": amount,
                    "applied_balance": new_balance,
                    "applied_at": firestore.SERVER_TIMESTAMP,
                },
            )
            return new_balance

        return apply(self.db.transaction(), user_ref, claim_ref)

    # -- weekly check-in streak --------------------------------------------

    def claim_check_in(self, user_id: str, today: str) -> dict:
        """Advance the weekly check-in streak and award the day's credits.

        `today` is a calendar-day string (YYYY-MM-DD) used to enforce one
        check-in per day and to detect a broken streak (a gap > 1 day resets to
        day 1). After day 7 the streak wraps back to day 1.

        Returns {"balance", "streak_day", "credits_awarded"}.
        Raises RewardAlreadyClaimed if already checked in today.
        """
        user_ref = self.collection.document(user_id)

        @firestore.transactional
        def apply(transaction, uref):
            user_snap = uref.get(transaction=transaction)
            data = user_snap.to_dict() if user_snap.exists else {}
            rewards = data.get("rewards", {}) if isinstance(data, dict) else {}
            last_day = rewards.get("check_in_last_day")
            last_streak = int(rewards.get("check_in_streak", 0) or 0)

            if last_day == today:
                raise RewardAlreadyClaimed(f"check_in:{today}")

            # Determine the next streak day. Consecutive day -> +1 (wrapping
            # after 7). Any gap (or first ever) -> restart at day 1.
            if last_day and _is_consecutive(last_day, today) and 1 <= last_streak < CHECK_IN_STREAK_LENGTH:
                next_day = last_streak + 1
            elif last_day and _is_consecutive(last_day, today) and last_streak >= CHECK_IN_STREAK_LENGTH:
                next_day = 1  # completed a full week; wrap around
            else:
                next_day = 1

            credits = check_in_credits_for_day(next_day)
            current = self._balance_of(user_snap)
            new_balance = current + credits

            updates = {
                "credits": new_balance,
                "rewards": {
                    **rewards,
                    "check_in_last_day": today,
                    "check_in_streak": next_day,
                },
            }
            if not user_snap.exists:
                transaction.set(uref, updates, merge=True)
            else:
                transaction.set(uref, updates, merge=True)
            return {
                "balance": new_balance,
                "streak_day": next_day,
                "credits_awarded": credits,
            }

        return apply(self.db.transaction(), user_ref)

    # -- referrals ----------------------------------------------------------

    def claim_referral(self, user_id: str, referred_id: str, amount: int) -> dict:
        """Reward a valid referred install, deduplicated by `referred_id` and
        capped at REFERRAL_MAX_SUCCESSFUL rewarded referrals.

        Returns {"balance", "referral_count", "credits_awarded"}.
        Raises RewardAlreadyClaimed if this referred user was already counted,
        or ReferralCapReached once the cap is hit.
        """
        user_ref = self.collection.document(user_id)
        ref_ref = user_ref.collection("referrals").document(referred_id)

        @firestore.transactional
        def apply(transaction, uref, rref):
            ref_snap = rref.get(transaction=transaction)
            user_snap = uref.get(transaction=transaction)
            if ref_snap.exists:
                raise RewardAlreadyClaimed(f"referral:{referred_id}")

            data = user_snap.to_dict() if user_snap.exists else {}
            rewards = data.get("rewards", {}) if isinstance(data, dict) else {}
            count = int(rewards.get("referral_count", 0) or 0)
            if count >= REFERRAL_MAX_SUCCESSFUL:
                raise ReferralCapReached()

            current = self._balance_of(user_snap)
            new_balance = current + amount
            new_count = count + 1
            updates = {
                "credits": new_balance,
                "rewards": {**rewards, "referral_count": new_count},
            }
            transaction.set(uref, updates, merge=True)
            transaction.set(
                rref,
                {
                    "referred_id": referred_id,
                    "amount": amount,
                    "applied_at": firestore.SERVER_TIMESTAMP,
                },
            )
            return {
                "balance": new_balance,
                "referral_count": new_count,
                "credits_awarded": amount,
            }

        return apply(self.db.transaction(), user_ref, ref_ref)


def _is_consecutive(prev_day: str, today: str) -> bool:
    """True if `today` is exactly one calendar day after `prev_day`.

    Both are YYYY-MM-DD strings (UTC calendar day). A same-day repeat is handled
    by the caller before this is consulted.
    """
    try:
        prev = datetime.strptime(prev_day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        cur = datetime.strptime(today, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return False
    return (cur - prev).days == 1


rewards_repo = RewardsRepository()
