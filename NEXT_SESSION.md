# Next Session - Device Integration

**Last Updated:** November 9, 2025 (After WiFi Setup & OTA Infrastructure)
**Current Phase:** Phase 4 ✅ COMPLETE - WiFi Hotspot & Captive Portal

---

## 🎉 What We Just Completed

### Phase 1-4: Device Setup Infrastructure ✅

**Commits:**
- `e4ff01b` - WiFi setup + OTA infrastructure (2,593 lines, 12 files)
- `4bf6389` - Documentation updates (271 lines to CLAUDE.md)

**Server-Side (Phases 1-3):**
- ✅ OTA Update database models (DeviceUpdate, UpdateDeployment)
- ✅ Staged rollout algorithm (hash-based percentage distribution)
- ✅ QR code generation for device registration
- ✅ 3 new device API endpoints (check updates, download, report status)

**Client-Side (Phase 4):**
- ✅ WiFi hotspot creation (`client/setup/hotspot.py`)
- ✅ Captive portal server (`client/setup/portal_server.py`)
- ✅ WiFi client connection (`client/setup/wifi_client.py`)
- ✅ End-to-end tested on Raspberry Pi Zero 2 WH
- ✅ Deployment script (`deploy_to_pi.sh`)
- ✅ 450-line deployment guide (`client/WIFI_SETUP_DEPLOYMENT.md`)

**Device Status:**
- SSH: `ssh badgy@192.168.1.40` (password: `JjKUa9XJ8*FFUZHYB.AP`)
- Device UUID: `1c91d1e9-3cc9-44ba-a008-9cdee188d90c`
- Location: `~/streamscene-client/` on the Pi
- WiFi setup: Fully functional (tested successfully)

---

## 🎯 Next Session: Phase 5 - Device State Machine & Registration

### Goal
Integrate WiFi setup into main device loop and implement the registration flow with QR code display.

### Tasks

#### 1. Create Device State Machine (`client/state_machine.py`)

**States to implement:**
1. **WIFI_SETUP** - No WiFi credentials or not connected
2. **REGISTRATION** - WiFi connected but device not registered with server
3. **OPERATIONAL** - Registered and ready to display content
4. **ERROR** - Recoverable error state

**Basic structure:**
```python
class DeviceState(Enum):
    WIFI_SETUP = "wifi_setup"
    REGISTRATION = "registration"
    OPERATIONAL = "operational"
    ERROR = "error"

class StateMachine:
    def __init__(self, device_uuid: str):
        self.state = DeviceState.WIFI_SETUP
        self.device_uuid = device_uuid
        self.api_key = None

    def run(self):
        """Main state machine loop."""
        while True:
            if self.state == DeviceState.WIFI_SETUP:
                self.handle_wifi_setup()
            elif self.state == DeviceState.REGISTRATION:
                self.handle_registration()
            elif self.state == DeviceState.OPERATIONAL:
                self.handle_operational()
            elif self.state == DeviceState.ERROR:
                self.handle_error()
```

#### 2. Create Registration Module (`client/registration.py`)

**Functions needed:**
- `generate_registration_qr()` - Generate QR code from device UUID
- `check_registration_status()` - Poll server to see if device is registered
- `save_api_key()` - Store API key locally after registration
- `load_api_key()` - Load saved API key on startup

**QR Code format:**
```
https://streamscene.dataandstories.com/register?device_uuid=1c91d1e9-3cc9-44ba-a008-9cdee188d90c
```

#### 3. Update Main Loop (`client/main.py`)

Integrate state machine:
```python
from state_machine import StateMachine

def main():
    # Load device UUID from /boot/firmware/streamscene-device.txt
    device_uuid = load_device_uuid()

    # Initialize state machine
    sm = StateMachine(device_uuid)

    # Run forever
    sm.run()
```

#### 4. E Ink Display Updates (Phase 6 Preview)

Add display helpers for setup states:
- Show "Connect to StreamScene-XXXX" during WiFi setup
- Display QR code for registration
- Show "Loading..." during operational state

**File to modify:** `client/display.py`

---

## 📋 Step-by-Step Implementation Plan

### Step 1: Test Existing WiFi Setup (Verify it still works)
```bash
ssh badgy@192.168.1.40
cd ~/streamscene-client
rm wifi_credentials.json  # Reset
sudo python3 test_wifi_setup.py
```

### Step 2: Create Registration Module
```bash
# On dev machine
cd /root/streamscene/client
# Create client/registration.py with QR generation & polling
```

