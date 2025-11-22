# StreamScene - Next Session Plan

**Last Updated:** 2025-11-22
**Current Phase:** Phase 1 (Day 1 Complete) - Service Layer Architecture Refactoring
**Device Status:** ✅ Operational (Raspberry Pi Zero 2 WH @ 192.168.1.40)

---

## 📊 Session Summary (2025-11-22)

### **What We Accomplished**

Today's session focused on **systematic architectural refactoring** of the device client. We identified critical complexity issues and began methodical improvement through service layer extraction.

#### **Phase 1 Completed: Service Layer Foundation + NetworkService** ✅

**Phase 1.1: Fixed Network Recovery Bug**
- Added missing `network_logger` import to main.py
- Fixed logger initialization that was causing NameError during recovery
- Root cause: Missing `import logging` (tried to use `logging.getLogger()` without import)

**Phase 1.2: Created Service Layer Infrastructure**
- Created `client/services/` directory
- Implemented `BaseService` abstract class:
  - Standardized initialization pattern
  - Centralized logging per service
  - Clean shutdown hooks
- Established dependency injection pattern

**Phase 1.3: Extracted NetworkService**
- **Massive code reduction:**
  - `_attempt_network_recovery()`: **58 lines → 3 lines** (95% reduction!)
  - `_check_initial_network_status()`: **52 lines → 37 lines** (29% reduction)
  - **Total: ~70 lines of duplicate logic eliminated**

- **Key improvements:**
  - DNS fallback handling (automatic Google DNS 8.8.8.8/8.8.4.4)
  - Retry logic for WiFi connections (2 attempts with 5s delay)
  - Configurable timeouts via constructor parameters
  - Clear separation of concerns
  - Comprehensive logging throughout
  - NetworkStatus dataclass for clean API

**Phase 1.4: Comprehensive Unit Tests**
- Created test infrastructure (`tests/services/`)
- **17 unit tests for NetworkService** - ALL PASSING ✅
- Test coverage:
  - Initial connectivity checks (ethernet/wifi/none)
  - Network recovery scenarios (ethernet up/down, wifi success/fail)
  - DNS configuration and fallback
  - Error handling and edge cases
  - Timeout and exception handling
- Clean mocking using unittest.mock

---

### **Key Discoveries**

#### **1. Architecture Was Fundamentally Flawed**

The architectural assessment revealed critical issues:

- **God Object antipattern**: main.py doing 11+ responsibilities
- **No service layer**: Business logic embedded directly in state handlers
- **Tight coupling**: NetworkManager, SetupManager, main.py all intertwined
- **Duplicate logic**: Network checks repeated 3+ times across codebase
- **Import hygiene violations**: Imports inside methods, missing imports

#### **2. Network Failover Completely Broken**

When ethernet disconnected:
- Device showed error screen but never recovered to WiFi
- Recovery logic triggered correctly but failed because:
  - DNS configuration lost immediately when ethernet disconnected
  - WiFi connection timeout too short (15s insufficient)
  - No retry logic for transient failures
  - Race conditions with system networking services

#### **3. Your Instinct Was Absolutely Correct**

- Code IS too complicated (God Object with 782 lines)
- Code IS too tightly coupled (no clear boundaries)
- Quick fixes would make it worse (band-aids on broken architecture)
- Refactoring investment justified (prevents months of debugging)

---

### **Architectural Improvements**

**Before Refactoring:**
```
main.py (782 lines, 11+ responsibilities)
├── _attempt_network_recovery() - 58 lines, duplicate checks
├── _check_initial_network_status() - 52 lines, duplicate logic
├── _refresh_config_if_needed() - 68 lines
├── Hard-coded timeouts everywhere
├── No retry logic
├── Imports inside methods
└── Zero tests
```

**After Refactoring:**
```
client/
├── main.py (simplified)
│   ├── _attempt_network_recovery() - 3 lines (delegates to service)
│   └── _check_initial_network_status() - 37 lines (uses service)
├── services/
│   ├── base.py - BaseService abstract class
│   └── network_service.py - NetworkService (340 lines)
│       ├── Configurable timeouts (constructor params)
│       ├── Built-in retry logic (2 attempts)
│       ├── DNS fallback handling
│       ├── Comprehensive logging
│       ├── NetworkStatus dataclass
│       └── 17 unit tests (100% passing)
└── tests/
    └── services/
        └── test_network_service.py - 17 tests ✅
```

