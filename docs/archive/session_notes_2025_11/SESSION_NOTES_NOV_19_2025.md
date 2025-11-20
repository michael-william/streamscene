# StreamScene Client Deployment Session - November 19, 2025

## Session Goal
Fix the Raspberry Pi Zero 2W deployment so the device boots properly and either:
- Creates a WiFi hotspot (when no WiFi credentials exist), OR
- Allows SSH access (with ethernet connected)

## Current Status: NOT WORKING ❌
After multiple rebuild attempts, the Pi still does not:
- Create a WiFi hotspot
- Accept SSH connections (even with ethernet)
- Appear on the network

**LED Behavior:** Unpredictable flashing pattern (not consistent with normal boot)

---

## What We Fixed Today

### 1. Simplified Architecture (Eliminated "First Boot" Concept)
**Problem:** Had a complex two-stage boot process with `first_boot.sh` script that duplicated work already done in image build.

**Solution:** Removed first boot service entirely and moved all one-time setup to image build phase.

**Changes:**
- Removed `streamscene-firstboot.service` from `build_sd_image.sh`
- Service now starts immediately on boot (no waiting for provisioning)
- All system setup (NetworkManager disable, Python caps, log dirs) happens during image build

**Files Modified:**
- `build_sd_image.sh` (lines 319-328)

---

### 2. Fixed UUID Generation and Storage
**Problem:** UUID file (`/boot/firmware/streamscene-device.txt`) didn't exist, causing service to crash on startup.

**Solution A - Image Build:** Generate unique UUID during image build and write to boot partition
```bash
# In build_sd_image.sh line 170-175
DEVICE_UUID=$(python3 -c 'import uuid; print(str(uuid.uuid4()))')
echo "$DEVICE_UUID" | sudo tee "$MOUNT_DIR/boot/firmware/streamscene-device.txt" > /dev/null
```

**Solution B - Runtime Fallback:** Added writable fallback location for UUID persistence
```python
# In client/config.py
DEVICE_UUID_FILE = Path("/boot/firmware/streamscene-device.txt")  # Primary
DEVICE_UUID_FALLBACK = Path.home() / "streamscene-client" / ".device-uuid"  # Fallback
```

**Why Both?**
- Image build creates initial UUID (each SD card gets unique UUID)
- If boot partition becomes read-only, runtime can save to fallback location
- UUID persists across reboots even without write access to boot partition

**Files Modified:**
- `client/config.py` (lines 17-19, 70-106)
- `build_sd_image.sh` (lines 170-175)

---

### 3. Fixed rfkill Permissions
**Problem:** Service file tried to run `rfkill unblock wifi` as user "pi" but lacked permissions.

**Solution:**
- Added `sudo` to rfkill commands in service file
- Added rfkill to sudoers configuration for passwordless execution

**Changes:**
```systemd
# In client/streamscene-client.service line 23-24
ExecStartPre=/usr/bin/sudo /usr/bin/rfkill unblock wifi
ExecStartPre=/usr/bin/sudo /usr/bin/rfkill unblock all
```

```
# In config/sudoers.streamscene line 38-39
pi ALL=(ALL) NOPASSWD: /usr/bin/rfkill unblock *
pi ALL=(ALL) NOPASSWD: /usr/sbin/rfkill unblock *
```

**Files Modified:**
- `client/streamscene-client.service` (lines 23-24)
- `config/sudoers.streamscene` (lines 37-39)

---

### 4. Verified SSH Enable File
**Problem:** SSH wasn't enabled in original image builds.

**Solution:** Confirmed `build_sd_image.sh` creates `/boot/firmware/ssh` file (line 168).

**Verification:** Image verification script confirmed SSH file exists in built image.

---

## Image Verification Results ✅

Ran comprehensive verification script on built image (`streamscene-client-1.0.0.img`):

```
✅ All critical files present (main.py, config.py, service file)
✅ SSH file exists at /boot/firmware/ssh
✅ Device UUID exists: 2aeba59c-bfb4-45bc-b2be-461d04a3a952
✅ Service enabled (symlink in multi-user.target.wants/)
✅ rfkill commands use sudo in service file
✅ Sudoers file configured correctly (mode 440)
✅ Python venv exists with all packages (Pillow, qrcode, requests)
✅ NetworkManager masked (won't interfere)
✅ UUID fallback logic present in config.py
```

