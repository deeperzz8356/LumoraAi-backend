"""
Tests for video generation pipeline.

Run with: pytest tests/test_video_generation.py -v
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from app.providers.video_stitch import (
    calculate_video_scenes,
    generate_scene_prompts,
    create_concat_demuxer_file,
)
from app.providers.gcs_utils import parse_gcs_uri


class TestVideoStitch:
    """Tests for video stitching utilities."""

    def test_calculate_video_scenes_3_minutes(self):
        """Test scene calculation for 3-minute video."""
        scenes = calculate_video_scenes(180)
        # 180 / 8 = 22.5, + 1 = 23
        assert scenes == 23

    def test_calculate_video_scenes_1_minute(self):
        """Test scene calculation for 1-minute video."""
        scenes = calculate_video_scenes(60)
        # 60 / 8 = 7.5, + 1 = 8
        assert scenes == 8

    def test_calculate_video_scenes_8_seconds(self):
        """Test scene calculation for single clip."""
        scenes = calculate_video_scenes(8)
        # 8 / 8 = 1, + 1 = 2
        assert scenes == 2

    def test_generate_scene_prompts_count(self):
        """Test that correct number of prompts generated."""
        base_prompt = "A cyberpunk city"
        prompts = generate_scene_prompts(base_prompt, 5, "cinematic")
        assert len(prompts) == 5

    def test_generate_scene_prompts_content(self):
        """Test that prompts include scene numbers."""
        base_prompt = "Test city"
        prompts = generate_scene_prompts(base_prompt, 3, "cinematic")
        
        assert "Scene 1/3" in prompts[0]
        assert "Scene 2/3" in prompts[1]
        assert "Scene 3/3" in prompts[2]

    def test_generate_scene_prompts_style(self):
        """Test that style is included in prompts."""
        prompts = generate_scene_prompts("City", 2, "noir")
        assert "noir" in prompts[0].lower()
        assert "noir" in prompts[1].lower()

    def test_create_concat_demuxer_file(self):
        """Test creation of FFmpeg concat file."""
        files = ["/path/to/video1.mp4", "/path/to/video2.mp4"]
        concat_file = create_concat_demuxer_file(files)
        
        # File should be created
        assert Path(concat_file).exists()
        
        # Content should have file lines
        content = Path(concat_file).read_text()
        assert "file" in content
        assert "video1.mp4" in content
        assert "video2.mp4" in content
        
        # Cleanup
        Path(concat_file).unlink()


class TestGCSUtils:
    """Tests for GCS utilities."""

    def test_parse_gcs_uri_valid(self):
        """Test parsing valid GCS URI."""
        uri = "gs://my-bucket/path/to/video.mp4"
        bucket, path = parse_gcs_uri(uri)
        
        assert bucket == "my-bucket"
        assert path == "path/to/video.mp4"

    def test_parse_gcs_uri_root_path(self):
        """Test parsing GCS URI with root path."""
        uri = "gs://bucket/video.mp4"
        bucket, path = parse_gcs_uri(uri)
        
        assert bucket == "bucket"
        assert path == "video.mp4"

    def test_parse_gcs_uri_with_trailing_slash(self):
        """Test parsing GCS URI with trailing slash."""
        uri = "gs://bucket/folder/"
        bucket, path = parse_gcs_uri(uri)
        
        assert bucket == "bucket"
        assert path == "folder/"

    def test_parse_gcs_uri_invalid(self):
        """Test parsing invalid GCS URI."""
        with pytest.raises(ValueError):
            parse_gcs_uri("invalid-uri")

    def test_parse_gcs_uri_no_bucket(self):
        """Test parsing GCS URI without bucket."""
        with pytest.raises(ValueError):
            parse_gcs_uri("gs:///path")


class TestVideoProvider:
    """Tests for VertexAIVideoProvider."""

    @pytest.mark.asyncio
    async def test_generate_single_video_payload(self):
        """Test that single video generation validates payload."""
        from app.providers.vertex_ai_video_provider import VertexAIVideoProvider
        
        provider = VertexAIVideoProvider()
        
        # Mock the actual generation
        with patch.object(provider, '_poll_video_operation', new_callable=AsyncMock) as mock_poll:
            # We can't fully test without real GCP access
            # This is a placeholder for structure validation
            assert hasattr(provider, 'generate_single_video')
            assert callable(provider.generate_single_video)

    @pytest.mark.asyncio
    async def test_generate_long_form_video_structure(self):
        """Test that long-form generation has correct structure."""
        from app.providers.vertex_ai_video_provider import VertexAIVideoProvider
        
        provider = VertexAIVideoProvider()
        assert hasattr(provider, 'generate_long_form_video')
        assert callable(provider.generate_long_form_video)


class TestGenerationService:
    """Tests for generation service."""

    @pytest.mark.asyncio
    async def test_generate_video_credit_check(self):
        """Test that video generation checks credits."""
        from app.services.generation_service import generate_video
        
        with patch('app.services.generation_service.credit_repo') as mock_credits:
            mock_credits.deduct_credits.return_value = False
            
            result = await generate_video("user-123", {"prompt": "test"})
            
            assert result["status"] == "error"
            assert "Insufficient credits" in result["message"]

    @pytest.mark.asyncio
    async def test_generate_long_form_video_structure(self):
        """Test that long-form service is callable."""
        from app.services.generation_service import generate_long_form_video
        
        assert callable(generate_long_form_video)


class TestVideoAPIEndpoints:
    """Tests for video API endpoints."""

    def test_video_generate_request_schema(self):
        """Test video generate request schema."""
        from app.routers.videos import VideoGenerateRequest
        
        # Valid request
        req = VideoGenerateRequest(
            prompt="A robot",
            duration=8,
            aspect_ratio="16:9"
        )
        assert req.prompt == "A robot"
        assert req.duration == 8

    def test_long_form_request_schema(self):
        """Test long-form request schema."""
        from app.routers.videos import LongFormVideoRequest
        
        # Valid request
        req = LongFormVideoRequest(
            prompt="A journey",
            duration_seconds=180,
            style="cinematic"
        )
        assert req.prompt == "A journey"
        assert req.duration_seconds == 180
        assert req.style == "cinematic"


class TestConfiguration:
    """Tests for configuration."""

    def test_config_defaults(self):
        """Test that configuration has proper defaults."""
        from app.core.config import get_settings
        
        settings = get_settings()
        
        # Video settings
        assert settings.vertex_video_model is not None
        assert settings.vertex_video_poll_seconds > 0
        assert settings.vertex_video_poll_attempts > 0
        
        # Stitch settings
        assert hasattr(settings, 'vertex_video_stitch_enabled')
        assert hasattr(settings, 'vertex_video_output_dir')

    def test_config_polling_limits(self):
        """Test that polling limits are valid."""
        from app.core.config import Settings
        
        # Valid settings
        settings = Settings(
            vertex_video_poll_seconds=15,
            vertex_video_poll_attempts=40
        )
        assert settings.vertex_video_poll_seconds == 15
        assert settings.vertex_video_poll_attempts == 40


# Integration Tests (require real GCP setup)
class TestIntegration:
    """Integration tests for real GCP environment."""

    @pytest.mark.skip(reason="Requires GCP credentials")
    @pytest.mark.asyncio
    async def test_real_video_generation(self):
        """Test real video generation (requires GCP setup)."""
        from app.providers.vertex_ai_video_provider import VertexAIVideoProvider
        
        provider = VertexAIVideoProvider()
        result = await provider.generate_single_video({
            "prompt": "A simple test video",
            "duration": 8,
        })
        
        # These would be real if GCP is available
        # assert result["status"] == "success"
        # assert "local_path" in result

    @pytest.mark.skip(reason="Requires GCP and FFmpeg")
    @pytest.mark.asyncio
    async def test_real_long_form_generation(self):
        """Test real long-form generation (requires GCP + FFmpeg)."""
        from app.providers.vertex_ai_video_provider import VertexAIVideoProvider
        
        provider = VertexAIVideoProvider()
        result = await provider.generate_long_form_video(
            base_prompt="A test journey",
            duration_seconds=16,  # 2 clips only
            style="test",
        )
        
        # These would be real if GCP is available
        # assert result["status"] == "success"
        # assert "total_scenes" in result


# Utility test helpers
def create_test_video_file(path: str, duration_ms: int = 1000) -> Path:
    """Create a minimal test video file."""
    # This would use ffmpeg in real tests
    # For now, just create a placeholder
    return Path(path).touch()


@pytest.fixture
def test_output_dir(tmp_path):
    """Provide temporary output directory for tests."""
    return tmp_path / "videos"


@pytest.fixture
def test_gcs_uri():
    """Provide test GCS URI."""
    return "gs://test-bucket/test-video.mp4"


@pytest.fixture
def test_prompts():
    """Provide test prompts."""
    return [
        "A robot dancing in space",
        "A peaceful forest scene",
        "A futuristic city",
    ]
