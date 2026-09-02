from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class NotificationType(str, Enum):
    TASK_COMPLETION = "TASK_COMPLETION"
    ENGAGEMENT = "ENGAGEMENT"
    FEATURE_ANNOUNCEMENT = "FEATURE_ANNOUNCEMENT"


class NotificationPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SendNotificationRequest(BaseModel):
    """Request to send a notification to a user"""
    user_id: str = Field(..., description="Target user ID")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    notification_type: NotificationType = Field(
        ...,
        description="Type of notification"
    )
    priority: NotificationPriority = Field(
        default=NotificationPriority.MEDIUM,
        description="Notification priority level"
    )
    image_url: Optional[str] = Field(
        default=None,
        description="Optional image URL for notification"
    )
    action_url: Optional[str] = Field(
        default=None,
        description="Optional deep link URL"
    )
    data: Optional[dict] = Field(
        default=None,
        description="Optional custom data payload"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-123",
                "title": "✅ Task Complete",
                "message": "Your AI video generation is ready!",
                "notification_type": "TASK_COMPLETION",
                "priority": "HIGH",
                "image_url": "https://example.com/image.jpg",
                "action_url": "lumora://task/task-123",
                "data": {
                    "task_id": "task-123",
                    "estimated_size_mb": "256"
                }
            }
        }


class SendNotificationResponse(BaseModel):
    """Response after sending notification"""
    status: str = "success"
    message: str = "Notification sent successfully"
    notification_id: Optional[str] = None
    user_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BroadcastNotificationRequest(BaseModel):
    """Request to send notification to multiple users"""
    user_ids: list[str] = Field(..., description="List of user IDs")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    notification_type: NotificationType
    priority: NotificationPriority = NotificationPriority.MEDIUM
    image_url: Optional[str] = None
    action_url: Optional[str] = None
    data: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_ids": ["user-1", "user-2", "user-3"],
                "title": "🎉 New Feature Available",
                "message": "We've launched real-time video editing!",
                "notification_type": "FEATURE_ANNOUNCEMENT",
                "priority": "MEDIUM"
            }
        }


class BroadcastNotificationResponse(BaseModel):
    """Response after broadcast notification"""
    status: str = "success"
    message: str
    total_users: int
    successful: int
    failed: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SegmentedNotificationRequest(BaseModel):
    """Request to send notification to users matching criteria"""
    segment: str = Field(..., description="User segment/tag (e.g., 'premium', 'free_trial')")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    notification_type: NotificationType
    priority: NotificationPriority = NotificationPriority.MEDIUM
    image_url: Optional[str] = None
    action_url: Optional[str] = None
    data: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "segment": "premium",
                "title": "🎁 Premium Feature",
                "message": "Exclusive access to advanced AI models",
                "notification_type": "FEATURE_ANNOUNCEMENT",
                "priority": "HIGH"
            }
        }


class NotificationStatusUpdate(BaseModel):
    """Request to update notification status"""
    notification_id: str = Field(..., description="Notification ID")
    is_read: bool = Field(..., description="Mark as read/unread")


class NotificationStatusResponse(BaseModel):
    """Response for notification status update"""
    status: str = "success"
    notification_id: str
    is_read: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class UserNotificationPreferences(BaseModel):
    """User notification preferences"""
    user_id: str
    notifications_enabled: bool = True
    task_completion_notifications: bool = True
    engagement_notifications: bool = True
    feature_announcement_notifications: bool = True
    sound_enabled: bool = True
    vibration_enabled: bool = True
    do_not_disturb_enabled: bool = False
    do_not_disturb_start_hour: int = 22
    do_not_disturb_end_hour: int = 8
    notification_frequency: str = "instant"  # "instant", "daily", "weekly"
    max_notifications_per_day: int = 20


class UpdatePreferencesRequest(BaseModel):
    """Request to update notification preferences"""
    notifications_enabled: Optional[bool] = None
    task_completion_notifications: Optional[bool] = None
    engagement_notifications: Optional[bool] = None
    feature_announcement_notifications: Optional[bool] = None
    sound_enabled: Optional[bool] = None
    vibration_enabled: Optional[bool] = None
    do_not_disturb_enabled: Optional[bool] = None
    do_not_disturb_start_hour: Optional[int] = None
    do_not_disturb_end_hour: Optional[int] = None
    notification_frequency: Optional[str] = None
    max_notifications_per_day: Optional[int] = None


class HealthCheckResponse(BaseModel):
    """Notification service health check"""
    status: str = "healthy"
    service: str = "notification_service"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