**Result:** Image passed all checks - should be ready to boot.

---

## What We Tried (Chronologically)

1. **Initial Build:** Used original `build_sd_image.sh` with first boot service
   - **Result:** Pi booted once (first boot log shows completion), but service never started

2. **Investigated Mounted SD Card:** Found first boot DID run but service was inactive
   - **Discovery:** Service needs UUID file to start, but it didn't exist

3. **Researched Industry Best Practices:** Compared our approach to Balena WiFi Connect, RaspAP, Comitup
   - **Finding:** Our custom approach is actually better/simpler than existing tools
   - **Decision:** Keep custom implementation, simplify architecture

4. **Removed First Boot Service:** Eliminated two-stage boot process
   - **Result:** Simplified but UUID generation still needed

5. **Fixed UUID + rfkill + SSH:** Made 3 critical fixes
   - **Result:** Image passes all verification checks

6. **Flashed with Raspberry Pi Imager (with customization):** Enabled SSH via Imager settings
   - **Result:** Didn't work - Imager's firstrun.sh conflicts with our setup

7. **Reflashed without customization:** Used Imager but no gear icon settings
   - **Result:** Still not working

8. **Verified Image Contents:** Mounted `.img` file and verified all components present
   - **Result:** Everything looks correct in image

9. **Rebuilt and Reflashed:** Clean build with all fixes
   - **Result:** Still not booting properly (current state)

---

## Technical Details

### Architecture Overview
```
Image Build (Proxmox Host):
  1. Download Raspberry Pi OS Lite base image
  2. Mount partitions (boot + root)
  3. Install dependencies via chroot (hostapd, dnsmasq, Python, etc.)
  4. Copy StreamScene client code
  5. Create Python venv and install packages
  6. Generate UUID and write to boot partition
  7. Enable SSH (create /boot/firmware/ssh)
  8. Configure sudoers
  9. Enable streamscene-client.service
  10. Unmount and finalize

First Boot (Raspberry Pi):
  1. Systemd runs ExecStartPre: sudo rfkill unblock wifi
  2. Systemd starts: /home/pi/streamscene-client/venv/bin/python3 main.py
  3. main.py imports config.py
  4. config.py loads UUID from /boot/firmware/streamscene-device.txt
  5. main.py enters state machine (WIFI_SETUP → CONNECTING → READY)
  6. If no WiFi creds: Start hotspot + captive portal
  7. If WiFi creds exist: Connect to WiFi
```

### State Machine Flow
```
WIFI_SETUP:
  - Check for saved credentials (~/streamscene-client/wifi_credentials.json)
  - If none: Start hotspot (StreamScene-XXXX) + captive portal (http://192.168.4.1)
  - If exist: Transition to CONNECTING

CONNECTING:
  - Stop hotspot
  - Start wpa_supplicant with credentials
  - If success: → AWAITING_REGISTRATION
  - If fail: → WIFI_SETUP (retry)

AWAITING_REGISTRATION:
  - Display QR code for registration
  - Poll server every 10s for registration status
  - If registered: → REGISTERED

REGISTERED → READY:
  - Normal operation (display content)
```

### Files and Locations

**On SD Card Boot Partition (`/boot/firmware/`):**
- `ssh` - Empty file to enable SSH on first boot
- `streamscene-device.txt` - Device UUID (generated during image build)
- `config.txt` - Raspberry Pi boot configuration
- `cmdline.txt` - Kernel command line parameters

**On SD Card Root Partition:**
- `/home/pi/streamscene-client/` - All client code
  - `main.py` - Main entry point (state machine)
  - `config.py` - Configuration loading (UUID, API URL)
  - `setup/` - WiFi setup modules (hotspot, client, captive portal)
  - `venv/` - Python virtual environment
- `/etc/systemd/system/streamscene-client.service` - Service file
- `/etc/systemd/system/multi-user.target.wants/streamscene-client.service` - Symlink (enables service)
- `/etc/sudoers.d/streamscene` - Sudoers configuration (mode 440)
- `/var/log/streamscene/` - Log directory (owned by pi:pi)

**Default Credentials:**
- Username: `pi`
- Password: `streamscene`

---

## Possible Issues (To Investigate Tomorrow)

### 1. Boot Partition Not Mounting
**Symptom:** Service can't read UUID from `/boot/firmware/streamscene-device.txt`

