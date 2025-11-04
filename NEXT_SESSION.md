# StreamScene - Current Status

**Last Updated:** November 4, 2025 (Testing on_load() lifecycle fix)
**Project:** StreamScene - Family E Ink Message Board
**Current Phase:** Phase 2 🚧 IN PROGRESS - Fixing Router Params Timing Issue

---

## 🚨 CURRENT ISSUE - Testing Solution

**"No stream specified" error when navigating to stream posts**

### Current Status: 🔄 TESTING on_load() Solution

**Route:** `/stream-posts?id={uuid}` (switched from dynamic routes to query params)

**Problem:**
- Router query parameters empty during component lifecycle
- Users see "No stream specified" error
- Posts can still be created (stream loads eventually)

**Root Cause:**
- Using `on_mount()` (component-level) instead of `on_load()` (page-level)
- Router params not populated when `on_mount()` fires
- Timing issue between component mount and router initialization

**Solution Attempt #3:**
- ✅ Changed `on_mount()` → `on_load()` in `stream_posts.py`
- ✅ Added fallback to `router.session.client_query_params` (from callback.py pattern)
- ✅ Added extensive debug logging
- ✅ Clear error messages before checking params
- 🔄 Testing in progress...

**Files Changed:**
- `streamscene/pages/stream_posts.py` - Lines 35-69 (on_load method)
- `streamscene/pages/stream_posts.py` - Line 287 (component lifecycle hook)

**Documentation:**
- See `DEBUGGING_HISTORY.md` for full debugging journey
- Tracks all 3 attempts: dynamic routes, on_mount, on_load

**Test URL:** https://streamscene.dataandstories.com/stream-posts?id=4ffed4d7-d1df-4bf9-bd57-0a5df5f52874

---

## 🔍 Debugging Journey (November 4, 2025)

### Attempt #1: Dynamic Routes with Slugs ❌
- Route: `/streams/[slug]`
- Failed: `DynamicRouteArgShadowsStateVarError`
- Issue: Reflex auto-creates slug var, timing issues

### Attempt #2: Query Params with on_mount() ❌
- Route: `/stream-posts?id={uuid}`
- Failed: `router.page.params` empty during on_mount
- Issue: Component-level lifecycle too early

### Attempt #3: Query Params with on_load() 🔄
- Route: `/stream-posts?id={uuid}`
- Change: Component → Page lifecycle method
- Pattern: Copied from working callback.py
- Status: **CURRENTLY TESTING**

---

## ✅ Recent Accomplishments (November 3, 2025)

### 1. URL Slugs Implementation
- ✅ Added `slug` field to Stream model (unique, indexed)
- ✅ Created Alembic migration that auto-generates slugs for existing streams
- ✅ Implemented slug generation utilities in `streamscene/core/utils.py`:
  - `generate_slug()` - Converts stream names to URL-safe slugs
  - `ensure_unique_slug()` - Guarantees uniqueness (appends -2, -3, etc.)
- ✅ Updated `create_stream()` to auto-generate unique slugs
- ✅ Added `get_stream_by_slug()` function for slug-based lookups
- ✅ URLs now use readable slugs instead of UUIDs

**URL Structure:**
- Old: `/streams/4ffed4d7-d1df-4bf9-bd57-0a5df5f52874`
- New: `/streams/family-updates` or `/streams/first`

### 2. Separate Stream Posts Pages
- ✅ Created new dynamic route: `/streams/[slug]`
- ✅ Added `streamscene/pages/stream_posts.py` for viewing/creating posts
- ✅ Removed post viewing from main `/streams` page (now full-width stream list)
- ✅ Added back button to return to streams list
- ✅ Implemented proper authentication with `require_auth()` helper

### 3. UI Layout Improvements
- ✅ Updated `/streams` page to single-column layout
- ✅ Separated "Streams I Own" and "Streams I'm Subscribed To" tables
- ✅ Added search functionality across both tables
- ✅ Moved stream creation to modal dialog
- ✅ Updated "View Posts" buttons to link to slug-based URLs
- ✅ Added proper empty states

---

## ✅ Phase 1: COMPLETED - Core Backend & Device API

### **What We've Accomplished**

#### 1. Database Foundation
- ✅ SQLAlchemy ORM models (6 tables):
  - User (minimal, Authentik is source of truth)
  - Stream (message channels) **+ slug field**
  - Post (text-only for MVP)
  - StreamSubscription (many-to-many user-stream relationships)
  - Device (E Ink devices)
  - DeviceStreamSettings (device rotation configuration)
- ✅ Alembic migrations: 2 applied (initial + slug field)
- ✅ 7 database tables created in PostgreSQL

#### 2. Core Business Logic
- ✅ `core/streams.py`:
  - Stream CRUD operations (with slug generation)
  - Post creation and retrieval
  - Subscription management
  - Permission helpers (can_user_view_stream, can_user_post_to_stream)
  - Device operations (register, get_content, heartbeat)
  - **NEW:** `get_stream_by_slug()` function
- ✅ `core/auth.py`:
  - User management (get_or_create_user)
  - API key generation (cryptographically secure)
  - API key hashing and verification (bcrypt)
  - Permission checks (is_stream_owner, is_post_author)
- ✅ **NEW:** `core/utils.py`:
  - Slug generation utilities
  - Unique slug enforcement

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

#### 4. Reflex Web UI + Production Authentication
- ✅ 4 pages:
  - `pages/index.py` - Landing page with direct OAuth link
  - `pages/callback.py` - OAuth callback handler (processes code, sets cookie)
  - `pages/streams.py` - Stream management UI (full-width, table-based)
  - **NEW:** `pages/stream_posts.py` - Dynamic posts page per stream
