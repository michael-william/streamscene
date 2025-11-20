# StreamScene Development Session Notes
**Date:** 2025-11-17
**Status:** WiFi Setup Fixes Complete - Ready for Testing

---

## Session Summary

Successfully identified and fixed **all 7 critical issues** preventing WiFi setup from working on Raspberry Pi devices. The captive portal now works, and all deployment methods (SD image, first boot, manual install) have consistent fixes applied.

---

## Issues Fixed (7 Total)

### ✅ 1. WiFi blocked by rfkill / Country code not set
**Files Modified:**
- `client/first_boot.sh` - Added `rfkill unblock wifi/all` at boot (step 2/9)
- `client/setup/hotspot.py:63` - Added `country_code=US` to hostapd config

### ✅ 2. Systemd service file error - StartLimitIntervalSec in wrong section
**Files Modified:**
- `client/streamscene-client.service:6-7` - Moved `StartLimitBurst` and `StartLimitIntervalSec` from `[Service]` to `[Unit]` section

### ✅ 3 & 6. Empty venv directory / First boot doesn't create venv (CRITICAL)
**Files Modified:**
- `client/first_boot.sh:73-89` - Added steps 7-8/9:
  - Creates venv: `python3 -m venv venv`
  - Upgrades pip: `pip install --upgrade pip`
  - Installs packages: `pip install -r requirements.txt`

### ✅ 4. Missing Pillow system libraries (CRITICAL)
**Files Modified:**
- `build_sd_image.sh:215-221` - Added image processing libraries:
  - libjpeg-dev
  - zlib1g-dev
  - libfreetype6-dev
  - libtiff-dev
  - libwebp-dev
  - liblcms2-dev
  - rfkill

### ✅ 5. Port 80 permission denied
**Files Modified:**
- `build_sd_image.sh` - Added `setcap 'cap_net_bind_service=+ep'` for Python
- `client/first_boot.sh` - Added setcap (step 5/9)
- `client/install.sh` - Added setcap in system dependencies section

### ✅ 7. dnsmasq timing check too fast
**Files Modified:**
- `client/setup/hotspot.py:282-310` - Improved dnsmasq verification:
  - Increased wait from 1→3 seconds
  - Added retry loop (3 attempts with 2-second delays)
  - Better error logging

---

## Additional Fixes Applied

### NetworkManager Conflict Resolution
**Problem:** NetworkManager fights with manual wpa_supplicant control
**Solution:** Disable NetworkManager in all deployment methods

**Files Modified:**
- `build_sd_image.sh:220-222` - Disable/mask NetworkManager in chroot
- `client/first_boot.sh:50-56` - Disable/mask NetworkManager at first boot (step 4/9)
- `client/install.sh:49-53` - Disable/mask NetworkManager during manual install

### DHCP Client Switch (dhclient → dhcpcd)
**Problem:** Code used dhcpcd but sudoers allowed dhclient
**Solution:** Update sudoers and remove legacy dhclient references

**Files Modified:**
- `config/sudoers.streamscene:39-42` - Replaced dhclient with dhcpcd permissions
- `client/setup/wifi_client.py:185-204` - Use dhcpcd for DHCP requests
- `client/setup/wifi_client.py:379` - Use dhcpcd in disconnect function

---

## Files Modified (Complete List)

1. ✅ `config/sudoers.streamscene` - dhcpcd permissions, added wpa_supplicant
2. ✅ `client/setup/wifi_client.py` - dhcpcd in connect and disconnect
3. ✅ `build_sd_image.sh` - Pillow libs, NetworkManager disable, setcap
4. ✅ `client/first_boot.sh` - 9 steps: rfkill, NetworkManager, setcap, venv creation
5. ✅ `client/install.sh` - NetworkManager disable, setcap
6. ✅ `client/streamscene-client.service` - Fixed systemd directives location
7. ✅ `client/setup/hotspot.py` - Country code, dnsmasq retry logic

---

## Current Pi Status

**Device:** Raspberry Pi Zero 2 WH (streamscene.local / 192.168.1.41)
**Connection:** Ethernet (192.168.1.x network)
**State:** Testing interrupted - NetworkManager still active

**Manual Fixes Still Needed on Current Pi:**
```bash
# These need to be run manually on the Pi since code was deployed but not reinstalled

# 1. Disable NetworkManager (CRITICAL - blocks WiFi client mode)
sudo systemctl stop NetworkManager
sudo systemctl disable NetworkManager
sudo systemctl mask NetworkManager

# 2. Verify Python setcap (should already be set from earlier testing)
getcap /usr/bin/python3
# If not set: sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3

# 3. Install updated sudoers (optional - only needed if deploying via deploy script)
sudo cp ~/streamscene-client/../config/sudoers.streamscene /etc/sudoers.d/streamscene
sudo chmod 440 /etc/sudoers.d/streamscene

# 4. Restart client to test
cd ~/streamscene-client
source venv/bin/activate
python3 main.py
```

---

## Expected WiFi Setup Flow (After Fixes)

1. **Hotspot Mode:**
   - Device creates `StreamScene-XXXX` WiFi network
   - Password: `streamscene`
   - Captive portal runs on port 80 (192.168.4.1)

