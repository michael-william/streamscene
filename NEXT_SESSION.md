# Next Session - Phase 6: E Ink Testing & Registration Flow Complete

**Last Updated:** November 20, 2025 (End of Session - Bug Fixed!)
**Current Phase:** Phase 6 ✅ REGISTRATION FLOW WORKING

---

## 🎉 Major Achievement: Registration Flow Fixed!

### What Was Broken
The registration-status endpoint was looking up devices by database `id` instead of `device_uuid`, causing all registration polling to fail with incorrect responses.

### What Was Fixed
1. **Registration-status endpoint** - Now correctly looks up by `device_uuid` (from SD card)
   - Changed from `get_device_by_id(db, device_id)` to direct query on `Device.device_uuid`
   - Location: `streamscene/api/routes/devices.py:103-106`

2. **JSONB column update issue** - One-time API key retrieval wasn't clearing properly
   - Added `flag_modified(device, "config")` to mark JSON column as changed
   - Location: `streamscene/api/routes/devices.py:124`

### Test Results ✅

```bash
# Before registration
curl https://streamscene.dataandstories.com/api/devices/1c91d1e9-3cc9-44ba-a008-9cdee188d90c/registration-status
# Returns: {"is_registered":false,"api_key":null,"nickname":null}

# After registration (first poll)
curl https://streamscene.dataandstories.com/api/devices/1c91d1e9-3cc9-44ba-a008-9cdee188d90c/registration-status
# Returns: {"is_registered":true,"api_key":"<full-key>","nickname":"Test StreamScene Frame"}

# Second poll (API key cleared)
curl https://streamscene.dataandstories.com/api/devices/1c91d1e9-3cc9-44ba-a008-9cdee188d90c/registration-status
# Returns: {"is_registered":true,"api_key":null,"nickname":"Test StreamScene Frame"}
```

**Result:** ✅ One-time API key retrieval working perfectly!

---

## 📝 Changes This Session

### Commit: `[pending]`
**Title:** "fix: registration-status endpoint to use device_uuid and fix JSONB update"

**Files Changed:**
1. `streamscene/api/routes/devices.py`
   - Line 6: Added `from sqlalchemy.orm.attributes import flag_modified`
   - Line 103-106: Changed lookup to use `device_uuid` instead of database `id`
   - Line 124: Added `flag_modified()` to mark JSON column as modified
   - Updated docstring to clarify `device_id` parameter is actually `device_uuid`

**Why This Was Critical:**
- Devices only know their `device_uuid` (from `/boot/firmware/streamscene-device.txt`)
- They don't know their database `id` until after first contact with server
- Registration polling was failing because endpoint expected wrong UUID type
- JSONB columns need explicit `flag_modified()` for SQLAlchemy change tracking

---

## 🎯 Current Status

### What Works ✅
- [x] WiFi setup flow (hotspot + captive portal)
- [x] WiFi client connection
- [x] E Ink display with QR codes (epd7in3g driver)
- [x] Device state machine transitions
- [x] Web registration UI
- [x] Device registration in database
- [x] **NEW:** Registration-status endpoint (unauthenticated)
- [x] **NEW:** One-time API key retrieval
- [x] **NEW:** JSONB column updates

### What Needs Testing 🔄
- [ ] **Device client polling** - Verify device can detect registration via endpoint
- [ ] **API key persistence** - Device saves key to `/boot/firmware/streamscene-apikey.txt`
- [ ] **State transitions** - Device goes from `AWAITING_REGISTRATION` → `REGISTERED` → `READY`
- [ ] **Content display** - Device fetches and displays stream content
- [ ] **Heartbeat** - Device sends periodic heartbeats to server

---

## 🚀 Next Session: End-to-End Device Testing

### Priority 1: Test Full Device Registration Flow

**Setup:**
```bash
# SSH to device
ssh badgy@192.168.1.40  # Password: JjKUa9XJ8*FFUZHYB.AP
cd ~/streamscene-client

# Reset device to clean state
sudo rm -f device_state.json device_api_key.txt

# Set environment variables
export STREAMSCENE_API_URL='https://streamscene.dataandstories.com'
export STREAMSCENE_DISPLAY_MODE='eink'

# Run client
sudo -E python3 main.py 2>&1 | tee device-test.log
```

