"""
Tests for the server-priced action deduction (POST /credits/deduct).

The client names the ACTION; the server prices it (so the amount can't be
spoofed). Used to charge for on-device actions like background removal.
"""

import asyncio
from unittest.mock import patch

from app.services import credits_service


def _run(coro):
    return asyncio.run(coro)


class _FakeCredits:
    def __init__(self, balance):
        self.balance = balance

    def get_credits(self, uid):
        return self.balance

    def deduct_credits(self, uid, amount=1):
        if self.balance >= amount:
            self.balance -= amount
            return True
        return False


def test_known_action_deducts_server_priced_cost():
    fake = _FakeCredits(10)
    with patch.object(credits_service, "credit_repo", fake):
        result = _run(credits_service.deduct_credits_for_action("u1", "background_removal"))
    assert result["status"] == "success"
    assert result["cost"] == 1
    assert result["balance"] == 9


def test_video_costs_five():
    fake = _FakeCredits(10)
    with patch.object(credits_service, "credit_repo", fake):
        result = _run(credits_service.deduct_credits_for_action("u1", "video_generation"))
    assert result["cost"] == 5
    assert result["balance"] == 5


def test_insufficient_credits():
    fake = _FakeCredits(0)
    with patch.object(credits_service, "credit_repo", fake):
        result = _run(credits_service.deduct_credits_for_action("u1", "image_generation"))
    assert result["status"] == "insufficient"


def test_unknown_action_rejected():
    fake = _FakeCredits(10)
    with patch.object(credits_service, "credit_repo", fake):
        result = _run(credits_service.deduct_credits_for_action("u1", "hack_free_stuff"))
    assert result["status"] == "error"
    assert fake.balance == 10  # nothing deducted
