# WiFi Hotspot Troubleshooting Log
**Date Started:** 2025-11-18
**Device:** Raspberry Pi Zero 2 WH
**Issue:** WiFi hotspot not appearing after fresh SD card flash

---

## Current Status
🟡 **MANUAL TROUBLESHOOTING - Issues Identified**

**Symptom:** SD card image built from outdated code. Manual deployment to stock Raspberry Pi OS revealed multiple issues.

---

## Session 1: 2025-11-18

### Root Cause Discovery

**CRITICAL FINDING:** SD card image was built from OLD code on Proxmox host that did NOT include SESSION_NOTES.md fixes. The LXC container has the fixes, but they weren't synced before build.

### Manual Deployment Method

Switched to **stock Raspberry Pi OS Lite 64-bit** + manual client deployment to troubleshoot issues.

**Deployment Process:**
1. Flashed stock Raspberry Pi OS Lite (64-bit) to SD card
2. Enabled SSH, booted Pi (accessible at 192.168.1.41)
3. Copied client code from LXC to Pi via Mac:
   ```bash
   scp -r root@192.168.1.118:/root/streamscene/client pi@192.168.1.41:~/streamscene-client
   scp root@192.168.1.118:/root/streamscene/config/sudoers.streamscene pi@192.168.1.41:~/
   ```
4. Ran `first_boot.sh` manually with verbose output

### Issues Found (7 Total)

✅ **Fixed During Session:**
1. ✅ Missing `libcap2-bin` package (needed for setcap)
2. ✅ Python version mismatch (hardcoded 3.11, stock OS has 3.13)
3. ✅ setcap command missing quotes
4. ✅ Service file not installed to /etc/systemd/system/
5. ✅ Sudoers file not installed to /etc/sudoers.d/

⏳ **In Progress:**
6. ⏳ Missing `waveshare-epd` library (service crashes on startup)

📝 **To Be Tested:**
7. 📝 WiFi hotspot functionality (pending library install)

---

## Fix History

### Fix #1: Missing libcap2-bin Package
**Issue:** `setcap` command not found during first boot
**Root Cause:** Stock Raspberry Pi OS Lite doesn't include libcap2-bin by default
**Solution Applied:**
```bash
sudo apt-get update
sudo apt-get install -y libcap2-bin
```
**Build Script Fix Needed:** Add to `build_sd_image.sh` package list
**Status:** ✅ Fixed

---

### Fix #2: Python Version Hardcoded as 3.11
**Issue:** Script tries to setcap on `/usr/bin/python3.11` but stock OS has Python 3.13
**Root Cause:** first_boot.sh hardcoded Python 3.11 path
**Solution Applied:**
```bash
# Instead of:
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3.11

# Use:
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3.13
```
**Build Script Fix Needed:** Make first_boot.sh detect Python version dynamically:
```bash
PYTHON_BIN=$(readlink -f /usr/bin/python3)
sudo setcap 'cap_net_bind_service=+ep' "$PYTHON_BIN"
```
**Status:** ✅ Fixed

---

### Fix #3: setcap Command Missing Quotes
**Issue:** `setcap cap_net_bind_service=+ep` fails with "Invalid file 'setcap'"
**Root Cause:** Missing quotes around capability string in first_boot.sh
**Solution Applied:**
```bash
# Wrong:
sudo setcap cap_net_bind_service=+ep /usr/bin/python3.11

# Correct:
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3.13
```
**Build Script Fix Needed:** Update first_boot.sh line ~55
**Status:** ✅ Fixed

---

### Fix #4: Service File Not Installed
**Issue:** `systemctl enable streamscene-client.service` fails - "Unit does not exist"
**Root Cause:** Service file not copied to /etc/systemd/system/ during first boot
**Solution Applied:**
```bash
sudo cp ~/streamscene-client/streamscene-client.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable streamscene-client.service
```
**Build Script Fix Needed:** Add to build_sd_image.sh:
- Copy service file to /etc/systemd/system/ in chroot
- Run systemctl daemon-reload in chroot
**Status:** ✅ Fixed

---

### Fix #5: Sudoers File Not Installed
**Issue:** Sudoers file not installed during first boot
**Root Cause:** first_boot.sh doesn't copy sudoers file
**Solution Applied:**
```bash
sudo cp ~/sudoers.streamscene /etc/sudoers.d/streamscene
sudo chmod 440 /etc/sudoers.d/streamscene
```
**Build Script Fix Needed:** Add to build_sd_image.sh (should already be there, verify)
**Status:** ✅ Fixed

---

### Fix #6: Missing waveshare-epd Library
**Issue:** Service crashes on startup with `ModuleNotFoundError: No module named 'waveshare_epd'`
**Root Cause:** Library not in requirements.txt or pip install failed
**Solution Applied:**
```bash
cd ~/streamscene-client
source venv/bin/activate
pip install waveshare-epd
pip install -r requirements.txt
deactivate
sudo systemctl restart streamscene-client.service
```
**Build Script Fix Needed:**
- Verify `waveshare-epd` is in requirements.txt
- Check if build script installs it correctly
**Status:** ⏳ In Progress

---

### Fix #7: WiFi Hotspot Functionality
**Issue:** To be determined after waveshare-epd is installed
**Status:** 📝 Pending Testing

---

## Commands Reference

### Copy Diagnostic Script to Pi
```bash
# From LXC container:
scp /root/streamscene/pi_diagnostic.sh pi@<PI_IP>:~/

# Then on Pi:
chmod +x ~/pi_diagnostic.sh
sudo ./pi_diagnostic.sh | tee diagnostic_output.txt
```

### Manual Checks (if script doesn't work)
```bash
# Check first boot
ls -la /var/lib/streamscene-firstboot-complete
cat /var/log/streamscene-firstboot.log

# Check UUID
cat /boot/firmware/streamscene-device.txt

# Check venv
ls -la /home/pi/streamscene-client/venv/bin/python3

# Check WiFi
rfkill list
iwconfig wlan0
ip addr show wlan0

# Check services
sudo systemctl status streamscene-client
sudo systemctl status NetworkManager
sudo systemctl status hostapd
sudo systemctl status dnsmasq

# Check logs
sudo journalctl -u streamscene-client -n 100
tail -50 /var/log/streamscene-firstboot.log
```

---

## Next Steps

1. ✅ Run diagnostic script on Pi
2. ⏳ Analyze diagnostic output
3. ⏳ Create targeted fix script
4. ⏳ Apply fixes
5. ⏳ Verify hotspot appears
6. ⏳ Test complete WiFi setup flow
7. ⏳ Update build scripts if needed
8. ⏳ Commit all fixes

---

## Notes

- SD card image was built on Proxmox host (not LXC) due to privileged operation requirements
- Image flashed successfully to SD card
- Pi boots successfully, SSH accessible via Ethernet
- This is a FRESH first boot from newly flashed SD card

---

**Last Updated:** 2025-11-18 21:25 CET (Session 1: Manual troubleshooting - 6/7 issues fixed)
