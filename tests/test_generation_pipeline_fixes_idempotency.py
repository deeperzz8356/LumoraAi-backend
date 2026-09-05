"""
Contract tests for Task 3.5 of the "generation-pipeline-fixes" bugfix spec:
DB-persisted idempotent credits/add + count-on-confirmed-output.

These are the FIX-CHECKING and PRESERVATION contract tests for Bug 4
(isBugCondition4):

    ( X.type = "generation"  AND countedAsSuccess(X) AND NOT confirmedOutput(X) )
 OR ( X.type = "credits/add" AND duplicateApplications(X) > 1 )

Fix Checking (design.md Property 4 / Fix Checking pseudocode):
    - credits/add: appliedCount(state, X.idempotencyKey) = 1
      -> a duplicate delivery of the SAME idempotency_key applies the amount
         once; the second call returns the SAME balance without re-applying.
    - distinct keys each apply once (Requirement 3.11 preservation).
    - generation: counterDelta = (1 iff confirmedOutput else 0)
      -> a confirmed success logs exactly one generation; an honest upstream
         failure (429/503) or error result logs zero.

Persistence model (Requirement 2.15, Render FREE plan): applied idempotency keys
live in Firestore (per-user subcollection) and the counter is the existing
generation_analytics collection — durable across cold starts, no in-memory-only
state, no Redis/queues. Here we mock the Firestore-backed repos (patch.object)
exactly as the sibling tests do, so no live DB is required; we model the durable
key store with an in-test dict to verify the check-and-apply contract.

Run with:
    pytest tests/test_generation_pipeline_fixes_idempotency.py -v
"""

import asyncio
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def _run(coro):
    return asyncio.run(coro)


VERTEX_429_MESSAGE = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'status': "
    "'RESOURCE_EXHAUSTED', 'message': 'Quota exceeded', "
    "'details': [{'retryDelay': '17s'}]}}"
)


class _FakeCreditStore:
    """In-test stand-in for the Firestore-backed CreditRepository.

    Models the DURABLE state the real repo persists: a per-user balance and a
    per-(user, idempotency_key) applied-key record. The apply is a single
    check-and-set, mirroring the transactional check-then-apply in
    ``CreditRepository.add_credits_idempotent`` so we verify the idempotency
    CONTRACT independent of Firestore.
    """

    STARTER = 7

    def __init__(self):
        self.balances: dict[str, int] = {}
        self.applied_keys: set[tuple[str, str]] = set()

    def get_credits(self, user_id: str) -> int:
        return self.balances.get(user_id, self.STARTER)

    def add_credits(self, user_id: str, amount: int = 1) -> int:
        new_balance = self.get_credits(user_id) + amount
        self.balances[user_id] = new_balance
        return new_balance

    def add_credits_idempotent(self, user_id, amount=1, idempotency_key=None):
        if not idempotency_key:
            return self.add_credits(user_id, amount)
        marker = (user_id, idempotency_key)
        if marker in self.applied_keys:
            # Already applied: return current balance WITHOUT re-applying.
            return self.get_credits(user_id)
        self.applied_keys.add(marker)
        return self.add_credits(user_id, amount)


class TestCreditsAddIdempotency:
    """Bug 4b: duplicate credits/add with the same key applies at most once."""

    def test_duplicate_same_key_applies_once(self):
        """
        (a) Duplicate credits/add with the SAME idempotency_key:
        balance increases by amount ONLY once; the second call returns the same
        balance. appliedCount(key) = 1.
        """
        from app.services import credits_service

        store = _FakeCreditStore()

        with patch.object(credits_service, "credit_repo", store):
            first = _run(
                credits_service.add_credits("user-dup", 5, idempotency_key="evt-1")
            )
            second = _run(
                credits_service.add_credits("user-dup", 5, idempotency_key="evt-1")
            )

        assert first["balance"] == _FakeCreditStore.STARTER + 5
        # Second delivery of the SAME logical event must NOT re-apply.
        assert second["balance"] == first["balance"], (
            "duplicate credits/add with same idempotency_key must not double-apply"
        )
        assert store.get_credits("user-dup") == _FakeCreditStore.STARTER + 5

    def test_five_back_to_back_same_key_applies_once(self):
        """The observed defect: credits/add fires in groups of five. With a
        stable key, all five deliveries collapse to a single application."""
        from app.services import credits_service

        store = _FakeCreditStore()

        with patch.object(credits_service, "credit_repo", store):
            balances = [
                _run(
                    credits_service.add_credits(
                        "user-burst", 5, idempotency_key="reward-42"
                    )
                )["balance"]
                for _ in range(5)
            ]

        assert balances == [_FakeCreditStore.STARTER + 5] * 5
        assert store.get_credits("user-burst") == _FakeCreditStore.STARTER + 5

    def test_distinct_keys_each_apply_once(self):
        """
        (b) Distinct idempotency keys each apply once (Requirement 3.11): three
        distinct logical events each add their amount exactly once.
        """
        from app.services import credits_service

        store = _FakeCreditStore()

        with patch.object(credits_service, "credit_repo", store):
            for i, key in enumerate(("a", "b", "c")):
                result = _run(
                    credits_service.add_credits("user-distinct", 5, idempotency_key=key)
                )
                assert result["balance"] == _FakeCreditStore.STARTER + 5 * (i + 1)

        assert store.get_credits("user-distinct") == _FakeCreditStore.STARTER + 15

    def test_no_key_preserves_non_idempotent_add(self):
        """Preservation: with no key supplied, add is non-idempotent as before —
        each call applies (legacy callers unchanged)."""
        from app.services import credits_service

        store = _FakeCreditStore()

        with patch.object(credits_service, "credit_repo", store):
            b1 = _run(credits_service.add_credits("user-nokey", 5))["balance"]
            b2 = _run(credits_service.add_credits("user-nokey", 5))["balance"]

        assert b1 == _FakeCreditStore.STARTER + 5
        assert b2 == _FakeCreditStore.STARTER + 10

    def test_endpoint_duplicate_key_applies_once(self):
        """Contract / API surface: POST /api/v1/credits/add with the same
        idempotency_key in the JSON body applies once across duplicate deliveries."""
        from app.services import credits_service

        store = _FakeCreditStore()
        client = TestClient(app)

        with patch.object(credits_service, "credit_repo", store):
            r1 = client.post(
                "/api/v1/credits/add",
                json={"amount": 5, "idempotency_key": "http-evt-1"},
                headers={"x-user-id": "http-dup"},
            )
            r2 = client.post(
                "/api/v1/credits/add",
                json={"amount": 5, "idempotency_key": "http-evt-1"},
                headers={"x-user-id": "http-dup"},
            )

        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["balance"] == _FakeCreditStore.STARTER + 5
        assert r2.json()["balance"] == _FakeCreditStore.STARTER + 5