### Step 3: Create State Machine
```bash
# Create client/state_machine.py with state transitions
```

### Step 4: Update Main Loop
```bash
# Modify client/main.py to use state machine
```

### Step 5: Deploy & Test
```bash
# Deploy to Pi
sshpass -p 'JjKUa9XJ8*FFUZHYB.AP' scp client/*.py badgy@192.168.1.40:~/streamscene-client/

# Test on Pi
ssh badgy@192.168.1.40
cd ~/streamscene-client
sudo python3 main.py
```

---

## 🔍 Technical Considerations

### Registration Flow
1. Device boots without WiFi → WiFi setup runs
2. WiFi connected → Check if API key saved locally
3. No API key → Enter registration state
4. Generate QR code (already have `qr_utils.py` on server)
5. Display QR code on E Ink (or print to console for testing)
6. Poll server every 5 seconds to check registration
7. Server endpoint returns API key when user completes registration
8. Save API key locally, transition to operational state

### Server-Side Registration Endpoint (May Need to Add)
```
POST /api/devices/check-registration
Body: { "device_uuid": "..." }
Returns: { "registered": true/false, "api_key": "..." }
```

### E Ink QR Code Display (Phase 6)
- Use Pillow to generate QR code image
- Convert to 6-color E Ink format
- Display on screen with instructions
- Can test headless first (print QR to console)

---

## 🔑 Key Files to Create/Modify

### New Files:
- `client/state_machine.py` - Main state machine logic
- `client/registration.py` - Registration flow & QR code handling

### Files to Modify:
- `client/main.py` - Integrate state machine
- `client/display.py` - Add setup state rendering (Phase 6)

### Files to Reference:
- `client/setup/hotspot.py` - WiFi setup (already working)
- `streamscene/core/qr_utils.py` - Server-side QR generation
- `streamscene/api/routes/devices.py` - Device API endpoints

---

## 🚀 Quick Commands

### SSH to Device
```bash
ssh badgy@192.168.1.40
# Password: JjKUa9XJ8*FFUZHYB.AP
```

### Deploy Code to Device
```bash
sshpass -p 'JjKUa9XJ8*FFUZHYB.AP' scp client/*.py badgy@192.168.1.40:~/streamscene-client/
```

### Test WiFi Setup (Already Working)
```bash
ssh badgy@192.168.1.40
cd ~/streamscene-client
sudo python3 test_wifi_setup.py
```

### View Device UUID
```bash
ssh badgy@192.168.1.40 "cat /boot/firmware/streamscene-device.txt"
# Output: DEVICE_UUID=1c91d1e9-3cc9-44ba-a008-9cdee188d90c
```

---

## 📖 Reference Documentation

- `DEVICE_SETUP_OTA_PLAN.md` - Full implementation plan (Phases 5-8 remaining)
- `client/WIFI_SETUP_DEPLOYMENT.md` - WiFi setup testing guide
- `CLAUDE.md` - Architecture, gotchas, WiFi/OTA documentation

---

## ❓ Questions to Consider

1. **Headless vs E Ink testing:**
   - Start with console output for QR code (easier to debug)?
   - Or implement E Ink display from the start?
   - **Recommendation:** Start headless, add E Ink in Phase 6

2. **Registration polling interval:**
   - Every 5 seconds? 10 seconds?
   - **Recommendation:** 5 seconds (user waiting, responsive feedback)

3. **API key storage:**
   - JSON file like wifi_credentials.json?
   - Separate file for security?
   - **Recommendation:** Separate file `/home/badgy/streamscene-client/device_api_key.txt`

4. **Server-side registration check endpoint:**
   - Does this endpoint exist yet?
   - Need to add to `streamscene/api/routes/devices.py`?
   - **Action:** Check existing endpoints, may need to implement

---

## ✅ Success Criteria

Phase 5 is complete when:
- ✅ Device boots and runs WiFi setup if no credentials
- ✅ Device connects to WiFi successfully
- ✅ Device generates registration QR code
- ✅ Device polls server for registration status
- ✅ User can scan QR code and register device via web UI
- ✅ Device receives and saves API key
- ✅ Device transitions to operational state
- ✅ State machine handles errors and retries gracefully

---

**Priority:** Start with `client/registration.py` (QR generation + polling), then `client/state_machine.py`, then integrate into `client/main.py`.

**Testing Strategy:** Use ethernet connection to maintain SSH access while testing WiFi state transitions.
