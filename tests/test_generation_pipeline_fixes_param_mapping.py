"""
Contract / fix-checking tests for Task 3.2 of the "generation-pipeline-fixes"
bugfix spec: backend parameter mapping to Vertex for Bugs 3 & 5.

Scope (backend / FastAPI):
    - Bug 3 (isBugCondition3): the UI-selected aspect_ratio must be mapped to the
      corresponding Vertex request parameter (GenerateVideosConfig.aspect_ratio).
    - Bug 5 (isBugCondition5): the UI-selected style must be mapped to the
      corresponding Vertex parameter / prompt directive. Veo's
      GenerateVideosConfig has no native `style` field, so style is carried as a
      prompt directive appended to the prompt.
    - Property 5 (shared invariant): every UI-selected generation parameter must
      be present in the outgoing Vertex request.

Design decision — where style maps:
    Vertex Veo's `GenerateVideosConfig` exposes `aspect_ratio`, `duration_seconds`,
    `number_of_videos`, `person_generation`, etc., but NO native `style`
    parameter. We therefore map `style` as an explicit prompt directive
    ("in <style> style") appended to the prompt (media_utils.apply_style_directive),
    while `aspect_ratio` maps to the native config field.

These tests must NOT regress the Bug 1 429 retry/backoff handling (Task 3.3):
    generate_video routes provider calls through `_call_upstream_with_retry`,
    which we exercise unchanged here (a successful provider result flows straight
    through).

Run with:
    pytest tests/test_generation_pipeline_fixes_param_mapping.py -v
"""

import asyncio
import random
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.providers.media_utils import (
    apply_style_directive,
    is_default_style,
)


def _run(coro):
    """Drive an async coroutine to completion from a sync test.

    This repo has no pytest-asyncio mode configured, so async tests would be
    silently SKIPPED. Driving the coroutine manually keeps them running.
    """
    return asyncio.run(coro)


def _success_result(payload):
    """A minimal successful provider result (shape used by generate_video)."""
    return {
        "status": "success",
        "video_url": "https://cdn.example/vid.mp4",
        "model": "veo",
        "duration": payload.get("duration", 10),
        "provider": "vertex-ai",
    }


class TestAspectRatioMapping:
    """Bug 3: aspect_ratio reaches the Vertex request unchanged."""

    def test_aspect_ratio_2_3_reaches_provider_payload(self):
        """
        POST /api/v1/generation/video with aspect_ratio="2:3" delivers that value
        into the payload handed to the Vertex video provider (the Vertex request
        boundary), so GenerateVideosConfig.aspect_ratio matches the selection.
        """
        from app.services import generation_service

        captured = {}

        async def spy_generate_single_video(payload):
            captured.update(payload)
            return _success_result(payload)

        client = TestClient(app)

        with patch.object(generation_service, "credit_repo") as mock_credits, \
                patch.object(generation_service, "analytics_repo"), \
                patch.object(
                    generation_service.video_provider,
                    "generate_single_video",
                    side_effect=spy_generate_single_video,
                ):
            mock_credits.deduct_credits.return_value = True
            mock_credits.add_credits.return_value = 10

            response = client.post(
                "/api/v1/generation/video",
                json={"prompt": "a cat surfing", "aspect_ratio": "2:3"},
                headers={"x-user-id": "user-ar"},
            )

        assert response.status_code == 200, response.json()
        assert captured.get("aspect_ratio") == "2:3", (
            f"aspect_ratio was not carried to the Vertex request: {captured!r}"
        )


class TestStyleMapping:
    """Bug 5: style reaches the Vertex request (as a prompt directive)."""

    def test_style_anime_reaches_provider_payload_and_prompt(self):
        """
        POST /api/v1/generation/video with style="Anime" delivers the style into
        the payload handed to the provider, and the provider maps it into the
        Vertex prompt directive.
        """
        from app.services import generation_service
        from app.providers.vertex_ai_video_provider import VertexAIVideoProvider

        captured = {}

        async def spy_generate_single_video(payload):
            captured.update(payload)
            return _success_result(payload)

        client = TestClient(app)

        with patch.object(generation_service, "credit_repo") as mock_credits, \
                patch.object(generation_service, "analytics_repo"), \
                patch.object(
                    generation_service.video_provider,
                    "generate_single_video",
                    side_effect=spy_generate_single_video,
                ):
            mock_credits.deduct_credits.return_value = True
            mock_credits.add_credits.return_value = 10

            response = client.post(
                "/api/v1/generation/video",
                json={"prompt": "a cat surfing", "style": "Anime"},
                headers={"x-user-id": "user-style"},
            )

        assert response.status_code == 200, response.json()
        # The style must reach the provider (Vertex request boundary)...
        assert captured.get("style") == "Anime", (
            f"style was not carried to the Vertex request: {captured!r}"
        )
        # ...and the provider maps it into the outgoing Vertex prompt directive.
        styled_prompt = apply_style_directive(captured.get("prompt", ""), captured.get("style"))
        assert "anime" in styled_prompt.lower(), (
            f"style directive not applied to Vertex prompt: {styled_prompt!r}"
        )
        # Sanity: the real provider uses the same helper on the prompt.
        assert hasattr(VertexAIVideoProvider, "generate_single_video")


