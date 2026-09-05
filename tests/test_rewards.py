"""
Contract tests for the credit-reward system (app/services/rewards_service.py
and app/routers/rewards.py).

The reward repository is Firestore-backed; here we mock it with an in-test fake
that models the DURABLE guards (per-key one-time markers, streak state, referral
counter) so the reward RULES and idempotency CONTRACT are verified without a live
DB — the same approach the idempotency tests use for credits.

Run with:
    pytest tests/test_rewards.py -v
"""

import random

from fastapi.testclient import TestClient

from app.core import rewards_config as cfg
from app.database.firestore_repositories.rewards_repo import (
    ReferralCapReached,
    RewardAlreadyClaimed,
)
from app.main import app
from app.services import rewards_service


STARTER = 7


class _FakeRewardsRepo:
    """In-test stand-in for the Firestore-backed RewardsRepository.

    Models the durable state: balances, one-time/per-period claim keys, weekly
    check-in streak state, and per-referral dedupe + counter.
    """

    def __init__(self):
        self.balances: dict[str, int] = {}
        self.claims: set[tuple[str, str]] = set()
        self.check_in_last_day: dict[str, str] = {}
        self.check_in_streak: dict[str, int] = {}
        self.referrals: dict[str, set[str]] = {}

    def _balance(self, user_id: str) -> int:
        return self.balances.get(user_id, STARTER)

    def claim_once(self, user_id: str, claim_key: str, amount: int) -> int:
        marker = (user_id, claim_key)
        if marker in self.claims:
            raise RewardAlreadyClaimed(claim_key)
        self.claims.add(marker)
        new_balance = self._balance(user_id) + amount
        self.balances[user_id] = new_balance
        return new_balance

    def claim_check_in(self, user_id: str, today: str) -> dict:
        if self.check_in_last_day.get(user_id) == today:
            raise RewardAlreadyClaimed(f"check_in:{today}")
        # For the test we always advance from the stored streak (consecutive
        # days are simulated by the caller controlling `today`).
        last = self.check_in_streak.get(user_id, 0)
        nxt = 1 if last >= cfg.CHECK_IN_STREAK_LENGTH or last == 0 else last + 1
        credits = cfg.check_in_credits_for_day(nxt)
        self.check_in_streak[user_id] = nxt
        self.check_in_last_day[user_id] = today
        new_balance = self._balance(user_id) + credits
        self.balances[user_id] = new_balance
        return {"balance": new_balance, "streak_day": nxt, "credits_awarded": credits}

    def claim_referral(self, user_id: str, referred_id: str, amount: int) -> dict:
        refs = self.referrals.setdefault(user_id, set())
        if referred_id in refs:
            raise RewardAlreadyClaimed(f"referral:{referred_id}")
        if len(refs) >= cfg.REFERRAL_MAX_SUCCESSFUL:
            raise ReferralCapReached()
        refs.add(referred_id)
        new_balance = self._balance(user_id) + amount
        self.balances[user_id] = new_balance
        return {"balance": new_balance, "referral_count": len(refs), "credits_awarded": amount}


def _patch(monkeypatch, fake):
    monkeypatch.setattr(rewards_service, "rewards_repo", fake)


# --- Weekly spin -----------------------------------------------------------

def test_spin_awards_a_valid_prize_once_per_week(monkeypatch):
    fake = _FakeRewardsRepo()
    _patch(monkeypatch, fake)
    # Force a deterministic prize.
    rng = random.Random(1)
    first = rewards_service.spin_wheel("u1", rng=rng)
    assert first["status"] == "success"
    assert first["prize"] in cfg.SPIN_PRIZES
    assert first["balance"] == STARTER + first["prize"]

    # Second spin in the same week is blocked.
    second = rewards_service.spin_wheel("u1", rng=rng)
    assert second["status"] == "already_claimed"


def test_spin_zero_prize_still_consumes_the_week(monkeypatch):
    fake = _FakeRewardsRepo()
    _patch(monkeypatch, fake)

    class _ZeroRng:
        def choices(self, seq, weights=None, k=1):
            return [0]

    result = rewards_service.spin_wheel("u-zero", rng=_ZeroRng())
    assert result["status"] == "success"
    assert result["prize"] == 0
    assert result["credits_awarded"] == 0
    assert "Better luck" in result["message"]
    # The spin was consumed: a second spin this week is blocked.
    assert rewards_service.spin_wheel("u-zero", rng=_ZeroRng())["status"] == "already_claimed"


# --- Daily reset -----------------------------------------------------------

def test_daily_reset_awards_two_once_per_day(monkeypatch):
    fake = _FakeRewardsRepo()
    _patch(monkeypatch, fake)
    first = rewards_service.claim_daily_reset("u2")
    assert first["status"] == "success"
    assert first["credits_awarded"] == cfg.DAILY_RESET_CREDITS == 2
    assert first["balance"] == STARTER + 2
    assert rewards_service.claim_daily_reset("u2")["status"] == "already_claimed"


# --- Check-in streak -------------------------------------------------------

