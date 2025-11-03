# StreamScene - Current Status

**Last Updated:** November 2, 2025 (Updated after authentication implementation session)
**Project:** StreamScene - Family E Ink Message Board
**Current Phase:** Phase 1.5 ✅ COMPLETE - Web Auth + Production Deployment

---

## ✅ Phase 1: COMPLETED - Core Backend & Device API

### **What We've Accomplished**

#### 1. Database Foundation
- ✅ SQLAlchemy ORM models (6 tables):
  - User (minimal, Authentik is source of truth)
  - Stream (message channels)
  - Post (text-only for MVP)
  - StreamSubscription (many-to-many user-stream relationships)
  - Device (E Ink devices)
  - DeviceStreamSettings (device rotation configuration)
- ✅ Alembic migrations initialized and applied
- ✅ 7 database tables created in PostgreSQL

#### 2. Core Business Logic
- ✅ `core/streams.py` (471 lines):
  - Stream CRUD operations
  - Post creation and retrieval
  - Subscription management
  - Permission helpers (can_user_view_stream, can_user_post_to_stream)
  - Device operations (register, get_content, heartbeat)
- ✅ `core/auth.py`:
  - User management (get_or_create_user)
  - API key generation (cryptographically secure)
  - API key hashing and verification (bcrypt)
  - Permission checks (is_stream_owner, is_post_author)

#### 3. FastAPI Device REST API
- ✅ Complete API implementation:
  - `api/__init__.py` - FastAPI app with CORS
  - `api/dependencies.py` - Database sessions and API key auth
  - `api/schemas.py` - Pydantic models for requests/responses
  - `api/routes/devices.py` - Device endpoints
- ✅ Integrated with Reflex using `api_transformer` parameter
- ✅ All endpoints tested and working:
  - `GET /api/health` - Health check
  - `POST /api/devices/register` - Register device, get API key
  - `GET /api/devices/{id}/content` - Get latest post to display
  - `POST /api/devices/{id}/heartbeat` - Update last_seen
  - `GET /api/devices/{id}/config` - Get device configuration
- ✅ API key authentication working (bcrypt hashed keys)
- ✅ Full data flow tested (user creates stream/post → device fetches content)

#### 4. Reflex Web UI + Production Authentication
- ✅ 3 pages (login page removed for direct OAuth):
  - `pages/index.py` - Landing page with direct OAuth link
  - `pages/callback.py` - OAuth callback handler (processes code, sets cookie)
  - `pages/streams.py` - Stream management UI (list, create, post)
- ✅ OAuth 2.0 / OIDC flow fully functional
- ✅ Cookie-based session management (`rx.Cookie()` State variables)
- ✅ Stream and post CRUD through UI
- ✅ **Production deployment working:** https://streamscene.dataandstories.com
- ✅ **Nginx Proxy Manager configured** for cross-container routing
- ✅ **WebSocket proxy working** for Reflex state management

#### 5. Testing
- ✅ 54 unit tests written (89% coverage):
  - `tests/test_models.py` - 10 tests (model creation, relationships)
  - `tests/test_auth.py` - 12 tests (user management, API keys)
  - `tests/test_streams.py` - 32 tests (CRUD operations, permissions)
- ✅ All tests passing
- ✅ Device API tested with curl (see `API_TESTING.md`)

### **Test Results**
See `API_TESTING.md` for comprehensive curl test documentation.

Key findings:
- ✅ All 5 device API endpoints working
- ✅ API key authentication secure
- ✅ Content delivery functional
- ✅ bcrypt key hashing working (truncated to 72 bytes)
- ✅ Invalid/missing keys properly rejected

---

## ✅ Phase 1.5: COMPLETED - Production Authentication & Deployment

### **What We Fixed (November 2, 2025 Session)**

#### Authentication Implementation
- ✅ **Direct OAuth Link:** Removed intermediate `/login` page, index links directly to Authentik
  - Fixes: WebSocket connection errors from premature page redirects
  - Implementation: OAuth URL built server-side in `index.py`, linked with `is_external=True`

- ✅ **Cookie-Based Sessions:** Switched from router.session to `rx.Cookie()` State variables
  - Problem: `router.session` is read-only in newer Reflex versions
  - Solution: `user_id: str = rx.Cookie("")` automatically syncs with browser
  - Usage: Direct assignment `self.user_id = "..."` sets cookie, read directly from State

- ✅ **OAuth Flow:** Complete authentication working end-to-end
  - Index → Authentik → Callback (code exchange) → Streams page
  - User created/fetched from database
  - Cookie persists across page loads

