"""
Bug condition exploration tests for the "generation-pipeline-fixes" bugfix spec.

CRITICAL BUGFIX SEMANTICS:
    These tests are written to FAIL on the CURRENT (unfixed) backend code.
    A failure here is the SUCCESS signal - it confirms the bug exists and
    surfaces a concrete counterexample. DO NOT change the code to make them
    pass as part of writing them (that is Task 3).

Scope of THIS file (backend / FastAPI):
    - Bug 1 (isBugCondition1): upstream Vertex 429 is swallowed and reported to
      the client as HTTP 200 with a body that indicates failure (no output).
      Expected fixed behavior: an honest failure status in {429, 503}.

The client-side bug conditions (Bugs 2, 3, 4b, 5) are exercised by the Android
JUnit exploration tests under:
    app/src/test/java/com/deep/lumoraai/GenerationPipelineFixesExplorationTest.kt

Run with:
    pytest tests/test_generation_pipeline_fixes_exploration.py -v
"""

import asyncio
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


# A representative Vertex "RESOURCE_EXHAUSTED" 429 error message, mirroring what
# google-genai raises and what the backend logs ("generate_content failed: 429
# RESOURCE_EXHAUSTED").
VERTEX_429_MESSAGE = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'status': "
    "'RESOURCE_EXHAUSTED', 'message': 'Quota exceeded', "
    "'details': [{'retryDelay': '17s'}]}}"
)


def _run(coro):
    """Drive an async coroutine to completion from a sync test.

    We deliberately avoid the @pytest.mark.asyncio marker because this repo has
    no pytest-asyncio mode configured, which causes async tests to be silently
    SKIPPED rather than run. A skipped test cannot surface a counterexample.
    """
    return asyncio.run(coro)


class TestBug1UpstreamesRateLimitPropagation:
    """
    Bug 1 / isBugCondition1: a generate/video request whose upstream Vertex
    status is 429 must NOT be reported to the client as a success.

    Property 1 (design.md): if retries are exhausted the result status must be
    in {429, 503} with a failure body - never HTTP 200 with no output.
    """

    def test_video_service_swallows_upstream_429_as_error_dict(self):
        """
        Service layer: simulate the Vertex provider hitting a 429 and assert the
        service surfaces an honest failure signal.

        EXPECTED ON UNFIXED CODE: FAILS.
        Today generate_single_video() catches the exception and returns
        {"status": "error", ...}; generate_video() propagates that dict but the
        HTTP layer still returns 200. There is also no retry/backoff honoring
        retryDelay. We assert here the *service* would raise / mark a retriable
        failure distinctly - which it does not.
        """
        from app.services import generation_service

        async def fake_generate_single_video(payload):
            # Mimic the provider's current behavior: swallow the 429 into an
            # error dict (no distinction between retriable 429 and other errors).
            return {
                "status": "error",
                "message": VERTEX_429_MESSAGE,
                "model": "veo",
                "provider": "vertex-ai",
            }

        with patch.object(generation_service, "credit_repo") as mock_credits, \
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

        # The fixed service must expose the upstream 429 as a retriable /
        # rate-limited failure so the router can map it to HTTP 429/503.
        # On unfixed code the message is a generic error string with no status
        # code hint the router can act on, so this assertion FAILS.
        status_code_hint = result.get("http_status") or result.get("status_code")
        assert status_code_hint in (429, 503), (
            "Upstream 429 was swallowed into a generic error with no honest "
            f"status code the API layer can propagate. result={result!r}"
        )

    def test_video_endpoint_returns_non_200_on_upstream_429(self):
        """
        Contract / API surface: POST /api/v1/generation/video when the upstream
        Vertex call returns 429 must yield a non-200 failure status in {429, 503}
        rather than 200-with-no-output.

        EXPECTED ON UNFIXED CODE: FAILS.
        The router unconditionally returns the service dict with HTTP 200, so a
        swallowed 429 is delivered as HTTP 200 with {"status": "error", ...} and
        no video_url.
        """
        from app.services import generation_service

        async def fake_generate_single_video(payload):
            return {
                "status": "error",
                "message": VERTEX_429_MESSAGE,
                "model": "veo",
                "provider": "vertex-ai",
            }

        client = TestClient(app)

        with patch.object(generation_service, "credit_repo") as mock_credits, \
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
                headers={"x-user-id": "user-429"},
            )

        body = response.json()
        has_output = bool(body.get("video_url"))

        # Honest failure propagation: an exhausted upstream 429 must not be a 200.
        assert response.status_code in (429, 503), (
            "Upstream Vertex 429 was swallowed and returned as "
            f"HTTP {response.status_code} (has_output={has_output}, body={body!r}). "
            "Expected an honest failure status in {429, 503}."
        )
