# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

StreamScene is a family message board system using color E Ink displays (Waveshare 7.3" 6-color) on Raspberry Pi Zero 2 WH devices. Family members remotely post messages and images through "Streams" - shared channels displayed on physical E Ink frames.

**Key Constraint:** E Ink displays have ~30 second refresh time, limiting content rotation to minimum 60 second intervals.

## Quick Start Commands

```bash
# Development
source venv/bin/activate
reflex run

# Reliable restart (handles port conflicts)
./restart-reflex.sh

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Testing
pytest
pytest --cov=streamscene --cov-report=html

# Database
psql -U streamscene -d streamscene -h localhost

# Redis
redis-cli
```

## Architecture

### Code Structure Philosophy

**Defensive architecture** - business logic is framework-agnostic in `core/` to enable easy framework migration if Reflex proves limiting.

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
- **Device authentication:** API key (generated during device registration)
- **Background processing:** Celery + Redis for image processing, notifications

### Key Design Decisions

**Device Provisioning:**
- Pre-configured SD cards with unique UUIDs in `/boot/streamscene-device.txt`
- QR code sticker on each device for user registration
- WiFi hotspot + captive portal for WiFi setup (no BLE)

**Database Strategy:**
- PostgreSQL for all data persistence
- Authentik is single source of truth for user data (only store user ID reference)
- Redis for WebSocket connection state, session caching, Celery broker

**Update Strategy:**
- Over-The-Air (OTA) updates via WebSocket push
- Staged rollout (10% → 50% → 100% of devices)
- Automatic rollback on failure
- See `docs/reference/OTA_SYSTEM.md` for details

## Current Phase: Phase 5 (Device State Machine & Registration)

**Status:** 🚧 IN PROGRESS

**Goal:** Integrate WiFi setup into main device loop and implement registration flow

**Completed Phases:**
- ✅ Phase 0: Infrastructure Setup
- ✅ Phase 1: Web App Core
- ✅ Phase 2-3: OTA Update Infrastructure (server-side)
- ✅ Phase 4: WiFi Setup System

**Current Tasks:**
- Create device state machine (`client/state_machine.py`)
- Create registration module (`client/registration.py`)
- Update main device loop (`client/main.py`)

**Next Phases:**
- Phase 6: E Ink Display Integration
- Phase 7: WebSocket & Content Display
- Phase 8: OTA Update Client

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
- Use **UUID primary keys** for all tables
- Add indexes for frequently queried fields
- Use **Alembic** for all schema changes (never manual SQL DDL)

See `docs/reference/DATABASE_SCHEMA.md` for complete schema documentation.

## Essential Gotchas (Top 10)

### 1. Don't Bypass Business Logic
Always call functions in `core/`, never duplicate logic in `ui/` or `api/`.

### 2. API Keys Must Be Hashed
Never store plaintext API keys in database (use bcrypt).

### 3. Use UUIDs Everywhere
All primary keys are UUIDs, not integers.

### 4. Reflex Session is Read-Only
Use `rx.Cookie()` State variables for authentication, not `router.session`.

### 5. Use on_load for Router Params
`on_mount()` fires before `router.page.params` is populated. Use `on_load()` method instead.

### 6. Reflex Var Compatibility
Use `rx.cond()` instead of Python `if` statements when working with Vars. Never use `if`, `and`, `or`, `not` directly on Reflex Vars.

### 7. WiFi Adapter Mode Conflicts (Raspberry Pi)
Single WiFi adapter can only be in ONE mode (AP or client). Must stop and mask services before mode switch.

### 8. Nginx Cross-Container Routing
Use container IP (192.168.1.118), not 127.0.0.1 for proxy targets.

### 9. Port Conflicts on Restart
Use `./restart-reflex.sh` to cleanly kill processes by port before restarting.

### 10. Pre-Process Images Server-Side
Pi Zero has limited CPU - don't process images on device.

**See `docs/development/GOTCHAS.md` for all 22 gotchas with detailed solutions.**

## Authentication Flows

### Web Users (OAuth2 + Cookies)

1. User visits `/` → clicks "Sign In" → redirected to Authentik
2. Authentik redirects to `/callback?code=...`
3. Callback exchanges code for access token and user info
4. User ID stored in `rx.Cookie()` State variable (auto-synced to browser)
5. Redirects to `/streams` page

**Implementation:** Cookie storage via `rx.Cookie("")`, no intermediate login page (avoids WebSocket issues).

### Device Authentication (API Keys)

1. Device boots with pre-configured UUID from `/boot/firmware/streamscene-device.txt`
2. Device enters `AWAITING_REGISTRATION` state and displays QR code
3. User scans QR code → opens web registration page
4. Server generates API key and temporarily stores in `device.config["pending_api_key"]`
5. Device polls `/api/devices/{id}/registration-status` (unauthenticated, every 10s)
6. Server returns API key ONE TIME, then clears from config
7. Device saves API key to `/boot/firmware/streamscene-apikey.txt`
8. All future requests include `X-Device-API-Key` header

**Security:** API keys hashed with bcrypt in database. Plaintext only exposed once during registration.

## Device Client (Raspberry Pi)

### Main Components

- `display.py` - E Ink driver and rendering logic
- `api_client.py` - WebSocket/REST API client
- `setup/` - WiFi hotspot and captive portal for setup
- `renderer.py` - Content rendering for E Ink
- `main.py` - Device main loop

### Device Main Loop (Target)

1. Check WiFi connection → start hotspot + captive portal if needed
2. Check registration → show QR code if not registered
3. Check for OTA updates → download and install
4. Connect WebSocket to server
5. Listen for content updates and render to display

### WiFi Setup Flow

1. Device boots without WiFi credentials
2. Hotspot mode activated (StreamScene-XXXX network)
3. User connects phone, captive portal auto-opens
4. User submits WiFi credentials via HTML form
5. Hotspot stopped, WiFi client mode activated
6. Device connects to home WiFi and proceeds to registration

**Tested end-to-end on Raspberry Pi Zero 2 WH.**

See `docs/deployment/WIFI_SETUP.md` for comprehensive testing guide.

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

Composable architecture for displaying E Ink previews in web UI:
- Theme system (5 pre-defined themes)
- Dynamic font sizing based on content length
- Reflex Var compatible (uses `rx.cond()`)

**Usage:**
```python
from streamscene.components.eink import eink_preview

preview = eink_preview(
    text_content=StreamPostsState.new_post_content,
    stream_name="Family Updates",
    author_name="You",
    theme_name="classic"
)
```

See `docs/plans/EINK_PREVIEW.md` for architecture details.

## Infrastructure

### Homelab Resources

- **LXC Container (StreamScene):** 192.168.1.118 (Debian 12, 4 cores, 4GB RAM)
- **LXC Container (Authentik):** 192.168.1.108:9000 (OAuth provider)
- **LXC Container (Nginx Proxy Manager):** 192.168.1.104:81 (reverse proxy + SSL)
- **Domain:** dataandstories.com

### System Services

- PostgreSQL 15
- Redis Server
- Reflex web server (frontend :3000, backend :8000)
- Celery worker (systemd service - not yet configured)
- Celery beat scheduler (systemd service - not yet configured)

See `docs/deployment/PRODUCTION.md` for complete deployment guide.

## Documentation Map

### Reference Documentation

- **`docs/reference/API_ENDPOINTS.md`** - Complete API endpoint reference (device & web)
- **`docs/reference/DATABASE_SCHEMA.md`** - Database schema, relationships, indexes
- **`docs/reference/OTA_SYSTEM.md`** - OTA update infrastructure and workflows
- **`docs/reference/ENVIRONMENT.md`** - Environment variables and configuration

### Development Guides

- **`docs/development/GOTCHAS.md`** - All 22 common gotchas with solutions (categorized)

### Deployment Documentation

- **`docs/deployment/PRODUCTION.md`** - Production deployment, Nginx config, systemd services
- **`docs/deployment/WIFI_SETUP.md`** - WiFi setup system testing guide
- **`docs/deployment/AUTHENTIK_SETUP.md`** - Authentik OAuth configuration
- **`docs/deployment/HARDWARE_TESTING.md`** - E Ink hardware testing procedures

### Planning Documents

- **`docs/plans/DEVICE_SETUP_OTA.md`** - Device setup and OTA implementation plan
- **`docs/plans/EINK_PREVIEW.md`** - E Ink preview system architecture

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

## Support Resources

- [Reflex Documentation](https://reflex.dev/docs)
- [Waveshare 7.3" E-Paper Wiki](https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT)
- [Authentik OAuth2 Setup](https://docs.goauthentik.io/docs/providers/oauth2)
- [SQLAlchemy ORM Docs](https://docs.sqlalchemy.org/en/20/)
