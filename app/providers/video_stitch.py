"""
Video stitching utilities for concatenating multiple 8-second clips into longer videos.
Handles batch video generation for 3-minute (180-second) content.
"""

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def create_concat_demuxer_file(video_files: list[str]) -> str:
    """
    Create FFmpeg concat demuxer file for stitching videos.
    
    Args:
        video_files: List of absolute paths to video files (in order)
        
    Returns:
        Path to temporary concat file
    """
    concat_content = "\n".join([f"file '{Path(f).absolute()}'" for f in video_files])
    
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        delete=False,
        prefix="ffmpeg_concat_"
    ) as f:
        f.write(concat_content)
        concat_file = f.name
    
    logger.info(f"Created FFmpeg concat file: {concat_file}")
    logger.debug(f"Concat content:\n{concat_content}")
    return concat_file


async def stitch_videos(
    video_files: list[str],
    output_path: str,
    codec: str = "libx264",
    preset: str = "medium",
) -> str:
    """
    Stitch multiple video files into a single output video.
    
    Uses FFmpeg concat demuxer for fast, lossless concatenation.
    
    Args:
        video_files: List of video file paths (in order)
        output_path: Path where stitched video will be saved
        codec: Video codec to use (default: libx264 for H.264)
        preset: FFmpeg preset for speed/quality tradeoff
                faster options: ultrafast, superfast, veryfast, fast
                slower options: slow, slower, veryslow
        
    Returns:
        Path to stitched video file
        
    Raises:
        RuntimeError: If stitching fails
    """
    if not video_files:
        raise ValueError("No video files provided for stitching")
    
    if len(video_files) == 1:
        logger.info("Only one video file; returning as-is without stitching")
        return video_files[0]
    
    try:
        # Create output directory
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Create concat demuxer file
        concat_file = create_concat_demuxer_file(video_files)
        
        # Build FFmpeg command
        # Using concat demuxer with copy codec for fast stitching (re-encodes video to target codec)
        cmd = [
            "ffmpeg",
            "-f", "concat",           # Input format: concat demuxer
            "-safe", "0",             # Allow absolute paths
            "-i", concat_file,        # Input concat file
            "-c:v", codec,            # Video codec
            "-preset", preset,        # Encoding preset
            "-c:a", "aac",            # Audio codec
            "-b:a", "128k",           # Audio bitrate
            "-y",                     # Overwrite output
            output_path,              # Output file
        ]
        
        logger.info(f"Starting video stitching: {len(video_files)} clips -> {output_path}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        # Run FFmpeg in executor to avoid blocking
        loop = asyncio.get_event_loop()
        
        def _run_ffmpeg():
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFmpeg error output:\n{stderr}")
                raise RuntimeError(f"FFmpeg failed with code {process.returncode}: {stderr}")
            
            return output_path
        
        result = await loop.run_in_executor(None, _run_ffmpeg)
        
        logger.info(f"Video stitching complete: {result}")
        logger.info(f"Output file size: {Path(result).stat().st_size / (1024**2):.2f} MB")
        
        return result
        
    except Exception as e:
        logger.error(f"Video stitching failed: {e}")
        raise RuntimeError(f"Failed to stitch videos: {e}") from e
    
    finally:
        # Cleanup concat file
        try:
            Path(concat_file).unlink()
            logger.debug(f"Cleaned up concat file: {concat_file}")
        except Exception as e:
            logger.warning(f"Failed to cleanup concat file: {e}")


async def validate_video_file(filepath: str) -> bool:
    """
    Validate that a file is a valid video using FFmpeg.
    
    Args:
        filepath: Path to video file to validate
        
    Returns:
        True if file is valid video, False otherwise
    """
    try:
        loop = asyncio.get_event_loop()
        
        def _validate():
            cmd = [
                "ffmpeg",
                "-v", "error",
                "-i", filepath,
                "-f", "null",
                "-",
            ]
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return process.returncode == 0
        
        result = await loop.run_in_executor(None, _validate)
        return result
        
    except Exception as e:
        logger.error(f"Video validation failed for {filepath}: {e}")
        return False


async def get_video_duration(filepath: str) -> float:
    """
    Get duration of a video file in seconds.
    
    Args:
        filepath: Path to video file
        
    Returns:
        Duration in seconds
    """
    try:
        loop = asyncio.get_event_loop()
        
        def _get_duration():
            cmd = [
                "ffmpeg",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1:nokey=1",
                "-i", filepath,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return float(result.stdout.strip()) if result.stdout.strip() else 0.0
        
        duration = await loop.run_in_executor(None, _get_duration)
        logger.info(f"Video duration: {filepath} = {duration:.2f}s")
        return duration
        
    except Exception as e:
        logger.error(f"Failed to get video duration for {filepath}: {e}")
        return 0.0


def cleanup_video_files(filepaths: list[str]) -> None:
    """
    Clean up temporary video files.
    
    Args:
        filepaths: List of file paths to delete
    """
    for filepath in filepaths:
        try:
            Path(filepath).unlink()
            logger.info(f"Deleted video file: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to delete video file {filepath}: {e}")


# Scene prompt template for batch video generation
SCENE_PROMPT_TEMPLATE = """
{base_description}

Scene {scene_num}/{total_scenes}
Duration: 8 seconds
Style: {style}
Technical requirements: 16:9 aspect ratio, cinematic quality, smooth transitions
"""


def generate_scene_prompts(
    base_description: str,
    num_scenes: int,
    style: str = "cinematic",
) -> list[str]:
    """
    Generate sequential scene prompts for batch video generation.
    
    Args:
        base_description: Master description of the overall video
        num_scenes: Number of 8-second scenes (typically 23 for 3-minute video)
        style: Visual style for all scenes
        
    Returns:
        List of scene-specific prompts
    """
    prompts = []
    for i in range(1, num_scenes + 1):
        prompt = SCENE_PROMPT_TEMPLATE.format(
            base_description=base_description,
            scene_num=i,
            total_scenes=num_scenes,
            style=style,
        ).strip()
        prompts.append(prompt)
    
    logger.info(f"Generated {num_scenes} scene prompts")
    return prompts


def calculate_video_scenes(duration_seconds: int = 180) -> int:
    """
    Calculate number of 8-second scenes needed for target duration.
    
    Args:
        duration_seconds: Target video duration (default: 180 for 3 minutes)
        
    Returns:
        Number of 8-second scenes needed
    """
    # Each Veo 3.1 clip is 8 seconds, add 1 for overhead
    scenes = (duration_seconds // 8) + 1
    logger.info(f"For {duration_seconds}s video, need {scenes} x 8s scenes")
    return scenes
