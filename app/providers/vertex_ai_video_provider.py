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

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    types = None

from app.core.config import get_settings
from app.core.credentials import load_vertex_credentials_from_settings
from app.providers.gcs_utils import download_video_from_gcs, parse_gcs_uri
from app.providers.media_utils import clamp_veo_duration, decode_base64_payload, encode_data_url, resolve_veo_model
from app.providers.video_stitch import (
    calculate_video_scenes,
    cleanup_video_files,
    generate_scene_prompts,
    get_video_duration,
    stitch_videos,
    validate_video_file,
)

logger = logging.getLogger(__name__)


def _build_client():
    """Build Vertex AI client."""
    if not GENAI_AVAILABLE:
        raise RuntimeError("google-generativeai package not available")
    
    settings = get_settings()
    if not settings.google_cloud_project:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT is not configured. Set it in backend/.env to use Vertex AI."
        )

    credentials = load_vertex_credentials_from_settings()

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
                'status': 'success',
                'video_url': str,  # data URL or GCS URL
                'model': str,
                'provider': 'vertex-ai',
                'duration': float,  # actual video duration
                'file_size_mb': float
            }
        """
        if not GENAI_AVAILABLE:
            raise RuntimeError("Vertex AI Video provider requires google-generativeai package")
        
        settings = get_settings()
        model = resolve_veo_model(payload.get("model"), settings.vertex_video_model)
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

            payload = await self._resolve_completed_video(
                operation=operation,
                settings=settings,
                model=model,
                duration=duration,
            )
            if payload is not None:
                return payload

            result = operation.result or operation.response
            logger.error(
                "Vertex AI Veo completed without video artifacts. operation=%s result=%r",
                getattr(operation, "name", "unknown"),
                result,
            )
            raise RuntimeError(
                "Vertex AI Veo returned no videos. The job finished but produced no output — "
                "try a simpler prompt, switch to FastDraft, or retry in a moment."
            )
            
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
                'file_size_mb': float
            }
        """
        if not GENAI_AVAILABLE:
            raise RuntimeError("Vertex AI Video provider requires google-generativeai package")
        
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

    async def _resolve_completed_video(
        self,
        *,
        operation: Any,
        settings: Any,
        model: str,
        duration: int,
    ) -> Optional[dict]:
        """Resolve inline bytes or GCS URI from a completed Veo operation."""
        result = operation.result or operation.response
        videos = getattr(result, "generated_videos", None) if result else None

        if videos:
            video = videos[0].video
            if not video:
                raise RuntimeError("Vertex AI Veo response missing video payload")

            if video.video_bytes:
                mime_type = video.mime_type or "video/mp4"
                return {
                    "status": "success",
                    "video_url": encode_data_url(video.video_bytes, mime_type),
                    "model": model,
                    "provider": "vertex-ai",
                    "duration": float(duration),
                }

            if video.uri:
                return await self._video_result_from_gcs_uri(
                    video.uri,
                    model=model,
                    duration=duration,
                )

            raise RuntimeError("Vertex AI Veo response had neither video bytes nor URI")

        if settings.vertex_video_output_gcs_uri:
            gcs_uri = await self._find_latest_gcs_video(settings)
            if gcs_uri:
                logger.info("Recovered Veo output from GCS fallback: %s", gcs_uri)
                return await self._video_result_from_gcs_uri(
                    gcs_uri,
                    model=model,
                    duration=duration,
                )

        return None

    async def _video_result_from_gcs_uri(
        self,
        gcs_uri: str,
        *,
        model: str,
        duration: int,
    ) -> dict:
        local_path = await self._download_video_from_gcs(gcs_uri)
        video_duration = await get_video_duration(local_path)
        return {
            "status": "success",
            "video_url": encode_data_url(Path(local_path).read_bytes(), "video/mp4"),
            "local_path": local_path,
            "model": model,
            "provider": "vertex-ai",
            "duration": video_duration,
        }

    async def _find_latest_gcs_video(self, settings: Any) -> Optional[str]:
        """Pick the newest video object under the configured Veo output prefix."""
        gcs_folder = settings.vertex_video_output_gcs_uri.rstrip("/") + "/"
        try:
            from google.cloud import storage

            bucket_name, folder_path = parse_gcs_uri(gcs_folder)

            def _latest_uri() -> Optional[str]:
                client = storage.Client(
                    project=settings.google_cloud_project,
                    credentials=load_vertex_credentials_from_settings(),
                )
                bucket = client.bucket(bucket_name)
                latest_blob = None
                for blob in bucket.list_blobs(prefix=folder_path):
                    if not blob.name.lower().endswith((".mp4", ".webm", ".mov")):
                        continue
                    if latest_blob is None or blob.updated > latest_blob.updated:
                        latest_blob = blob
                if latest_blob is None:
                    return None
                return f"gs://{bucket_name}/{latest_blob.name}"

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _latest_uri)
        except Exception as exc:
            logger.warning("GCS fallback lookup failed for %s: %s", gcs_folder, exc)
            return None

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
        client: Any,
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
