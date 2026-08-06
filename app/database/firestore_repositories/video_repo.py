"""
Firestore repository for video generation tracking.

Handles persistence of video generation jobs and metadata.
"""

import logging
from datetime import datetime
from typing import Optional, List

from app.database.firestore_db import db
from app.database.models.video_model import (
    VideoGenerationJob,
    VideoStatus,
    VideoGenerationHistory,
)

logger = logging.getLogger(__name__)

# Collection names
VIDEO_JOBS_COLLECTION = "video_generation_jobs"
VIDEO_HISTORY_COLLECTION = "video_generation_history"


class VideoRepository:
    """Repository for video generation data."""

    def create_job(self, job: VideoGenerationJob) -> bool:
        """
        Create a new video generation job.
        
        Args:
            job: VideoGenerationJob to create
            
        Returns:
            True if successful
        """
        try:
            db.collection(VIDEO_JOBS_COLLECTION).document(job.job_id).set(
                job.to_dict()
            )
            logger.info(f"Created video job: {job.job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create video job: {e}")
            return False

    def update_job(self, job_id: str, updates: dict) -> bool:
        """
        Update a video generation job.
        
        Args:
            job_id: Job identifier
            updates: Dictionary of fields to update
            
        Returns:
            True if successful
        """
        try:
            # Convert datetime objects to ISO strings
            for key, value in updates.items():
                if isinstance(value, datetime):
                    updates[key] = value.isoformat()
                elif isinstance(value, VideoStatus):
                    updates[key] = value.value
            
            db.collection(VIDEO_JOBS_COLLECTION).document(job_id).update(updates)
            logger.info(f"Updated video job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update video job {job_id}: {e}")
            return False

    def get_job(self, job_id: str) -> Optional[VideoGenerationJob]:
        """
        Get a video generation job by ID.
        
        Args:
            job_id: Job identifier
            
        Returns:
            VideoGenerationJob or None if not found
        """
        try:
            doc = db.collection(VIDEO_JOBS_COLLECTION).document(job_id).get()
            if doc.exists:
                return VideoGenerationJob.from_dict(doc.to_dict())
            return None
        except Exception as e:
            logger.error(f"Failed to get video job {job_id}: {e}")
            return None

    def get_user_jobs(self, user_id: str, limit: int = 50) -> List[VideoGenerationJob]:
        """
        Get all video generation jobs for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of jobs to return
            
        Returns:
            List of VideoGenerationJob objects
        """
        try:
            docs = db.collection(VIDEO_JOBS_COLLECTION) \
                .where('user_id', '==', user_id) \
                .order_by('created_at', direction='DESCENDING') \
                .limit(limit) \
                .stream()
            
            jobs = []
            for doc in docs:
                try:
                    job = VideoGenerationJob.from_dict(doc.to_dict())
                    jobs.append(job)
                except Exception as e:
                    logger.warning(f"Failed to parse video job: {e}")
            
            return jobs
        except Exception as e:
            logger.error(f"Failed to get user jobs for {user_id}: {e}")
            return []

    def get_jobs_by_status(
        self,
        status: VideoStatus,
        limit: int = 50
    ) -> List[VideoGenerationJob]:
        """
        Get all jobs with a specific status.
        
        Args:
            status: VideoStatus to filter by
            limit: Maximum number of jobs
            
        Returns:
            List of VideoGenerationJob objects
        """
        try:
            docs = db.collection(VIDEO_JOBS_COLLECTION) \
                .where('status', '==', status.value) \
                .limit(limit) \
                .stream()
            
            jobs = []
            for doc in docs:
                try:
                    job = VideoGenerationJob.from_dict(doc.to_dict())
                    jobs.append(job)
                except Exception as e:
                    logger.warning(f"Failed to parse video job: {e}")
            
            return jobs
        except Exception as e:
            logger.error(f"Failed to get jobs by status {status}: {e}")
            return []

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a video generation job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if successful
        """
        try:
            db.collection(VIDEO_JOBS_COLLECTION).document(job_id).delete()
            logger.info(f"Deleted video job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete video job {job_id}: {e}")
            return False

    def update_job_status(
        self,
        job_id: str,
        status: VideoStatus,
        **additional_updates
    ) -> bool:
        """
        Update job status with optional additional fields.
        
        Args:
            job_id: Job identifier
            status: New status
            **additional_updates: Other fields to update
            
        Returns:
            True if successful
        """
        updates = {'status': status.value}
        
        # Add timestamps based on status
        if status == VideoStatus.GENERATING:
            updates['started_at'] = datetime.now().isoformat()
        elif status in (VideoStatus.COMPLETED, VideoStatus.FAILED):
            updates['completed_at'] = datetime.now().isoformat()
        
        # Add additional updates
        updates.update(additional_updates)
        
        return self.update_job(job_id, updates)

    def record_clip_completion(
        self,
        job_id: str,
        clip_number: int,
        success: bool,
        **metadata
    ) -> bool:
        """
        Record the completion of a single clip generation.
        
        Args:
            job_id: Job identifier
            clip_number: Clip number (1-indexed)
            success: Whether clip generation succeeded
            **metadata: Additional metadata (gcs_uri, file_size, etc.)
            
        Returns:
            True if successful
        """
        try:
            job = self.get_job(job_id)
            if not job:
                return False
            
            # Update counts
            if success:
                job.clips_completed += 1
            else:
                job.clips_failed += 1
            
            # Record clip metadata
            clip_data = {
                'clip_number': clip_number,
                'success': success,
                'completed_at': datetime.now().isoformat(),
                **metadata
            }
            
            # Add to clips array
            if job.clips is None:
                job.clips = []
            job.clips.append(clip_data)
            
            # Update in Firestore
            updates = {
                'clips_completed': job.clips_completed,
                'clips_failed': job.clips_failed,
                'clips': job.clips,
            }
            
            return self.update_job(job_id, updates)
        except Exception as e:
            logger.error(f"Failed to record clip completion: {e}")
            return False

    # History management
    def get_or_create_history(self, user_id: str) -> VideoGenerationHistory:
        """
        Get or create video generation history for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            VideoGenerationHistory object
        """
        try:
            doc = db.collection(VIDEO_HISTORY_COLLECTION).document(user_id).get()
            if doc.exists:
                data = doc.to_dict()
                return VideoGenerationHistory(**data)
            else:
                # Create new history
                history = VideoGenerationHistory(user_id=user_id, job_ids=[])
                db.collection(VIDEO_HISTORY_COLLECTION).document(user_id).set(
                    history.to_dict()
                )
                return history
        except Exception as e:
            logger.error(f"Failed to get user history for {user_id}: {e}")
            return VideoGenerationHistory(user_id=user_id, job_ids=[])

    def add_job_to_history(self, user_id: str, job_id: str) -> bool:
        """
        Add a completed job to user history.
        
        Args:
            user_id: User identifier
            job_id: Job identifier
            
        Returns:
            True if successful
        """
        try:
            history_ref = db.collection(VIDEO_HISTORY_COLLECTION).document(user_id)
            history_ref.update({
                'job_ids': [job_id],  # Will be appended by Firebase
                'last_generation_at': datetime.now().isoformat(),
            })
            return True
        except Exception as e:
            logger.error(f"Failed to add job to history: {e}")
            return False


# Global instance
video_repo = VideoRepository()
