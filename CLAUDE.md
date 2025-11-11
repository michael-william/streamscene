# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StreamScene is a family message board system using color E Ink displays (Waveshare 7.3" 6-color) on Raspberry Pi Zero 2 WH devices. Family members can remotely post messages and images through "Streams" - shared channels displayed on physical E Ink frames.

**Key Constraint:** E Ink displays have ~30 second refresh time, limiting content rotation to minimum 60 second intervals.

## Development Commands

### Environment Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Database migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

### Running the Application
```bash
# Development mode (with hot reload)
reflex run

# Production mode
reflex run --env prod

# Reliable restart (handles port conflicts)
./restart-reflex.sh

# Background tasks (Celery worker)
celery -A streamscene.core.tasks worker --loglevel=info

# Celery beat (scheduled tasks)
celery -A streamscene.core.tasks beat --loglevel=info
```

**Restart Script:** Use `./restart-reflex.sh` to cleanly stop and restart Reflex. This script:
- Finds processes by port (3000 and 8000)
- Kills them gracefully
- Verifies ports are free
- Clears Python cache
- Starts fresh instance

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=streamscene --cov-report=html

# Run specific test file
pytest tests/test_models.py

# Run specific test
pytest tests/test_models.py::test_stream_creation
```

### Database
```bash
# Connect to PostgreSQL
psql -U streamscene -d streamscene -h localhost

# Reset database (development only)
alembic downgrade base
alembic upgrade head

# Backup database
pg_dump -U streamscene streamscene > backup.sql

# Restore database
psql -U streamscene streamscene < backup.sql
```

### Redis
```bash
# Connect to Redis
redis-cli

# Monitor Redis commands
redis-cli monitor

# Check Redis memory usage
redis-cli info memory
```

## Architecture

### Code Structure Philosophy
The codebase uses **defensive architecture** - business logic is framework-agnostic (in `core/`) to enable easy framework migration if Reflex proves limiting. Reflex is currently used but may be swapped for FastAPI if device API requirements aren't met.

```
streamscene/
├── core/              # Pure Python business logic (NO framework dependencies)
│   ├── models.py      # SQLAlchemy ORM models
│   ├── database.py    # Database connection & session management
│   ├── auth.py        # Authentication logic
│   ├── streams.py     # Stream business logic
│   ├── devices.py     # Device management logic
│   └── tasks.py       # Celery background tasks
├── api/               # API layer (Reflex-exposed endpoints)
│   ├── device_api.py  # Device REST/WebSocket endpoints
│   └── schemas.py     # Pydantic request/response models
└── ui/                # Reflex UI components
    ├── pages/         # Page components
    ├── components/    # Reusable UI components
    └── state.py       # Reflex state management
```

### Communication Architecture
- **Web users → Server:** Reflex web interface + Authentik OAuth2
- **Devices → Server:** WebSocket connections (primary) with polling fallback
- **Real-time updates:** WebSocket server pushes content to devices
- **Device authentication:** API key (generated during device registration)
- **Background processing:** Celery + Redis for image processing, notifications

### Key Design Decisions

**Device Provisioning:**
- Pre-configured SD cards with unique UUIDs burned into `/boot/streamscene-device.txt`
- QR code sticker on each device for user registration
- Bluetooth Low Energy (BLE) for WiFi credential setup

**Database Strategy:**
- PostgreSQL for all data persistence
- Authentik is single source of truth for user data (only store user ID reference)
- Redis for WebSocket connection state, session caching, Celery broker

**Update Strategy:**
- Over-The-Air (OTA) updates via WebSocket push
- Staged rollout (10% of devices first)
- Automatic rollback on failure
- Update packages stored in `/var/lib/streamscene/updates/`

## Database Schema

### Core Tables

**users** (Minimal - Authentik is single source of truth)
```sql
users
  - id (UUID, primary)
  - email (unique, string)
  - username (unique, string)
  - created_at (timestamp)
  - updated_at (timestamp)
```

**devices**
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

**streams**
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

**stream_subscriptions**
```sql
stream_subscriptions
  - id (UUID, primary)
  - user_id (foreign key to users)
  - stream_id (foreign key to streams)
  - is_approved (boolean, default false for private streams)
  - subscribed_at (timestamp)
  - unique(user_id, stream_id)
```

**posts**
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

**device_stream_settings**
```sql
device_stream_settings
  - id (UUID, primary)
  - device_id (foreign key to devices)
  - stream_id (foreign key to streams)
  - display_order (integer)
  - is_active (boolean)
