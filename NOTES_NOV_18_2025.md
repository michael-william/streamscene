# StreamScene Development Notes - November 18, 2025

**Session Duration:** ~3 hours
**Primary Goal:** Get WiFi hotspot working on Raspberry Pi
**Current Status:** 🟡 Service running, hotspot blocked by code bug

---

## Session Overview

Attempted to deploy StreamScene client to Raspberry Pi Zero 2 WH and get WiFi hotspot functioning. Discovered that SD card image was built from outdated code, leading to manual deployment on stock Raspberry Pi OS to troubleshoot issues systematically.

---

## Deployment Approach Evolution

### Initial Attempt: Custom SD Card Image
1. **Built image on Proxmox host** (privileged operations needed, can't build in LXC)
2. **Transferred to Mac** via SCP: `scp root@192.168.1.30:/root/streamscene/streamscene-client-*.img ~/Downloads/`
3. **Flashed to 64GB SanDisk Ultra** SD card
4. **Result:** Pi booted but no WiFi hotspot, couldn't SSH via Ethernet

### Root Cause
**CRITICAL DISCOVERY:** Proxmox host had OLD code without SESSION_NOTES.md fixes from Nov 17. The rsync initially showed 0 bytes because directory path was wrong.

### Pivot: Stock Raspberry Pi OS + Manual Deployment
1. Flashed **stock Raspberry Pi OS Lite (64-bit)** to SD card
2. Pi accessible via Ethernet at **192.168.1.41**
3. Manually copied client code and ran setup scripts to identify issues one-by-one

**Copy commands used:**
```bash
# From Mac (bridging LXC → Mac → Pi):
scp -r root@192.168.1.118:/root/streamscene/client pi@192.168.1.41:~/streamscene-client
scp root@192.168.1.118:/root/streamscene/config/sudoers.streamscene pi@192.168.1.41:~/
```

---

## Issues Discovered & Fixed (8 Total)

### ✅ Issue #1: Missing libcap2-bin Package
**Error:** `setcap: command not found`
**Root Cause:** Stock Raspberry Pi OS Lite doesn't include libcap2-bin
**Fix:**
```bash
sudo apt-get update
sudo apt-get install -y libcap2-bin
```
**Build Script Update Needed:** Add to package list in `build_sd_image.sh`

---

### ✅ Issue #2: Python Version Hardcoded as 3.11
**Error:** Script tries to setcap on `/usr/bin/python3.11` but stock OS has Python 3.13
**Root Cause:** `first_boot.sh` hardcoded Python 3.11 path
**Fix:**
```bash
# Dynamic detection:
PYTHON_BIN=$(readlink -f /usr/bin/python3)
sudo setcap 'cap_net_bind_service=+ep' "$PYTHON_BIN"
```
**Build Script Update Needed:** Update `first_boot.sh` to detect Python version dynamically

---

### ✅ Issue #3: setcap Command Missing Quotes
**Error:** `Invalid file 'setcap' for capability operation`
**Root Cause:** Missing quotes around capability string in `first_boot.sh`
**Fix:**
```bash
# Wrong:
sudo setcap cap_net_bind_service=+ep /usr/bin/python3

# Correct:
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3
```
**Build Script Update Needed:** Add quotes in `first_boot.sh` line ~55

---

### ✅ Issue #4: Service File Not Installed
**Error:** `systemctl enable streamscene-client.service` fails - "Unit does not exist"
**Root Cause:** Service file not copied to `/etc/systemd/system/` during first boot
**Fix:**
```bash
sudo cp ~/streamscene-client/streamscene-client.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable streamscene-client.service
```
**Build Script Update Needed:** Add to `build_sd_image.sh` chroot section

---

### ✅ Issue #5: Sudoers File Not Installed
**Error:** Sudoers file not present in `/etc/sudoers.d/`
**Root Cause:** `first_boot.sh` doesn't copy sudoers file
**Fix:**
```bash
sudo cp ~/sudoers.streamscene /etc/sudoers.d/streamscene
sudo chmod 440 /etc/sudoers.d/streamscene
```
**Build Script Update Needed:** Verify it's in `build_sd_image.sh`

---

### ✅ Issue #6: Missing waveshare-epd Library
**Error:** Service crashes with `ModuleNotFoundError: No module named 'waveshare_epd'`
**Root Cause:**
- Library NOT in `requirements.txt`
- Service configured with `STREAMSCENE_DISPLAY_MODE=eink` by default
- waveshare-epd doesn't exist on PyPI (must install from GitHub)

**Temporary Fix:** Switched to headless mode
```bash
# Edit service file:
sudo nano /etc/systemd/system/streamscene-client.service

# Change line 17:
Environment="STREAMSCENE_DISPLAY_MODE=headless"

# Restart:
sudo systemctl daemon-reload
sudo systemctl restart streamscene-client.service
```

**Permanent Fix (deferred due to GitHub repo issues):**
```bash
# Install from GitHub (when accessible):
cd ~/streamscene-client
source venv/bin/activate
pip install RPi.GPIO spidev
git clone --depth 1 https://github.com/waveshare/e-Paper
cd e-Paper/RaspberryPi_JetsonNano/python
pip install .
```

**Build Script Update Needed:**
- Add waveshare-epd installation to `build_sd_image.sh`
- Document headless vs eink mode switching
- Consider making E Ink library optional with graceful fallback

---

### ✅ Issue #7: Venv Created with Root Ownership
**Error:** Permission denied when trying to remove/modify venv files
**Root Cause:** `first_boot.sh` runs as root (via systemd), creates root-owned venv. User ran `sudo pip install` which corrupted ownership further.
**Fix:**
```bash
cd ~/streamscene-client
sudo chown -R pi:pi venv
```
**Build Script Update Needed:** Add `chown` after venv creation in `first_boot.sh`

---

### ✅ Issue #8: Missing hostapd and dnsmasq
**Error:** `/etc/hostapd/hostapd.conf: No such file or directory`
**Root Cause:** hostapd and dnsmasq packages not installed on stock OS
**Fix:**
```bash
sudo apt-get install -y hostapd dnsmasq
```
**Build Script Update Needed:** Already in SESSION_NOTES.md fixes, verify in `build_sd_image.sh`

---

### 🔴 Issue #9: Cross-Filesystem mv Bug (CURRENT BLOCKER)
**Error:** `mv: inter-device move failed: '/tmp/hostapd.conf' to '/etc/hostapd/hostapd.conf'; unable to remove target: Read-only file system`
**Root Cause:**
- `/tmp` is mounted on tmpfs (RAM)
- `/etc` is on SD card (ext4)
- `mv` command can't move files between different filesystems (tries rename, not copy)
- Code in `client/setup/hotspot.py` uses `sudo mv /tmp/hostapd.conf /etc/hostapd/hostapd.conf`

**Filesystem Layout:**
```
tmpfs           209M   44K  209M   1% /tmp
/dev/mmcblk0p2   58G  2.5G   54G   5% /
```

**Why This Wasn't Caught:**
- Stock Raspberry Pi OS mounts `/tmp` as tmpfs by default
- Custom SD card images might not have this configuration
- Testing on systems without tmpfs wouldn't show this bug

**Fix Required:** Change `hotspot.py` to use `cp` + `rm` instead of `mv`

**Location:** `client/setup/hotspot.py` (around line where hostapd config is moved)

**Code Change:**
```python
# Wrong:
subprocess.run(['sudo', 'mv', '/tmp/hostapd.conf', '/etc/hostapd/hostapd.conf'])

# Correct approach 1 (copy + remove):
subprocess.run(['sudo', 'cp', '/tmp/hostapd.conf', '/etc/hostapd/hostapd.conf'])
subprocess.run(['sudo', 'rm', '/tmp/hostapd.conf'])

# OR Correct approach 2 (write directly):
# Write config directly to /etc/hostapd/hostapd.conf instead of /tmp first
```

**Status:** 🔴 **BLOCKING** - Service runs but hotspot creation fails at this step

---

## Current System State

### What's Working ✅
- Service starts successfully
- Headless display mode functional (saves PNG files to `~/streamscene-client/output/`)
- State machine initializes correctly
- Enters WIFI_SETUP state as expected
- All preliminary WiFi setup steps succeed (stopping NetworkManager, unblocking WiFi, etc.)

### What's Not Working ❌
- Hotspot creation fails when trying to write hostapd.conf
- WiFi network "StreamScene-68B7" does not appear
- Service enters ERROR state and retries every 10 seconds

### Service Logs (Final State)
```
[INFO] [WIFI] Starting hotspot setup flow
[INFO] [HOTSPOT] Creating WiFi hotspot: StreamScene-68B7
[INFO] [HOTSPOT] Password: streamscene
[INFO] [HOTSPOT] Step 4: Creating hostapd configuration at /etc/hostapd/hostapd.conf
[ERROR] [HOTSPOT] Command failed: ['sudo', 'mv', '/tmp/hostapd.conf', '/etc/hostapd/hostapd.conf']
[ERROR] [HOTSPOT] stderr: mv: inter-device move failed...unable to remove target: Read-only file system
[ERROR] [HOTSPOT] Hotspot creation failed
[ERROR] [STATE] WiFi setup failed, transitioning to ERROR state
```

---

## Key Learnings

### 1. Deployment Process Insight
**Problem:** Building SD image on Proxmox without syncing latest code from LXC
**Solution:** Always sync code before building:
```bash
# From LXC:
ssh root@192.168.1.30 "rm -rf /root/streamscene && mkdir -p /root/streamscene"
rsync -avz --delete --progress /root/streamscene/ root@192.168.1.30:/root/streamscene/
```

### 2. Manual Deployment is Invaluable
Stock Raspberry Pi OS + manual deployment revealed issues that would be hidden in a custom image. This approach should be the FIRST step in troubleshooting, not the last resort.

### 3. tmpfs Mounting Can Break Code
Code that works on systems without tmpfs `/tmp` will break on stock Raspberry Pi OS. Always test on actual target OS, not just custom builds.

### 4. Venv Ownership Matters
Creating venv as root causes permission issues. `first_boot.sh` should chown after creation:
```bash
python3 -m venv venv
sudo chown -R pi:pi venv
```

### 5. Hardcoded Paths Are Fragile
Python version, directory paths, etc. should be detected dynamically, not hardcoded.

---

## Next Session Action Plan

### Immediate Fix (10 minutes)
1. **Fix the mv bug in hotspot.py**
   ```bash
   # On LXC:
   nano /root/streamscene/client/setup/hotspot.py

   # Find the mv command (around line 280-310)
   # Change to cp + rm or write directly to /etc/hostapd/
   ```

2. **Copy fixed file to Pi**
   ```bash
   # From Mac:
   scp root@192.168.1.118:/root/streamscene/client/setup/hotspot.py pi@192.168.1.41:~/streamscene-client/setup/
   ```

3. **Restart service and verify hotspot appears**
   ```bash
   # On Pi:
   sudo systemctl restart streamscene-client.service
   sudo journalctl -u streamscene-client -f

   # Check for WiFi network "StreamScene-68B7" on phone/laptop
   ```

### Short-Term Fixes (1 hour)
4. **Update all build scripts** with the 9 fixes discovered today
   - `build_sd_image.sh`
   - `first_boot.sh`
   - `client/setup/hotspot.py`

5. **Test complete WiFi setup flow**
   - Connect to hotspot
   - Submit credentials
   - Verify device connects to home WiFi
   - Verify QR code appears for registration

6. **Update WIFI_TROUBLESHOOTING_LOG.md** with Issue #9

### Long-Term Improvements
7. **Add waveshare-epd library** to build process (when GitHub accessible)
8. **Create graceful E Ink fallback** - detect library availability and auto-switch to headless
9. **Improve first_boot.sh robustness** - better error handling, ownership fixes
10. **Add filesystem checks** to diagnostic script

---

## Files Modified This Session

### On LXC Container
- `pi_diagnostic.sh` - Created comprehensive diagnostic script
- `WIFI_TROUBLESHOOTING_LOG.md` - Updated with Fixes #1-#6
- `streamscene/pages/devices.py` - Fixed rx.Base deprecation (separate issue)

### On Raspberry Pi (192.168.1.41)
- `/etc/systemd/system/streamscene-client.service` - Changed DISPLAY_MODE to headless
- `/home/pi/streamscene-client/venv/` - Fixed ownership with chown

### To Be Modified Next Session
- `client/setup/hotspot.py` - Fix mv → cp bug
- `build_sd_image.sh` - Add all 9 fixes
- `first_boot.sh` - Dynamic Python detection, ownership fixes
- `requirements.txt` - Document waveshare-epd (optional, Pi-only)

---

## Hardware Status

**Raspberry Pi Zero 2 WH:**
- IP: 192.168.1.41 (Ethernet)
- SD Card: 64GB SanDisk Ultra (brand new, healthy)
- Power: No throttling detected (`vcgencmd get_throttled` = 0x0)
- WiFi: Unblocked, ready for hotspot
- E Ink Display: Connected but not initialized (using headless mode)

**SD Card History:**
- Yesterday's card became unreadable by Mac (unknown cause)
- Today's card is brand new, flashed with stock Raspberry Pi OS Lite
- Filesystem healthy (ext4, read-write, no errors)

---

## Questions for Next Session

1. **Should we keep headless mode as default?**
   Pro: Works without E Ink hardware, easier development
   Con: Need to document mode switching for production

2. **How should waveshare-epd be installed?**
   - Add to requirements.txt with platform check?
   - Install in build script only?
   - Keep optional with graceful fallback?

3. **Should first_boot.sh create venv as pi user?**
   Current: Runs as root via systemd, creates root-owned venv
   Alternative: Run as pi, use sudo only for specific commands

4. **Why did yesterday's SD card become unreadable?**
   If it happens again, investigate power supply quality

---

## Session End State

**Time:** ~22:00 CET
**Status:** Service running, hotspot blocked by mv bug
**Next Action:** Fix hotspot.py mv → cp bug
**Estimated Time to Working Hotspot:** 10-15 minutes

**User Status:** Exhausted (understandably - this was a marathon debugging session!)

---

## Summary

Today we discovered that the SD card image build process was using outdated code, leading us to manually deploy on stock Raspberry Pi OS. This revealed **9 distinct issues**, of which we fixed **8**. The final blocker is a cross-filesystem `mv` bug in `hotspot.py` that prevents the WiFi hotspot from starting.

**The good news:** We're ONE small code change away from a working WiFi hotspot. The service runs, state machine works, all prerequisites are met. Just need to fix the tmpfs/mv issue.

**The frustration:** What seemed like it should "just work" required fixing 9 separate issues. But now we have a complete understanding of the deployment process and all failure points are documented.

**Next session will start with the fix and hopefully end with a working demo.**

---

**End of Notes**
