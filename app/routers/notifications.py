from fastapi import APIRouter, HTTPException, Depends, status
from typing import Optional
import logging

from app.services.notification_service import (
    list_notifications,
    send_notification,
    broadcast_notification,
    send_segmented_notification,
    update_notification_status,
    get_user_preferences,
    update_user_preferences,
)
from app.schemas.notifications import (
    SendNotificationRequest,
    SendNotificationResponse,
    BroadcastNotificationRequest,
    BroadcastNotificationResponse,
    SegmentedNotificationRequest,
    NotificationStatusUpdate,
    NotificationStatusResponse,
    UpdatePreferencesRequest,
    UserNotificationPreferences,
    HealthCheckResponse,
)
from app.schemas.common import ApiResponse, ErrorResponse

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Notification Sending Endpoints ============

@router.post(
    "/send",
    response_model=SendNotificationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
async def send_notification_endpoint(request: SendNotificationRequest):
    """
    Send a notification to a specific user.
    
    - **user_id**: Target user ID
    - **title**: Notification title (max 100 chars)
    - **message**: Notification message (max 500 chars)
    - **notification_type**: Type of notification (TASK_COMPLETION, ENGAGEMENT, FEATURE_ANNOUNCEMENT)
    - **priority**: Priority level (HIGH, MEDIUM, LOW)
    - **image_url**: Optional image URL
    - **action_url**: Optional deep link (e.g., lumora://task/123)
    - **data**: Optional custom data object
    """
    try:
        # Validate request
        if not request.user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        if not request.title:
            raise HTTPException(status_code=400, detail="title is required")
        if not request.message:
            raise HTTPException(status_code=400, detail="message is required")

        result = await send_notification(request)
        return SendNotificationResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send notification"
        )


@router.post(
    "/broadcast",
    response_model=BroadcastNotificationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
async def broadcast_notification_endpoint(request: BroadcastNotificationRequest):
    """
    Send a notification to multiple users.
    
    - **user_ids**: List of target user IDs
    - **title**: Notification title
    - **message**: Notification message
    - **notification_type**: Type of notification
    - **priority**: Priority level
    - **image_url**: Optional image URL
    - **action_url**: Optional deep link
    - **data**: Optional custom data
    """
    try:
        if not request.user_ids or len(request.user_ids) == 0:
            raise HTTPException(status_code=400, detail="At least one user_id is required")

        result = await broadcast_notification(request)
        return BroadcastNotificationResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in broadcast: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to broadcast notification"
        )


@router.post(
    "/segment",
    response_model=BroadcastNotificationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
async def send_segmented_notification_endpoint(request: SegmentedNotificationRequest):
    """
    Send a notification to users matching a segment/tag.
    
    - **segment**: User segment (e.g., 'premium', 'free_trial', 'inactive')
    - **title**: Notification title
    - **message**: Notification message
    - **notification_type**: Type of notification
    - **priority**: Priority level
    - **image_url**: Optional image URL
    - **action_url**: Optional deep link
    - **data**: Optional custom data
    """
    try:
        if not request.segment:
            raise HTTPException(status_code=400, detail="segment is required")

        result = await send_segmented_notification(request)
        return BroadcastNotificationResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in segmented notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send segmented notification"
        )


# ============ Notification Management Endpoints ============

@router.get("", response_model=dict)
async def get_notifications():
    """
    Get all notifications.
    
    Returns a list of all notifications in the system.
    """
    try:
        notifications = await list_notifications()
        return {
            "status": "success",
            "items": notifications,
            "count": len(notifications)
        }
    except Exception as e:
        logger.error(f"Error fetching notifications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch notifications"
        )


@router.put(
    "/{notification_id}/status",
    response_model=NotificationStatusResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
async def update_notification_status_endpoint(
    notification_id: str,
    request: NotificationStatusUpdate,
    user_id: str = None  # In production, get from auth token
):
    """
    Update notification status (mark as read/unread).
    
    - **notification_id**: ID of notification to update
    - **is_read**: Boolean indicating if notification is read
    """
    try:
        result = await update_notification_status(notification_id, request.is_read, user_id)
        return NotificationStatusResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating notification status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification status"
        )


# ============ Preferences Endpoints ============

@router.get(
    "/preferences/{user_id}",
    response_model=dict,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    }
)
async def get_notification_preferences(user_id: str):
    """
    Get notification preferences for a user.
    
    - **user_id**: Target user ID
    """
    try:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        preferences = await get_user_preferences(user_id)
        return {
            "status": "success",
            "data": preferences
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch preferences"
        )


@router.put(
    "/preferences/{user_id}",
    response_model=dict,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
async def update_notification_preferences(
    user_id: str,
    request: UpdatePreferencesRequest
):
    """
    Update notification preferences for a user.
    
    - **user_id**: Target user ID
    - **body**: Preferences to update (all fields are optional)
    """
    try:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        # Build preferences dict with only provided values
        preferences = request.dict(exclude_unset=True)
        
        result = await update_user_preferences(user_id, preferences)
        return {
            "status": result["status"],
            "message": result["message"],
            "data": {"user_id": user_id, **preferences}
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )


# ============ Health & Status Endpoints ============

@router.get(
    "/health",
    response_model=HealthCheckResponse,
    tags=["health"]
)
async def notification_service_health():
    """
    Check notification service health status.
    """
    return HealthCheckResponse()


@router.get("", response_model=dict)
async def notifications_route():
    """
    Get all notifications (legacy endpoint).
    """
    return {"status": "success", "items": await list_notifications()}

