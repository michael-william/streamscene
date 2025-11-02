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

# Background tasks (Celery worker)
celery -A streamscene.core.tasks worker --loglevel=info

# Celery beat (scheduled tasks)
celery -A streamscene.core.tasks beat --loglevel=info
```

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

### Device Endpoints (Key for device client)
- `POST /api/devices/register` - Register device with UUID from QR code
- `GET /api/devices/{id}/config` - Get device configuration
- `GET /api/devices/{id}/content` - Get current content to display
- `POST /api/devices/{id}/heartbeat` - Device health check (every 30s)
- `WS /api/devices/{id}/stream` - WebSocket for real-time content updates

### User Endpoints
- `GET/POST/PUT/DELETE /api/streams` - Stream CRUD operations
- `POST /api/streams/{id}/posts` - Create post in stream
- `GET /api/streams/{id}/posts` - List posts (paginated)
- `POST /api/streams/{id}/subscribe` - Subscribe to stream

## Environment Configuration

Required `.env` variables:
```bash
DATABASE_URL=postgresql://streamscene:password@localhost/streamscene
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
AUTHENTIK_URL=http://192.168.1.108:9000
AUTHENTIK_CLIENT_ID=streamscene
AUTHENTIK_CLIENT_SECRET=your-client-secret
DOMAIN=streamscene.dataandstories.com
UPLOAD_PATH=/var/lib/streamscene/uploads
PROCESSED_PATH=/var/lib/streamscene/processed
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

### Web Users
1. User visits Reflex web app
2. Redirected to Authentik OAuth2 flow (http://192.168.1.108:9000)
3. After auth, Reflex creates session with user reference
4. Query Authentik API for user details (cached in Redis for 15min)

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
- **LXC Container:** StreamScene app (Debian 12, 4 cores, 4GB RAM, 50GB storage)
- **Authentik:** http://192.168.1.108:9000 (OAuth provider)
- **Nginx Proxy Manager:** http://192.168.1.104:81 (reverse proxy + SSL)
- **Domain:** dataandstories.com

**System Services:**
- PostgreSQL 15
- Redis Server
- Reflex web server (systemd service)
- Celery worker (systemd service)
- Celery beat scheduler (systemd service)

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