**Why:** Raspberry Pi OS Bookworm changed boot partition mount point from `/boot/` to `/boot/firmware/`

**Check:**
- Does `/boot/firmware/` exist when Pi boots?
- Is boot partition actually mounted at that location?
- Check `/etc/fstab` entry

**Test:** Boot Pi with ethernet, SSH in, run:
```bash
ls -la /boot/firmware/
cat /boot/firmware/streamscene-device.txt
```

**If mount point is wrong:** Update `client/config.py` line 18 to correct location

---

### 2. Python Dependencies Missing or Wrong Architecture
**Symptom:** Service crashes on import (Pillow C extensions fail)

**Why:** Pillow has native C extensions that must be compiled for ARM architecture

**Check:** During image build, packages should install via chroot with qemu-arm-static

**Evidence From Earlier Testing:** We confirmed Pillow binaries ARE ARM architecture:
```bash
file _imaging.cpython-311-arm-linux-gnueabihf.so
# Output: ELF 32-bit LSB shared object, ARM, EABI5
```

**But:** Running from x86_64 host gives `ImportError: cannot import name '_imaging'`

**Test:** Boot Pi, SSH in, manually run:
```bash
cd ~/streamscene-client
source venv/bin/activate
python3 -c "from PIL import Image; print('OK')"
```

**If this works:** Problem is elsewhere (not Pillow)
**If this fails:** Need to rebuild venv on actual Pi hardware

---

### 3. Service Crashes Before Creating Logs
**Symptom:** No logs in `/var/log/streamscene/`, no journalctl output

**Why:** Service might be crashing immediately on startup before logging initializes

**Check:** Look at systemd journal for any Python tracebacks:
```bash
sudo journalctl -u streamscene-client.service -n 100 --no-pager
sudo journalctl -xe  # All recent errors
```