#### Production Deployment Configuration
- ✅ **Nginx Proxy Manager Setup:**
  - Main proxy: Forward to `192.168.1.118:3000` (frontend)
  - Advanced config: Route `/_event/` WebSocket to `:8000` backend
  - Advanced config: Route `/api/*` requests to `:8000` backend
  - **Critical Fix:** Use container IP (192.168.1.118), not 127.0.0.1

- ✅ **Reflex Configuration (`rxconfig.py`):**
  - Added `api_url` and `deploy_url` for production
  - Backend binds to 0.0.0.0:8000, frontend to 0.0.0.0:3000

- ✅ **Reliable Restart Script:** Created `restart-reflex.sh`
  - Finds processes by port (avoids "Address in use" errors)
  - Cleans up gracefully before restart
  - Clears Python cache

#### Files Modified
- `streamscene/pages/index.py` - Direct OAuth link generation
- `streamscene/pages/callback.py` - Cookie-based user_id storage
- `streamscene/pages/streams.py` - Cookie-based authentication check
- `streamscene/pages/login.py` - (Effectively deprecated, but kept for reference)
- `rxconfig.py` - Added production URLs
- `restart-reflex.sh` - New reliable restart script
- `CLAUDE.md` - Updated with authentication & deployment docs

#### Known Issues Resolved
- ❌ ~~Session assignment errors~~ → ✅ Fixed with `rx.Cookie()`
- ❌ ~~WebSocket 502 errors~~ → ✅ Fixed with correct container IP in Nginx
- ❌ ~~Port conflict on restart~~ → ✅ Fixed with restart script
- ❌ ~~Extra login button click~~ → ✅ Fixed with direct OAuth link

---

## 🚧 NEXT: Phase 2 - Device Client & Advanced Features

### **Immediate Next Steps**

#### 1. Add Device Management UI (Optional for MVP)
Currently device registration is tested via API only. Could add to `/streams` page:
- List user's devices
- Register new device form
- Display API key once
- Assign stream to device

#### 2. Raspberry Pi E Ink Client
Create Python client for Pi Zero 2 WH:
- Fetch content from `/api/devices/{id}/content`
- Render text to 800x480 E Ink display
- Handle 6-color palette
- Poll every 60 seconds minimum
- Send heartbeat every 5 minutes
- Handle network errors gracefully

#### 3. Celery Background Tasks
Set up asynchronous job processing:
- Image processing pipeline (resize, dither to 6 colors)
- Content rotation for devices
- Scheduled cleanup tasks

#### 4. Image Support (Phase 5 deferred feature)
Once MVP is stable:
- Add image upload to posts
- Implement image processing (Pillow)
- 6-color dithering (Floyd-Steinberg)
- Cache processed images

#### 5. Web UI Enhancements
- Better error handling in OAuth flow
- Device management interface
- Stream subscription approval workflow
- User profile page

---

## 📊 Architecture Validation

### **Key Decisions Confirmed**

✅ **Reflex + FastAPI works perfectly**
- Reflex handles web UI beautifully
- FastAPI (via `api_transformer`) provides REST API for devices
- Best of both worlds: Python-only development

✅ **Defensive architecture successful**
- All business logic in `core/` modules
- Framework-agnostic design
- Can swap frameworks if needed (but Reflex is working well)

✅ **bcrypt API keys secure**
- Keys are 86 characters (base64 from 64 bytes entropy)
- Properly hashed with bcrypt (truncated to 72 bytes)
- Verification working correctly

---

## 🔑 Key Files Reference

### Configuration
- `.env` - All environment variables (DATABASE_URL, REDIS_URL, OAuth credentials)
- `CREDENTIALS.md` - All passwords and secrets (NOT in git)
- `requirements.txt` - Python dependencies

### Core Business Logic (Framework-agnostic)
- `streamscene/core/models.py` - SQLAlchemy ORM models
- `streamscene/core/database.py` - Database session management
- `streamscene/core/auth.py` - User management, API keys
- `streamscene/core/streams.py` - Stream/post/device operations

### API Layer
- `streamscene/api/__init__.py` - FastAPI app initialization
- `streamscene/api/dependencies.py` - Auth and database dependencies
- `streamscene/api/schemas.py` - Pydantic models
- `streamscene/api/routes/devices.py` - Device endpoints

