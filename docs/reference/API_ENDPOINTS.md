# API Endpoints Reference

This document provides comprehensive documentation for all StreamScene API endpoints.

## Core Endpoints

- `GET /api/health` - Health check (returns service status)
- `GET /docs` - FastAPI automatic API documentation (Swagger UI)
- `GET /redoc` - FastAPI automatic API documentation (ReDoc)

## Authentication Endpoints

Web users authenticate via Authentik OAuth2:
- User visits `/` → clicks "Sign In" → redirected to Authentik
- Authentik redirects back to `/callback?code=...` with authorization code
- Callback page exchanges code for access token and user info
- User ID stored in cookie-based session (`rx.Cookie`)

## Device Endpoints (For E Ink Devices)

**Authentication:** All device endpoints require `X-Device-Api-Key` header (except registration)

### Registration & Configuration

#### Register Device
```
POST /api/devices/register
```
Register device with UUID (returns API key - shown once!)

**Request body:**
```json
{
  "device_uuid": "UUID",
  "nickname": "optional"
}
```

**Response:**
```json
{
  "device_id": "UUID",
  "api_key": "key"
}
```

**Note:** API key returned only once, device must save it

#### Get Device Configuration
```
GET /api/devices/{id}/config
```
Returns: nickname, current_stream_id, rotation settings, version

#### Device Heartbeat
```
POST /api/devices/{id}/heartbeat
```
Update device last_seen timestamp

- Devices should call this every 5-10 minutes
- Returns: `{"status": "ok", "server_time": "timestamp"}`

### Content Retrieval

#### Get Current Content
```
GET /api/devices/{id}/content
```
Get current content to display

**Returns:**
- Latest post from device's assigned stream
- Includes: content_type, text_content, image_url, stream_name, posted_at, author_name

### OTA Updates

See `streamscene/api/routes/devices.py` for implementation details.

#### Check for Updates
```
GET /api/devices/{device_id}/updates/check
Headers: X-Device-API-Key
```

**Returns:**
```json
{
  "update_available": bool,
  "version": "1.2.3",
  "is_mandatory": bool,
  "package_size": int,
  "changelog": "..."
}
```

Uses staged rollout algorithm (hash-based percentage)

#### Download Update Package
```
GET /api/devices/{device_id}/updates/{version}/download
Headers: X-Device-API-Key
```

**Returns:** Binary .tar.gz file (FileResponse)

**Note:** Device must verify SHA256 hash after download

#### Report Installation Status
```
POST /api/devices/{device_id}/updates/report
Headers: X-Device-API-Key
```

**Request body:**
```json
{
  "update_id": "UUID",
  "status": "completed|failed",
  "download_progress": 100,
  "error_message": "...",
  "rollback_reason": "..."
}
```

**Response:**
```json
{
  "success": true,
  "message": "Status recorded"
}
```

### WebSocket Endpoint

#### Real-time Content Stream
```
WS /api/devices/{id}/stream
```

- **Authentication:** API key in connection headers
- **Server pushes** new content when stream posts are created
- **Heartbeat:** Every 30 seconds required
- **Auto-reconnect:** Exponential backoff on disconnect

## Stream Endpoints (Web UI - via Reflex State)

Implemented in `streamscene/core/streams.py`

### CRUD Operations

- `create_stream(session, owner_id, name, description, is_public)` - Create new stream
- `get_stream_by_id(session, stream_id)` - Get stream details
- `get_user_streams(session, user_id)` - List user's owned streams
- `update_stream(session, stream_id, **kwargs)` - Update stream settings
- `delete_stream(session, stream_id)` - Delete stream (cascade deletes posts)

### Subscriptions

- `subscribe_to_stream(session, user_id, stream_id)` - Subscribe to stream
- `unsubscribe_from_stream(session, user_id, stream_id)` - Unsubscribe
- `get_subscribed_streams(session, user_id)` - List subscribed streams
- `approve_subscription(session, subscription_id)` - Approve private stream subscription
- `get_stream_subscribers(session, stream_id)` - List all subscribers

### Posts

- `create_post(session, stream_id, author_id, content_type, text_content, image_path)` - Create post
- `get_stream_posts(session, stream_id, limit, offset)` - Get paginated posts
- `get_latest_stream_post(session, stream_id)` - Get most recent post
- `delete_post(session, post_id)` - Delete post

## User Endpoints (Web UI Pages)

Implemented as Reflex pages:

- `/` - Landing page (with direct OAuth link to Authentik)
- `/callback` - OAuth callback handler (processes code, creates user, sets cookie)
- `/streams` - Stream management UI (create streams, post messages, view posts, manage subscriptions)
- `/devices` - Device management (register, configure, view status)

**Note:** `/login` page removed - index page links directly to Authentik OAuth URL to avoid WebSocket issues.