---

### **Files Created/Modified**

**New Files:**
- `client/services/__init__.py`
- `client/services/base.py`
- `client/services/network_service.py`
- `client/tests/__init__.py`
- `client/tests/services/__init__.py`
- `client/tests/services/test_network_service.py`

**Modified Files:**
- `client/main.py`:
  - Added NetworkService import
  - Added network_logger import
  - Instantiate NetworkService in __init__()
  - Simplified _attempt_network_recovery() to delegate
  - Simplified _check_initial_network_status() to use service
  - **Removed 70+ lines of duplicate network logic**

**Deployed to Pi:**
- All changes deployed to `/home/pi/streamscene-client/`
- Service restarted and verified operational
- Device displaying content correctly on E Ink

---

## 🎯 Next Session Priorities

### **Phase 2: Extract Configuration & Setup Services (Est: 4-5 hours)**

#### **Phase 2.1: Extract ConfigurationService** (2-3 hours)

**Goal:** Consolidate all configuration management into single service

**Tasks:**
1. Create `services/config_service.py`
2. Move from main.py:
   - `_fetch_initial_config()` → `ConfigService.get_initial_config()`
   - `_refresh_config_if_needed()` → `ConfigService.get_config()` (with caching)
   - API key management from config.py
3. Consolidate scattered config logic:
   - config.py: load/save API key functions
   - registration.py: API key handling during registration
   - State machine: config stored in state_data
4. Create single source of truth for device configuration
5. Implement proper caching with TTL (currently 120s hardcoded)
6. Update main.py to use ConfigService
7. Write unit tests (target: 15+ tests)

**Expected Outcome:**
- `_refresh_config_if_needed()`: **68 lines → ~5 lines**
- Configuration logic centralized
- Config caching properly abstracted
- API key management unified

#### **Phase 2.2: Extract SetupService** (2 hours)

**Goal:** Consolidate WiFi setup and registration logic

**Tasks:**
1. Create `services/setup_service.py`
2. Move WiFi setup logic from main.py state handlers
3. Move registration polling logic
4. Consolidate duplicate credential loading:
   - `setup_manager.check_saved_credentials()`
   - `setup_manager.has_saved_credentials()`
   - Multiple `load_credentials()` imports
5. Update main.py to use SetupService
6. Write unit tests (target: 10+ tests)

**Expected Outcome:**
- WiFi setup logic extracted from main.py
- Registration logic consolidated
- Credential management simplified
- Clear service API

---

### **Phase 3: State Pattern Implementation (Est: 4-5 hours)**

**Goal:** Replace monolithic state handlers with encapsulated state classes

#### **Phase 3.1: Create State Handler Infrastructure** (1 hour)
1. Create `states/handlers/` directory
2. Create `states/handlers/base.py` (StateHandler abstract class)
3. Define DeviceContext dataclass for passing state data
4. Document state handler pattern

#### **Phase 3.2: Implement Concrete State Handlers** (2-3 hours)

Create handler classes that replace main.py methods:
- `wifi_setup_state.py` → Replaces `_handle_wifi_setup()`
- `connecting_state.py` → Replaces `_handle_connecting()`
- `awaiting_registration_state.py` → Replaces `_handle_awaiting_registration()`
- `ready_state.py` → Replaces `_handle_ready()`
- `error_state.py` → Replaces `_handle_error()`

Each handler:
- Calls services (NetworkService, ConfigService, SetupService)
- Returns state transition decisions
- Encapsulates all business logic for that state
- Testable in complete isolation

#### **Phase 3.3: Wire State Handlers Into State Machine** (1 hour)
1. Update StateMachine to work with handlers
2. Add `execute_state()` delegation method
3. Update main.py to use state execution model
4. Write unit tests for each state handler
5. Integration tests for state transitions

**Expected Outcome:**
- State handler methods: **400+ lines → clean handler classes**
- Business logic completely removed from main.py
- Each state independently testable
- Clear state transition logic