```

**device_updates** (OTA System - See streamscene/core/models.py for DeviceUpdate model)
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

**update_deployments** (OTA System - Tracks installation per device)
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

### Important Relationships
- Devices belong to one user (1:N)
- Streams owned by one user, subscribed by many (N:M via subscriptions)
- Posts belong to one stream and one author (N:1)
- Devices can display multiple streams in rotation
- OTA updates deployed to multiple devices (1:N)

### Performance Indexes
```sql
CREATE INDEX idx_posts_stream_created ON posts(stream_id, created_at DESC);
CREATE INDEX idx_devices_user ON devices(user_id);
CREATE INDEX idx_stream_subs ON stream_subscriptions(user_id, stream_id);
CREATE INDEX idx_posts_author ON posts(author_id, created_at DESC);
CREATE INDEX idx_devices_last_seen ON devices(last_seen DESC);
CREATE INDEX idx_update_deployments_device ON update_deployments(device_id, status);
```

## API Endpoints

### Core Endpoints
- `GET /api/health` - Health check (returns service status)
- `GET /docs` - FastAPI automatic API documentation (Swagger UI)
- `GET /redoc` - FastAPI automatic API documentation (ReDoc)

### Authentication Endpoints
Web users authenticate via Authentik OAuth2:
- User visits `/` → clicks "Sign In" → redirected to Authentik
- Authentik redirects back to `/callback?code=...` with authorization code
- Callback page exchanges code for access token and user info
- User ID stored in cookie-based session (`rx.Cookie`)

### Device Endpoints (For E Ink Devices)
**Authentication:** All device endpoints require `X-Device-Api-Key` header (except registration)

**Registration & Configuration:**
- `POST /api/devices/register` - Register device with UUID (returns API key - shown once!)
  - Request body: `{"device_uuid": "UUID", "nickname": "optional"}`
  - Returns: `{"device_id": "UUID", "api_key": "key"}`
  - Note: API key returned only once, device must save it

- `GET /api/devices/{id}/config` - Get device configuration
  - Returns: nickname, current_stream_id, rotation settings, version

- `POST /api/devices/{id}/heartbeat` - Update device last_seen timestamp
  - Devices should call this every 5-10 minutes
  - Returns: `{"status": "ok", "server_time": "timestamp"}`

**Content Retrieval:**
- `GET /api/devices/{id}/content` - Get current content to display
  - Returns: Latest post from device's assigned stream
  - Includes: content_type, text_content, image_url, stream_name, posted_at, author_name

**OTA Updates (See streamscene/api/routes/devices.py):**
- `GET /api/devices/{id}/updates/check` - Check if update available
  - Returns: `{"update_available": bool, "version": "1.2.3", "is_mandatory": bool, "package_size": int, "changelog": "..."}`
  - Uses staged rollout algorithm (hash-based percentage)

- `GET /api/devices/{id}/updates/{version}/download` - Download update package
  - Returns: Binary .tar.gz file (FileResponse)
  - Device must verify SHA256 hash after download

- `POST /api/devices/{id}/updates/report` - Report installation status
  - Request body: `{"update_id": "UUID", "status": "completed|failed", "download_progress": 100, "error_message": "...", "rollback_reason": "..."}`
  - Returns: `{"success": true, "message": "Status recorded"}`

**WebSocket Endpoint:**
- `WS /api/devices/{id}/stream` - WebSocket for real-time content updates
  - Authentication via API key in connection headers
  - Server pushes new content when stream posts are created
  - Heartbeat every 30 seconds required
  - Auto-reconnect with exponential backoff on disconnect

### Stream Endpoints (Web UI - via Reflex State)
Implemented in `streamscene/core/streams.py`:
- **CRUD Operations:**
  - `create_stream(session, owner_id, name, description, is_public)` - Create new stream
  - `get_stream_by_id(session, stream_id)` - Get stream details
  - `get_user_streams(session, user_id)` - List user's owned streams
  - `update_stream(session, stream_id, **kwargs)` - Update stream settings
  - `delete_stream(session, stream_id)` - Delete stream (cascade deletes posts)

- **Subscriptions:**
  - `subscribe_to_stream(session, user_id, stream_id)` - Subscribe to stream
  - `unsubscribe_from_stream(session, user_id, stream_id)` - Unsubscribe
  - `get_subscribed_streams(session, user_id)` - List subscribed streams
  - `approve_subscription(session, subscription_id)` - Approve private stream subscription
  - `get_stream_subscribers(session, stream_id)` - List all subscribers

- **Posts:**
  - `create_post(session, stream_id, author_id, content_type, text_content, image_path)` - Create post
  - `get_stream_posts(session, stream_id, limit, offset)` - Get paginated posts
  - `get_latest_stream_post(session, stream_id)` - Get most recent post
  - `delete_post(session, post_id)` - Delete post

### User Endpoints (Web UI Pages)
Implemented as Reflex pages:
- `/` - Landing page (with direct OAuth link to Authentik)
- `/callback` - OAuth callback handler (processes code, creates user, sets cookie)
- `/streams` - Stream management UI (create streams, post messages, view posts, manage subscriptions)
- `/devices` - Device management (register, configure, view status)

**Note:** `/login` page removed - index page links directly to Authentik OAuth URL to avoid WebSocket issues.

## Environment Configuration

Required `.env` variables:
```bash
# Database
DATABASE_URL=postgresql://streamscene:password@localhost/streamscene
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
API_KEY_SALT=your-api-key-salt-here

