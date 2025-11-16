# StreamScene - Comprehensive Implementation Plan

**Created:** 2025-11-16
**Status:** Planning Phase Complete, Ready for Implementation
**Architecture:** Composable, Simple, Pure Python

---

## Executive Summary

This document provides a comprehensive, phase-by-phase implementation plan for completing the StreamScene E Ink family message board system. The focus is on **composable**, **simple**, and **pure Python** code that follows the defensive architecture pattern (framework-agnostic business logic in `core/`).

### Current Status: Phase 5 Progress

**✅ Phases 0-4 Complete:**
- Phase 0: Infrastructure Setup ✅
- Phase 1: Web App Core ✅
- Phase 2-3: OTA Update Infrastructure (server-side) ✅
- Phase 4: WiFi Setup System ✅

**🚧 Phase 5: In Progress (85% Complete)**
- State machine ✅
- Registration module ✅
- Network manager ✅
- Setup manager ✅
- Main device loop ✅
- API client ✅
- Missing: Web UI for device setup page, E Ink rendering for setup screens

**📋 Remaining Phases:**
- Phase 6: E Ink Display Integration
- Phase 7: WebSocket & Content Display
- Phase 8: OTA Update Client

---

## Code Assessment

### ✅ Client-Side (Complete - 95%)

| Component | Status | File | Notes |
|-----------|--------|------|-------|
| State Machine | ✅ Complete | `client/states.py` | Full state management with persistence |
| Registration | ✅ Complete | `client/setup/registration.py` | Polling and status checking |
| Main Loop | ✅ Complete | `client/main.py` | State-driven execution |
| Configuration | ✅ Complete | `client/config.py` | Environment and file-based config |
| Setup Manager | ✅ Complete | `client/setup/setup_manager.py` | WiFi and registration coordination |
| Network Manager | ✅ Complete | `client/setup/network_manager.py` | AP/Client mode switching |
| WiFi Hotspot | ✅ Complete | `client/setup/hotspot.py` | Access point creation |
| WiFi Client | ✅ Complete | `client/setup/wifi_client.py` | WiFi connection |
| Captive Portal | ✅ Complete | `client/setup/portal_server.py` | HTTP server for WiFi setup |
| API Client | ✅ Complete | `client/api_client.py` | Server communication |
| Display Adapter | ✅ Complete | `client/display.py` | E Ink and headless modes |
| Content Renderer | ⚠️ Partial | `client/renderer.py` | Missing: QR code and setup screens |

### ✅ Server-Side (Complete - 90%)

| Component | Status | File | Notes |
|-----------|--------|------|-------|
| Device Models | ✅ Complete | `streamscene/core/models.py` | Full data model |
| Stream Logic | ✅ Complete | `streamscene/core/streams.py` | Device registration, content |
| OTA Logic | ✅ Complete | `streamscene/core/ota.py` | Update management |
| Device API | ✅ Complete | `streamscene/api/routes/devices.py` | All endpoints implemented |
| API Schemas | ✅ Complete | `streamscene/api/schemas.py` | Request/response models |
| Setup Page | ❌ Missing | `streamscene/pages/setup.py` | Web UI for QR code scanning |
| Device Management | ❌ Missing | `streamscene/pages/devices.py` | Web UI for device admin |

---

## Phase-by-Phase Implementation Plan

### Phase 5: Complete Device Setup Flow (Remaining 15%)

**Goal:** Finish web UI and E Ink rendering for setup

**Estimated Time:** 3-4 hours

**Tasks:**

1. **Create Setup Page (Web UI)** - 1.5 hours
   - File: `streamscene/pages/setup.py`
   - Reflex page for device registration via QR code
   - Shows device info, registration button
   - Uses existing `streams.register_device()` logic
   - **Composable:** Reuses existing core logic

2. **Add Setup Rendering to ContentRenderer** - 1 hour
   - File: `client/renderer.py`
   - Add `render_qr_code()` method
   - Add `render_message()` method for simple messages
   - **Simple:** Uses PIL/qrcode, no complex dependencies

3. **Testing** - 0.5 hours
   - Test WiFi setup flow end-to-end
   - Test registration polling
   - Test QR code display
   - Test state persistence across reboots

4. **Update main.py to use new rendering methods** - 0.5 hours
   - Replace placeholders with actual QR code rendering
   - Add proper error display rendering
   - **Composable:** Main loop calls renderer methods

**Deliverables:**
- ✅ Device setup web page
- ✅ QR code rendering on E Ink
- ✅ Full setup flow tested

