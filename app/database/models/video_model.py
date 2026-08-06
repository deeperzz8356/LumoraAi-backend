"""
Firestore models for video generation tracking.

Stores metadata about generated videos for:
- Progress tracking
- History
- Analytics
- Retry/recovery
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List
from enum import Enum


class VideoStatus(str, Enum):
    """Video generation status."""
    QUEUED = "queued"
    GENERATING = "generating"
    STITCHING = "stitching"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class VideoClipMetadata:
    """Metadata for a single generated video clip."""
    clip_id: str
    scene_number: int
    prompt: str
    status: str  # "pending", "completed", "failed"
    gcs_uri: Optional[str] = None
    local_path: Optional[str] = None
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    error_message: Optional[str] = None
    created_at: datetime = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary for Firestore."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat() if self.created_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return data


@dataclass
class VideoGenerationJob:
    """Firestore document for video generation job."""
    
    # Identifiers
    job_id: str
    user_id: str
    
    # Content
    base_prompt: str
    style: str = "cinematic"
    
    # Configuration
    target_duration_seconds: int = 180
    num_clips: int = 23
    model: str = "veo-3.1-fast-generate-001"
    
    # Status tracking
    status: VideoStatus = VideoStatus.QUEUED
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Progress
    clips_completed: int = 0
    clips_failed: int = 0
    clips: List[dict] = None  # List of VideoClipMetadata as dicts
    
    # Output
    stitched_file_path: Optional[str] = None
    stitched_file_gcs_uri: Optional[str] = None
    final_duration_seconds: float = 0.0
    total_file_size_bytes: int = 0
    
    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = 0
    last_error_at: Optional[datetime] = None
    
    # Metadata
    credit_cost: int = 0  # Credits spent
    generation_time_seconds: int = 0
    notes: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.clips is None:
            self.clips = []

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.num_clips == 0:
            return 0.0
        return (self.clips_completed / self.num_clips) * 100

    @property
    def is_completed(self) -> bool:
        """Check if job is fully completed."""
        return self.status == VideoStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if job has failed."""
        return self.status == VideoStatus.FAILED

    def to_dict(self) -> dict:
        """Convert to dictionary for Firestore."""
        data = {
            'job_id': self.job_id,
            'user_id': self.user_id,
            'base_prompt': self.base_prompt,
            'style': self.style,
            'target_duration_seconds': self.target_duration_seconds,
            'num_clips': self.num_clips,
            'model': self.model,
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'clips_completed': self.clips_completed,
            'clips_failed': self.clips_failed,
            'clips': self.clips,
            'stitched_file_path': self.stitched_file_path,
            'stitched_file_gcs_uri': self.stitched_file_gcs_uri,
            'final_duration_seconds': self.final_duration_seconds,
            'total_file_size_bytes': self.total_file_size_bytes,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'last_error_at': self.last_error_at.isoformat() if self.last_error_at else None,
            'credit_cost': self.credit_cost,
            'generation_time_seconds': self.generation_time_seconds,
            'notes': self.notes,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'VideoGenerationJob':
        """Create from Firestore document."""
        # Convert ISO strings back to datetime
        if data.get('created_at'):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('started_at'):
            data['started_at'] = datetime.fromisoformat(data['started_at'])
        if data.get('completed_at'):
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        if data.get('last_error_at'):
            data['last_error_at'] = datetime.fromisoformat(data['last_error_at'])
        
        # Convert status string to enum
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = VideoStatus(data['status'])
        
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class VideoGenerationHistory:
    """User's video generation history."""
    user_id: str
    job_ids: List[str]  # References to VideoGenerationJob documents
    total_videos_generated: int = 0
    total_credits_spent: int = 0
    total_generation_time_seconds: int = 0
    average_quality_rating: float = 0.0
    last_generation_at: Optional[datetime] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary for Firestore."""
        return {
            'user_id': self.user_id,
            'job_ids': self.job_ids,
            'total_videos_generated': self.total_videos_generated,
            'total_credits_spent': self.total_credits_spent,
            'total_generation_time_seconds': self.total_generation_time_seconds,
            'average_quality_rating': self.average_quality_rating,
            'last_generation_at': self.last_generation_at.isoformat() if self.last_generation_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
