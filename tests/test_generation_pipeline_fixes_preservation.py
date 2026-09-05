"""
Preservation property tests for the "generation-pipeline-fixes" bugfix spec.

CRITICAL BUGFIX SEMANTICS:
    These tests MUST PASS on the CURRENT (unfixed) backend code. They capture the
    baseline NON-BUGGY behavior (inputs where isBugCondition1 does NOT hold) that
    must remain unchanged after the Task 3 fixes are applied. They are the
    "Preservation Checking" half of the bugfix workflow (design.md → Preservation
    Checking; Property 7).

OBSERVATION-FIRST METHODOLOGY:
    The assertions below were written after observing the actual outputs of the
    unfixed production code for non-buggy (non-429) inputs:
      - A successful upstream generation returns
        {"status": "success", "video_url": ..., ...} and the router returns it
        with HTTP 200.
      - A non-retriable upstream error (provider raises, or returns an error
        dict) is surfaced as {"status": "error", "message": ...} with HTTP 200
        and NO 429 retry/backoff is applied (there is none today).
    We assert these observed behaviors hold across the non-buggy input domain so
    that, after Task 3 adds 429 handling, these paths remain unchanged.

Scope of THIS file (backend / FastAPI): ¬isBugCondition1 only.
The client-side preservation (¬isBugCondition2/3/4/5) is exercised by the Android
JUnit preservation tests under:
    app/src/test/java/com/deep/lumoraai/GenerationPipelineFixesPreservationTest.kt

Run with:
    pytest tests/test_generation_pipeline_fixes_preservation.py -v
"""

import asyncio
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def _run(coro):
    """Drive an async coroutine to completion from a sync test.

    We deliberately avoid the @pytest.mark.asyncio marker because this repo has
    no pytest-asyncio mode configured, which would silently SKIP async tests.
    """
    return asyncio.run(coro)


# A representative set of non-429 (non-retriable) upstream failures. None of
# these satisfy isBugCondition1, so their handling must be preserved.
NON_RETRIABLE_MESSAGES = [
    "400 INVALID_ARGUMENT. Request payload is malformed.",
    "401 UNAUTHENTICATED. Missing or invalid credentials.",
    "403 PERMISSION_DENIED. Caller lacks permission.",
]


class TestBug1SuccessfulGenerationPreservation:
    """
    ¬isBugCondition1: a generate/video request whose upstream succeeds must
    CONTINUE to return HTTP 200 with the generated output (Requirement 3.1).
    """

    def test_service_success_returns_status_success_with_video_url(self):
        """
        Service layer: a successful provider result is returned as
        {"status": "success", "video_url": ...} unchanged.

        EXPECTED ON UNFIXED CODE: PASSES (baseline to preserve).
        """
        from app.services import generation_service

        async def fake_generate_single_video(payload):
            return {
                "status": "success",
                "video_url": "https://cdn.example/vid.mp4",
                "local_path": "/tmp/vid.mp4",
                "model": "veo",
                "duration": payload.get("duration", 10),
                "provider": "vertex-ai",
            }

        with patch.object(generation_service, "credit_repo") as mock_credits, \
                patch.object(generation_service, "analytics_repo"), \
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
        assert result["video_url"] == "https://cdn.example/vid.mp4"
        assert result["provider"] == "vertex-ai"

    def test_endpoint_success_returns_http_200_with_output(self):
        """
        Contract / API surface: POST /api/v1/generation/video with a successful
        upstream returns HTTP 200 with a video_url.

        Property over a range of valid durations (non-buggy input domain):
        every successful request stays 200-with-output.

        EXPECTED ON UNFIXED CODE: PASSES (baseline to preserve).
        """
        from app.services import generation_service

        client = TestClient(app)

        for duration in (5, 8, 10, 12, 15):
            async def fake_generate_single_video(payload, _d=duration):
                return {
                    "status": "success",
                    "video_url": "https://cdn.example/vid.mp4",
                    "model": "veo",
                    "duration": _d,
                    "provider": "vertex-ai",
                }

            with patch.object(generation_service, "credit_repo") as mock_credits, \
                    patch.object(generation_service, "analytics_repo"), \
                    patch.object(
                        generation_service.video_provider,
                        "generate_single_video",
                        side_effect=fake_generate_single_video,
                    ):
                mock_credits.deduct_credits.return_value = True
                mock_credits.add_credits.return_value = 10

                response = client.post(
                    "/api/v1/generation/video",
                    json={"prompt": "a cat surfing", "duration": duration},
                    headers={"x-user-id": "user-ok"},
                )

            body = response.json()
            assert response.status_code == 200, (
                f"successful generation must stay HTTP 200 (duration={duration}, "
                f"body={body!r})"
            )
            assert body.get("status") == "success"
            assert body.get("video_url"), "successful generation must carry output"