# Authentik OAuth (old format - for reference)
AUTHENTIK_URL=http://192.168.1.108:9000
AUTHENTIK_CLIENT_ID=streamscene
AUTHENTIK_CLIENT_SECRET=your-client-secret

# OAuth Configuration (used by Reflex pages)
OAUTH_CLIENT_ID=streamscene
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_AUTHORIZATION_URL=https://auth.dataandstories.com/application/o/authorize/
OAUTH_TOKEN_URL=https://auth.dataandstories.com/application/o/token/
OAUTH_USERINFO_URL=https://auth.dataandstories.com/application/o/userinfo/
OAUTH_REDIRECT_URI=https://streamscene.dataandstories.com/callback

# Application
DOMAIN=streamscene.dataandstories.com
FRONTEND_URL=https://streamscene.dataandstories.com
BACKEND_URL=https://streamscene.dataandstories.com
ENVIRONMENT=production

# Storage
UPLOAD_PATH=/var/lib/streamscene/uploads
PROCESSED_PATH=/var/lib/streamscene/processed
CACHE_PATH=/var/lib/streamscene/cache
```

## E Ink Display Constraints

**Waveshare 7.3" 6-Color E-Paper:**
- Resolution: 800x480 pixels
- Colors: Black, White, Red, Yellow, Blue, Green only
- Refresh time: ~30 seconds for full update
- **Minimum content rotation:** 60 seconds (30s refresh + buffer)

**Image Processing Pipeline:**
1. Resize to exactly 800x480 pixels
2. Reduce to 6-color palette using Floyd-Steinberg dithering
3. Convert to Waveshare buffer format
4. Pre-process on server (not on Pi) to save CPU
5. Cache processed images

## E Ink Preview System

**Location:** `streamscene/components/eink/`

The E Ink preview system allows users to see exactly how their posts will appear on the physical E Ink display before posting. It uses a composable architecture that's future-proof for theming and image support.

### Architecture

**Composable Design Principles:**
- **Separation of Concerns:** Layout, content, and theming are completely independent
- **Theme System:** Colors and styles abstracted into reusable themes
- **Content Renderers:** Pure functions for text, images, and mixed content
- **Layout Components:** Header, footer, and content area are independent and reusable

**Component Files:**
```
streamscene/components/eink/
├── __init__.py              # Public API exports
├── theme.py                 # Theme system (5 pre-defined themes)
├── layout.py                # Composable layout components
├── content_renderers.py     # Text/image/mixed renderers
├── preview.py               # Main preview component
└── text_utils.py            # Text measurement & wrapping
```

### Usage

**Basic usage in UI:**
```python
from streamscene.components.eink import eink_preview

# Simple text preview
preview = eink_preview(
    text_content=StreamPostsState.new_post_content,  # Can be Var or str
    stream_name="Family Updates",
    author_name="You",
    theme_name="classic"
)
```

**Available themes:**
- `classic` - Black text on white background (default)
- `dark` - White text on black background
- `accent_red` - Black text with red header accents
- `accent_blue` - Black text with blue header accents
- `minimal` - Clean design without dividers

**Adding a new theme:**
```python
# In streamscene/components/eink/theme.py
from streamscene.components.eink import EInkTheme, register_theme

sunset_theme = EInkTheme(
    name="sunset",
    description="Warm sunset colors",
    background_color="yellow",
    text_color="black",
    header_color="red",
    divider_color="#ffddaa",
    font_family="monospace",
    header_weight="bold",
    show_dividers=True,
    border_style="rounded"
)

register_theme(sunset_theme)
```

### Dynamic Font Sizing

Text automatically resizes based on content length:
- **< 100 chars:** 48px (large, impactful)
- **100-200 chars:** 36px
- **200-300 chars:** 28px
- **300-400 chars:** 22px
- **> 400 chars:** 18px + warning message

### Integration

**In post creation form (`stream_posts.py`):**
- Toggle switch to show/hide preview
- Real-time character counter (turns red >400 chars)
- Warning messages for long content
- Responsive scaling (70% desktop, 50% mobile)

### Future Enhancements (Already Architected)

1. **Stream-specific themes:** Add `theme_name` field to streams table
2. **Image support:** Just update `image_content_renderer()` in `content_renderers.py`
3. **Custom theme editor:** UI for creating themes (architecture ready)
4. **Rotation preview:** Show multiple posts cycling (just compose multiple previews)

### Important Notes for Development

**Reflex Var Compatibility:**
- Use `rx.cond()` instead of Python `if` statements when working with Vars
- Content renderers handle both plain strings and Reflex Vars
- Preview component works with reactive state updates

**Example of Var-safe code:**
```python
# ❌ WRONG - Python if doesn't work with Vars
if text.strip():
    return rx.text(text)

