"""
Enhanced Vertex AI Video Generation Provider with GCS integration and video stitching.
Handles:
- Single 8-second video generation
- Batch video generation for long-form content
- Automatic GCS download
- Video stitching for 3-minute output
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from google import genai
from google.genai import types
from google.oauth2 import service_account
from google.auth import load_credentials_from_file

from app.core.config import get_settings
from app.providers.gcs_utils import download_video_from_gcs, parse_gcs_uri
from app.providers.media_utils import clamp_veo_duration, decode_base64_payload, encode_data_url
from app.providers.video_stitch import (
    calculate_video_scenes,
    cleanup_video_files,
    generate_scene_prompts,
    get_video_duration,
    stitch_videos,
    validate_video_file,
)

logger = logging.getLogger(__name__)

_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)


def _resolve_credentials_path(raw_path: str) -> str:
    """Resolve credentials file path."""
    from pathlib import Path
    
    backend_root = Path(__file__).resolve().parents[2]
    path = Path(raw_path)
    
    if path.is_file():
        return str(path.resolve())
    candidate = backend_root / raw_path
    if candidate.is_file():
        return str(candidate.resolve())
    candidate = backend_root / Path(raw_path).name
    if candidate.is_file():
        return str(candidate.resolve())
    
    raise FileNotFoundError(
        f"Vertex AI credentials file not found: {raw_path!r} (looked under {backend_root})"
    )


def _build_client() -> genai.Client:
    """Build Vertex AI client."""
    settings = get_settings()
    if not settings.google_cloud_project:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT is not configured. Set it in backend/.env to use Vertex AI."
        )

    credentials = None
    if settings.google_application_credentials:
        creds_path = _resolve_credentials_path(settings.google_application_credentials)
        try:
            # Try to load as service account first
            credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=_SCOPES,
            )
        except Exception as e:
            # If that fails, let google-auth handle ADC (authorized_user format)
            logger.info(f"Not a service account file, using as ADC credentials: {e}")
            credentials, _ = load_credentials_from_file(creds_path, scopes=_SCOPES)

    return genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
        credentials=credentials,
    )


class VertexAIVideoProvider:
    """
    Vertex AI video generation with GCS integration.
    
    Features:
    - Single video generation (up to 8 seconds)
    - Batch video generation for long-form content
    - Automatic GCS download to local disk
    - Video stitching for 3-minute output
    """

    async def generate_single_video(self, payload: dict) -> dict:
        """
        Generate a single 8-second video and download from GCS.
        
        Args:
            payload: {
                'prompt': str,
                'model': str (optional),
                'aspect_ratio': str (default: '16:9'),
                'duration': int (default: 8, max: 8),
                'source_image_b64': str (optional),
            }
            
        Returns:
            {
                'status': 'success' | 'error',
                'video_url': str (data URL or local path),
                'local_path': str (local file path if saved),
                'duration': float (video duration in seconds),
                'model': str,
                'provider': 'vertex-ai',
            }
        """
        settings = get_settings()
        model = payload.get("model") or settings.vertex_video_model
        prompt = payload.get("prompt") or ""
        aspect_ratio = payload.get("aspect_ratio") or "16:9"
        duration = clamp_veo_duration(int(payload.get("duration") or 8), model)

        source_image = None
        source_b64 = payload.get("source_image_b64")
        if source_b64:
            image_bytes = decode_base64_payload(source_b64)
            source_image = types.Image(image_bytes=image_bytes, mime_type="image/png")

        config_kwargs: dict[str, Any] = {
            "number_of_videos": 1,
            "aspect_ratio": aspect_ratio,
            "duration_seconds": duration,
            "person_generation": "allow_adult",
        }
        
        # Use GCS output if configured
        if settings.vertex_video_output_gcs_uri:
            config_kwargs["output_gcs_uri"] = settings.vertex_video_output_gcs_uri.rstrip("/") + "/"

        try:
            logger.info(f"Starting video generation: {model} with prompt: {prompt[:50]}...")
            client = _build_client()
            
            operation = await client.aio.models.generate_videos(
                model=model,
                prompt=prompt,
                image=source_image,
                config=types.GenerateVideosConfig(**config_kwargs),
            )

            # Poll for completion
            operation = await self._poll_video_operation(client, operation)
            
            if operation.error:
                raise RuntimeError(f"Vertex AI Veo failed: {operation.error}")

            result = operation.result or operation.response
            videos = getattr(result, "generated_videos", None) if result else None
            
            if not videos:
                raise RuntimeError("Vertex AI Veo returned no videos")

            video = videos[0].video
            if not video:
                raise RuntimeError("Vertex AI Veo response missing video payload")

            # Handle video bytes (in-memory)
            if video.video_bytes:
                mime_type = video.mime_type or "video/mp4"
                return {
                    "status": "success",
                    "video_url": encode_data_url(video.video_bytes, mime_type),
                    "model": model,
                    "provider": "vertex-ai",
                    "duration": float(duration),
                }

            # Handle GCS URI (download to local)
            if video.uri:
                local_path = await self._download_video_from_gcs(video.uri)
                video_duration = await get_video_duration(local_path)
                
                return {
                    "status": "success",
                    "video_url": encode_data_url(Path(local_path).read_bytes(), "video/mp4"),
                    "local_path": local_path,
                    "model": model,
                    "provider": "vertex-ai",
                    "duration": video_duration,
                }

            raise RuntimeError("Vertex AI Veo response had neither video bytes nor URI")
            
        except Exception as e:
            logger.error(f"Single video generation failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "model": model,
                "provider": "vertex-ai",
            }

    async def generate_long_form_video(
        self,
        base_prompt: str,
        duration_seconds: int = 180,
        style: str = "cinematic",
        payload_overrides: Optional[dict] = None,
    ) -> dict:
        """
        Generate a long-form video (3 minutes = 180 seconds) by batch-generating
        8-second clips and stitching them together.
        
        Args:
            base_prompt: Description of the overall video
            duration_seconds: Target duration (default: 180 for 3 minutes)
            style: Visual style for all scenes
            payload_overrides: Optional overrides for individual video generation
            
        Returns:
            {
                'status': 'success' | 'error',
                'video_url': str,
                'local_path': str,
                'total_scenes': int,
                'duration': float,
                'model': str,
                'provider': 'vertex-ai',
            }
        """
        settings = get_settings()
        
        if not settings.vertex_video_stitch_enabled:
            return {
                "status": "error",
                "message": "Video stitching is disabled",
                "provider": "vertex-ai",
            }

        try:
            # Calculate number of scenes
            num_scenes = calculate_video_scenes(duration_seconds)
            logger.info(f"Generating {num_scenes} scenes for {duration_seconds}s video")

            # Generate scene prompts
            scene_prompts = generate_scene_prompts(base_prompt, num_scenes, style)

            # Create output directory
            output_dir = Path(settings.vertex_video_output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Batch generate all clips
            video_clips = []
            failed_scenes = []
            
            for scene_num, scene_prompt in enumerate(scene_prompts, 1):
                try:
                    logger.info(f"Generating scene {scene_num}/{num_scenes}...")
                    
                    payload = {
                        "prompt": scene_prompt,
                        "duration": 8,
                        **(payload_overrides or {}),
                    }
                    
                    result = await self.generate_single_video(payload)
                    
                    if result["status"] != "success":
                        failed_scenes.append((scene_num, result.get("message", "Unknown error")))
                        continue

                    # Save clip to disk
                    clip_path = output_dir / f"scene_{scene_num:03d}.mp4"
                    
                    if "local_path" in result:
                        # Video already on disk, just track it
                        video_clips.append(result["local_path"])
                    else:
                        # Video in data URL, extract and save
                        video_bytes = decode_base64_payload(result["video_url"])
                        clip_path.write_bytes(video_bytes)
                        video_clips.append(str(clip_path))
                    
                    logger.info(f"Scene {scene_num} saved: {video_clips[-1]}")
                    
                except Exception as e:
                    logger.error(f"Failed to generate scene {scene_num}: {e}")
                    failed_scenes.append((scene_num, str(e)))
                    continue

            if not video_clips:
                return {
                    "status": "error",
                    "message": f"All {num_scenes} scenes failed to generate",
                    "provider": "vertex-ai",
                }

            if failed_scenes:
                logger.warning(
                    f"Generated {len(video_clips)}/{num_scenes} scenes. "
                    f"Failed scenes: {failed_scenes}"
                )

            # Stitch clips together
            stitched_path = output_dir / f"stitched_{duration_seconds}s.mp4"
            logger.info(f"Stitching {len(video_clips)} clips into {stitched_path}...")
            
            stitched_path = await stitch_videos(
                video_clips,
                str(stitched_path),
                codec="libx264",
                preset="medium",
            )

            # Get final video duration
            final_duration = await get_video_duration(stitched_path)

            # Cleanup temporary clips
            cleanup_video_files(video_clips)

            # Load stitched video
            video_bytes = Path(stitched_path).read_bytes()
            video_url = encode_data_url(video_bytes, "video/mp4")

            return {
                "status": "success",
                "video_url": video_url,
                "local_path": str(stitched_path),
                "total_scenes": len(video_clips),
                "failed_scenes": len(failed_scenes),
                "duration": final_duration,
                "model": settings.vertex_video_model,
                "provider": "vertex-ai",
            }

        except Exception as e:
            logger.error(f"Long-form video generation failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "provider": "vertex-ai",
            }

    async def _download_video_from_gcs(self, gcs_uri: str) -> str:
        """
        Download a video from GCS to local disk.
        
        Args:
            gcs_uri: GCS URI (gs://bucket-name/path)
            
        Returns:
            Local file path
        """
        settings = get_settings()
        
        try:
            bucket_name, object_path = parse_gcs_uri(gcs_uri)
            
            # Create local path
            output_dir = Path(settings.vertex_video_output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Use object name for local file
            filename = Path(object_path).name or "video.mp4"
            local_path = output_dir / filename
            
            # Download
            local_path = await download_video_from_gcs(
                gcs_uri,
                str(local_path),
                settings.google_cloud_project,
                settings.google_application_credentials,
            )
            
            logger.info(f"Downloaded GCS video: {gcs_uri} -> {local_path}")
            return local_path
            
        except Exception as e:
            logger.error(f"Failed to download video from GCS: {e}")
            raise

    async def _poll_video_operation(
        self,
        client: genai.Client,
        operation: Any,
    ) -> Any:
        """
        Poll a video generation operation until complete.
        
        Args:
            client: Vertex AI client
            operation: Operation to poll
            
        Returns:
            Completed operation
        """
        settings = get_settings()
        attempts = max(1, settings.vertex_video_poll_attempts)
        delay = max(1, settings.vertex_video_poll_seconds)

        logger.info(f"Polling video operation {operation.name} (max {attempts * delay}s)")
        
        for attempt in range(attempts):
            if operation.done:
                logger.info(f"Operation completed after {attempt} polls")
                return operation
            
            await asyncio.sleep(delay)
            operation = await client.aio.operations.get(operation)
            logger.debug(f"Poll attempt {attempt + 1}/{attempts}: operation.done={operation.done}")

        raise TimeoutError(
            f"Vertex AI Veo timed out after {attempts * delay}s waiting for video generation"
        )