class TestGenerationCountOnConfirmedOutput:
    """Bug 4a: the generation counter increments only for confirmed outputs."""

    def test_confirmed_video_success_counts_once(self):
        """counterDelta = 1 when confirmedOutput: a successful video with a real
        video_url logs exactly one generation."""
        from app.services import generation_service

        async def fake_generate_single_video(payload):
            return {
                "status": "success",
                "video_url": "https://cdn.example/vid.mp4",
                "model": "veo",
                "duration": payload.get("duration", 8),
                "provider": "vertex-ai",
            }

        with patch.object(generation_service, "credit_repo") as mock_credits, \
                patch.object(generation_service, "analytics_repo") as mock_analytics, \
                patch.object(
                    generation_service.video_provider,
                    "generate_single_video",
                    side_effect=fake_generate_single_video,
                ):
            mock_credits.deduct_credits.return_value = True
            mock_credits.add_credits.return_value = 10

            result = _run(
                generation_service.generate_video(
                    "user-ok", {"prompt": "a cat surfing", "duration": 8}
                )
            )

        assert result["status"] == "success"
        assert mock_analytics.log_generation.call_count == 1

    def test_upstream_429_does_not_count(self):
        """counterDelta = 0 when NOT confirmedOutput: an exhausted upstream 429
        (honest {429,503} failure from Task 3.3) logs zero generations."""
        from app.services import generation_service
        from app.utils.upstream_rate_limit import UpstreamRateLimitError

        async def fake_generate_single_video(payload):
            raise UpstreamRateLimitError(VERTEX_429_MESSAGE, http_status=429)

        with patch.object(generation_service, "credit_repo") as mock_credits, \
                patch.object(generation_service, "analytics_repo") as mock_analytics, \
                patch.object(
                    generation_service.video_provider,
                    "generate_single_video",
                    side_effect=fake_generate_single_video,
                ):
            mock_credits.deduct_credits.return_value = True
            mock_credits.add_credits.return_value = 10

            result = _run(
                generation_service.generate_video(
                    "user-429", {"prompt": "a cat surfing", "duration": 8}
                )
            )

        assert result["status"] == "error"
        assert result.get("http_status") in (429, 503)
        assert mock_analytics.log_generation.call_count == 0, (
            "a rate-limited failure must NOT increment the generation counter"
        )

    def test_error_result_does_not_count(self):
        """counterDelta = 0: a provider error result (no video_url) logs zero."""
        from app.services import generation_service

        async def fake_generate_single_video(payload):
            return {
                "status": "error",
                "message": "veo internal error",
                "model": "veo",
                "provider": "vertex-ai",
            }

        with patch.object(generation_service, "credit_repo") as mock_credits, \
                patch.object(generation_service, "analytics_repo") as mock_analytics, \
                patch.object(
                    generation_service.video_provider,
                    "generate_single_video",
                    side_effect=fake_generate_single_video,
                ):
            mock_credits.deduct_credits.return_value = True
            mock_credits.add_credits.return_value = 10

            result = _run(
                generation_service.generate_video(
                    "user-err", {"prompt": "a cat surfing", "duration": 8}
                )
            )

        assert result["status"] == "error"
        assert mock_analytics.log_generation.call_count == 0

    def test_confirmed_image_success_counts_once(self):
        """Image path: a confirmed image_url logs exactly one generation."""
        from app.services import generation_service

        class _Gen:
            image_bytes = b"\x89PNGfake"
            mime_type = "image/png"
            model = "imagen"

        async def fake_generate_image(request_obj):
            return _Gen()

        with patch.object(generation_service, "credit_repo") as mock_credits, \
                patch.object(generation_service, "analytics_repo") as mock_analytics, \
                patch.object(
                    generation_service.image_provider,
                    "generate_image",
                    side_effect=fake_generate_image,
                ):
            mock_credits.deduct_credits.return_value = True
            mock_credits.add_credits.return_value = 10

            result = _run(
                generation_service.generate_image("user-img", {"prompt": "a fox"})
            )

        assert result["status"] == "success"
        assert result["image_url"]
        assert mock_analytics.log_generation.call_count == 1