# ✅ CORRECT - Use rx.cond()
return rx.cond(
    text,  # Condition (works with Vars)
    rx.text(text),  # If truthy
    rx.text("Empty")  # If falsy
)
```

## Authentication Flow

### Web Users (OAuth2 + Cookie-Based Sessions)
1. User visits index page (`/`)
2. Clicks "Sign In" → Direct link to Authentik OAuth authorization URL (no intermediate page)
3. User authenticates at Authentik (https://auth.dataandstories.com)
4. Authentik redirects to `/callback?code=...`
5. Callback page:
   - Exchanges code for access token
   - Fetches user info from Authentik
   - Creates/gets user in local database
   - Stores user_id in `rx.Cookie()` State variable (auto-synced to browser)
6. Redirects to `/streams` page
7. Streams page reads user_id from cookie (auto-loaded into State)

**Implementation Details:**
- **Cookie Storage:** `rx.Cookie("")` State variables automatically sync with browser cookies
- **No Session Assignment:** Reflex router.session is read-only; use Cookie State vars instead
- **Authentication Check:** `if not self.user_id: return rx.redirect("/")`
- **Logout:** Set cookie to empty string: `self.user_id = ""`

### Device Authentication
1. Device boots with pre-configured UUID
2. User scans QR code during setup
3. Device registration endpoint generates API key
4. All device requests include `X-Device-API-Key` header
5. API keys hashed in database (bcrypt)

## Development Workflow

### Adding a New Feature
1. Write business logic in `core/` (framework-agnostic)
2. Add API endpoint in `api/` if needed for devices
3. Add UI components in `ui/` for web interface
4. Create database migration if schema changes
5. Write tests in `tests/`
6. Update CLAUDE.md if architecture changes

### Working with Database Models
- All models use SQLAlchemy ORM in `core/models.py`
- Use UUID primary keys for all tables
- Add indexes for frequently queried fields
- Use Alembic for all schema changes (never manual SQL DDL)

### WebSocket Development
- WebSocket connections managed in `api/device_api.py`
- Connection state tracked in Redis
- Heartbeat every 30 seconds required
- Auto-reconnect with exponential backoff on client
- Monitor connection stability - if <90%, switch to polling fallback

## Device Client (Raspberry Pi)

The device client code is located in `client/` directory:

**Main Components:**
- `display.py` - E Ink driver and rendering logic
- `api_client.py` - WebSocket/REST API client
- `setup/` - WiFi hotspot and captive portal for setup
  - `hotspot.py` - WiFi access point management (hostapd/dnsmasq)
  - `portal_server.py` - Captive portal web server
  - `wifi_client.py` - WiFi client connection management
- `renderer.py` - Content rendering for E Ink
- `main.py` - Device main loop

**Device Main Loop:**
1. Check WiFi connection → start hotspot + captive portal if needed
2. Check registration → show QR code if not registered
3. Check for OTA updates → download and install
4. Connect WebSocket to server
5. Listen for content updates and render to display

## WiFi Setup System

**Architecture:**
The WiFi setup system enables devices to connect to home networks without pre-configuration. It uses a WiFi hotspot + captive portal approach (tested successfully on Raspberry Pi Zero 2 WH).

**Components:**

### 1. Hotspot Creation (`client/setup/hotspot.py`)
- Creates WiFi access point using hostapd and dnsmasq
- Generates device-specific SSID from UUID: `StreamScene-XXXX` (last 4 chars before final UUID segment)
- Configures static IP 192.168.4.1 on wlan0
- Default password: `streamscene` (8+ characters required by WPA2)
- Automatically stops/masks wpa_supplicant to prevent mode conflicts

**Key Functions:**
```python
generate_ssid(device_uuid: str) -> str  # StreamScene-XXXX from UUID
create_hotspot(ssid: str, password: str = "streamscene") -> bool
stop_hotspot() -> bool
is_hotspot_active() -> bool
```

### 2. Captive Portal (`client/setup/portal_server.py`)
- HTTP server on port 80 with threading support
- Beautiful HTML form (NO JavaScript for maximum compatibility)
- DNS wildcard redirect (all queries → 192.168.4.1) for automatic portal opening
- Stores credentials to `wifi_credentials.json` on submission
- Modern CSS gradient design with mobile-responsive layout

**Key Class:**
```python
class CaptivePortalServer:
    def start(self) -> None  # Start server in background thread
    def stop(self) -> None
    def has_credentials(self) -> bool
    def get_credentials(self) -> dict