---

### Phase 6: E Ink Display Integration (Hardware)

**Goal:** Full E Ink hardware support on Raspberry Pi

**Estimated Time:** 2-3 hours

**Prerequisites:**
- Raspberry Pi Zero 2 WH
- Waveshare 7.3" 6-color E-Paper display

**Tasks:**

1. **Install Waveshare Library** - 0.5 hours
   ```bash
   # On Raspberry Pi
   pip install waveshare-epd
   sudo raspi-config  # Enable SPI
   ```

2. **Implement EInkDisplay Class** - 1 hour
   - File: `client/display.py`
   - Uncomment and complete E Ink implementation
   - Handle initialization, refresh, sleep
   - **Simple:** Thin wrapper around Waveshare library

3. **Test Display on Hardware** - 1 hour
   - Test with sample images
   - Test full refresh cycle
   - Test sleep/wake
   - Test color palette
   - **Composable:** Uses same PIL Image interface

**Deliverables:**
- ✅ E Ink display driver integrated
- ✅ Display tested with real content
- ✅ Refresh timing validated (~30s)

---

### Phase 7: Content Display & Rotation

**Goal:** Display stream content on E Ink, handle rotation

**Estimated Time:** 4-5 hours

**Tasks:**

1. **Enhance Content Renderer** - 2 hours
   - File: `client/renderer.py`
   - Implement `render_content()` fully
   - Handle text posts with proper formatting
   - Handle image posts (resize, dither)
   - Add theme support (colors, layouts)
   - **Composable:** Separate rendering logic from display logic

2. **Test Content Rendering** - 1 hour
   - Test various text lengths
   - Test different themes
   - Test image rendering (if implemented)
   - **Simple:** PNG output for verification

3. **Implement Content Rotation** - 1.5 hours
   - Add rotation state to state machine
   - Track current post index
   - Rotate on timer if enabled
   - **Composable:** Rotation logic separate from rendering

4. **Integration Testing** - 0.5 hours
   - Test full flow: fetch → render → display
   - Test rotation transitions
   - Test theme switching

**Deliverables:**
- ✅ Full content rendering
- ✅ Content rotation working
- ✅ Multiple themes supported

---

### Phase 8: OTA Update Client

**Goal:** Implement client-side OTA update system

**Estimated Time:** 4-5 hours

**Tasks:**

1. **Create Update Client Module** - 2 hours
   - File: `client/updater/update_client.py`
   - Check for updates
   - Download update packages
   - Verify checksums
   - Install updates
   - Rollback on failure
   - **Composable:** Separate module, called from main loop

2. **Add Update States to State Machine** - 1 hour
   - File: `client/states.py`
   - Add `CHECKING_UPDATES` state
   - Add `UPDATING` state
   - Add state transitions
   - **Simple:** Extends existing state machine

3. **Integrate with Main Loop** - 1 hour
   - File: `client/main.py`
   - Add update check after registration
   - Add periodic update checks (optional)
   - Add update handlers
   - **Composable:** Calls update_client methods

4. **Testing** - 1 hour
   - Test update download
   - Test checksum verification
   - Test installation
   - Test rollback
   - **Note:** Requires creating test update packages

**Deliverables:**
- ✅ OTA update client implemented
- ✅ Update installation tested
- ✅ Rollback mechanism tested

---

## Architecture Principles

### 1. **Composability**

Every component is a standalone module with clear interfaces:

```python
# Good: Composable
class NetworkManager:
    def switch_to_ap_mode(self) -> bool: ...
    def switch_to_client_mode(self, ssid, password) -> tuple: ...

# Main loop just calls these
if state == WIFI_SETUP:
    network_manager.switch_to_ap_mode()
```

### 2. **Simplicity**

No over-engineering. Use standard library where possible:

```python
# Good: Simple
import json
with open("state.json", "w") as f:
    json.dump(data, f)

# Bad: Over-engineered
from complex_state_manager import StateSerializer, StateManager
manager = StateManager(StateSerializer(), backend="json")
```

### 3. **Pure Python**

No JavaScript, no complex frameworks beyond what's necessary:

```python
# Good: Pure Python
from http.server import HTTPServer, BaseHTTPRequestHandler

class PortalHandler(BaseHTTPRequestHandler):
    def do_GET(self): ...
    def do_POST(self): ...

# Run it
server = HTTPServer(('0.0.0.0', 80), PortalHandler)
server.serve_forever()
```

