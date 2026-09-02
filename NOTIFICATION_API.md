# Notification API Documentation

Complete API reference for the LumoraAI notification system.

## Base URL

```
/api/v1/notifications
```

## Authentication

All endpoints require authentication (Bearer token in Authorization header).

## Endpoints

### 1. Send Notification to Single User

**POST** `/send`

Send a notification to a specific user via OneSignal.

#### Request Body

```json
{
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
```

#### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | string | ✅ | Target user ID |
| title | string | ✅ | Notification title (max 100 chars) |
| message | string | ✅ | Notification message (max 500 chars) |
| notification_type | enum | ✅ | Type: `TASK_COMPLETION`, `ENGAGEMENT`, `FEATURE_ANNOUNCEMENT` |
| priority | enum | ❌ | Priority level: `HIGH`, `MEDIUM` (default), `LOW` |
| image_url | string | ❌ | Optional image URL for notification |
| action_url | string | ❌ | Optional deep link (e.g., `lumora://task/123`) |
| data | object | ❌ | Optional custom data payload |

#### Response (201 Created)

```json
{
  "status": "success",
  "message": "Notification sent successfully",
  "notification_id": "notif_1234567890",
  "user_id": "user-123",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### Error Responses

| Status | Error | Description |
|--------|-------|-------------|
| 400 | Bad Request | Missing required fields |
| 500 | Server Error | Failed to send notification |

#### Example Usage

```python
import requests

url = "http://localhost:8000/api/v1/notifications/send"
headers = {"Authorization": "Bearer YOUR_TOKEN"}