```

### 3. WiFi Client Connection (`client/setup/wifi_client.py`)
- Generates wpa_supplicant configuration for home network
- Manually starts wpa_supplicant with config file (bypasses unreliable systemd service)
- Requests DHCP lease via dhclient
- Verifies connection via wpa_cli status (checks for `wpa_state=COMPLETED`)
- Tests internet connectivity by pinging 8.8.8.8

**Key Functions:**
```python
save_credentials(ssid: str, password: str) -> bool
load_credentials() -> Optional[dict]
connect_to_wifi(ssid: str, password: str, timeout: int = 30) -> bool
is_connected() -> bool
get_ip_address() -> Optional[str]
test_internet_connectivity(timeout: int = 10) -> bool
```

### WiFi Setup Flow

1. **Device boots without WiFi credentials**
2. **Hotspot mode activated:**
   - Stop and mask wpa_supplicant (prevent conflicts)
   - Configure wlan0 with static IP 192.168.4.1
   - Start hostapd (WiFi AP) and dnsmasq (DHCP/DNS)
3. **User connects phone to StreamScene-XXXX network**
4. **Captive portal auto-opens** (DNS redirect to 192.168.4.1)
5. **User submits WiFi credentials via HTML form**
6. **Credentials saved to JSON file**
7. **Hotspot stopped, services cleaned up**
8. **WiFi client mode activated:**
   - Unmask and manually start wpa_supplicant with config
   - Request DHCP lease
   - Verify connection and internet access
9. **Device proceeds to registration flow**

**Testing:**
- End-to-end tested on Raspberry Pi Zero 2 WH
- Requires ethernet for development/testing SSH access
- See `docs/deployment/WIFI_SETUP.md` for comprehensive testing guide

**System Dependencies (Raspberry Pi):**
```bash
sudo apt-get install -y hostapd dnsmasq
sudo systemctl disable hostapd dnsmasq  # Manual control only
```

**Configuration Files:**
- `/etc/hostapd/hostapd.conf` - Hotspot configuration (generated dynamically)
- `/etc/dnsmasq.d/streamscene.conf` - DNS/DHCP configuration
- `/etc/wpa_supplicant/wpa_supplicant.conf` - WiFi client configuration
- `/home/badgy/streamscene-client/wifi_credentials.json` - Saved credentials
- `/boot/firmware/streamscene-device.txt` - Device UUID

## OTA Update System

**Server-Side Infrastructure (Phases 1-3):**

### Database Models (`streamscene/core/models.py`)

**DeviceUpdate:**
- Stores update package metadata (version, path, hash, size, changelog)
- Supports staged rollout via `rollout_percentage` (0-100)
- Version compatibility via `min_version_required`
- Mandatory vs optional updates via `is_mandatory`
- Active/inactive flag for withdrawing bad updates

**UpdateDeployment:**
- Tracks installation status per device (pending → downloading → installing → completed/failed)
- Records download progress (0-100%)
- Captures error messages and rollback reasons
- Links device to update via foreign keys

### OTA Business Logic (`streamscene/core/ota.py`)

**Staged Rollout Algorithm:**
```python
# Devices selected for rollout based on hash of device ID
device_hash = int(hashlib.md5(str(device_id).encode()).hexdigest(), 16)
device_percentage = (device_hash % 100) + 1
eligible = device_percentage <= update.rollout_percentage
```

**Key Functions:**
- `check_for_updates(device_id)` - Eligibility check (version, rollout %, active status)
- `create_update_deployment(device_id, update_id)` - Initialize tracking record
- `update_deployment_status(device_id, update_id, status, progress, error)` - Track progress
- `get_deployment_stats(update_id)` - Success rate monitoring

### Device API Endpoints (`streamscene/api/routes/devices.py`)

**Check for Updates:**
```
GET /api/devices/{device_id}/updates/check
Headers: X-Device-API-Key
Returns: { update_available, version, is_mandatory, package_size, changelog }
```

**Download Update:**
```
GET /api/devices/{device_id}/updates/{version}/download
Headers: X-Device-API-Key
Returns: Binary .tar.gz file (FileResponse)
```

**Report Status:**
```
POST /api/devices/{device_id}/updates/report
Headers: X-Device-API-Key
Body: { update_id, status, download_progress, error_message, rollback_reason }
Returns: { success, message }
```

### QR Code Generation (`streamscene/core/qr_utils.py`)

**Device Registration QR Codes:**
- Generates QR codes for device registration URLs
- Format: `{FRONTEND_URL}/register?device_uuid={uuid}`
- High error correction for reliability
- Configurable size and border
- Returns PNG bytes (ready for display or file save)

**Functions:**
```python
generate_registration_qr(device_uuid: UUID, base_url: str = None,
                        box_size: int = 10, border: int = 4) -> bytes