### Web UI
- `streamscene/streamscene.py` - Main app (integrates FastAPI)
- `streamscene/pages/index.py` - Landing page
- `streamscene/pages/login.py` - OAuth login
- `streamscene/pages/callback.py` - OAuth callback
- `streamscene/pages/streams.py` - Stream management

### Testing
- `tests/conftest.py` - Pytest fixtures
- `tests/test_models.py` - Model tests
- `tests/test_auth.py` - Auth tests
- `tests/test_streams.py` - Stream operation tests
- `API_TESTING.md` - Device API curl test documentation

### Documentation
- `CLAUDE.md` - Guide for Claude Code sessions
- `API_TESTING.md` - API test results and examples
- `NEXT_SESSION.md` - This file

---

## 💡 Quick Start Commands

### Run Development Server
```bash
cd /root/streamscene
source venv/bin/activate
reflex run
```
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Run Tests
```bash
source venv/bin/activate
pytest                                    # Run all tests
pytest --cov=streamscene                  # With coverage
pytest tests/test_streams.py              # Specific file
```

### Database Operations
```bash
# Connect to PostgreSQL
psql -U streamscene -d streamscene -h localhost

# Run migration
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

### Test Device API
```bash
# Health check
curl http://localhost:8000/api/health

# Register device
curl -X POST http://localhost:8000/api/devices/register \
  -H "Content-Type: application/json" \
  -d '{"device_uuid": "YOUR-UUID-HERE", "nickname": "My Frame"}'

# Get content (with API key from registration)
curl http://localhost:8000/api/devices/{device_id}/content \
  -H "X-Device-Api-Key: YOUR-API-KEY"
```

See `API_TESTING.md` for complete examples.

---

## 🎯 Phase 2 Priorities

### Week 2 Focus: Device Client Development

**Critical Path:**
1. **Raspberry Pi Client** (2-3 days)
   - Fetch content from API
   - Display on E Ink (use Waveshare examples)
   - Poll every 60+ seconds
   - Heartbeat every 5 minutes

2. **Error Handling** (1 day)
   - Network failures (retry with backoff)
   - API errors (graceful degradation)
   - Display "Offline" message if needed

3. **Testing** (1 day)
   - Test on actual Pi Zero 2 WH
   - Test with actual 7.3" E Ink display
   - Measure power consumption
   - Verify 60-second minimum refresh works

4. **Celery Setup** (Optional, 1 day)
   - Background task runner
   - Image processing (deferred to Phase 5)
   - Scheduled jobs

---

## 📈 Project Metrics

### Code Statistics
- **Total Lines:** ~2,800 (excluding tests)
- **Test Lines:** ~860
- **Test Coverage:** 89%
- **Files Created:** 25+
- **Git Commits:** 5

### Database
- **Tables:** 7 (6 models + alembic_version)
- **Migrations:** 1 (initial schema)
- **Test Users:** 1 (test-user-123)
- **Test Streams:** 1 (Family Updates)

### API
- **Endpoints:** 5 device endpoints + 1 health check
- **Authentication:** API key (bcrypt hashed)
- **Documentation:** Auto-generated (Swagger/ReDoc)

---

## 🔗 Important Links

- **Reflex Documentation:** https://reflex.dev/docs
- **FastAPI Documentation:** https://fastapi.tiangolo.com
- **Authentik OAuth:** http://192.168.1.108:9000
- **Waveshare E-Paper:** https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT
- **SQLAlchemy ORM:** https://docs.sqlalchemy.org/en/20/
- **Alembic Migrations:** https://alembic.sqlalchemy.org/

---

## 🚨 Known Issues / TODOs

1. **OAuth Registration Flow:** Device registration endpoint currently uses first user in database as workaround. Need to add user authentication to registration endpoint.

2. **Reflex Deprecation Warnings:** State auto-setters deprecated in 0.8.9. Need to define setters explicitly or set `state_auto_setters=False`.

3. **Icon Warning:** Invalid icon tag `alert_triangle` in streams.py - using fallback.

4. **Device Management UI:** Not yet implemented in web interface (devices can be registered via API only).

5. **WebSocket Support:** Not yet implemented (polling works, WebSockets can be added later for real-time updates).

---

## 📊 Project Status: Phase 1 Complete ✅

**Next Major Milestone:**
- Build Raspberry Pi E Ink client
- Test on actual hardware
- Set up Celery for background tasks
- Add device management UI (optional)

**Ready for Phase 2: Device Client Development** 🚀

---

**🎉 Phase 1 Achievement: Fully functional backend, REST API, and web UI in 1 session!**