def test_check_in_streak_progression(monkeypatch):
    fake = _FakeRewardsRepo()
    _patch(monkeypatch, fake)
    # Simulate 7 consecutive days by advancing the fake's stored day each call.
    expected = [1, 1, 2, 2, 3, 4, 5]
    total = 0
    for day_index, expected_credits in enumerate(expected, start=1):
        fake.check_in_last_day.pop("u3", None)  # allow a new "day"
        result = rewards_service.claim_check_in("u3")
        assert result["status"] == "success"
        assert result["streak_day"] == day_index
        assert result["credits_awarded"] == expected_credits
        total += expected_credits
    assert total == sum(cfg.CHECK_IN_STREAK_CREDITS.values()) == 18
    # Day 8 wraps back to day 1.
    fake.check_in_last_day.pop("u3", None)
    wrap = rewards_service.claim_check_in("u3")
    assert wrap["streak_day"] == 1
    assert wrap["credits_awarded"] == 1


def test_check_in_blocks_same_day(monkeypatch):
    fake = _FakeRewardsRepo()
    _patch(monkeypatch, fake)
    assert rewards_service.claim_check_in("u4")["status"] == "success"
    assert rewards_service.claim_check_in("u4")["status"] == "already_claimed"


# --- Sign-up & email login (one-time) --------------------------------------

def test_sign_up_bonus_once(monkeypatch):
    fake = _FakeRewardsRepo()
    _patch(monkeypatch, fake)
    first = rewards_service.claim_sign_up_bonus("u5")
    assert first["credits_awarded"] == cfg.SIGN_UP_BONUS_CREDITS == 2
    assert first["balance"] == STARTER + 2
    assert rewards_service.claim_sign_up_bonus("u5")["status"] == "already_claimed"


def test_email_login_once(monkeypatch):
    fake = _FakeRewardsRepo()
    _patch(monkeypatch, fake)
    first = rewards_service.claim_email_login("u6")
    assert first["credits_awarded"] == cfg.EMAIL_LOGIN_CREDITS == 1
    assert rewards_service.claim_email_login("u6")["status"] == "already_claimed"


# --- Referrals -------------------------------------------------------------

def test_referral_rewards_and_caps_at_five(monkeypatch):
    fake = _FakeRewardsRepo()
    _patch(monkeypatch, fake)
    for i in range(cfg.REFERRAL_MAX_SUCCESSFUL):
        result = rewards_service.claim_referral("u7", f"friend-{i}")
        assert result["status"] == "success"
        assert result["credits_awarded"] == cfg.REFERRAL_CREDITS_PER_INSTALL == 5
        assert result["referral_count"] == i + 1
    # 6th distinct referral is capped.
    capped = rewards_service.claim_referral("u7", "friend-extra")
    assert capped["status"] == "capped"
    assert capped["referral_count"] == cfg.REFERRAL_MAX_SUCCESSFUL


def test_referral_dedupes_same_friend(monkeypatch):
    fake = _FakeRewardsRepo()
    _patch(monkeypatch, fake)
    assert rewards_service.claim_referral("u8", "friend-1")["status"] == "success"
    assert rewards_service.claim_referral("u8", "friend-1")["status"] == "already_claimed"


def test_referral_rejects_self_and_empty(monkeypatch):
    fake = _FakeRewardsRepo()
    _patch(monkeypatch, fake)
    assert rewards_service.claim_referral("u9", "u9")["status"] == "error"
    assert rewards_service.claim_referral("u9", "")["status"] == "error"


# --- Social share ----------------------------------------------------------

def test_social_share_rewards_three_per_unique_share(monkeypatch):
    fake = _FakeRewardsRepo()
    _patch(monkeypatch, fake)
    first = rewards_service.claim_social_share("u10", "instagram_story", "share-abc")
    assert first["status"] == "success"
    assert first["credits_awarded"] == cfg.SOCIAL_SHARE_CREDITS == 3
    # Same share id is not double-rewarded.
    assert rewards_service.claim_social_share("u10", "instagram_story", "share-abc")["status"] == "already_claimed"
    # A different share id rewards again.
    assert rewards_service.claim_social_share("u10", "youtube_shorts", "share-xyz")["status"] == "success"


def test_social_share_rejects_unknown_platform(monkeypatch):
    fake = _FakeRewardsRepo()
    _patch(monkeypatch, fake)
    assert rewards_service.claim_social_share("u11", "myspace", "s1")["status"] == "error"


# --- HTTP surface ----------------------------------------------------------

def test_endpoints_wire_through(monkeypatch):
    fake = _FakeRewardsRepo()
    _patch(monkeypatch, fake)
    client = TestClient(app)

    r = client.post("/api/v1/rewards/daily-reset", headers={"x-user-id": "http-u"})
    assert r.status_code == 200
    assert r.json()["status"] == "success"
    assert r.json()["credits_awarded"] == 2

    r2 = client.post(
        "/api/v1/rewards/social-share",
        json={"platform": "instagram_story", "share_id": "http-share-1"},
        headers={"x-user-id": "http-u"},
    )
    assert r2.status_code == 200
    assert r2.json()["credits_awarded"] == 3

    r3 = client.post(
        "/api/v1/rewards/referral",
        json={"referred_id": "http-friend-1"},
        headers={"x-user-id": "http-u"},
    )
    assert r3.status_code == 200
    assert r3.json()["credits_awarded"] == 5
