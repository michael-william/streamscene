# OTA (Over-The-Air) Update System - Implementation Plan

**Status:** Planning Phase
**Created:** 2025-11-24
**Priority:** HIGH (needed before scaling to multiple devices)

---

## Executive Summary

**Current Situation:**
- Server-side OTA infrastructure is **100% complete** (Phases 2-3)
- Client-side OTA implementation is **NOT started** (Phase 8)
- One working Pi device in production (192.168.1.195)
- No SD card image exists yet (build script ready but untested)

**Risk Assessment:**
- Implementing untested OTA code on only working device: **HIGH RISK**
- Creating backup before any OTA work: **CRITICAL**
- Building SD card image first: **STRONGLY RECOMMENDED**

**Recommended Approach:** Image First, Then OTA

---

## Table of Contents

1. [Current System Status](#current-system-status)
2. [Risk Analysis](#risk-analysis)
3. [Recommended Implementation Order](#recommended-implementation-order)
4. [Phase A: Safety Net](#phase-a-safety-net)
5. [Phase B: Image Validation](#phase-b-image-validation)
6. [Phase C: OTA Implementation](#phase-c-ota-implementation)
7. [Phase D: Family Deployment](#phase-d-family-deployment)
8. [Technical Specifications](#technical-specifications)
9. [Testing Strategy](#testing-strategy)
10. [Rollback Procedures](#rollback-procedures)

---

## Current System Status

### Server-Side OTA Infrastructure (✅ COMPLETE)

**Implementation:** Phases 2-3 (100% complete)

**Database Models:**
- `DeviceUpdate` - Update package metadata
  - Version tracking with semantic versioning
  - SHA256 hash for package integrity
  - Staged rollout support (0-100%)
  - Mandatory vs optional update flags
  - Minimum version requirements
  - Active/inactive flag

- `UpdateDeployment` - Per-device installation tracking
  - Status: pending, downloading, installing, completed, failed, rolled_back
  - Download progress (0-100%)
  - Error messages and rollback reasons
  - Timestamps for tracking

**API Endpoints:** (All implemented in `streamscene/api/routes/devices.py`)
1. `GET /api/devices/{device_id}/updates/check` - Check for updates
2. `GET /api/devices/{device_id}/updates/{version}/download` - Download package
3. `POST /api/devices/{device_id}/updates/report` - Report installation status

**Business Logic:** (`streamscene/core/ota.py`)
- `check_for_updates()` - Deterministic hash-based staged rollout
- `create_update_deployment()` - Initialize deployment tracking
- `update_deployment_status()` - Track installation progress
- `verify_update_package()` - SHA256 verification

**Deployment Options:**
- Staged rollout (10% → 50% → 100%)
- Mandatory vs optional updates
- Minimum version requirements
- Emergency update withdrawal

### Client-Side OTA Implementation (❌ NOT STARTED)

**Status:** Phase 8 - Future work

**Missing Components:**
- Update checking loop in device main loop
- Package download mechanism
- Package verification (SHA256 check)
- Installation scripts
- Backup/restore logic
- Automatic rollback on failure
- Status reporting to server

**Documentation:** Planned in `docs/reference/OTA_SYSTEM.md` (lines 188-239)

### Network Architecture (✅ READY FOR REMOTE UPDATES)

**Server Configuration:**
- Public domain: `streamscene.dataandstories.com`
- SSL/TLS: Let's Encrypt with auto-renewal
- Reverse proxy: Nginx Proxy Manager (192.168.1.104)
- Backend: FastAPI on port 8000

**Client Configuration:**
```python
# client/config.py
API_BASE_URL = "https://streamscene.dataandstories.com"
```

**Authentication:** Device API keys (generated during registration)

**Connectivity:**
- ✅ Works from local network (192.168.1.x)
- ✅ Works from any internet connection
- ✅ No VPN required
- ✅ HTTPS encrypted

### Current Production Device

**Raspberry Pi Zero 2 WH:**
- IP: 192.168.1.195 (WiFi)
- WiFi Network: Louisiamsterdam-TP
- State: READY
- Device UUID: 1c91d1e9-3cc9-44ba-a008-9cdee188d90c
- Database ID: 2c0d4fe8-2426-4228-b2a9-8f89762cc338
- Display: Waveshare 7.3" E Ink (7-color, E variant)
- Status: ✅ Fully operational (displaying PIL-rendered posts)
- Service: `streamscene-client.service` (systemd)

**How it was configured:**
- Manually flashed Raspberry Pi OS Lite
- Manually installed dependencies
- Copied client code
- Configured WiFi setup system
- Tested end-to-end flows

**Configuration is NOT reproducible** (no SD card image exists)

### SD Card Image Building (✅ READY BUT UNTESTED)

**Script:** `/root/streamscene/build_sd_image.sh` (440 lines, executable)
**Documentation:** `/root/streamscene/docs/deployment/SD_CARD_IMAGE.md`
**Status:** Never run, untested

**What it does:**
1. Downloads Raspberry Pi OS Lite (Bookworm, Nov 2024)
2. Configures system in chroot
3. Enables SSH (dual mechanism)
4. Sets credentials (pi:streamscene)
5. Generates unique device UUID
6. Installs dependencies (hostapd, dnsmasq, Python packages)
7. Copies StreamScene client code
8. Creates Python virtualenv
9. Installs system configurations
10. Installs and enables systemd services
11. Creates SHA256 checksum

**Output:** `streamscene-client-1.0.0.img` (~2GB, compressible to ~500MB with xz)

**Requirements:**
- Debian/Ubuntu Linux (✅ Current system is Debian 12 LXC)
- Root access (✅ Available)
- 8GB free disk space (need to verify)
- Internet connection (✅ Available)
- Estimated build time: 15-30 minutes

---

## Risk Analysis

### Implementing OTA on Only Working Device

**CRITICAL RISKS:**

**1. Corrupted Update Package**
- Device downloads broken update
- Device becomes unbootable
- **Impact:** Device offline until physical access
- **Likelihood:** Medium (untested code)
- **Mitigation:** Backup first, test on spare hardware
- **Recovery:** Restore from backup or flash new SD card

**2. Network Failure During Update**
- Download interrupted mid-transfer
- Device in inconsistent state
- **Impact:** Device may not boot or function correctly
- **Likelihood:** Low (but possible on WiFi)
- **Mitigation:** Checksum verification, retry logic
- **Recovery:** Manual SSH access or physical SD card swap

**3. OTA System Bugs**
- Phase 8 code has NEVER been tested
- State machine transitions could fail
- Installation scripts may have errors
- **Impact:** Unpredictable device behavior
- **Likelihood:** HIGH (completely untested code)
- **Mitigation:** Extensive testing on spare hardware first
- **Recovery:** SSH access to debug, or backup restoration

**4. Filesystem Corruption**
- Power loss during write operations
- SD card failure (common on Pi devices)
- **Impact:** Device unbootable, data loss
- **Likelihood:** Low (but catastrophic)
- **Mitigation:** None (hardware failure)
- **Recovery:** Replace SD card, flash new image

**5. Rollback Failure**
- Automatic rollback mechanism fails
- Device stuck in failed state
- **Impact:** Device offline until manual intervention
- **Likelihood:** Medium (rollback code also untested)
- **Mitigation:** Test rollback extensively
- **Recovery:** SSH access or physical restoration

### Current Situation Analysis

**Only One Working Device:**
- Took significant effort to configure
- No spare hardware for testing
- Physical access required for recovery
- Family may be using it (downtime unacceptable)

**No Safety Net:**
- No backup exists
- No SD card image to fall back on
- Cannot quickly rebuild if device breaks
- Would need to reconfigure manually (time-consuming)

**Professional Development Standards:**
- NEVER test untested code in production
- ALWAYS have backups before risky operations
- ALWAYS test on non-production hardware first
- ALWAYS have documented rollback procedures

---

## Recommended Implementation Order

### ⚠️ DO NOT IMPLEMENT OTA FIRST

**Why image-first is critical:**

1. **Reproducibility:** Can create identical devices for testing
2. **Safety Net:** Can restore production device quickly
3. **Scaling:** Needed anyway before family deployment
4. **Professional Practice:** Test before deploying to production
5. **Risk Mitigation:** Separate image testing from OTA testing

### Recommended Sequence

```
Phase A: Safety Net (1 hour)
  ↓ Backup production device
  ↓ Build SD card image
  ↓ Verify image builds successfully

Phase B: Image Validation (2 hours, requires spare hardware)
  ↓ Flash image to spare SD card
  ↓ Test on Pi hardware
  ↓ Fix any image build issues

Phase C: OTA Implementation (8-12 hours)
  ↓ Implement Phase 8 client code
  ↓ Test on spare device
  ↓ Deploy to production when stable

Phase D: Family Deployment (when ready)
  ↓ Build final SD cards from tested image
  ↓ Devices include OTA from day one
  ↓ Remote updates after deployment
```

---

## Phase A: Safety Net

**Goal:** Create backup and validate image building process
**Time:** 1 hour
**Risk:** LOW (no changes to production device)

### Step 1: Backup Production Device (30 minutes)

**Before any OTA work, create full backup of working Pi:**

```bash
# From server (192.168.1.118), backup Pi (192.168.1.195)
mkdir -p /root/streamscene-backups
cd /root/streamscene-backups

# Full disk image (recommended)
ssh pi@192.168.1.195 "sudo dd if=/dev/mmcblk0 bs=4M status=progress | gzip -c" > pi-backup-$(date +%Y%m%d).img.gz

# Calculate checksum
sha256sum pi-backup-$(date +%Y%m%d).img.gz > pi-backup-$(date +%Y%m%d).img.gz.sha256

# Verify backup size (should be ~2GB compressed)
ls -lh pi-backup-*.img.gz
```

**Alternative: Filesystem-only backup (faster, smaller)**
```bash
# Backup critical files only
ssh pi@192.168.1.195 "sudo tar czf - \
  /home/pi/streamscene-client \
  /boot/firmware/streamscene-device.txt \
  /boot/firmware/streamscene-apikey.txt \
  /etc/systemd/system/streamscene-client.service \
  /etc/sudoers.d/streamscene \
  /var/log/streamscene \
  /etc/wpa_supplicant/wpa_supplicant.conf" > pi-filesystem-backup-$(date +%Y%m%d).tar.gz
```

**Verify backup integrity:**
```bash
# Test decompression
gunzip -t pi-backup-$(date +%Y%m%d).img.gz && echo "Backup OK" || echo "Backup CORRUPTED"
```

### Step 2: Build SD Card Image (30 minutes)

**Run image build script:**
```bash
cd /root/streamscene

# Check disk space first (need 8GB)
df -h /root /tmp

# Build image
sudo ./build_sd_image.sh
```

**Expected output:**
- `streamscene-client-1.0.0.img` (~2GB)
- `streamscene-client-1.0.0.img.sha256` (checksum)
- Build log showing all steps

**If build fails:**
- Review error messages
- Check dependencies
- Fix script issues
- Document problems
- DO NOT proceed to Phase B until build succeeds

**Success criteria:**
- ✅ Image file created
- ✅ Checksum calculated
- ✅ No errors in build log
- ✅ File size reasonable (~1.5-2.5GB)

### Step 3: Store Backups Safely

**Create backup storage structure:**
```bash
mkdir -p /root/streamscene-backups/{production,images,checksums}
mv pi-backup-*.img.gz /root/streamscene-backups/production/
mv pi-backup-*.sha256 /root/streamscene-backups/checksums/
mv streamscene-client-1.0.0.img* /root/streamscene-backups/images/

# Document what's what
cat > /root/streamscene-backups/README.md <<EOF
# StreamScene Backups

## Production Device Backups
- pi-backup-YYYYMMDD.img.gz - Full disk image of working Pi
- Created before any risky operations (OTA implementation)

## SD Card Images
- streamscene-client-1.0.0.img - Built from build_sd_image.sh
- Ready to flash to new devices

## Checksums
- *.sha256 files for integrity verification
EOF
```

---

## Phase B: Image Validation

**Goal:** Verify image builds working device
**Time:** 2 hours
**Prerequisites:** Spare Pi hardware and SD card
**Risk:** LOW (testing on spare hardware only)

### Step 1: Prepare Test Hardware

**Required hardware:**
- Spare Raspberry Pi Zero 2 WH
- Spare SD card (16GB minimum, Class 10)
- Spare E Ink display (optional, can test without)
- USB power supply
- SD card reader/adapter

**If no spare hardware available:**
- **STOP HERE** - Do not proceed to OTA implementation
- Order spare hardware before continuing
- Continue working on other features (admin backgrounds, etc.)

### Step 2: Flash Image to Test SD Card

**Using Raspberry Pi Imager (GUI):**
1. Insert SD card into card reader
2. Launch Raspberry Pi Imager
3. Choose OS → Use custom image
4. Select `streamscene-client-1.0.0.img`
5. Choose SD card
6. Write

**Using dd command (CLI):**
```bash
# Find SD card device (be VERY careful with device names)
lsblk

# Unmount if mounted
sudo umount /dev/sdX*

# Write image (replace sdX with actual device)
sudo dd if=/root/streamscene-backups/images/streamscene-client-1.0.0.img \
  of=/dev/sdX \
  bs=4M \
  status=progress \
  conv=fsync

# Eject safely
sync
sudo eject /dev/sdX
```

### Step 3: Boot and Test

**Initial boot:**
1. Insert SD card into spare Pi
2. Connect power
3. Wait 2-3 minutes for first boot
4. Device should create hotspot: `StreamScene-XXXX`

**WiFi setup test:**
1. Connect phone/laptop to `StreamScene-XXXX`
2. Captive portal should open automatically
3. Enter WiFi credentials
4. Submit form
5. Device should connect to WiFi
6. Hotspot should disappear

**Registration test:**
1. Device should display QR code on screen (if E Ink connected)
2. Scan QR code with phone
3. Opens web page: `streamscene.dataandstories.com/setup?id=...`
4. Complete registration
5. Device should transition to READY state
6. Content should display (if registered to stream)

**SSH access test:**
```bash
# Find device IP (check router or use mDNS)
ssh pi@streamscene.local
# Password: streamscene

# Check service status
sudo systemctl status streamscene-client

# Check logs
sudo journalctl -u streamscene-client -f
```

### Step 4: Compare to Production

**Verify functionality matches production device:**
- [ ] WiFi setup works
- [ ] Hotspot activates when no credentials
- [ ] Registration via QR code works
- [ ] Content fetches from server
- [ ] E Ink display updates (if connected)
- [ ] Device stays connected
- [ ] Logs show no errors
- [ ] Service auto-starts on boot

**If any tests fail:**
- Debug issue
- Fix `build_sd_image.sh` script
- Rebuild image
- Repeat testing
- DO NOT proceed to Phase C until image is perfect

**Success criteria:**
- ✅ Image boots successfully
- ✅ All functionality works
- ✅ Identical to production device
- ✅ No errors in logs
- ✅ Can reproduce multiple times

---

## Phase C: OTA Implementation

**Goal:** Implement client-side OTA update system
**Time:** 8-12 hours
**Prerequisites:** Phase A and B complete
**Risk:** MEDIUM (testing on spare hardware, backup exists)

### Overview

**Client-side components to implement:**
1. Update checking loop in main device loop
2. Package download with progress tracking
3. SHA256 verification
4. Installation script execution
5. Backup before installation
6. Automatic rollback on failure
7. Status reporting to server

**Location:** All code in `/root/streamscene/client/` directory

### Step 1: Implement Update Checking (2 hours)

**File:** `client/ota_updater.py` (new file)

**Core class structure:**
```python
from typing import Optional, Dict
import logging
from pathlib import Path
import hashlib
import tarfile
import subprocess
import time

from client.api_client import APIClient
from client.config import Config

logger = logging.getLogger(__name__)

class OTAUpdater:
    """Handles OTA update checking, downloading, and installation."""

    def __init__(self, api_client: APIClient, config: Config):
        self.api = api_client
        self.config = config
        self.update_dir = Path("/tmp/streamscene-update")
        self.backup_dir = Path("/var/lib/streamscene/backups")

    def check_for_updates(self) -> Optional[Dict]:
        """
        Check if updates are available.

        Returns:
            Update metadata if available, None otherwise
        """
        try:
            response = self.api.get(f"/api/devices/{self.config.device_id}/updates/check")
            if response.status_code == 200:
                data = response.json()
                if data.get("update_available"):
                    logger.info(f"Update available: {data['version']}")
                    return data
            return None
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return None

    def download_update(self, version: str, expected_hash: str) -> Optional[Path]:
        """
        Download update package and verify hash.

        Returns:
            Path to downloaded file if successful, None otherwise
        """
        try:
            # Create update directory
            self.update_dir.mkdir(parents=True, exist_ok=True)

            # Download package
            package_path = self.update_dir / f"update-{version}.tar.gz"
            url = f"/api/devices/{self.config.device_id}/updates/{version}/download"

            logger.info(f"Downloading update {version}...")
            response = self.api.get(url, stream=True)

            if response.status_code != 200:
                logger.error(f"Download failed: HTTP {response.status_code}")
                return None

            # Write to file with progress
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(package_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    progress = int((downloaded / total_size) * 100) if total_size else 0

                    # Report progress every 10%
                    if progress % 10 == 0:
                        self.report_status(version, "downloading", progress)

            # Verify hash
            logger.info("Verifying package integrity...")
            calculated_hash = self._calculate_sha256(package_path)

            if calculated_hash != expected_hash:
                logger.error(f"Hash mismatch: expected {expected_hash}, got {calculated_hash}")
                package_path.unlink()
                return None

            logger.info("Package verified successfully")
            return package_path

        except Exception as e:
            logger.error(f"Error downloading update: {e}")
            return None

    def install_update(self, package_path: Path, version: str) -> bool:
        """
        Install update package.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.report_status(version, "installing", 0)

            # Create backup
            logger.info("Creating backup...")
            if not self._create_backup():
                logger.error("Backup failed, aborting update")
                return False

            # Extract package
            logger.info("Extracting update package...")
            extract_dir = self.update_dir / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)

            with tarfile.open(package_path, 'r:gz') as tar:
                tar.extractall(extract_dir)

            # Run installation script
            install_script = extract_dir / "install.sh"
            if not install_script.exists():
                logger.error("Installation script not found in package")
                return False

            logger.info("Running installation script...")
            install_script.chmod(0o755)

            result = subprocess.run(
                [str(install_script)],
                cwd=extract_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"Installation failed: {result.stderr}")
                return False

            logger.info("Update installed successfully")
            self.report_status(version, "completed", 100)

            # Schedule reboot
            logger.info("Rebooting in 10 seconds...")
            time.sleep(10)
            subprocess.run(["sudo", "reboot"])

            return True

        except Exception as e:
            logger.error(f"Error installing update: {e}")
            self.report_status(version, "failed", 0, str(e))
            return False

    def rollback(self, reason: str) -> bool:
        """
        Rollback to previous version from backup.

        Returns:
            True if rollback successful
        """
        try:
            logger.warning(f"Rolling back update: {reason}")

            # Find latest backup
            backups = sorted(self.backup_dir.glob("backup-*.tar.gz"), reverse=True)
            if not backups:
                logger.error("No backups found for rollback")
                return False

            latest_backup = backups[0]
            logger.info(f"Restoring from {latest_backup.name}...")

            # Extract backup
            with tarfile.open(latest_backup, 'r:gz') as tar:
                tar.extractall("/")

            # Restart service
            subprocess.run(["sudo", "systemctl", "restart", "streamscene-client"])

            logger.info("Rollback completed successfully")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def report_status(self, version: str, status: str, progress: int, error: str = ""):
        """Report update status to server."""
        try:
            data = {
                "version": version,
                "status": status,
                "progress": progress,
                "error_message": error
            }
            self.api.post(f"/api/devices/{self.config.device_id}/updates/report", json=data)
        except Exception as e:
            logger.error(f"Error reporting status: {e}")

    def _create_backup(self) -> bool:
        """Create backup of current installation."""
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"backup-{timestamp}.tar.gz"

            # Backup critical directories
            subprocess.run([
                "tar", "czf", str(backup_path),
                "/home/pi/streamscene-client",
                "/boot/firmware/streamscene-device.txt",
                "/boot/firmware/streamscene-apikey.txt"
            ], check=True)

            logger.info(f"Backup created: {backup_path}")

            # Keep only last 3 backups
            backups = sorted(self.backup_dir.glob("backup-*.tar.gz"))
            for old_backup in backups[:-3]:
                old_backup.unlink()
                logger.info(f"Removed old backup: {old_backup.name}")

            return True

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
```

### Step 2: Integrate into Main Loop (1 hour)

**File:** `client/main.py`

**Add update checking to main loop:**
```python
from client.ota_updater import OTAUpdater

# In Device class
def __init__(self):
    # ... existing init ...
    self.ota_updater = OTAUpdater(self.api, self.config)
    self.last_update_check = 0
    self.update_check_interval = 3600  # Check every hour

def run(self):
    """Main device loop."""
    while True:
        try:
            # ... existing loop logic ...

            # Check for updates periodically
            current_time = time.time()
            if current_time - self.last_update_check > self.update_check_interval:
                self._check_and_apply_updates()
                self.last_update_check = current_time

            time.sleep(60)  # Main loop interval

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")

def _check_and_apply_updates(self):
    """Check for and apply updates if available."""
    try:
        # Check for updates
        update_info = self.ota_updater.check_for_updates()

        if not update_info:
            logger.debug("No updates available")
            return

        version = update_info["version"]
        expected_hash = update_info["package_hash"]
        is_mandatory = update_info.get("is_mandatory", False)

        logger.info(f"Update {version} available (mandatory: {is_mandatory})")

        # Download update
        package_path = self.ota_updater.download_update(version, expected_hash)

        if not package_path:
            logger.error("Update download failed")
            return

        # Install update
        success = self.ota_updater.install_update(package_path, version)

        if not success:
            logger.error("Update installation failed, rolling back")
            self.ota_updater.rollback("Installation failed")

        # Device will reboot after successful install

    except Exception as e:
        logger.error(f"Error during update: {e}")
```

### Step 3: Create Update Package Format (1 hour)

**Update package structure:**
```
update-{version}.tar.gz
├── install.sh              # Installation script
├── version.json            # Version metadata
├── client/                 # Updated client code
│   ├── main.py
│   ├── api_client.py
│   ├── ota_updater.py
│   └── ...
├── requirements.txt        # Python dependencies
└── README.md              # Release notes
```

**Example install.sh:**
```bash
#!/bin/bash
set -e

echo "Installing StreamScene update..."

# Stop service
sudo systemctl stop streamscene-client

# Backup current version (already done by updater)

# Install new code
cp -r client/* /home/pi/streamscene-client/

# Update dependencies
cd /home/pi/streamscene-client
source venv/bin/activate
pip install -r requirements.txt

# Start service
sudo systemctl start streamscene-client

echo "Update installed successfully"
exit 0
```

**Example version.json:**
```json
{
  "version": "1.1.0",
  "release_date": "2025-11-25",
  "changelog": [
    "Added OTA update support",
    "Fixed E Ink refresh timing",
    "Improved WiFi stability"
  ],
  "minimum_version": "1.0.0",
  "breaking_changes": false
}
```

### Step 4: Test on Spare Device (4 hours)

**Create test update package:**
1. Make small change to client code (e.g., add log message)
2. Package into update-1.0.1.tar.gz
3. Calculate SHA256 hash
4. Upload to server

**Test scenarios:**

**1. Successful update:**
- Create update deployment in database
- Mark as 100% rollout
- Wait for device to check for updates
- Verify download progresses
- Verify installation succeeds
- Verify device reboots
- Verify new code is running

**2. Failed download (network interruption):**
- Interrupt network during download
- Verify device retries
- Verify eventually succeeds

**3. Hash mismatch:**
- Corrupt package file
- Verify device rejects package
- Verify device reports error

**4. Installation failure:**
- Create update with broken install.sh
- Verify device attempts installation
- Verify automatic rollback occurs
- Verify device returns to previous version

**5. Staged rollout:**
- Set rollout to 10%
- Verify device may or may not receive update (hash-based)
- Increase to 100%
- Verify device eventually receives update

**Success criteria:**
- ✅ Happy path works end-to-end
- ✅ All failure scenarios handled gracefully
- ✅ Rollback mechanism works
- ✅ Device never becomes unresponsive
- ✅ No manual intervention needed

### Step 5: Deploy to Production (1 hour)

**Only after ALL tests pass on spare device:**

1. **Create production update:**
   - Package current working version as "1.0.0"
   - Package OTA-enabled version as "1.1.0"
   - Upload to server

2. **Create deployment:**
   - Start with 10% rollout
   - Set as optional (not mandatory)
   - Monitor for 24 hours

3. **Monitor production device:**
   - Watch logs during update
   - Verify successful installation
   - Verify device still functions

4. **Increase rollout:**
   - If successful, increase to 50%
   - Then 100%

5. **Document process:**
   - Update NEXT_SESSION.md
   - Add to CLAUDE.md
   - Create OTA runbook

---

## Phase D: Family Deployment

**Goal:** Deploy devices to family members with OTA pre-installed
**Time:** Depends on number of devices
**Risk:** LOW (tested and proven on production device)

### Preparation

**Update SD card image build script:**
1. Ensure image includes OTA code (from Phase C)
2. Test image builds successfully
3. Verify OTA works on fresh image

**Build production SD cards:**
```bash
# Build final image with OTA included
cd /root/streamscene
sudo ./build_sd_image.sh

# Flash to multiple SD cards
for device in 1 2 3 4 5; do
  echo "Flashing device $device..."
  sudo dd if=streamscene-client-1.0.0.img of=/dev/sdX bs=4M status=progress
  sync
done
```

### Deployment Process

**Per device:**
1. Flash SD card from tested image
2. Insert into Pi
3. Power on, wait for hotspot
4. User configures WiFi via captive portal
5. User scans QR code for registration
6. Device connects to server
7. Device checks for updates automatically
8. Family member receives device ready to use

**Post-deployment:**
- Monitor device health via web dashboard
- Push updates as needed
- Devices automatically update themselves
- No physical access required

---

## Technical Specifications

### Update Package Format

**Filename:** `update-{version}.tar.gz`
**Contents:** Installation script, code, metadata
**Hash:** SHA256 for integrity verification
**Size limit:** 50MB (Pi Zero bandwidth constraints)

### Installation Process

1. Device checks for updates (hourly when idle)
2. Server returns update metadata (if available)
3. Device downloads package to `/tmp/streamscene-update/`
4. Device verifies SHA256 hash
5. Device creates backup to `/var/lib/streamscene/backups/`
6. Device extracts package and runs `install.sh`
7. Device restarts service
8. Device reports success to server
9. If device doesn't report within 5 minutes, automatic rollback

### Staged Rollout Algorithm

**Deterministic hash-based selection:**
```python
def should_receive_update(device_id: str, rollout_percentage: int) -> bool:
    """Determine if device should receive update based on rollout percentage."""
    # Hash device ID to get consistent value
    hash_value = hashlib.sha256(device_id.encode()).hexdigest()
    # Take first 8 hex chars and convert to integer
    device_hash = int(hash_value[:8], 16)
    # Calculate threshold
    threshold = (rollout_percentage / 100.0) * 0xFFFFFFFF
    # Device receives update if hash is below threshold
    return device_hash < threshold
```

**Properties:**
- Deterministic (same device always gets same result)
- Evenly distributed (10% = exactly 10% of devices)
- Consistent across checks (device doesn't randomly opt in/out)

### Rollback Mechanism

**Automatic rollback triggers:**
- Device doesn't report success within 5 minutes
- Installation script exits with non-zero code
- Service fails to start after update

**Rollback process:**
1. Extract backup tarball to root
2. Restart service
3. Report rollback to server with reason
4. Mark update deployment as "rolled_back"

**Manual rollback (SSH access):**
```bash
# Restore from latest backup
sudo tar xzf /var/lib/streamscene/backups/backup-*.tar.gz -C /
sudo systemctl restart streamscene-client
```

### Security Considerations

**Package integrity:**
- ✅ SHA256 verification prevents tampering
- ⚠️ No package signing (future enhancement)

**Authentication:**
- ✅ Device API keys required for all endpoints
- ✅ HTTPS encryption in transit

**Authorization:**
- ✅ Devices can only download their own updates
- ✅ Server validates device ID in all requests

**Rate limiting:**
- ✅ 10 requests/minute per device (prevents abuse)

---

## Testing Strategy

### Unit Tests

**Test files to create:**
- `client/tests/test_ota_updater.py`
- Mock API client
- Mock filesystem operations
- Test all updater methods

**Coverage targets:**
- Check for updates: 100%
- Download with verification: 100%
- Installation process: 90%
- Rollback mechanism: 100%

### Integration Tests

**Test on spare device:**
1. Successful update (happy path)
2. Network interruption during download
3. Corrupted package (hash mismatch)
4. Installation script failure
5. Service failure after update
6. Automatic rollback
7. Manual rollback
8. Staged rollout (10%, 50%, 100%)
9. Mandatory vs optional updates
10. Minimum version requirements

### Production Validation

**Before family deployment:**
- ✅ Test on spare device (all scenarios)
- ✅ Test on production device (single update)
- ✅ Monitor for 48 hours
- ✅ Verify no regressions
- ✅ Document all issues encountered

---

## Rollback Procedures

### Scenario 1: Update Fails During Installation

**Automatic rollback (no manual intervention):**
- Device detects installation failure
- Restores from backup automatically
- Reports failure to server
- Continues normal operation

**Manual rollback (if automatic fails):**
```bash
# SSH into device
ssh pi@192.168.1.195

# Check backup exists
ls -la /var/lib/streamscene/backups/

# Restore latest backup
sudo tar xzf /var/lib/streamscene/backups/backup-*.tar.gz -C /

# Restart service
sudo systemctl restart streamscene-client

# Verify service running
sudo systemctl status streamscene-client
```

### Scenario 2: Device Won't Boot After Update

**Physical access required:**
1. Remove SD card from device
2. Insert into card reader on laptop
3. Mount root partition
4. Restore backup files manually
5. Or flash fresh image from Phase A
6. Reinsert SD card
7. Power on device

### Scenario 3: Service Fails to Start

**SSH access available:**
```bash
# Check service logs
sudo journalctl -u streamscene-client -n 100

# Check Python errors
sudo systemctl status streamscene-client

# If update caused issue, rollback
sudo tar xzf /var/lib/streamscene/backups/backup-*.tar.gz -C /
sudo systemctl restart streamscene-client
```

### Scenario 4: Mass Deployment Failure

**Multiple devices affected:**
1. Immediately mark update as inactive in database
2. Prevent more devices from receiving it
3. Prepare rollback update package (previous version)
4. Deploy rollback update at 100% rollout
5. Devices will download and install previous version
6. Investigate root cause
7. Fix issue and redeploy

---

## Success Criteria

### Phase A Success
- ✅ Backup of production device exists
- ✅ SD card image builds without errors
- ✅ Image file and checksum stored safely

### Phase B Success
- ✅ Image boots on spare hardware
- ✅ All functionality works (WiFi, registration, content)
- ✅ No errors in logs
- ✅ Identical to production device

### Phase C Success
- ✅ OTA code implemented
- ✅ All test scenarios pass
- ✅ Rollback mechanism works
- ✅ Production device successfully updates
- ✅ No downtime or manual intervention

### Phase D Success
- ✅ Multiple devices deployed to family
- ✅ All devices self-configure (WiFi + registration)
- ✅ All devices can be updated remotely
- ✅ No physical access required post-deployment

---

## Timeline Estimates

### Conservative Timeline (With Spare Hardware)
- **Phase A:** 1 hour (backup + build image)
- **Phase B:** 2 hours (test image on spare)
- **Phase C:** 8-12 hours (implement + test OTA)
- **Phase D:** 1 hour per device (flash + deploy)
- **Total:** 12-16 hours + deployment time

### Aggressive Timeline (Testing on Production)
- **Phase A:** 1 hour (backup + build image)
- **Phase B:** SKIPPED (no spare hardware)
- **Phase C:** 10-14 hours (implement + test on production)
- **Phase D:** 1 hour per device
- **Total:** 11-15 hours + deployment time
- **Risk:** HIGH (no spare hardware safety net)

### Recommended Timeline (Safe Approach)
- **Week 1:** Phase A (create safety net)
- **Week 2:** Order spare hardware if needed
- **Week 3:** Phase B (validate image)
- **Week 4:** Phase C (implement OTA)
- **Week 5:** Production testing + monitoring
- **Week 6:** Family deployment
- **Total:** 6 weeks to stable, scalable system

---

## Open Questions

**Before starting implementation:**

1. **Do you have spare hardware?**
   - [ ] Spare Pi Zero 2 WH
   - [ ] Spare SD cards
   - [ ] Spare E Ink display
   - If NO: Order before Phase B

2. **Disk space check:**
   ```bash
   df -h /root /tmp
   # Need 8GB free for image building
   ```

3. **Family deployment timeline:**
   - When do you want to give devices to family?
   - Can wait for OTA to be stable?
   - Or deploy without OTA and update manually later?

4. **Update frequency:**
   - How often do you expect to push updates?
   - Daily/weekly/monthly?
   - Helps determine if OTA is critical

5. **Tolerance for downtime:**
   - Is production device actively used?
   - Can it be offline for testing?
   - Need to schedule maintenance window?

---

## Next Steps

**Immediate actions (before any coding):**

1. ✅ Save this plan as `ota_plan.md`
2. ⬜ Create backup of production device
3. ⬜ Verify disk space for image building
4. ⬜ Build SD card image
5. ⬜ Decide on spare hardware (order if needed)

**Then choose path:**

**Path A: Safe (Recommended)**
- Wait for spare hardware
- Test everything before production
- Lower risk, higher confidence

**Path B: Aggressive (Not Recommended)**
- Test on production device
- Higher risk of breaking only working device
- Faster timeline but dangerous

**Path C: Defer OTA**
- Deploy devices without OTA
- Update manually when needed (physical access)
- Implement OTA later as enhancement

---

**The most important step is creating the backup FIRST. Everything else can be undone, but only if you have a backup.**