save_registration_qr(device_uuid: UUID, output_path: str, ...) -> bool
```

**Client-Side Integration (Phase 7 - Pending):**
- Download update package over WiFi
- Verify SHA256 hash matches server
- Extract to temporary directory
- Run update script
- Verify new version works
- Automatic rollback on failure

## Development Phases Status

### Phase 0: Infrastructure Setup ✅ COMPLETE (Nov 2, 2025)
- ✅ LXC container created and configured
- ✅ PostgreSQL 15 installed and configured
- ✅ Redis server setup
- ✅ Authentik OAuth provider configured
- ✅ Nginx Proxy Manager + SSL certificates
- ✅ Domain configuration (dataandstories.com)
- ✅ Development environment initialized

### Phase 1: Web App Core ✅ COMPLETE (Nov 3, 2025)
- ✅ SQLAlchemy ORM models (users, devices, streams, posts, subscriptions)
- ✅ Alembic database migrations
- ✅ Authentik OAuth2 integration (cookie-based sessions)
- ✅ Stream CRUD operations (`streamscene/core/streams.py`)
- ✅ Post creation (text-only MVP)
- ✅ Subscription system (subscribe/unsubscribe/approve)
- ✅ Reflex web UI with responsive design
- ✅ Streams page redesign (table-based layout, search, modals)
- ✅ E Ink preview system (composable themes, dynamic font sizing)

### Phase 2-3: OTA Update Infrastructure ✅ COMPLETE (Nov 9, 2025)
**Server-Side (Phases 1-3):**
- ✅ DeviceUpdate and UpdateDeployment models
- ✅ Staged rollout algorithm (hash-based percentage)
- ✅ QR code generation (`streamscene/core/qr_utils.py`)
- ✅ Device API endpoints:
  - `GET /api/devices/{id}/updates/check`
  - `GET /api/devices/{id}/updates/{version}/download`
  - `POST /api/devices/{id}/updates/report`

### Phase 4: WiFi Setup System ✅ COMPLETE (Nov 9, 2025)
**Client-Side:**
- ✅ WiFi hotspot creation (`client/setup/hotspot.py`)
- ✅ Captive portal server (`client/setup/portal_server.py`)
- ✅ WiFi client connection (`client/setup/wifi_client.py`)
- ✅ End-to-end tested on Raspberry Pi Zero 2 WH
- ✅ Deployment script (`deploy_to_pi.sh`)
- ✅ Comprehensive deployment guide (`docs/deployment/WIFI_SETUP.md`)

### Phase 5: Device State Machine & Registration 🚧 IN PROGRESS (Current)
**Goal:** Integrate WiFi setup into main device loop and implement registration flow

**Tasks:**
- 🚧 Create device state machine (`client/state_machine.py`)
  - States: WIFI_SETUP → REGISTRATION → OPERATIONAL → ERROR
- 🚧 Create registration module (`client/registration.py`)
  - Generate QR code from device UUID
  - Poll server for registration status (every 5 seconds)
  - Save API key locally after registration
- 🚧 Update main device loop (`client/main.py`)
  - Load device UUID from `/boot/firmware/streamscene-device.txt`
  - Run state machine
- 🚧 Server-side registration check endpoint (may need to add)

**Reference:** See `docs/plans/DEVICE_SETUP_OTA.md` for detailed Phase 5 plan

### Phase 6: E Ink Display Integration ⏳ PENDING
- ⏳ E Ink driver integration (`client/display.py`)
- ⏳ Setup state rendering (WiFi setup screen, QR code display)
- ⏳ Content rendering for operational state
- ⏳ Transition effects (slide/fade)
- ⏳ Display testing on physical Waveshare 7.3" 6-color screen

### Phase 7: WebSocket & Content Display ⏳ PENDING
- ⏳ WebSocket client implementation (`client/api_client.py`)
- ⏳ Connect to server WebSocket endpoint
- ⏳ Handle real-time content push
- ⏳ Heartbeat mechanism (every 30 seconds)
- ⏳ Auto-reconnect with exponential backoff
- ⏳ Render content to E Ink display

### Phase 8: OTA Update Client ⏳ PENDING
- ⏳ Download update packages over WiFi
- ⏳ Verify SHA256 hash matches server
- ⏳ Extract to temporary directory
- ⏳ Run update script
- ⏳ Verify new version works
- ⏳ Automatic rollback on failure

### Phase 9: Production Deployment ⏳ PENDING
- ⏳ SD card "golden image" creation
- ⏳ Device UUID pre-configuration process
- ⏳ QR code sticker generation and printing
- ⏳ Device testing checklist
- ⏳ End-to-end production device test
- ⏳ Documentation for device provisioning

## MVP Scope

**Included in MVP (v1.0):**
- ✅ User authentication via Authentik OAuth2
- ✅ Stream creation and management (CRUD + subscriptions)
- ✅ Text post creation and display
- ✅ E Ink preview system (web UI)
- ✅ WiFi hotspot + captive portal setup
- ✅ OTA update infrastructure (server-side)
- 🚧 Device registration via QR code (Phase 5)
- 🚧 WebSocket real-time updates (Phase 7)
- 🚧 Device state machine (Phase 5)
- 🚧 E Ink content display (Phase 6-7)
- ⏳ OTA update client (Phase 8)

**Deferred to v2:**
- ❌ Image upload and processing
- ❌ Stream discovery/search
- ❌ User profiles and analytics
- ❌ Advanced moderation tools
- ❌ Multi-device stream rotation

## Infrastructure

**Homelab Resources:**
- **Proxmox:** http://192.168.1.30
- **LXC Container (StreamScene):** 192.168.1.118 (Debian 12, 4 cores, 4GB RAM, 50GB storage)
- **LXC Container (Authentik):** 192.168.1.108:9000 (OAuth provider)
- **LXC Container (Nginx Proxy Manager):** 192.168.1.104:81 (reverse proxy + SSL)
- **Domain:** dataandstories.com

**System Services:**
- PostgreSQL 15
- Redis Server
- Reflex web server (production: frontend on :3000, backend on :8000)
- Celery worker (systemd service - not yet configured)
- Celery beat scheduler (systemd service - not yet configured)

## Deployment & Nginx Configuration

**Reflex Production Setup:**
- Frontend (React SPA): Port 3000
- Backend (FastAPI): Port 8000
- Running on LXC container at 192.168.1.118

**Nginx Proxy Manager Configuration:**

Main Proxy Host Settings (Details tab):
- Scheme: `http`
- Forward Hostname/IP: `192.168.1.118` (StreamScene container IP)
- Forward Port: `3000` (frontend)
- Enable: WebSockets Support, Cache Assets, Block Common Exploits

Advanced Configuration (Advanced tab):
```nginx
# WebSocket support for Reflex
location /_event/ {
    proxy_pass http://192.168.1.118:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 86400;
}