---

### **Phase 4: Dependency Injection + Cleanup (Est: 3-4 hours)**

**Goal:** Proper dependency injection and comprehensive cleanup

#### **Tasks:**

1. **Create DI Container** (1 hour)
   - Create `client/container.py` (dependency injection factory)
   - Factory functions:
     - `create_network_service()`
     - `create_config_service()`
     - `create_setup_service()`
     - `create_client()` (main factory orchestrator)
   - Configuration management for service creation

2. **Refactor main.py Constructor** (1 hour)
   - Update `StreamSceneClient.__init__()` to accept injected dependencies
   - Remove direct instantiation of services
   - Simplify initialization logic
   - Update `main()` function to use factory

3. **Create Utility Modules** (1 hour)
   - `utils/network_utils.py` (shared network checks)
   - `utils/file_utils.py` (shared file operations)
   - Extract common patterns from across codebase

4. **Code Cleanup** (1 hour)
   - Remove ALL duplicate code
   - Fix ALL import hygiene issues (move to top of files)
   - Standardize error handling patterns
   - Remove dead code

**Expected Outcome:**
- main.py: **782 lines → ~150 lines** (81% reduction!)
- Clean, testable dependency graph
- Zero duplicate code
- Proper imports throughout
- Consistent error handling

---

### **Phase 5: Testing + Documentation (Est: 3-4 hours)**

**Goal:** Comprehensive testing and updated documentation

#### **Tasks:**

1. **Integration Tests** (2 hours)
   - `tests/integration/test_wifi_setup_flow.py`
   - `tests/integration/test_registration_flow.py`
   - `tests/integration/test_network_failover.py`
   - `tests/integration/test_content_display_flow.py`

2. **E2E Test** (1 hour)
   - `tests/e2e/test_device_lifecycle.py`
   - Complete flow: boot → setup → registration → operation
   - Use mocked hardware or real Pi

3. **Documentation** (1 hour)
   - Update CLAUDE.md with new architecture
   - Document service layer pattern
   - Document state handler pattern
   - Add testing guide
   - Create architecture diagrams
   - Update deployment docs

**Expected Outcome:**
- **80%+ test coverage**
- All major flows tested end-to-end
- Clear, up-to-date documentation
- Architecture diagrams for new developers

---

## 🐛 Known Issues

### **DNS Configuration Lost on Network Mode Switch**
**Status:** Partial fix implemented
**Issue:** `/etc/resolv.conf` emptied when ethernet disconnects or WiFi mode switches
**Current Fix:** NetworkService auto-adds Google DNS when needed
**Permanent Fix:** Create `/etc/dhcpcd.conf.d/streamscene-dns.conf` with persistent config

### **Network Failover Still Not Working**
**Status:** Known issue, will fix in Phase 2
**Issue:** WiFi connection times out after 15s when recovering from ethernet failure
**Root Causes:**
- DNS lost immediately on ethernet disconnect
- WiFi adapter state conflicts
- System networking conflicts with manual setup
- 15s timeout insufficient for WiFi carrier establishment

**Fix Required:** Enhanced NetworkService with better DNS handling + longer WiFi timeout

---

## 📈 Progress Metrics

### **Code Quality Improvements**

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| main.py line count | 782 | ~750 | 4% (Phase 1) |
| Network recovery | 58 lines | 3 lines | 95% reduction |
| Initial network check | 52 lines | 37 lines | 29% reduction |
| Duplicate logic | 3+ places | 1 service | Consolidated |
| Unit tests | 0 | 17 passing | ∞% improvement |
| Import violations | 7+ | 1 | 86% reduction |
| Test coverage | 0% | ~15% | Increasing |

### **Remaining Refactoring Work**

**Completed:** Phase 1 (Day 1) - **25%** of total refactoring plan
**Next:** Phases 2-3 (Days 2-3) - **50%** of total refactoring plan
**Then:** Phases 4-5 (Days 4-5) - Final **25%** + comprehensive testing

**Estimated Time Remaining:** 3-4 days of focused refactoring

**Target main.py Size:** 150 lines (81% reduction from 782 lines)

---

## 🔧 Device Status