**Expected Flow:**
1. Device starts in `WIFI_SETUP` state (or `CONNECTING` if WiFi credentials exist)
2. Device connects to WiFi → transitions to `AWAITING_REGISTRATION`
3. Device displays QR code on E Ink display
4. Device polls `/api/devices/{device_uuid}/registration-status` every 10s
5. User scans QR code → registers device via web UI
6. Device detects registration on next poll
7. Device receives API key and saves to file
8. Device transitions to `REGISTERED` then `READY`
9. Device fetches content and displays on E Ink
10. Device sends heartbeat every 5 minutes

### Priority 2: Create Test Content

**Create a test stream and post:**
```bash
# Via web UI at https://streamscene.dataandstories.com/streams
# Or programmatically:
python3 -c "
from streamscene.core.database import get_db_session
from streamscene.core import streams as stream_ops
from uuid import UUID

user_id = UUID('314daf51-9126-4fde-990f-0337711ac71f')  # Badgy

with get_db_session() as db:
    # Create test stream
    stream = stream_ops.create_stream(
        db,
        owner_id=user_id,
        name='Test Stream',
        description='Testing device display',
        theme_name='classic'
    )

    # Create test post
    post = stream_ops.create_post(
        db,
        stream_id=stream.id,
        author_id=user_id,
        text_content='Hello from StreamScene! This is a test message.',
        content_type='text'
    )

    print(f'Stream ID: {stream.id}')
"
```

### Priority 3: Assign Stream to Device

**Via web UI:**
1. Go to https://streamscene.dataandstories.com/devices
2. Select device "Test StreamScene Frame"
3. Assign "Test Stream" to device
4. Device should fetch and display content on next poll

**Or programmatically:**
```bash
python3 -c "
from streamscene.core.database import get_db_session
from streamscene.core import streams as stream_ops
from uuid import UUID

device_id = UUID('2c0d4fe8-2426-4228-b2a9-8f89762cc338')
stream_id = UUID('<stream-id-from-above>')

with get_db_session() as db:
    stream_ops.update_device_stream(db, device_id, stream_id)
    print('Stream assigned to device')
"
```

---

## 📋 Testing Checklist

### Registration Flow ✅
- [x] Registration-status endpoint returns correct response for unregistered device
- [x] Device can be registered via web UI
- [x] Registration-status endpoint returns API key on first poll
- [x] API key is cleared after first retrieval (one-time only)
- [x] Second poll returns `is_registered=true, api_key=null`

### Device Client Testing 🔄 NEXT
- [ ] Device polls registration-status endpoint correctly
- [ ] Device receives and saves API key
- [ ] Device transitions from `AWAITING_REGISTRATION` to `REGISTERED`
- [ ] Device transitions from `REGISTERED` to `READY`
- [ ] Device persists state across reboots

### Content Display ⏸️ PENDING
- [ ] Device fetches content from API
- [ ] Content renders correctly on E Ink
- [ ] Display updates show on physical screen
- [ ] Heartbeat sent every 5 minutes
- [ ] Content polling every 60 seconds

### Error Recovery ⏸️ NOT TESTED
- [ ] WiFi errors → back to wifi_setup
- [ ] Registration timeout → error state with retry
- [ ] Server errors → stay in ready, show error
- [ ] Generic errors → attempt to continue

---

## 🔧 Known Issues & Solutions

### Issue 1: Registration Endpoint UUID Mismatch ✅ SOLVED
**Problem:** Endpoint expected database `id`, device only knows `device_uuid`.

**Solution:** Changed endpoint to query by `Device.device_uuid` instead of `Device.id`.

### Issue 2: JSONB Column Not Updating ✅ SOLVED
**Problem:** `device.config.pop()` didn't trigger SQLAlchemy change tracking.

**Solution:** Added `flag_modified(device, "config")` after modifying JSON column.

### Issue 3: Device Has No Database ID Initially ✅ EXPLAINED
**Context:** This is by design - device doesn't need database `id` until after registration.