- ✅ OAuth 2.0 / OIDC flow fully functional
- ✅ Cookie-based session management (`rx.Cookie()` State variables)
- ✅ Stream and post CRUD through UI
- ✅ **Production deployment working:** https://streamscene.dataandstories.com
- ✅ **Nginx Proxy Manager configured** for cross-container routing
- ✅ **WebSocket proxy working** for Reflex state management

#### 5. Testing
- ✅ 54 unit tests written (89% coverage)
- ✅ All tests passing
- ✅ Device API tested with curl (see `API_TESTING.md`)

---

## 🚧 Current Sprint: UI Polish & Bug Fixes

### Immediate Tasks

1. **DEBUG SLUG LOOKUP ISSUE** (Highest Priority)
   - Fix "Stream not found" error when accessing `/streams/first`
   - Verify dynamic route parameter is being read correctly
   - Test slug lookup with existing streams

2. **UI Polish**
   - Add loading states to stream posts page
   - Improve error messaging
   - Add success confirmations for post creation

3. **Testing**
   - Test creating new streams (verify slug generation)
   - Test slug uniqueness (create streams with same name)
   - Test navigation between streams list and posts

---

## 🔑 Key Files Reference

### Configuration
- `.env` - Environment variables
- `CREDENTIALS.md` - Passwords and secrets
- `requirements.txt` - Python dependencies

### Core Business Logic (Framework-agnostic)
- `streamscene/core/models.py` - SQLAlchemy ORM models
- `streamscene/core/database.py` - Database session management
- `streamscene/core/auth.py` - User management, API keys
- `streamscene/core/streams.py` - Stream/post/device operations
- **NEW:** `streamscene/core/utils.py` - Slug generation utilities

### API Layer
- `streamscene/api/__init__.py` - FastAPI app initialization
- `streamscene/api/dependencies.py` - Auth and database dependencies
- `streamscene/api/schemas.py` - Pydantic models
- `streamscene/api/routes/devices.py` - Device endpoints

### Web UI
- `streamscene/streamscene.py` - Main app (routes registration)
- `streamscene/pages/index.py` - Landing page
- `streamscene/pages/callback.py` - OAuth callback
- `streamscene/pages/streams.py` - Stream list (table view)
- **NEW:** `streamscene/pages/stream_posts.py` - Stream posts page
- `streamscene/pages/base_state.py` - Shared authentication state

### Database Migrations
- `alembic/versions/536ca4a23ba0_*.py` - Initial schema
- **NEW:** `alembic/versions/4a8af4c1fe26_*.py` - Add slug field

### Testing
- `tests/conftest.py` - Pytest fixtures
- `tests/test_models.py` - Model tests
- `tests/test_auth.py` - Auth tests
- `tests/test_streams.py` - Stream operation tests

### Documentation
- `CLAUDE.md` - Guide for Claude Code sessions
- `NEXT_SESSION.md` - This file
- `STREAMS_PAGE_REDESIGN.md` - Redesign plan (implemented)

---

## 💡 Quick Start Commands

### Run Development Server
```bash
cd /root/streamscene
source venv/bin/activate
reflex run
# or use reliable restart:
./restart-reflex.sh
```
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Production: https://streamscene.dataandstories.com

### Run Tests
```bash
source venv/bin/activate
pytest
pytest --cov=streamscene
```

### Database Operations
```bash
# View streams with slugs
PGPASSWORD='43cYkZeh4Li3EWTEjKm7Du8JCIbjiLQfWMmkvb7pKKQ' \
  psql -U streamscene -d streamscene -h localhost \
  -c "SELECT name, slug FROM streams;"

# Run migration
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

---

## 🔧 Known Issues

### 1. **Stream Not Found Error (CRITICAL)**
- **Issue:** Accessing `/streams/first` shows "Stream not found: first"
- **Impact:** Users cannot view posts via slug URLs
- **Debug Priority:** HIGH
- **Next Step:** Check dynamic route parameter binding in `stream_posts.py`

### 2. **Reflex Deprecation Warnings**
- State auto-setters deprecated in 0.8.9
- Need to define setters explicitly or set `state_auto_setters=False`
- **Impact:** Low (warnings only)
- **Priority:** LOW

### 3. **Database Migration Warning**
- "Target database is not up to date" warning on startup
- Migrations are actually up to date (alembic alembic_version shows latest)
- **Impact:** None (cosmetic warning)
- **Priority:** LOW

---

## 📊 Project Metrics

### Code Statistics
- **Total Lines:** ~3,300 (excluding tests)
- **Test Lines:** ~860
- **Test Coverage:** 89%
- **Files Created:** 30+
- **Git Commits:** 7

### Database
- **Tables:** 7
- **Migrations:** 2
- **Test Streams:** 2 ("Family Updates", "First")
- **Slugs Generated:** 2 ("family-updates", "first")

### API
- **Endpoints:** 5 device endpoints + 1 health check
- **Authentication:** API key (bcrypt hashed) + OAuth2/OIDC
- **Documentation:** Auto-generated (Swagger/ReDoc)

---

## 🎯 Next Session Priorities

1. **FIX SLUG LOOKUP BUG** - Get `/streams/first` working
2. Test full flow: create stream → view posts → create post
3. Add loading states and better error handling
4. Consider adding stream editing/deletion features
5. Polish UI: Better spacing, colors, responsive design

---

## 🔗 Important Links

- **Production:** https://streamscene.dataandstories.com
- **Reflex Docs:** https://reflex.dev/docs
- **Authentik OAuth:** http://192.168.1.108:9000
- **Waveshare E-Paper:** https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT

---

**🎉 Progress: Phase 1 Complete + URL Slugs & Dynamic Pages Implemented!**
**⚠️ Current Blocker: Slug lookup issue needs debugging**