**Possible Causes:**
- Python syntax error (but we tested this - unlikely)
- Missing import (PIL, qrcode, requests)
- Permission error (can't write to log directory)
- Immediate crash in config.py UUID loading

---

### 4. Systemd Service Dependency Issue
**Symptom:** Service starts before network/filesystem is ready

**Why:** Service file has:
```
After=local-fs.target network-online.target
Wants=network-online.target
```

But maybe boot partition isn't mounted yet when service starts?

**Check Service File:** Look at `client/streamscene-client.service` line 4-5

**Test:** Add more explicit dependency:
```systemd
After=local-fs.target network-online.target boot.mount
Requires=boot.mount
```

---

### 5. Raspberry Pi Imager Interference
**Symptom:** Imager adds files that conflict with our setup

**Why:** Even without customization, Imager might add `firstrun.sh`

**Check:** Mount SD card after flashing, look for:
```bash
ls -la /mnt/sdboot/firstrun.sh
ls -la /mnt/sdboot/rename_to_enable  # Imager's trick for features
```

**Solution:** Use `dd` instead of Raspberry Pi Imager:
```bash
# On Proxmox host (or Mac)
sudo dd if=streamscene-client-1.0.0.img of=/dev/sdX bs=4M status=progress
sync
```

Replace `/dev/sdX` with actual SD card device (find with `lsblk`)

---

### 6. Power Supply Issue
**Symptom:** Pi boots partially but crashes/reboots

**Why:** Pi Zero 2W needs stable 5V at 1-2A. Insufficient power causes:
- Random crashes
- WiFi failures
- SD card corruption
- Unpredictable LED patterns

**Check:**
- Use official Raspberry Pi power supply (5V 2.5A recommended)
- Avoid powered USB hubs or cheap chargers
- Look for lightning bolt icon on display (indicates low voltage)

**Test:** Try different power supply

---

### 7. SD Card Corruption
**Symptom:** Image verified fine but Pi won't boot

**Why:** SD card might have bad sectors or got corrupted during flashing

**Check:**
- Try different SD card (known-good card)
- Use SD card from major brand (SanDisk, Samsung)
- Minimum: Class 10, UHS-I (U1)

**Test:** Flash image to different SD card

---

### 8. Raspberry Pi Hardware Issue
**Symptom:** Nothing we try works

**Why:** The Pi Zero 2W itself might be faulty

**Check:**
- Does Pi boot with official Raspberry Pi OS Lite (unmodified)?
- Try fresh download from raspberrypi.com
- Flash and test

**If stock image doesn't boot:** Hardware issue (bad Pi, bad SD slot, bad power)

---

## Next Steps (Tomorrow's Plan)

### Option A: Debug via Serial Console
**Goal:** See actual boot messages (before network/SSH available)

**What You Need:**
- USB-to-TTL serial adapter (FTDI, CP2102, or similar)
- 3 jumper wires
- Computer with serial terminal (minicom, screen, or PuTTY)

**Connections:**
```
USB Serial Adapter → Raspberry Pi Zero 2W GPIO
GND (Black)        → Pin 6  (GND)
TX  (White)        → Pin 10 (GPIO 15, RXD)
RX  (Green)        → Pin 8  (GPIO 14, TXD)
(Don't connect VCC)
```

**Terminal Settings:**
- Baud rate: 115200
- Data bits: 8
- Parity: None
- Stop bits: 1
- Flow control: None

**Commands:**
```bash
# Linux/Mac
screen /dev/ttyUSB0 115200

# Or
minicom -D /dev/ttyUSB0 -b 115200
```

**What You'll See:**
- Complete boot sequence
- Kernel messages
- Systemd service startup
- Python errors (if any)
- Actual reason for failure

---

### Option B: Manual Service Start (SSH via Ethernet)
**Goal:** If we CAN SSH in with ethernet, manually debug the service

**Steps:**
1. Connect ethernet cable
2. Power on Pi
3. Wait 2 minutes
4. Find IP address (check router or use `nmap 192.168.1.0/24`)
5. SSH: `ssh pi@<ip>` (password: `streamscene`)
6. Check service status:
```bash
sudo systemctl status streamscene-client.service
sudo journalctl -u streamscene-client.service -n 200
```

7. If service failed, try manual start:
```bash
cd ~/streamscene-client
source venv/bin/activate
python3 main.py
```

8. Watch output - see actual error

---

### Option C: Flash Stock Raspberry Pi OS First
**Goal:** Verify hardware/SD card works with known-good image

**Steps:**
1. Download fresh Raspberry Pi OS Lite from raspberrypi.com
2. Flash with Raspberry Pi Imager (enable SSH in settings)
3. Boot Pi
4. Verify SSH works
5. **If this works:** Hardware is fine, problem is in our image
6. **If this fails:** Hardware/SD card issue

---

### Option D: Simplified Test Image
**Goal:** Build minimal image just to prove boot + service start

**Create Test Script:**
```python
#!/usr/bin/env python3
# /home/pi/test-service.py
import time
import logging

logging.basicConfig(
    filename='/tmp/test-service.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

logging.info("Test service started!")
print("Test service started!")

while True:
    logging.info("Still running...")
    print("Still running...")
    time.sleep(10)
```

**Create Test Service:**
```systemd
[Unit]
Description=Test Service
After=local-fs.target

[Service]
Type=simple
User=pi
ExecStart=/usr/bin/python3 /home/pi/test-service.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Build Test Image:**
- Use `build_sd_image.sh` but replace StreamScene client with test script
- Enable test service
- Flash and boot
- Check if log file appears: `/tmp/test-service.log`

**If this works:** Proves boot sequence is fine, issue is in StreamScene code
**If this fails:** Problem is more fundamental (systemd, filesystem, etc.)

---

## Key Learnings Today

### 1. Industry Research Validated Our Approach
Compared to Balena WiFi Connect, RaspAP, Comitup, and RaspiWiFi:
- **Our solution is simpler** (no NetworkManager dependency)
- **Right level of complexity** (not over-engineered)
- **Well-architected** (state machine, proper logging)
- **Custom is better than generic** (optimized for StreamScene)

### 2. "First Boot" Was Unnecessary Complexity
We successfully eliminated the first boot provisioning concept:
- All one-time setup moved to image build
- Service starts immediately (no two-stage boot)
- UUID generation happens at build time (each image is unique)
- Simpler architecture is more reliable

### 3. Image Verification Is Essential
We built comprehensive verification script that checks:
- All files present
- Correct permissions
- Service enabled
- Dependencies installed
- Configuration correct

This proves image is built correctly - problem must be at runtime.

### 4. Raspberry Pi Imager Can Interfere
Even without customization, Imager might add files.
Consider using `dd` for more control.

### 5. Serial Console Is Critical for Debugging
Can't troubleshoot boot issues without seeing boot messages.
Serial adapter is essential tool for embedded development.

---

## Files Modified Today

### Source Code Changes
1. `client/config.py` - UUID fallback logic (lines 17-19, 70-106)
2. `client/streamscene-client.service` - rfkill sudo (lines 23-24)
3. `config/sudoers.streamscene` - rfkill permissions (lines 37-39)
4. `build_sd_image.sh` - UUID generation (lines 170-175), removed first boot service (lines 319-328)

### Verification
- Created image verification script (inline, not saved to file)
- Verified image `streamscene-client-1.0.0.img` passes all checks

---

## Environment Details

**Build Host:** Proxmox LXC Container (192.168.1.30)
- OS: Debian 12
- Resources: 4 cores, 4GB RAM

**Development Host:** LXC Container (192.168.1.118)
- StreamScene server running here
- Source code in `/root/streamscene/`

**Target Device:** Raspberry Pi Zero 2 WH
- WiFi: Built-in (cypress WiFi chip)
- Expected to create hotspot or accept SSH

**Base Image:** Raspberry Pi OS Lite (Bookworm)
- Downloaded from: https://downloads.raspberrypi.org/raspios_lite_armhf/images/
- Date: 2024-11-19
- Size: ~500MB compressed

**Final Image:** `streamscene-client-1.0.0.img`
- Size: 2.4GB
- Contains: StreamScene client + all dependencies
- UUID: 2aeba59c-bfb4-45bc-b2be-461d04a3a952

---

## Tomorrow's Priority

**#1: Get ANY visibility into what's happening during boot**

Three options (in order of preference):
1. **Serial console** - See complete boot sequence and actual errors
2. **SSH with ethernet** - If we can get in, manually debug service
3. **Test with stock OS** - Verify hardware works with known-good image

Once we can see boot messages or get SSH access, we'll know exactly what's failing.

---

## Questions to Answer Tomorrow

1. Does `/boot/firmware/` mount point exist and get mounted?
2. Can Python import PIL successfully on the Pi (not on x86_64 host)?
3. Does the service start at all? (Check systemd journal)
4. Are there any Python exceptions in logs?
5. Does the Pi work with stock Raspberry Pi OS?
6. Is the power supply sufficient?
7. Is the SD card good?

---

## Useful Commands for Tomorrow

```bash
# Find Pi on network
nmap -sn 192.168.1.0/24 | grep -B 2 "Raspberry"

# SSH into Pi (if it appears)
ssh pi@<ip>  # password: streamscene

# Check service status
sudo systemctl status streamscene-client.service
sudo journalctl -u streamscene-client.service -n 200 --no-pager

# Check if boot partition mounted
mount | grep boot
ls -la /boot/firmware/

# Check UUID file
cat /boot/firmware/streamscene-device.txt

# Test Python imports
cd ~/streamscene-client
source venv/bin/activate
python3 -c "from PIL import Image; import qrcode; import requests; print('All imports OK')"

# Check WiFi
sudo rfkill list
iwconfig

# Run service manually (see errors)
cd ~/streamscene-client
source venv/bin/activate
python3 main.py

# Check logs
ls -la /var/log/streamscene/
cat /var/log/streamscene/client.log

# Scan for available WiFi networks
sudo iwlist wlan0 scan | grep ESSID
```

---

## Contact Points (If We Get Stuck)

**Raspberry Pi Forums:**
- https://forums.raspberrypi.com/
- Active community, helpful for boot issues

**Similar Projects:**
- Balena Forums: https://forums.balena.io/
- RaspAP Issues: https://github.com/RaspAP/raspap-webgui/issues

**Serial Console Guides:**
- https://learn.adafruit.com/adafruits-raspberry-pi-lesson-5-using-a-console-cable
- https://www.raspberrypi.com/documentation/computers/configuration.html#configuring-uarts

---

## Morale Check

We made significant architectural improvements today:
- ✅ Simplified deployment (removed first boot complexity)
- ✅ Fixed 3 critical bugs (UUID, rfkill, SSH)
- ✅ Image verification passes all checks
- ✅ Research confirmed our approach is sound

The image is correctly built. The issue is at runtime on the Pi itself.

Tomorrow we'll get visibility into boot and find the issue.

**We're close!** 🚀

---

*End of session notes for November 19, 2025*