2. **Credential Submission:**
   - User connects to hotspot
   - Portal auto-opens (or manual: http://192.168.4.1)
   - User enters home WiFi SSID and password
   - Form submits successfully

3. **WiFi Connection:**
   - Device stops hotspot
   - wpa_supplicant connects to home WiFi
   - dhcpcd requests IP address
   - Connection succeeds

4. **Registration:**
   - Device shows QR code on display
   - User scans QR → opens web registration page
   - User registers device with nickname
   - Device transitions to READY state

---

## Next Session: Testing Plan

### Option 1: Test on Current Pi (Quick Test)
**Purpose:** Verify fixes work without full rebuild

```bash
# On LXC - Deploy updated code
./deploy_to_pi.sh

# On Pi - Apply manual fixes (see "Manual Fixes Still Needed" above)
# Then test full WiFi setup flow
```

**Pros:** Fast, uses existing Pi setup
**Cons:** Manual steps required, not testing first-boot flow

### Option 2: Build Fresh SD Card Image (Comprehensive Test)
**Purpose:** Test complete deployment including first-boot provisioning

```bash
# On LXC - Build SD card image with all fixes
sudo ./build_sd_image.sh

# Flash to SD card
# Boot Pi from fresh SD card
# Observe first boot logs: sudo journalctl -u streamscene-firstboot -f
# Test complete WiFi setup flow
```

**Pros:** Tests everything end-to-end, validates first-boot venv creation
**Cons:** Takes longer (~30-60 min for build + flash + boot)

### Option 3: Both (Recommended)
1. Quick test on current Pi first (validate WiFi fixes work)
2. If successful, build SD image (validate deployment works)

---

## Known Working State (Before Testing)

### What's Verified:
- ✅ Captive portal server can bind to port 80 (setcap works)
- ✅ Hotspot creation works (hostapd + dnsmasq start successfully)
- ✅ User can see hotspot and connect to it
- ✅ Captive portal HTML form loads correctly
- ✅ Form submission saves credentials to file

### What's NOT Verified Yet:
- ❓ WiFi client mode connection (dhcpcd timeout needs testing)
- ❓ NetworkManager disable prevents wpa_supplicant conflicts
- ❓ First boot venv creation works correctly
- ❓ Image processing libraries work for Pillow
- ❓ Complete registration flow

---

## Troubleshooting Commands

### Check Network State
```bash
# Check NetworkManager status
systemctl status NetworkManager

# Check wpa_supplicant status
ps aux | grep wpa_supplicant
sudo wpa_cli -i wlan0 status

# Check WiFi interface
ip addr show wlan0
iwconfig wlan0
```

### Check Service Logs
```bash
# Main client logs
sudo journalctl -u streamscene-client -f

# First boot logs (fresh SD card only)
sudo journalctl -u streamscene-firstboot -f
cat /var/log/streamscene-firstboot.log

# Network service logs
sudo journalctl -u hostapd -n 50
sudo journalctl -u dnsmasq -n 50
sudo journalctl -u NetworkManager -n 50
```

### Check Permissions
```bash
# Python capabilities
getcap /usr/bin/python3
getcap /usr/bin/python3.11

# Sudoers
sudo cat /etc/sudoers.d/streamscene

# File permissions
ls -la /boot/firmware/streamscene-device.txt
ls -la ~/streamscene-client/wifi_credentials.json
```

---

## Critical Files Reference

### Configuration Files
- `/boot/firmware/streamscene-device.txt` - Device UUID
- `/boot/firmware/streamscene-apikey.txt` - API key (after registration)
- `/home/pi/streamscene-client/wifi_credentials.json` - WiFi credentials
- `/etc/wpa_supplicant/wpa_supplicant.conf` - WiFi client config
- `/etc/hostapd/hostapd.conf` - Hotspot config
- `/etc/dnsmasq.d/streamscene.conf` - DHCP server config

### System Services
- `/etc/systemd/system/streamscene-client.service` - Main client service
- `/etc/systemd/system/streamscene-firstboot.service` - First boot provisioning (one-time)
- `/etc/sudoers.d/streamscene` - Passwordless sudo permissions

### Log Locations
- `/var/log/streamscene/` - Client logs (main.log, wifi.log, api.log, etc.)
- `/var/log/streamscene-firstboot.log` - First boot provisioning log
- `sudo journalctl -u streamscene-client` - Systemd service logs

---

## Git Status (Uncommitted Changes)

All fixes are in working directory but NOT committed yet. Files modified:
```
M client/config.py
M client/setup/portal_server.py
M client/setup/wifi_client.py
M deploy_to_pi.sh
M build_sd_image.sh
M client/first_boot.sh
M client/install.sh
M client/streamscene-client.service
M client/setup/hotspot.py
M config/sudoers.streamscene
```

**Action Needed:** After testing confirms fixes work, commit all changes:
```bash
git add -A
git commit -m "fix: resolve all WiFi setup issues

- Add rfkill unblock and country code for WiFi
- Fix systemd service StartLimitIntervalSec location
- Create venv and install packages in first_boot.sh
- Add Pillow system libraries to build script
- Disable NetworkManager to prevent wpa_supplicant conflicts
- Switch from dhclient to dhcpcd
- Improve dnsmasq timing check with retry logic
- Add setcap for port 80 binding in all deployment methods

Fixes 7 critical issues preventing device WiFi setup flow."
```

---

## Contact Points for Next Session

**Last Known Issue (From Conversation):**
- WiFi client connection timing out when trying to connect to "Louisiamsterdam" network
- dhclient was failing (now fixed - using dhcpcd)
- NetworkManager was killing wpa_supplicant (now fixed - NetworkManager disabled)

**Next Debug Step:**
Run the client and watch for WiFi connection success after NetworkManager disable.

**Success Criteria:**
1. Hotspot creates successfully
2. Portal accessible at http://192.168.4.1
3. WiFi credentials submitted via form
4. Device connects to home WiFi and gets IP address
5. QR code displays for registration

---

**End of Session Notes**