payload = {
    "user_id": "user-123",
    "title": "✅ Task Complete",
    "message": "Your AI video is ready!",
    "notification_type": "TASK_COMPLETION",
    "priority": "HIGH",
    "action_url": "lumora://task/task-123"
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

---

### 2. Broadcast Notification to Multiple Users

**POST** `/broadcast`

Send the same notification to multiple users.

#### Request Body

```json
{
  "user_ids": ["user-1", "user-2", "user-3"],
  "title": "🎉 New Feature Available",
  "message": "We've launched real-time video editing!",
  "notification_type": "FEATURE_ANNOUNCEMENT",
  "priority": "MEDIUM"
}
```

#### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| user_ids | array | ✅ | List of user IDs |
| title | string | ✅ | Notification title |
| message | string | ✅ | Notification message |
| notification_type | enum | ✅ | Notification type |
| priority | enum | ❌ | Priority level (default: MEDIUM) |
| image_url | string | ❌ | Optional image URL |
| action_url | string | ❌ | Optional deep link |
| data | object | ❌ | Optional custom data |

#### Response (201 Created)

```json
{
  "status": "success",
  "message": "Broadcast notification sent to 3/3 users",
  "total_users": 3,
  "successful": 3,
  "failed": 0,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### 3. Send Segmented Notification

**POST** `/segment`

Send notification to users matching a specific segment/tag (e.g., all premium users).

#### Request Body

```json
{
  "segment": "premium",
  "title": "🎁 Premium Feature",
  "message": "Exclusive access to advanced AI models",
  "notification_type": "FEATURE_ANNOUNCEMENT",
  "priority": "HIGH"
}
```

#### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| segment | string | ✅ | User segment (e.g., 'premium', 'free_trial', 'inactive') |
| title | string | ✅ | Notification title |
| message | string | ✅ | Notification message |
| notification_type | enum | ✅ | Notification type |
| priority | enum | ❌ | Priority level |
| image_url | string | ❌ | Optional image URL |
| action_url | string | ❌ | Optional deep link |
| data | object | ❌ | Optional custom data |

#### Response (201 Created)

```json
{
  "status": "success",
  "message": "Broadcast notification sent to 150/150 users",
  "total_users": 150,
  "successful": 150,
  "failed": 0,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### 4. Get All Notifications

**GET** `/`

Retrieve all notifications from the system.

#### Response (200 OK)

```json
{
  "status": "success",
  "items": [
    {
      "id": "notif_123",
      "user_id": "user-123",
      "title": "✅ Task Complete",
      "message": "Your video is ready!",
      "type": "TASK_COMPLETION",
      "priority": "HIGH",
      "image_url": "...",
      "action_url": "lumora://task/123",
      "is_read": false,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "count": 1
}
```

---

### 5. Update Notification Status

**PUT** `/{notification_id}/status`

Mark a notification as read or unread.

#### Request Body

```json
{
  "is_read": true
}
```

#### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| is_read | boolean | ✅ | Mark as read (true) or unread (false) |

#### Response (200 OK)

```json
{
  "status": "success",
  "notification_id": "notif_123",
  "is_read": true,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### 6. Get User Notification Preferences

**GET** `/preferences/{user_id}`

Retrieve notification preferences for a specific user.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| user_id | string | ✅ | Target user ID |

#### Response (200 OK)

```json
{
  "status": "success",
  "data": {
    "user_id": "user-123",
    "notifications_enabled": true,
    "task_completion_notifications": true,
    "engagement_notifications": true,
    "feature_announcement_notifications": true,
    "sound_enabled": true,
    "vibration_enabled": true,
    "do_not_disturb_enabled": false,
    "do_not_disturb_start_hour": 22,
    "do_not_disturb_end_hour": 8,
    "notification_frequency": "instant",
    "max_notifications_per_day": 20
  }
}
```

---

### 7. Update User Notification Preferences

**PUT** `/preferences/{user_id}`

Update notification preferences for a user. Only provided fields will be updated.

#### Request Body

```json
{
  "notifications_enabled": false,
  "sound_enabled": false,
  "do_not_disturb_enabled": true,
  "do_not_disturb_start_hour": 22,
  "do_not_disturb_end_hour": 8
}
```

#### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| notifications_enabled | boolean | ❌ | Enable/disable all notifications |
| task_completion_notifications | boolean | ❌ | Enable/disable task completion |
| engagement_notifications | boolean | ❌ | Enable/disable engagement |
| feature_announcement_notifications | boolean | ❌ | Enable/disable feature announcements |
| sound_enabled | boolean | ❌ | Enable/disable notification sounds |
| vibration_enabled | boolean | ❌ | Enable/disable vibration |
| do_not_disturb_enabled | boolean | ❌ | Enable/disable DND |
| do_not_disturb_start_hour | integer | ❌ | DND start hour (0-23) |
| do_not_disturb_end_hour | integer | ❌ | DND end hour (0-23) |
| notification_frequency | string | ❌ | `instant`, `daily`, or `weekly` |
| max_notifications_per_day | integer | ❌ | Max notifications per day |

#### Response (200 OK)

```json
{
  "status": "success",
  "message": "Preferences updated successfully",
  "data": {
    "user_id": "user-123",
    "notifications_enabled": false,
    "sound_enabled": false,
    "do_not_disturb_enabled": true,
    "do_not_disturb_start_hour": 22,
    "do_not_disturb_end_hour": 8
  }
}
```

---

### 8. Notification Service Health Check

**GET** `/health`

Check the health status of the notification service.

#### Response (200 OK)

```json
{
  "status": "healthy",
  "service": "notification_service",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Notification Types

```
TASK_COMPLETION       # AI task finished (e.g., video generation complete)
ENGAGEMENT           # Usage reminders, keep-alive alerts
FEATURE_ANNOUNCEMENT # New features, app updates
```

## Priority Levels

```
HIGH    # Urgent: task completion, critical alerts
MEDIUM  # Important: feature announcements
LOW     # Informational: tips, suggestions
```

## Deep Link Format

Deep links follow this format:

```
lumora://task/{task_id}              # Navigate to task
lumora://feature/{feature_id}        # Navigate to feature
lumora://notifications               # Open notifications tab
lumora://profile                     # Open profile
```

## Error Handling

All errors include a standard error response:

```json
{
  "status": "error",
  "message": "Error description",
  "code": "ERROR_CODE"
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| 400 | Bad Request | Missing or invalid parameters |
| 401 | Unauthorized | Missing or invalid authentication token |
| 404 | Not Found | Resource not found |
| 500 | Server Error | Internal server error |

## Rate Limiting

- Broadcast endpoints are rate-limited to 10 requests per minute per user
- Single notification sends are limited to 100 requests per minute
- Preference updates are limited to 50 requests per minute

## Best Practices

1. **Use appropriate priority levels** - Reserve HIGH for truly urgent notifications
2. **Include action URLs** - Always provide deep links when applicable
3. **Test with sandbox first** - Use development environment before production
4. **Monitor delivery** - Track notification delivery rates and user engagement
5. **Respect user preferences** - Always check user's notification settings before sending
6. **Include clear messages** - Keep notification text concise and actionable
7. **Use images wisely** - Include images only when they add value

## Integration with OneSignal

The notification system integrates with OneSignal for reliable push delivery:

1. Notifications are queued in the backend
2. Backend publishes to OneSignal REST API
3. OneSignal handles device routing and delivery
4. Delivery status is tracked and logged

### OneSignal Configuration

```python
# In .env or config
ONESIGNAL_APP_ID="your-app-id"
ONESIGNAL_REST_API_KEY="your-rest-api-key"
ONESIGNAL_API_URL="https://onesignal.com/api/v1"
```

## Monitoring and Logging

All notification events are logged:

```
INFO  - Notification sent to user-123
INFO  - Broadcast sent to 150 users
ERROR - Failed to send notification: connection_timeout
```

View logs:

```bash
docker logs lumora-backend
# or
tail -f /var/log/lumora/notifications.log
```
