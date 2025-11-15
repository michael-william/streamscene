# Over-The-Air (OTA) Update System

Complete documentation for the StreamScene OTA update infrastructure.

## Overview

The OTA system enables remote software updates for Raspberry Pi devices over WiFi. It includes:
- Staged rollout (gradual deployment to percentage of devices)
- Version compatibility checking
- Mandatory vs optional updates
- Automatic rollback on failure
- Update package verification via SHA256 hash

## Server-Side Infrastructure (Phases 1-3)

### Database Models

See `streamscene/core/models.py` for implementation.

#### DeviceUpdate Model

Stores update package metadata.

**Fields:**
- `version` (string, unique) - e.g., "1.2.3"
- `release_date` (timestamp)
- `package_path` (string) - Path to .tar.gz update package
- `package_hash` (string) - SHA256 checksum for verification
- `package_size` (integer) - Size in bytes
- `changelog` (text) - User-facing release notes
- `is_active` (boolean) - Can be disabled to withdraw bad updates
- `min_version_required` (string, nullable) - Minimum version that can install this update
- `is_mandatory` (boolean) - Force installation
- `rollout_percentage` (integer, 0-100) - Staged rollout (0=none, 100=all devices)

**Features:**
- Supports staged rollout via `rollout_percentage`
- Version compatibility via `min_version_required`
- Mandatory vs optional updates
- Active/inactive flag for withdrawing bad updates

#### UpdateDeployment Model

Tracks installation status per device.

**Fields:**
- `device_id` (foreign key)
- `update_id` (foreign key)
- `status` (enum: pending, downloading, installing, completed, failed, rolled_back)
- `download_progress` (integer, 0-100)
- `error_message` (text, nullable)
- `rollback_reason` (text, nullable)
- `started_at` (timestamp)
- `completed_at` (timestamp, nullable)

**Features:**
- Records download progress (0-100%)
- Captures error messages and rollback reasons
- Links device to update via foreign keys

### OTA Business Logic

See `streamscene/core/ota.py` for implementation.

#### Staged Rollout Algorithm

Devices are selected for rollout based on deterministic hash of device ID:

```python
# Devices selected for rollout based on hash of device ID
device_hash = int(hashlib.md5(str(device_id).encode()).hexdigest(), 16)
device_percentage = (device_hash % 100) + 1
eligible = device_percentage <= update.rollout_percentage
```

**Example:**
- `rollout_percentage = 10` → first 10% of devices eligible
- `rollout_percentage = 50` → half of devices eligible
- `rollout_percentage = 100` → all devices eligible

**Benefits:**
- Deterministic (same device always gets same percentage)
- Evenly distributed across device population
- No database state required

#### Key Functions

**check_for_updates(device_id)**
- Eligibility check (version, rollout %, active status)
- Returns update if available, None otherwise

**create_update_deployment(device_id, update_id)**
- Initialize tracking record
- Sets status to "pending"

**update_deployment_status(device_id, update_id, status, progress, error)**
- Track progress during installation
- Update download_progress, error_message, etc.

**get_deployment_stats(update_id)**
- Success rate monitoring
- Returns counts by status (completed, failed, etc.)

### Device API Endpoints

See `streamscene/api/routes/devices.py` for implementation.

#### Check for Updates

```
GET /api/devices/{device_id}/updates/check
Headers: X-Device-API-Key
```

**Returns:**
```json
{
  "update_available": true,
  "version": "1.2.3",
  "is_mandatory": false,
  "package_size": 1048576,
  "changelog": "Bug fixes and performance improvements"
}
```

Uses staged rollout algorithm (hash-based percentage).

#### Download Update Package

```
GET /api/devices/{device_id}/updates/{version}/download
Headers: X-Device-API-Key
```

**Returns:** Binary .tar.gz file (FileResponse)

**Note:** Device must verify SHA256 hash after download

#### Report Installation Status

```
POST /api/devices/{device_id}/updates/report
Headers: X-Device-API-Key
```

**Request body:**
```json
{
  "update_id": "UUID",
  "status": "completed",
  "download_progress": 100,
  "error_message": null,
  "rollback_reason": null
}
```

**Response:**
```json
{
  "success": true,
  "message": "Status recorded"
}
```