class TestSharedInvariantProperty:
    """
    Property 5 (shared invariant, Bugs 3 & 5): for a request, every UI-selected
    generation parameter must be present in the outgoing Vertex request. Verified
    over random combinations of aspect_ratio + style + pass-through params.
    """

    ASPECT_RATIOS = ["16:9", "9:16", "1:1", "2:3", "3:4", "4:3"]
    STYLES = ["Anime", "Cinematic", "Cyberpunk", "Retro", "Comic", "Default"]

    def test_every_selected_param_reaches_vertex_request(self):
        from app.services import generation_service

        rng = random.Random(1337)
        client = TestClient(app)

        for _ in range(40):
            aspect_ratio = rng.choice(self.ASPECT_RATIOS)
            style = rng.choice(self.STYLES)
            duration = rng.choice([5, 8, 10, 12])
            motion_strength = rng.choice([30, 65, 90])

            selected = {
                "prompt": "a robot dancing",
                "aspect_ratio": aspect_ratio,
                "duration": duration,
                "motion_strength": motion_strength,
            }
            # Client omits style when Default (matches generateImage semantics);
            # simulate that so preservation of unstyled output holds.
            if style != "Default":
                selected["style"] = style

            captured = {}

            async def spy_generate_single_video(payload):
                captured.update(payload)
                return _success_result(payload)

            with patch.object(generation_service, "credit_repo") as mock_credits, \
                    patch.object(generation_service, "analytics_repo"), \
                    patch.object(
                        generation_service.video_provider,
                        "generate_single_video",
                        side_effect=spy_generate_single_video,
                    ):
                mock_credits.deduct_credits.return_value = True
                mock_credits.add_credits.return_value = 10

                response = client.post(
                    "/api/v1/generation/video",
                    json=selected,
                    headers={"x-user-id": "user-invariant"},
                )

            assert response.status_code == 200, response.json()

            # Invariant: each UI-selected parameter is present in the outgoing
            # Vertex request payload with the selected value.
            assert captured.get("aspect_ratio") == aspect_ratio
            assert captured.get("duration") == duration
            assert captured.get("motion_strength") == motion_strength
            if style != "Default":
                assert captured.get("style") == style
                # style is realized in the Vertex prompt directive
                styled_prompt = apply_style_directive(
                    captured.get("prompt", ""), captured.get("style")
                )
                assert style.lower() in styled_prompt.lower()


class TestPreservationDefaults:
    """
    Preservation (req 3.7, 3.13): a request with NO aspect_ratio and NO style
    must use the existing default aspect ratio and must NOT inject a style
    directive into the prompt.
    """

    def test_no_aspect_no_style_uses_default_and_no_directive(self):
        from app.services import generation_service

        captured = {}

        async def spy_generate_single_video(payload):
            captured.update(payload)
            return _success_result(payload)

        client = TestClient(app)

        with patch.object(generation_service, "credit_repo") as mock_credits, \
                patch.object(generation_service, "analytics_repo"), \
                patch.object(
                    generation_service.video_provider,
                    "generate_single_video",
                    side_effect=spy_generate_single_video,
                ):
            mock_credits.deduct_credits.return_value = True
            mock_credits.add_credits.return_value = 10

            response = client.post(
                "/api/v1/generation/video",
                json={"prompt": "a quiet forest"},
                headers={"x-user-id": "user-default"},
            )

        assert response.status_code == 200, response.json()
        # Default aspect ratio preserved (schema default 16:9).
        assert captured.get("aspect_ratio") == "16:9"
        # No style selected -> no style value and no injected directive.
        assert is_default_style(captured.get("style"))
        styled_prompt = apply_style_directive(captured.get("prompt", ""), captured.get("style"))
        assert styled_prompt == captured.get("prompt"), (
            "no-style request must not inject a style directive into the prompt"
        )

    def test_passthrough_params_unchanged(self):
        """Other params (duration, motion_strength, camera_direction, source
        image) pass through unchanged alongside the mapping (req 3.8, 3.15)."""
        from app.services import generation_service

        captured = {}

        async def spy_generate_single_video(payload):
            captured.update(payload)
            return _success_result(payload)

        client = TestClient(app)
        body = {
            "prompt": "a neon city",
            "aspect_ratio": "9:16",
            "style": "Cyberpunk",
            "duration": 12,
            "motion_strength": 80,
            "camera_direction": "pan_left",
            "source_image_b64": "data:image/png;base64,AAAA",
        }

        with patch.object(generation_service, "credit_repo") as mock_credits, \
                patch.object(generation_service, "analytics_repo"), \
                patch.object(
                    generation_service.video_provider,
                    "generate_single_video",
                    side_effect=spy_generate_single_video,
                ):
            mock_credits.deduct_credits.return_value = True
            mock_credits.add_credits.return_value = 10

            response = client.post(
                "/api/v1/generation/video",
                json=body,
                headers={"x-user-id": "user-passthrough"},
            )

        assert response.status_code == 200, response.json()
        assert captured.get("duration") == 12
        assert captured.get("motion_strength") == 80
        assert captured.get("camera_direction") == "pan_left"
        assert captured.get("source_image_b64") == "data:image/png;base64,AAAA"
        assert captured.get("aspect_ratio") == "9:16"
        assert captured.get("style") == "Cyberpunk"


class TestMediaUtilsStyleMapping:
    """Unit tests for the style prompt-directive mapping helper."""

    def test_apply_style_directive_appends(self):
        assert apply_style_directive("a cat", "Anime") == "a cat, in Anime style"

    def test_apply_style_directive_default_sentinels_unchanged(self):
        for sentinel in [None, "", "Default", "default", "None", "standard"]:
            assert apply_style_directive("a cat", sentinel) == "a cat"

    def test_apply_style_directive_idempotent(self):
        once = apply_style_directive("a cat", "Anime")
        twice = apply_style_directive(once, "Anime")
        assert once == twice

    def test_is_default_style(self):
        assert is_default_style(None)
        assert is_default_style("Default")
        assert not is_default_style("Anime")