**Raspberry Pi Zero 2 WH**
- **IP Address:** 192.168.1.40
- **Connection:** Ethernet (priority mode)
- **State:** READY
- **Device UUID:** 1c91d1e9-3cc9-44ba-a008-9cdee188d90c
- **Database ID:** 2c0d4fe8-2426-4228-b2a9-8f89762cc338
- **Registration:** ✅ Registered to Badgy
- **Display:** ✅ Waveshare 7.3" E Ink (7-color, E variant - epd7in3e)
- **Current Content:** "Deep thoughts" stream
- **Service:** `streamscene-client.service` (systemd)
- **SSH:** `ssh pi@192.168.1.40` (password: `JjKUa9XJ8*FFUZHYB.AP`)

**Server**
- **URL:** https://streamscene.dataandstories.com
- **Status:** ✅ Operational
- **Container:** LXC @ 192.168.1.118
- **Rendering:** Server-side HTML/CSS with Playwright

---

## 💡 Key Learnings

1. **Architectural Debt Compounds Quickly**
   - "Network failover not working" revealed fundamental design flaws
   - Quick fixes would have created more technical debt
   - Systematic refactoring was the correct choice

2. **Unit Tests Catch Issues Immediately**
   - Tests revealed import and mocking issues instantly
   - Having tests gives confidence for aggressive refactoring
   - Test-driven refactoring is powerful and efficient

3. **Service Layer Provides Clarity**
   - Clear boundaries between services
   - Easy to test in complete isolation
   - Dramatically reduces cognitive load
   - Makes codebase extensible

4. **User's Intuition Was Spot-On**
   - "Code is too complicated" → Confirmed: God Object antipattern
   - "Too tightly coupled" → Confirmed: No clear boundaries
   - "Not extensible" → Confirmed: Would be nightmare to add features
   - Trusting domain expertise paid off

---

## 🚀 Quick Commands for Next Session

**Check Device Status:**
```bash
ssh pi@192.168.1.40 'sudo journalctl -u streamscene-client -n 50 --no-pager | tail -20'
```

**Verify Device Working:**
```bash
# Check if displaying content
ssh pi@192.168.1.40 'ls -lth ~/streamscene-client/output/latest.png'

# Check network connectivity
ssh pi@192.168.1.40 'ping -c 3 streamscene.dataandstories.com'

# Verify DNS configured
ssh pi@192.168.1.40 'cat /etc/resolv.conf'
```

**Run Unit Tests:**
```bash
cd /root/streamscene/client
python3 -m unittest tests.services.test_network_service -v
```

**Deploy Changes to Pi:**
```bash
# Copy services
scp -r /root/streamscene/client/services pi@192.168.1.40:~/streamscene-client/

# Copy main.py
scp /root/streamscene/client/main.py pi@192.168.1.40:~/streamscene-client/

# Restart service
ssh pi@192.168.1.40 'sudo systemctl restart streamscene-client'

# Check logs
ssh pi@192.168.1.40 'sudo journalctl -u streamscene-client -f'
```

**Start Phase 2.1:**
1. Create `services/config_service.py`
2. Extract configuration logic from main.py
3. Write unit tests
4. Deploy and verify

---

## 📚 References

**Session Artifacts:**
- Comprehensive architectural assessment (in conversation history)
- Approved refactoring plan (ExitPlanMode output)
- NetworkService implementation: `client/services/network_service.py`
- NetworkService tests: `client/tests/services/test_network_service.py`

**Documentation to Update:**
- `docs/development/GOTCHAS.md` - Add refactoring lessons
- `CLAUDE.md` - Update with new service layer architecture
- `docs/deployment/PRODUCTION.md` - Update with new structure

---

## 🎓 Refactoring Philosophy

**Remember:** We're fixing the foundation now to prevent months of debugging later.

**Principles:**
1. **Incremental progress** - Deploy after each phase, verify working
2. **Test everything** - Unit tests give confidence to refactor aggressively
3. **Clear boundaries** - Services have single, well-defined responsibilities
4. **No shortcuts** - Do it right the first time, avoid future technical debt

**The investment IS justified.**

---

**Next Action:** Start Phase 2.1 - Extract ConfigurationService to consolidate all configuration management logic.