### QR Code Generation

See `streamscene/core/qr_utils.py` for implementation.

#### Device Registration QR Codes

Generates QR codes for device registration URLs.

**Format:** `{FRONTEND_URL}/register?device_uuid={uuid}`

**Features:**
- High error correction for reliability
- Configurable size and border
- Returns PNG bytes (ready for display or file save)

**Functions:**
```python
generate_registration_qr(device_uuid: UUID, base_url: str = None,
                        box_size: int = 10, border: int = 4) -> bytes

save_registration_qr(device_uuid: UUID, output_path: str, ...) -> bool
```

## Client-Side Integration (Phase 8 - Pending)

### Update Installation Flow

1. **Check for updates** periodically (every hour when idle)
2. **Download update package** over WiFi to temporary directory
3. **Verify SHA256 hash** matches server-provided hash
4. **Extract package** to `/tmp/streamscene-update/`
5. **Run update script** (`update.sh` in package)
6. **Verify new version** boots successfully
7. **Report success** to server
8. **Automatic rollback** on failure (restore backup)

### Update Package Structure

```
streamscene-update-1.2.3.tar.gz
├── update.sh           # Installation script
├── client/             # Updated Python code
├── requirements.txt    # Python dependencies
├── systemd/            # Service files (if changed)
└── VERSION             # Version file
```

### Update Script Template

```bash
#!/bin/bash
# update.sh - OTA update installer

set -e  # Exit on error

VERSION=$(cat VERSION)
BACKUP_DIR="/var/lib/streamscene/backups/$(date +%Y%m%d-%H%M%S)"

# Backup current installation
mkdir -p "$BACKUP_DIR"
cp -r /home/badgy/streamscene-client "$BACKUP_DIR/"

# Install new version
cp -r client/* /home/badgy/streamscene-client/
pip install -r requirements.txt

# Update version file
echo "$VERSION" > /home/badgy/streamscene-client/VERSION

# Restart service
sudo systemctl restart streamscene-client

echo "Update to $VERSION completed successfully"
```

### Rollback Mechanism

If device doesn't report success within 5 minutes:
1. Assume update failed
2. Restore from backup directory
3. Restart service
4. Report failure with rollback_reason to server

## Update Strategy

### Staged Rollout Process

1. **Create update** with `rollout_percentage = 10`
2. **Monitor deployment stats** for 24-48 hours
3. **If success rate > 95%**, increase to 50%
4. **Monitor again**, then increase to 100%
5. **If failures occur**, set `is_active = false` to stop rollout

### Version Compatibility

Use `min_version_required` to prevent incompatible updates:

**Example:**
- v1.0.0 → v1.1.0: No min_version (all devices eligible)
- v2.0.0: Set `min_version_required = "1.5.0"` (breaking changes)

### Mandatory Updates

Set `is_mandatory = true` for critical security updates:
- Device must install before resuming normal operation
- No "skip" option in UI
- Retries automatically on failure

## Update Package Storage

**Location:** `/var/lib/streamscene/updates/`

**Structure:**
```
/var/lib/streamscene/updates/
├── streamscene-update-1.0.0.tar.gz
├── streamscene-update-1.1.0.tar.gz
└── streamscene-update-1.2.0.tar.gz
```

**Package naming convention:** `streamscene-update-{version}.tar.gz`

## Monitoring & Diagnostics

### Deployment Statistics

Use `get_deployment_stats(update_id)` to monitor rollout:

```python
stats = get_deployment_stats(update_id)
# Returns: {
#   "pending": 10,
#   "downloading": 5,
#   "installing": 2,
#   "completed": 80,
#   "failed": 3
# }
```

### Success Rate Calculation

```python
total = stats["completed"] + stats["failed"]
success_rate = stats["completed"] / total if total > 0 else 0
```

**Thresholds:**
- **> 95%** - Healthy, safe to increase rollout
- **90-95%** - Acceptable, monitor closely
- **< 90%** - Investigate failures, consider withdrawing update

## Security Considerations

- **SHA256 verification** prevents tampered packages
- **HTTPS only** for download (TLS encryption)
- **API key authentication** prevents unauthorized access
- **Package signing** (future enhancement)
