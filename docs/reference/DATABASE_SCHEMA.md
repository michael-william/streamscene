# Database Schema Reference

Complete database schema documentation for StreamScene.

## Core Tables

### users

Minimal user table - Authentik is single source of truth for user data.

```sql
users
  - id (UUID, primary)
  - email (unique, string)
  - username (unique, string)
  - created_at (timestamp)
  - updated_at (timestamp)
```

### devices

Physical E Ink devices owned by users.

```sql
devices
  - id (UUID, primary)
  - device_uuid (unique, string) - Pre-configured UUID
  - user_id (foreign key to users)
  - nickname (string)
  - api_key (unique, hashed with bcrypt)
  - current_version (string)
  - last_seen (timestamp)
  - current_stream_id (foreign key to streams, nullable)
  - rotation_enabled (boolean)
  - rotation_interval (integer, seconds)
  - registered_at (timestamp)
  - created_at (timestamp)
  - updated_at (timestamp)
```

### streams

Content channels that users can create and subscribe to.

```sql
streams
  - id (UUID, primary)
  - owner_id (foreign key to users)
  - name (string, max 100 chars)
  - description (text)
  - is_public (boolean, default false)
  - allow_text (boolean, default true)
  - allow_images (boolean, default true)
  - show_history (boolean, default true)
  - max_history_items (integer, default 10)
  - theme_name (string, default "classic")
  - created_at (timestamp)
  - updated_at (timestamp)
```

### stream_subscriptions

User subscriptions to streams (many-to-many relationship).

```sql
stream_subscriptions
  - id (UUID, primary)
  - user_id (foreign key to users)
  - stream_id (foreign key to streams)
  - is_approved (boolean, default false for private streams)
  - subscribed_at (timestamp)
  - unique(user_id, stream_id)
```

### posts

Messages and images posted to streams.

```sql
posts
  - id (UUID, primary)
  - stream_id (foreign key to streams)
  - author_id (foreign key to users)
  - content_type (enum: text, image, mixed)
  - text_content (text, nullable)
  - image_path (string, nullable)
  - processed_image_path (string, nullable)
  - created_at (timestamp)
  - updated_at (timestamp)
```

### device_stream_settings

Which streams each device displays (rotation configuration).

```sql
device_stream_settings
  - id (UUID, primary)
  - device_id (foreign key to devices)
  - stream_id (foreign key to streams)
  - display_order (integer)
  - is_active (boolean)
```

## OTA Update Tables

### device_updates

Available software updates for devices.

See `streamscene/core/models.py` for DeviceUpdate model.

```sql
device_updates
  - id (UUID, primary)
  - version (string, unique, e.g., "1.2.3")
  - release_date (timestamp)
  - package_path (string) - Path to .tar.gz update package
  - package_hash (string) - SHA256 checksum for verification
  - package_size (integer) - Size in bytes
  - changelog (text)
  - is_active (boolean) - Can be disabled to withdraw bad updates
  - min_version_required (string, nullable) - Minimum version that can install this update
  - is_mandatory (boolean)
  - rollout_percentage (integer, 0-100) - Staged rollout (0=none, 100=all devices)
  - created_at (timestamp)
  - updated_at (timestamp)
```

### update_deployments

Tracks OTA update installation per device.

```sql
update_deployments
  - id (UUID, primary)
  - device_id (foreign key to devices)
  - update_id (foreign key to device_updates)
  - status (enum: pending, downloading, installing, completed, failed, rolled_back)
  - download_progress (integer, 0-100)
  - error_message (text, nullable)
  - rollback_reason (text, nullable)
  - started_at (timestamp)
  - completed_at (timestamp, nullable)
  - created_at (timestamp)
  - updated_at (timestamp)
```

## Important Relationships

- **Devices → Users:** One-to-many (each device belongs to one user)
- **Streams → Users:** One-to-many (each stream has one owner)
- **Streams ↔ Users:** Many-to-many via `stream_subscriptions` (users can subscribe to many streams)
- **Posts → Streams:** Many-to-one (posts belong to one stream)
- **Posts → Users:** Many-to-one (posts have one author)
- **Devices ↔ Streams:** Many-to-many via `device_stream_settings` (rotation)
- **Updates → Devices:** One-to-many via `update_deployments`

## Performance Indexes

```sql
CREATE INDEX idx_posts_stream_created ON posts(stream_id, created_at DESC);
CREATE INDEX idx_devices_user ON devices(user_id);
CREATE INDEX idx_stream_subs ON stream_subscriptions(user_id, stream_id);
CREATE INDEX idx_posts_author ON posts(author_id, created_at DESC);
CREATE INDEX idx_devices_last_seen ON devices(last_seen DESC);
CREATE INDEX idx_update_deployments_device ON update_deployments(device_id, status);
```

## Working with Database Models

- All models use SQLAlchemy ORM in `core/models.py`
- Use **UUID primary keys** for all tables
- Add indexes for frequently queried fields
- Use **Alembic** for all schema changes (never manual SQL DDL)

## Common Queries

### Get user's streams
```python
from streamscene.core.streams import get_user_streams
streams = get_user_streams(session, user_id)
```

### Get latest post from stream
```python
from streamscene.core.streams import get_latest_stream_post
post = get_latest_stream_post(session, stream_id)
```

### Check device registration status
```python
device = session.query(Device).filter_by(device_uuid=uuid).first()
is_registered = device and device.user_id is not None
```
