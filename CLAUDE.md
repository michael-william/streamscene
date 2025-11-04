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
- `users` - Minimal user records (references Authentik)
- `devices` - Raspberry Pi devices with UUID, API key, last_seen
- `streams` - Shared message channels (public/private, text/image settings)
- `stream_subscriptions` - User memberships in streams
- `posts` - Messages/images posted to streams
- `device_stream_settings` - Per-device stream display configuration

### Important Relationships
- Devices belong to one user (1:N)
- Streams owned by one user, subscribed by many (N:M via subscriptions)
- Posts belong to one stream and one author (N:1)
- Devices can display multiple streams in rotation

## API Endpoints

### Core Endpoints
- `GET /api/health` - Health check (returns service status)
- `GET /docs` - FastAPI automatic API documentation (Swagger UI)
- `GET /redoc` - FastAPI automatic API documentation (ReDoc)

### Device Endpoints (For E Ink Devices)
**Authentication:** All device endpoints require `X-Device-Api-Key` header (except registration)

- `POST /api/devices/register` - Register device with UUID (returns API key - shown once!)
  - Request body: `{"device_uuid": "UUID", "nickname": "optional"}`
  - Returns: Device ID and API key

- `GET /api/devices/{id}/content` - Get current content to display
  - Returns: Latest post from device's assigned stream
  - Includes: content_type, text_content, image_url, stream_name, posted_at

- `POST /api/devices/{id}/heartbeat` - Update device last_seen timestamp
  - Devices should call this every 5-10 minutes

- `GET /api/devices/{id}/config` - Get device configuration
  - Returns: nickname, current_stream_id, rotation settings, version

### User Endpoints (Web UI)
Currently implemented through Reflex pages:
- `/` - Landing page (with direct OAuth link to Authentik)
- `/callback` - OAuth callback handler (processes code, creates user, sets cookie)
- `/streams` - Stream management UI (create streams, post messages, manage devices)

**Note:** `/login` page removed - index page links directly to Authentik OAuth URL to avoid WebSocket issues.

**Core business logic** in `streamscene/core/streams.py`:
- Stream CRUD: create_stream, get_stream_by_id, update_stream, delete_stream
- Post operations: create_post, get_stream_posts, get_latest_stream_post
- Subscriptions: subscribe_to_stream, unsubscribe_from_stream
- Device operations: register_device, get_device_content, update_device_heartbeat

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

The device client code lives in a separate `streamscene-client/` repository:

**Main Components:**
- `display/` - E Ink driver and rendering logic
- `network/` - WebSocket/REST API client
- `setup/` - BLE server for WiFi configuration
- `storage/` - Local content caching
- `updater/` - OTA update client

**Device Main Loop:**
1. Check WiFi connection → start BLE setup if needed
2. Check registration → show QR code if not registered
3. Check for OTA updates → download and install
4. Connect WebSocket to server
5. Listen for content updates and render to display

## MVP Scope

**Phase 1 (Current):**
- ✅ Text-only posts (images deferred to Phase 5)
- ✅ Stream creation and management
- ✅ User authentication via Authentik
- ✅ Device registration via QR + BLE WiFi setup
- ✅ WebSocket real-time updates
- ✅ OTA update system

**Deferred to v2:**
- ❌ Image upload and processing
- ❌ Stream discovery/search
- ❌ User profiles and analytics
- ❌ Advanced moderation tools

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

## Critical Decision Points

**Week 1 Day 5:** Validate Reflex can handle device API endpoints with WebSockets. If not, migrate to FastAPI while keeping UI in Reflex or switching entirely.

**WebSocket Stability:** If connection stability <90% after 1 week testing, immediately switch to polling fallback (60 second interval).

**Bluetooth Setup:** If BLE implementation takes >1 week or success rate <90%, fallback to ethernet-assisted setup.

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