# API routes to backend
location /api/ {
    proxy_pass http://192.168.1.118:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**Important:**
- Main proxy forwards ALL traffic to frontend (:3000) by default
- Advanced config routes `/_event/` (WebSocket) and `/api/` to backend (:8000)
- Use container IP (192.168.1.118), not 127.0.0.1 (Nginx is in different container)

**Reflex Configuration (`rxconfig.py`):**
```python
config = rx.Config(
    app_name="streamscene",
    backend_host="0.0.0.0",
    backend_port=8000,
    frontend_port=3000,
    api_url="https://streamscene.dataandstories.com",
    deploy_url="https://streamscene.dataandstories.com",
    plugins=[...]
)
```

## Device Deployment

**Deploy Client Code to Raspberry Pi:**

Using the provided deployment script:
```bash
# From development machine
./deploy_to_pi.sh

# Or manual deployment with sshpass
sshpass -p 'password' scp -r client/ user@host:~/streamscene-client/
```

**Initial Device Setup (One-Time):**
```bash
# SSH into Raspberry Pi
ssh badgy@192.168.1.40  # Use device IP or streamscene.local

# Install system dependencies
sudo apt-get update
sudo apt-get install -y hostapd dnsmasq python3-pip

# Disable services (manual control only)
sudo systemctl disable hostapd dnsmasq
sudo systemctl stop hostapd dnsmasq

# Generate device UUID (if not already done)
DEVICE_UUID=$(uuidgen)
echo "DEVICE_UUID=$DEVICE_UUID" | sudo tee /boot/firmware/streamscene-device.txt
cat /boot/firmware/streamscene-device.txt  # Verify

# Test WiFi setup
cd ~/streamscene-client
sudo python3 test_wifi_setup.py
```

**Testing WiFi Setup:**
1. Run test script (creates hotspot + portal)
2. Connect phone to StreamScene-XXXX network
3. Enter home WiFi credentials in captive portal
4. Verify device connects to home WiFi
5. Check IP address: `ip addr show wlan0`
6. Test internet: `ping -c 3 8.8.8.8`

**Reset WiFi Credentials (for re-testing):**
```bash
rm ~/streamscene-client/wifi_credentials.json
sudo python3 ~/streamscene-client/test_wifi_setup.py
```

## Critical Decision Points

**✅ WiFi Setup Approach (RESOLVED):**
- Implemented hotspot + captive portal instead of BLE
- Successfully tested on Raspberry Pi Zero 2 WH
- No BLE dependencies required

**WebSocket Stability (PENDING):**
- If connection stability <90% after 1 week testing, switch to polling fallback (60 second interval)
- Device client WebSocket integration not yet implemented

**Reflex for Device API (PENDING):**
- Device API endpoints implemented and tested successfully
- WebSocket endpoint exists but not yet tested with real device clients
- If issues arise, consider FastAPI-only migration

## Common Gotchas

1. **Don't bypass business logic:** Always call functions in `core/`, never duplicate logic in `ui/` or `api/`
2. **API keys must be hashed:** Never store plaintext API keys in database
3. **Pre-process images server-side:** Pi Zero has limited CPU, don't process images on device
4. **Respect E Ink timing:** Never rotate content faster than 60 seconds
5. **Cache Authentik user data:** Reduce OAuth API calls with Redis caching
6. **Use UUIDs everywhere:** All primary keys are UUIDs, not integers
7. **WebSocket heartbeat required:** Devices must ping every 30 seconds or connection times out
8. **Reflex session is read-only:** Use `rx.Cookie()` State variables for authentication, not `router.session`
9. **No intermediate login page:** Link directly to OAuth URL to avoid WebSocket initialization issues
10. **Nginx cross-container routing:** Use container IP (192.168.1.118), not 127.0.0.1 for proxy targets
11. **Port conflicts on restart:** Use `./restart-reflex.sh` to cleanly kill processes by port before restarting
12. **Reflex on_mount must be connected AND use yield from:** Lifecycle methods like `on_mount()` must:
    - Be passed to component: `rx.container(..., on_mount=StateName.on_mount)`
    - Use `yield from` when calling generator methods: `yield from self.load_data()`
    - Methods that update state must `yield` to trigger UI updates
    - Without both, methods never execute or state updates don't render
13. **Use on_load (page-level) for router params, not on_mount (component-level):**
    - `on_mount()` fires before router.page.params is populated → empty query params
    - Use method named `on_load()` to access router params reliably
    - Pattern: Define `def on_load(self):` method, trigger with `on_mount=StateName.on_load`
    - Example from callback.py shows the correct pattern
    - See DEBUGGING_HISTORY.md for full explanation of timing issues
14. **Query params vs dynamic routes for UUID lookups:**
    - Query params (`/page?id={uuid}`) more reliable than dynamic routes (`/page/[id]`)
    - Dynamic routes have timing issues and auto-creation conflicts in Reflex
    - For user-clicked navigation (not typed URLs), query params are simpler
    - Access via: `self.router.page.params.get("id", "")`
15. **Use fallback pattern for router params (from callback.py):**
    ```python
    # Primary method
    param = self.router.page.params.get("key", "") if hasattr(self.router.page, "params") else ""
    # Fallback for edge cases
    if not param:
        query_params = self.router.session.client_query_params
        param = query_params.get("key", [""])[0] if query_params else ""
    ```
16. **Component event trigger limitations:**
    - Not all components support all events (e.g., `rx.container` doesn't support `on_load` event)
    - Always trigger lifecycle via `on_mount` parameter, even if method is named `on_load`
    - Error: "The Container does not take in an `on_load` event trigger"
17. **Document complex debugging in DEBUGGING_HISTORY.md:**
    - For issues requiring multiple attempts, create debugging documentation
    - Track: what was tried, why it failed, server logs, lessons learned
    - Prevents repeating failed approaches in future sessions
    - Pattern: DEBUGGING_HISTORY.md with chronological attempt log
18. **Reflex Var compatibility in component functions:**
    - Never use Python `if`, `and`, `or`, `not` directly on Reflex Vars
    - Use `rx.cond()` for conditional rendering instead of `if` statements
    - Error: `VarTypeError: Cannot convert Var to bool`
    - Example: E Ink preview components use `rx.cond(text, ...)` instead of `if text:`
    - See `streamscene/components/eink/content_renderers.py` for working examples
19. **WiFi adapter mode conflicts (Raspberry Pi):**
    - Single WiFi adapter (wlan0) can only be in ONE mode: access point OR client, never both
    - Before creating hotspot: MUST stop and mask wpa_supplicant to prevent conflicts
    - Before connecting as client: MUST stop hostapd/dnsmasq
    - Use `systemctl mask <service>` to prevent systemd from auto-restarting during mode switch
    - Symptom: Hotspot not visible or client won't connect = both services running simultaneously
20. **systemd command timeouts are critical:**
    - ALWAYS add timeout parameter to subprocess.run() for systemd commands
    - Without timeout, Ctrl+C can cause Pi to hang indefinitely on `systemctl stop`
    - Use 5-10 second timeouts: `subprocess.run([...], timeout=10)`
    - Use `check=False` for cleanup operations (don't fail if service already stopped)
21. **Manual wpa_supplicant startup vs systemd service:**
    - systemd wpa_supplicant service doesn't read config file by default
    - Manual startup required: `wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf`
    - Don't use `systemctl start wpa_supplicant` - it starts without `-c` flag
    - Verify connection with: `wpa_cli -i wlan0 status` (look for `wpa_state=COMPLETED`)
22. **Deploy to Pi workflow:**
    - Use `sshpass -p 'password' scp file user@host:path` for automated deployment
    - Ethernet connection recommended for testing (maintains SSH during WiFi mode switching)
    - Always test WiFi setup end-to-end after deployment
    - Reset test: `rm ~/streamscene-client/wifi_credentials.json` and rerun setup script

## Testing Strategy

- **Unit tests:** Core business logic in `core/`
- **Integration tests:** API endpoints, database operations
- **E2E tests:** Full user flows (Playwright)
- **Load tests:** 50+ concurrent device connections
- **Hardware tests:** Mock E Ink display for CI/CD

## Security Considerations

- Rate limiting: 100 req/min per user, 10 req/min per device
- Input validation on all API endpoints (Pydantic schemas)
- SQL injection prevention via SQLAlchemy ORM only
- TLS/SSL required for all production connections
- API keys rotated every 90 days
- Device decommission flow revokes API keys
- Image uploads validated and scanned

## Monitoring & Diagnostics

**Device Health:**
- Heartbeat API tracks last_seen timestamp
- Devices log last 100 lines to server on request
- Remote SSH access via VPN for debugging

**Server Monitoring:**
- Structured JSON logs
- PostgreSQL connection pool monitoring
- WebSocket connection tracking
- Celery task queue length monitoring
- Optional: Grafana + Prometheus setup

## Support Resources

- [Reflex Documentation](https://reflex.dev/docs)
- [Waveshare 7.3" E-Paper Wiki](https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT)
- [Authentik OAuth2 Setup](https://docs.goauthentik.io/docs/providers/oauth2)
- [Web Bluetooth API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Bluetooth_API)
- [SQLAlchemy ORM Docs](https://docs.sqlalchemy.org/en/20/)