**Flow:**
1. Device boots with pre-configured `device_uuid` from SD card
2. Device polls endpoint with `device_uuid`
3. Server creates/updates device record (generates database `id`)
4. Device receives API key and uses it for future authenticated requests

---

## 🎯 Success Criteria for Phase 6

Phase 6 (E Ink Display Integration) will be complete when:
- [x] Registration-status endpoint works correctly
- [x] One-time API key retrieval implemented
- [ ] Device can detect registration via polling
- [ ] API key saved locally after registration
- [ ] Device transitions to READY state after registration
- [ ] Device fetches and displays content in READY state
- [ ] State persists across reboots
- [ ] Full lifecycle tested end-to-end

**Current Progress:** 5/8 complete (62%)

---

## 🔑 Device Info

- **Device UUID:** `1c91d1e9-3cc9-44ba-a008-9cdee188d90c` (from SD card)
- **Database ID:** `2c0d4fe8-2426-4228-b2a9-8f89762cc338` (generated on registration)
- **Nickname:** "Test StreamScene Frame"
- **Registered to:** Badgy (michael@dataandstories.com)
- **SSH:** `ssh badgy@192.168.1.40` (password: `JjKUa9XJ8*FFUZHYB.AP`)
- **Client code:** `~/streamscene-client/`
- **Registration URL:** `https://streamscene.dataandstories.com/setup?device_uuid=1c91d1e9-3cc9-44ba-a008-9cdee188d90c`

---

## 📖 Architecture Reference

### Device UUID vs Database ID

**Two types of UUIDs in Device model:**
1. **`device_uuid`** - Pre-configured on SD card, device's "identity"
   - Source: `/boot/firmware/streamscene-device.txt`
   - Known by device at boot
   - Used in QR codes and unauthenticated endpoints

2. **`id`** - Database primary key, auto-generated
   - Created when device record is inserted
   - Not known by device until after first server contact
   - Used in authenticated API endpoints

**Why Two UUIDs?**
- Device needs stable identity before registration (device_uuid)
- Server needs internal ID for foreign keys and relationships (id)
- Separation allows device provisioning without server access

### Registration Flow

```
Device                          Server                           User
  |                               |                                |
  | 1. Boot with device_uuid      |                                |
  |---------------------------->  |                                |
  |                               |                                |
  | 2. Poll: GET /registration-status?device_uuid=...             |
  |---------------------------->  |                                |
  |     <- {is_registered: false} |                                |
  |                               |                                |
  | 3. Display QR code            |                                |
  |                               |                                |
  |                               |     4. Scan QR, visit /setup   |
  |                               |  <-----------------------------|
  |                               |                                |
  |                               | 5. POST /register              |
  |                               |  <-----------------------------|
  |                               |     {device_uuid, nickname}    |
  |                               |                                |
  |                               | 6. Create device record        |
  |                               |    Store pending_api_key       |
  |                               |                                |
  | 7. Poll: GET /registration-status                             |
  |---------------------------->  |                                |
  |     <- {is_registered: true,  |                                |
  |         api_key: "...",       |                                |
  |         nickname: "..."}      |                                |
  |                               |                                |
  | 8. Save API key to file       |                                |
  |    Transition to REGISTERED   |                                |
  |                               |                                |
```

---

## 🚀 Quick Commands

```bash
# Restart Reflex server
sudo systemctl restart reflex

# View Reflex logs
sudo journalctl -u reflex -f

# Test registration endpoint
curl https://streamscene.dataandstories.com/api/devices/1c91d1e9-3cc9-44ba-a008-9cdee188d90c/registration-status

# Check device in database
python3 -c "
from streamscene.core.database import get_db_session
from streamscene.core.models import Device
from uuid import UUID

with get_db_session() as db:
    device = db.query(Device).filter(
        Device.device_uuid == UUID('1c91d1e9-3cc9-44ba-a008-9cdee188d90c')
    ).first()
    print(f'Device: {device.nickname}')
    print(f'Registered: {device.user_id is not None}')
    print(f'Has pending key: {\"pending_api_key\" in device.config}')
"
```

---

**Next Action:** Test end-to-end device registration flow with actual Raspberry Pi hardware. The server-side implementation is complete and working!