### 4. **Defensive Architecture**

Business logic in `core/`, framework-specific code in `ui/` and `api/`:

```
streamscene/
├── core/              # Pure Python, no framework deps
│   ├── streams.py     # register_device(), get_content()
│   └── ota.py         # check_for_updates(), deploy_update()
├── api/               # FastAPI endpoints (thin layer)
│   └── routes/
│       └── devices.py # Calls core.streams, core.ota
└── ui/                # Reflex components (thin layer)
    └── pages/
        └── setup.py   # Calls core.streams
```

---

## Testing Strategy

### Unit Tests

Test each module independently:

```python
# Test state machine
def test_state_transitions():
    sm = StateMachine("test-uuid")
    assert sm.get_state() == DeviceState.WIFI_SETUP
    assert sm.transition_to(DeviceState.CONNECTING) == True
    assert sm.get_state() == DeviceState.CONNECTING
```

### Integration Tests

Test component interactions:

```python
# Test setup flow
def test_wifi_setup_flow():
    manager = SetupManager("test-uuid")
    # Mock captive portal submission
    credentials = manager.run_wifi_setup(timeout=10)
    assert credentials["ssid"] == "TestNetwork"
```

### Hardware Tests

Test on real Raspberry Pi:

```bash
# Test hotspot creation
sudo python -m client.setup.hotspot

# Test state machine persistence
python -m client.states
# Ctrl+C
python -m client.states  # Should resume from saved state
```

---

## File Structure Summary

### New Files to Create (Phase 5-8)

```
streamscene/pages/
└── setup.py                          # Device setup page (Phase 5)

client/
├── renderer.py                        # Add QR/message rendering (Phase 5)
├── display.py                         # Complete E Ink class (Phase 6)
└── updater/
    ├── __init__.py                    # (Phase 8)
    └── update_client.py               # OTA update client (Phase 8)
```

### Files to Modify

```
client/
├── states.py                          # Add CHECKING_UPDATES, UPDATING states (Phase 8)
├── main.py                            # Add update handlers (Phase 8)
└── renderer.py                        # Add render_content() enhancements (Phase 7)
```

---

## Timeline Estimate

| Phase | Description | Time | Dependencies |
|-------|-------------|------|--------------|
| **Phase 5** | Complete Setup Flow | 3-4 hours | None (can start now) |
| **Phase 6** | E Ink Hardware Integration | 2-3 hours | Requires Pi + Display |
| **Phase 7** | Content Display & Rotation | 4-5 hours | Phase 6 complete |
| **Phase 8** | OTA Update Client | 4-5 hours | None (parallel with 6-7) |

**Total:** 13-17 hours of focused development

**Realistic Schedule:**
- **Day 1 (4-5 hours):** Phase 5 complete, Phase 8 started
- **Day 2 (4-5 hours):** Phase 8 complete, Phase 6 started (if hardware available)
- **Day 3 (4-5 hours):** Phase 6 complete, Phase 7 complete
- **Day 4 (2-3 hours):** Testing, polish, documentation

---

## Next Steps

1. **Immediate:** Complete Phase 5 (Setup Page + QR Rendering)
2. **After Phase 5:** Choose path based on hardware availability:
   - **If hardware available:** Phase 6 → Phase 7
   - **If no hardware yet:** Phase 8 → Wait for hardware → Phase 6 → Phase 7

3. **Testing:** End-to-end testing after each phase
4. **Documentation:** Update CLAUDE.md after completing phases
5. **Production:** Deploy and test on real devices

---

## Success Criteria

### Phase 5 Complete When:
- ✅ User can scan QR code and register device via web UI
- ✅ Device polls and detects registration
- ✅ QR code renders on display (headless or E Ink)

### Phase 6 Complete When:
- ✅ E Ink display shows content
- ✅ Refresh cycle works (~30s)
- ✅ Colors render correctly

### Phase 7 Complete When:
- ✅ Stream content displays on E Ink
- ✅ Content rotation works
- ✅ Multiple themes supported

### Phase 8 Complete When:
- ✅ Device checks for updates
- ✅ Updates download and install
- ✅ Rollback works on failure

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| E Ink hardware delay | Continue with headless mode, test with PNG output |
| WiFi setup issues on Pi | Test with network simulation, use test harness |
| OTA update corruption | Implement checksums, test rollback extensively |
| State machine bugs | Unit test all transitions, integration test flows |

---

**Last Updated:** 2025-11-16
**Next Review:** After Phase 5 completion
