"""
Batch video processing worker for handling multiple video generation requests.

Supports:
- Queue-based video generation
- Parallel clip generation
- Progress tracking
- Failure recovery
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class VideoBatchJob:
    """Represents a batch video generation job."""

    def __init__(
        self,
        job_id: str,
        user_id: str,
        base_prompt: str,
        num_clips: int,
        duration_seconds: int = 180,
        style: str = "cinematic",
    ):
        self.job_id = job_id
        self.user_id = user_id
        self.base_prompt = base_prompt
        self.num_clips = num_clips
        self.duration_seconds = duration_seconds
        self.style = style
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        
        # Progress tracking
        self.total_clips = num_clips
        self.completed_clips = 0
        self.failed_clips = 0
        self.clip_files: list[str] = []
        self.stitched_file: Optional[str] = None
        
        # Status
        self.status = "queued"  # queued, generating, stitching, completed, failed
        self.error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": {
                "total_clips": self.total_clips,
                "completed_clips": self.completed_clips,
                "failed_clips": self.failed_clips,
                "progress_percent": (self.completed_clips / self.total_clips * 100) if self.total_clips > 0 else 0,
            },
            "output": {
                "stitched_file": self.stitched_file,
                "total_clips": len(self.clip_files),
            },
            "error_message": self.error_message,
        }


class VideoBatchProcessor:
    """
    Processes video generation jobs in a queue with progress tracking.
    
    Supports:
    - Sequential and parallel processing
    - Progress callbacks
    - Failure handling and recovery
    - Job persistence
    """

    def __init__(self, max_parallel_jobs: int = 1):
        """
        Initialize batch processor.
        
        Args:
            max_parallel_jobs: Maximum concurrent video generation jobs
        """
        self.max_parallel_jobs = max_parallel_jobs
        self.job_queue: list[VideoBatchJob] = []
        self.active_jobs: dict[str, VideoBatchJob] = {}
        self.completed_jobs: dict[str, VideoBatchJob] = {}
        self.progress_callbacks: dict[str, list[Callable]] = {}
        self.lock = asyncio.Lock()

    def add_job(
        self,
        job_id: str,
        user_id: str,
        base_prompt: str,
        num_clips: int,
        duration_seconds: int = 180,
        style: str = "cinematic",
    ) -> VideoBatchJob:
        """
        Add a new video generation job to the queue.
        
        Args:
            job_id: Unique job identifier
            user_id: User requesting the generation
            base_prompt: Base description for video
            num_clips: Number of clips to generate
            duration_seconds: Total video duration
            style: Visual style
            
        Returns:
            Created job object
        """
        job = VideoBatchJob(
            job_id=job_id,
            user_id=user_id,
            base_prompt=base_prompt,
            num_clips=num_clips,
            duration_seconds=duration_seconds,
            style=style,
        )
        
        self.job_queue.append(job)
        logger.info(f"Added job {job_id}: {num_clips} clips for user {user_id}")
        
        return job

    def register_progress_callback(
        self,
        job_id: str,
        callback: Callable[[VideoBatchJob], None],
    ) -> None:
        """
        Register a callback for job progress updates.
        
        Args:
            job_id: Job to track
            callback: Async function to call on progress
        """
        if job_id not in self.progress_callbacks:
            self.progress_callbacks[job_id] = []
        self.progress_callbacks[job_id].append(callback)

    async def _notify_progress(self, job: VideoBatchJob) -> None:
        """Notify all progress callbacks for a job."""
        callbacks = self.progress_callbacks.get(job.job_id, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(job)
                else:
                    callback(job)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    async def get_job_status(self, job_id: str) -> Optional[VideoBatchJob]:
        """
        Get current status of a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job object or None if not found
        """
        # Check active jobs
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]
        
        # Check completed jobs
        if job_id in self.completed_jobs:
            return self.completed_jobs[job_id]
        
        # Check queue
        for job in self.job_queue:
            if job.job_id == job_id:
                return job
        
        return None

    async def process_next_job(
        self,
        video_generator: Callable,
    ) -> Optional[VideoBatchJob]:
        """
        Process the next job in queue.
        
        Args:
            video_generator: Async function to generate individual clips
                            Expected signature: async def generate(prompt) -> dict
            
        Returns:
            Processed job or None if queue empty
        """
        async with self.lock:
            if not self.job_queue:
                return None
            
            # Check if we can start a new job
            if len(self.active_jobs) >= self.max_parallel_jobs:
                return None
            
            job = self.job_queue.pop(0)
            self.active_jobs[job.job_id] = job

        try:
            job.status = "generating"
            job.started_at = datetime.now()
            logger.info(f"Starting job {job.job_id}")
            
            await self._notify_progress(job)

            # Generate scene prompts
            from app.providers.video_stitch import generate_scene_prompts
            
            prompts = generate_scene_prompts(
                job.base_prompt,
                job.total_clips,
                job.style,
            )

            # Generate all clips
            for clip_num, prompt in enumerate(prompts, 1):
                try:
                    logger.info(f"Generating clip {clip_num}/{job.total_clips} for job {job.job_id}")
                    
                    result = await video_generator(prompt)
                    
                    if result.get("status") == "success":
                        if "local_path" in result:
                            job.clip_files.append(result["local_path"])
                        job.completed_clips += 1
                    else:
                        job.failed_clips += 1
                        logger.warning(f"Clip {clip_num} failed: {result.get('message')}")
                    
                    await self._notify_progress(job)
                    
                except Exception as e:
                    logger.error(f"Error generating clip {clip_num}: {e}")
                    job.failed_clips += 1
                    await self._notify_progress(job)

            # Stitch videos if all clips generated
            if job.clip_files:
                job.status = "stitching"
                await self._notify_progress(job)
                
                try:
                    from app.providers.video_stitch import stitch_videos
                    
                    output_path = f"./generated_videos/stitched_{job.job_id}.mp4"
                    
                    stitched = await stitch_videos(
                        job.clip_files,
                        output_path,
                        codec="libx264",
                        preset="medium",
                    )
                    
                    job.stitched_file = stitched
                    job.status = "completed"
                    job.completed_at = datetime.now()
                    
                except Exception as e:
                    logger.error(f"Error stitching videos: {e}")
                    job.status = "failed"
                    job.error_message = str(e)
            else:
                job.status = "failed"
                job.error_message = "No clips generated"

            # Move to completed
            async with self.lock:
                del self.active_jobs[job.job_id]
                self.completed_jobs[job.job_id] = job

            await self._notify_progress(job)
            logger.info(f"Job {job.job_id} completed: {job.status}")

            return job

        except Exception as e:
            logger.error(f"Error processing job {job.job_id}: {e}")
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now()
            
            async with self.lock:
                del self.active_jobs[job.job_id]
                self.completed_jobs[job.job_id] = job
            
            await self._notify_progress(job)
            return job

    async def process_all_queued(
        self,
        video_generator: Callable,
    ) -> list[VideoBatchJob]:
        """
        Process all queued jobs.
        
        Args:
            video_generator: Async function to generate clips
            
        Returns:
            List of processed jobs
        """
        processed = []
        
        while True:
            job = await self.process_next_job(video_generator)
            if job is None:
                await asyncio.sleep(1)
                if not self.job_queue and not self.active_jobs:
                    break
                continue
            
            processed.append(job)
        
        return processed

    def get_queue_stats(self) -> dict:
        """Get statistics about queue."""
        return {
            "queued": len(self.job_queue),
            "active": len(self.active_jobs),
            "completed": len(self.completed_jobs),
            "total": len(self.job_queue) + len(self.active_jobs) + len(self.completed_jobs),
        }

    def export_job_to_json(self, job_id: str, filepath: str) -> bool:
        """Export job details to JSON file."""
        job = asyncio.run(self.get_job_status(job_id))
        if not job:
            return False
        
        try:
            Path(filepath).write_text(json.dumps(job.to_dict(), indent=2))
            return True
        except Exception as e:
            logger.error(f"Failed to export job {job_id}: {e}")
            return False


# Global processor instance
_processor: Optional[VideoBatchProcessor] = None


def get_batch_processor() -> VideoBatchProcessor:
    """Get or create global batch processor."""
    global _processor
    if _processor is None:
        _processor = VideoBatchProcessor(max_parallel_jobs=1)
    return _processor