class TestBug1NonRetriableErrorPreservation:
    """
    ¬isBugCondition1: a non-429 (non-retriable) upstream error must CONTINUE to
    surface without any 429 retry/backoff (Requirement 3.2). Today the router
    returns the service error dict with HTTP 200; that observed behavior is the
    baseline to preserve (the fix only changes the 429 path).
    """

    def test_service_surfaces_non_retriable_error_dict(self):
        """
        Service layer: a non-retriable provider error dict is surfaced as
        {"status": "error", "message": ...}, and a single upstream call is made
        (no 429 retry loop).

        EXPECTED ON UNFIXED CODE: PASSES (baseline to preserve).
        """
        from app.services import generation_service

        for message in NON_RETRIABLE_MESSAGES:
            call_count = {"n": 0}

            async def fake_generate_single_video(payload, _m=message):
                call_count["n"] += 1
                return {
                    "status": "error",
                    "message": _m,
                    "model": "veo",
                    "provider": "vertex-ai",
                }

            with patch.object(generation_service, "credit_repo") as mock_credits, \
                    patch.object(generation_service, "analytics_repo"), \
                    patch.object(
                        generation_service.video_provider,
                        "generate_single_video",
                        side_effect=fake_generate_single_video,
                    ):
                mock_credits.deduct_credits.return_value = True
                mock_credits.add_credits.return_value = 10

                result = _run(
                    generation_service.generate_video(
                        "user-4xx", {"prompt": "a cat surfing", "duration": 8}
                    )
                )

            assert result["status"] == "error", f"message={message!r}"
            # No 429 retry/backoff: the upstream is called exactly once.
            assert call_count["n"] == 1, (
                "non-retriable error must not trigger a retry loop "
                f"(calls={call_count['n']}, message={message!r})"
            )

    def test_endpoint_non_retriable_error_preserved(self):
        """
        Contract / API surface: POST /api/v1/generation/video with a non-429
        upstream error surfaces the error dict as it does today, across a range
        of non-retriable error kinds.

        EXPECTED ON UNFIXED CODE: PASSES (baseline to preserve).
        """
        from app.services import generation_service

        client = TestClient(app)

        for message in NON_RETRIABLE_MESSAGES:
            async def fake_generate_single_video(payload, _m=message):
                return {
                    "status": "error",
                    "message": _m,
                    "model": "veo",
                    "provider": "vertex-ai",
                }

            with patch.object(generation_service, "credit_repo") as mock_credits, \
                    patch.object(generation_service, "analytics_repo"), \
                    patch.object(
                        generation_service.video_provider,
                        "generate_single_video",
                        side_effect=fake_generate_single_video,
                    ):
                mock_credits.deduct_credits.return_value = True
                mock_credits.add_credits.return_value = 10

                response = client.post(
                    "/api/v1/generation/video",
                    json={"prompt": "a cat surfing", "duration": 8},
                    headers={"x-user-id": "user-4xx"},
                )

            body = response.json()
            # Baseline observed behavior: non-429 errors are surfaced as an error
            # body and are NOT re-mapped into 429/503 by any retry logic.
            assert body.get("status") == "error", f"message={message!r}, body={body!r}"
            assert response.status_code not in (429, 503), (
                "a non-retriable error must not be mapped to a 429/503 "
                f"retry-exhausted status (status={response.status_code}, "
                f"message={message!r})"
            )
