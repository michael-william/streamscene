# StreamScene Device Setup & OTA Update System - Implementation Plan

**Created:** November 9, 2025
**Status:** Planning
**Estimated Time:** 16-20 hours (2-3 days focused work)

---

## Overview

Implement complete device setup and OTA (Over-The-Air) update system where devices:

1. **Boot into WiFi hotspot mode** with setup instructions on E Ink screen
2. **User connects to device hotspot** and provides home WiFi credentials via web form (no JavaScript)
3. **Device connects to home WiFi** and displays QR code for registration
4. **User scans QR code** to register device on web app
5. **Device checks for updates**, downloads, installs, and reboots if available
6. **Device operates normally**, checking for updates when user triggers them

---

## Device Boot Flow (Final)

```
1. Device boots → Check state file

2. If state = WIFI_SETUP (or first boot):
   - Create WiFi hotspot (StreamScene-XXXX)
   - Start captive portal server
   - Display on E Ink:
     "Welcome to StreamScene!

      Connect your phone to:
      Network: StreamScene-A1B2
      Password: streamscene

      Open browser to: 192.168.4.1
      Enter your home WiFi credentials"
   - Wait for credentials

3. When credentials received:
   - Save credentials
   - Stop hotspot
   - Switch to client mode
   - Connect to home WiFi
   - State = CONNECTING

4. If state = CONNECTING:
   - Attempt WiFi connection
   - On success: State = AWAITING_REGISTRATION
   - On failure: State = ERROR (show error, return to WIFI_SETUP)

5. If state = AWAITING_REGISTRATION:
   - Generate QR code URL: https://streamscene.dataandstories.com/setup?device={UUID}
   - Display QR code on E Ink with instructions
   - Poll server to check if registered
   - On registered: State = CHECKING_UPDATES

6. If state = CHECKING_UPDATES:
   - Call /api/devices/{id}/updates/check
   - If update available:
     - State = UPDATING
     - Download update
     - Verify checksum
     - Install update
     - Report success
     - Reboot
   - If no update:
     - State = READY

7. If state = READY:
   - Normal operation (fetch content, display posts)
   - Periodically check for user-triggered updates
   - If update triggered: State = UPDATING
```

---

## Implementation Phases

### Phase 1: Server-Side Infrastructure (2-3 hours)

#### Database Schema Updates

**File:** `streamscene/core/models.py`

**New Models:**

```python
class OTAUpdate(Base):
    """OTA update packages."""
    __tablename__ = "ota_updates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(String(20), unique=True, nullable=False)
    release_date = Column(DateTime(timezone=True), server_default=func.now())
    package_path = Column(String(500), nullable=False)  # Path on server
    package_checksum = Column(String(64), nullable=False)  # SHA256
    changelog = Column(Text)
    is_active = Column(Boolean, default=True)
    min_version = Column(String(20))  # Minimum version that can upgrade
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DeviceUpdate(Base):
    """Tracks update status per device."""
    __tablename__ = "device_updates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    update_id = Column(UUID(as_uuid=True), ForeignKey("ota_updates.id"), nullable=False)
    status = Column(Enum("pending", "downloading", "installing", "complete", "failed", name="update_status"))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)

    # Relationships
    device = relationship("Device", back_populates="updates")
    update = relationship("OTAUpdate")
```

**Updates to Device Model:**

```python
# Add to Device class
setup_state = Column(
    Enum("wifi_setup", "connecting", "awaiting_registration", "registered",
         "checking_updates", "updating", "ready", "error", name="device_setup_state"),
    default="wifi_setup",
    nullable=False
)
setup_completed_at = Column(DateTime(timezone=True))

# Add relationship
updates = relationship("DeviceUpdate", back_populates="device")
```

**Migration:**
```bash
alembic revision --autogenerate -m "Add OTA update tables and device setup state"
alembic upgrade head
```

#### Business Logic

**New File:** `streamscene/core/updates.py`

```python
"""OTA update business logic."""

from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from . import models
import hashlib

def create_ota_update(
    session: Session,
    version: str,
    package_path: str,
    changelog: str = "",
    min_version: Optional[str] = None
) -> models.OTAUpdate:
    """Create a new OTA update package."""
    # Calculate checksum
    checksum = calculate_package_checksum(package_path)

    update = models.OTAUpdate(
        version=version,
        package_path=package_path,
        package_checksum=checksum,
        changelog=changelog,
        min_version=min_version,
        is_active=True
    )
    session.add(update)
    return update

def check_device_updates(
    session: Session,
    device_id: UUID
) -> Optional[models.OTAUpdate]:
    """Check if device has available updates."""
    device = session.query(models.Device).filter_by(id=device_id).first()
    if not device:
        return None

    # Get latest active update newer than device version
    latest_update = session.query(models.OTAUpdate).filter(
        models.OTAUpdate.is_active == True,
        models.OTAUpdate.version > device.current_version
    ).order_by(models.OTAUpdate.version.desc()).first()

    return latest_update

def record_update_status(
    session: Session,
    device_id: UUID,
    update_id: UUID,
    status: str,
    error_message: Optional[str] = None
):
    """Record device update status."""
    device_update = session.query(models.DeviceUpdate).filter_by(
        device_id=device_id,
        update_id=update_id
    ).first()

    if not device_update:
        device_update = models.DeviceUpdate(
            device_id=device_id,
            update_id=update_id,
            status=status
        )
        session.add(device_update)
    else:
        device_update.status = status
        if error_message:
            device_update.error_message = error_message
        if status in ["complete", "failed"]:
            from datetime import datetime
            device_update.completed_at = datetime.utcnow()

def calculate_package_checksum(filepath: str) -> str:
    """Calculate SHA256 checksum of package file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
```

#### API Endpoints

**New File:** `streamscene/api/routes/updates.py`

```python
"""OTA update API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional

from ..dependencies import get_db, verify_device_api_key
from ..schemas import UpdateCheckResponse, UpdateConfirmRequest
from ...core import updates as update_ops
from ...core import models

router = APIRouter(prefix="/api", tags=["updates"])

@router.get("/devices/{device_id}/updates/check", response_model=UpdateCheckResponse)
async def check_for_updates(
    device_id: UUID,
    db: Session = Depends(get_db),
    device: models.Device = Depends(verify_device_api_key)
):
    """Device checks for available updates."""
    update = update_ops.check_device_updates(db, device_id)

    if update:
        return {
            "has_update": True,
            "version": update.version,
            "download_url": f"/updates/{update.version}/{update.package_path.split('/')[-1]}",
            "checksum": update.package_checksum,
            "changelog": update.changelog
        }
    else:
        return {
            "has_update": False,
            "version": None,
            "download_url": None,
            "checksum": None,
            "changelog": None
        }

@router.post("/devices/{device_id}/updates/confirm")
async def confirm_update(
    device_id: UUID,
    request: UpdateConfirmRequest,
    db: Session = Depends(get_db),
    device: models.Device = Depends(verify_device_api_key)
):
    """Device reports update installation status."""
    # Find the update
    update = db.query(models.OTAUpdate).filter_by(version=request.version).first()
    if not update:
        raise HTTPException(status_code=404, detail="Update not found")

    # Record status
    status = "complete" if request.success else "failed"
    update_ops.record_update_status(
        db,
        device_id,
        update.id,
        status,
        request.error_message
    )

    # Update device version if successful
    if request.success:
        device.current_version = request.version

    db.commit()

    return {"status": "ok"}

# Admin endpoints (require user authentication)
@router.post("/admin/updates")
async def upload_update(
    file: UploadFile = File(...),
    version: str = None,
    changelog: str = "",
    db: Session = Depends(get_db),
    # Add user authentication dependency here
):
    """Upload new update package (admin only)."""
    import os
    from datetime import datetime

    # Save file
    upload_dir = "/var/lib/streamscene/updates"
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"streamscene-{version}.tar.gz"
    filepath = os.path.join(upload_dir, filename)

    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    # Create update record
    update = update_ops.create_ota_update(
        db,
        version=version,
        package_path=filepath,
        changelog=changelog
    )
    db.commit()

    return {"version": version, "id": str(update.id)}

@router.get("/admin/updates")
async def list_updates(
    db: Session = Depends(get_db),
    # Add user authentication dependency here
):
    """List all available updates (admin only)."""
    updates = db.query(models.OTAUpdate).order_by(
        models.OTAUpdate.release_date.desc()
    ).all()

    return [
        {
            "id": str(u.id),
            "version": u.version,
            "release_date": u.release_date.isoformat(),
            "is_active": u.is_active,
            "changelog": u.changelog
        }
        for u in updates
    ]

@router.post("/admin/updates/{update_id}/trigger/{device_id}")
async def trigger_device_update(
    update_id: UUID,
    device_id: UUID,
    db: Session = Depends(get_db),
    # Add user authentication dependency here
):
    """Trigger specific device to update (admin only)."""
    device = db.query(models.Device).filter_by(id=device_id).first()
    update = db.query(models.OTAUpdate).filter_by(id=update_id).first()

    if not device or not update:
        raise HTTPException(status_code=404, detail="Device or update not found")

    # Create pending update record
    update_ops.record_update_status(db, device_id, update_id, "pending")
    db.commit()

    return {"status": "triggered"}
```

**Update Schemas:** `streamscene/api/schemas.py`

```python
# Add these schemas

class UpdateCheckResponse(BaseModel):
    has_update: bool
    version: Optional[str]
    download_url: Optional[str]
    checksum: Optional[str]
    changelog: Optional[str]

class UpdateConfirmRequest(BaseModel):
    version: str
    success: bool
    error_message: Optional[str] = None
```

#### QR Code Utility

**New File:** `streamscene/utils/qr_code.py`

```python
"""QR code generation utilities."""

import qrcode
from io import BytesIO
from PIL import Image

def generate_setup_qr(device_uuid: str, base_url: str = "https://streamscene.dataandstories.com") -> Image.Image:
    """
    Generate QR code for device setup.

    Args:
        device_uuid: Device UUID
        base_url: Base URL of the web app

    Returns:
        PIL Image containing QR code
    """
    url = f"{base_url}/setup?device={device_uuid}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    return img

def generate_setup_qr_bytes(device_uuid: str, base_url: str = "https://streamscene.dataandstories.com") -> bytes:
    """Generate QR code as PNG bytes."""
    img = generate_setup_qr(device_uuid, base_url)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
```

#### File Storage Setup

```bash
# Create update storage directory
sudo mkdir -p /var/lib/streamscene/updates
sudo chown -R $USER:$USER /var/lib/streamscene/updates
sudo chmod 755 /var/lib/streamscene/updates

# Configure Nginx to serve update files (add to nginx config)
location /updates/ {
    alias /var/lib/streamscene/updates/;
    autoindex off;
}
```

---

### Phase 2: Web UI Updates (1-2 hours)

#### Setup Page

**New File:** `streamscene/pages/setup.py`

```python
"""Device setup page."""

import reflex as rx
from uuid import UUID
from ..pages.base_state import BaseState
from ..core import streams as stream_ops

class SetupState(BaseState):
    """State for device setup page."""

    device_uuid: str = ""
    device_info: dict = {}
    registration_complete: bool = False
    error_message: str = ""

    def on_load(self):
        """Load device info from query params."""
        if not self.user_id:
            return rx.redirect("/")

        # Get device UUID from query params
        self.device_uuid = self.router.page.params.get("device", "")

        if not self.device_uuid:
            self.error_message = "No device specified"
            return

        # Load device info (check if already registered)
        self.load_device_info()

    def load_device_info(self):
        """Load device information."""
        try:
            device_id = UUID(self.device_uuid)

            with get_db_session() as session:
                device = session.query(models.Device).filter_by(
                    device_uuid=device_id
                ).first()

                if device:
                    self.device_info = {
                        "id": str(device.id),
                        "uuid": str(device.device_uuid),
                        "nickname": device.nickname or "Unnamed Device",
                        "registered": device.user_id is not None,
                        "owner_id": str(device.user_id) if device.user_id else None
                    }
                else:
                    self.error_message = "Device not found"
        except Exception as e:
            self.error_message = f"Error loading device: {str(e)}"

    def register_device(self):
        """Register device to current user."""
        try:
            user_uuid = UUID(self.user_id)
            device_uuid = UUID(self.device_uuid)

            with get_db_session() as session:
                # Use existing registration logic
                api_key = stream_ops.register_device(
                    session,
                    device_uuid,
                    user_uuid,
                    nickname=self.device_info.get("nickname", "My Frame")
                )
                session.commit()

                self.registration_complete = True
                self.error_message = ""

        except Exception as e:
            self.error_message = f"Registration failed: {str(e)}"

def setup_page() -> rx.Component:
    """Device setup page."""
    return rx.container(
        rx.vstack(
            rx.heading("Setup Your StreamScene Device", size="8"),

            # Error message
            rx.cond(
                SetupState.error_message,
                rx.callout(
                    SetupState.error_message,
                    icon="triangle_alert",
                    color_scheme="red",
                ),
            ),

            # Device info
            rx.cond(
                SetupState.device_info,
                rx.card(
                    rx.vstack(
                        rx.text("Device Information", weight="bold", size="5"),
                        rx.divider(),
                        rx.hstack(
                            rx.text("Device ID:", weight="medium"),
                            rx.code(SetupState.device_info["uuid"]),
                        ),
                        rx.hstack(
                            rx.text("Nickname:", weight="medium"),
                            rx.text(SetupState.device_info["nickname"]),
                        ),
                        spacing="3",
                    ),
                ),
            ),

            # Registration complete
            rx.cond(
                SetupState.registration_complete,
                rx.callout(
                    "Device registered successfully! Your device will now check for updates and begin displaying content.",
                    icon="check",
                    color_scheme="green",
                ),
                # Registration button
                rx.cond(
                    ~SetupState.device_info.get("registered", False),
                    rx.button(
                        "Register This Device",
                        on_click=SetupState.register_device,
                        size="4",
                        color_scheme="blue",
                    ),
                    rx.callout(
                        "This device is already registered to another user.",
                        icon="info",
                        color_scheme="orange",
                    ),
                ),
            ),

            spacing="6",
            padding="6",
        ),
        max_width="600px",
        on_mount=SetupState.on_load,
    )
```

#### Device Management Page Updates

**Update or Create:** `streamscene/pages/devices.py`

Add device list view with update triggers, version display, and status indicators.

---

### Phase 3: Client-Side WiFi Hotspot & Captive Portal (3-4 hours)

#### WiFi Hotspot Setup

**New File:** `client/setup/hotspot.py`

```python
"""WiFi Access Point (hotspot) management."""

import subprocess
import os
from typing import Optional

HOSTAPD_CONF = "/etc/hostapd/hostapd.conf"
DNSMASQ_CONF = "/etc/dnsmasq.conf"

def create_hotspot(ssid: str, password: str = "streamscene") -> bool:
    """
    Create WiFi hotspot.

    Args:
        ssid: Network name (e.g., "StreamScene-A1B2")
        password: WiFi password

    Returns:
        True if successful
    """
    try:
        # Create hostapd configuration
        hostapd_config = f"""
interface=wlan0
driver=nl80211
ssid={ssid}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""

        with open(HOSTAPD_CONF, "w") as f:
            f.write(hostapd_config)

        # Create dnsmasq configuration
        dnsmasq_config = """
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
address=/#/192.168.4.1
"""

        with open(DNSMASQ_CONF, "w") as f:
            f.write(dnsmasq_config)

        # Configure static IP for wlan0
        subprocess.run([
            "sudo", "ip", "addr", "add", "192.168.4.1/24", "dev", "wlan0"
        ], check=True)

        # Start services
        subprocess.run(["sudo", "systemctl", "start", "hostapd"], check=True)
        subprocess.run(["sudo", "systemctl", "start", "dnsmasq"], check=True)

        print(f"[Hotspot] Created AP: {ssid}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"[Hotspot] Error creating hotspot: {e}")
        return False

def stop_hotspot() -> bool:
    """Stop WiFi hotspot."""
    try:
        subprocess.run(["sudo", "systemctl", "stop", "hostapd"], check=True)
        subprocess.run(["sudo", "systemctl", "stop", "dnsmasq"], check=True)

        # Remove static IP
        subprocess.run([
            "sudo", "ip", "addr", "del", "192.168.4.1/24", "dev", "wlan0"
        ], check=False)

        print("[Hotspot] Stopped AP")
        return True

    except subprocess.CalledProcessError as e:
        print(f"[Hotspot] Error stopping hotspot: {e}")
        return False

def generate_ssid(device_uuid: str) -> str:
    """Generate SSID from device UUID."""
    # Use last 4 characters of UUID
    suffix = device_uuid.replace("-", "")[-4:].upper()
    return f"StreamScene-{suffix}"
```

#### Captive Portal Web Server

**New File:** `client/setup/portal_server.py`

```python
"""Captive portal web server for WiFi setup."""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import json
import os

WIFI_CONFIG_FILE = "/home/pi/streamscene-client/wifi_credentials.json"

class PortalHandler(BaseHTTPRequestHandler):
    """Handle captive portal requests."""

    def do_GET(self):
        """Serve setup page."""
        if self.path == "/" or self.path.startswith("/setup"):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self.get_setup_page().encode())
        else:
            # Redirect all other requests to setup page (captive portal behavior)
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()

    def do_POST(self):
        """Handle WiFi credential submission."""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode()
        params = parse_qs(post_data)

        ssid = params.get('ssid', [''])[0]
        password = params.get('password', [''])[0]

        if ssid and password:
            # Save credentials
            credentials = {
                "ssid": ssid,
                "password": password
            }

            with open(WIFI_CONFIG_FILE, 'w') as f:
                json.dump(credentials, f)

            # Send success page
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self.get_success_page().encode())
        else:
            # Send error
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Error: Missing credentials</h1></body></html>")

    def get_setup_page(self) -> str:
        """HTML form for WiFi setup (NO JAVASCRIPT)."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>StreamScene WiFi Setup</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 500px;
            margin: 50px auto;
            padding: 20px;
        }
        h1 { color: #333; }
        form { margin-top: 30px; }
        label {
            display: block;
            margin-top: 15px;
            font-weight: bold;
        }
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 10px;
            margin-top: 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            margin-top: 20px;
            padding: 12px 30px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 16px;
            cursor: pointer;
        }
        button:hover {
            background: #0056b3;
        }
    </style>
</head>
<body>
    <h1>StreamScene WiFi Setup</h1>
    <p>Enter your home WiFi credentials to connect your StreamScene device to the internet.</p>

    <form method="POST" action="/">
        <label for="ssid">WiFi Network Name (SSID):</label>
        <input type="text" id="ssid" name="ssid" required>

        <label for="password">WiFi Password:</label>
        <input type="password" id="password" name="password" required>

        <button type="submit">Connect to WiFi</button>
    </form>
</body>
</html>
"""

    def get_success_page(self) -> str:
        """Success confirmation page."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>WiFi Setup Complete</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 500px;
            margin: 50px auto;
            padding: 20px;
            text-align: center;
        }
        h1 { color: #28a745; }
        p { font-size: 18px; }
    </style>
</head>
<body>
    <h1>✓ WiFi Credentials Saved</h1>
    <p>Your StreamScene device will now connect to your home WiFi network.</p>
    <p>Please disconnect from the StreamScene network and return to your normal WiFi.</p>
    <p>Your device will display a QR code for final registration in a moment.</p>
</body>
</html>
"""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

def start_portal_server(port: int = 80):
    """Start captive portal server."""
    server = HTTPServer(('0.0.0.0', port), PortalHandler)
    print(f"[Portal] Server started on port {port}")
    server.serve_forever()

def stop_portal_server():
    """Stop captive portal server."""
    # Server will be stopped when process is killed
    pass
```

#### WiFi Client Connection

**New File:** `client/setup/wifi_client.py`

```python
"""WiFi client mode connection."""

import subprocess
import json
import time
from typing import Optional, Dict

WIFI_CONFIG_FILE = "/home/pi/streamscene-client/wifi_credentials.json"

def load_credentials() -> Optional[Dict[str, str]]:
    """Load WiFi credentials from file."""
    try:
        with open(WIFI_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def connect_to_wifi(ssid: str, password: str) -> bool:
    """
    Connect to WiFi network.

    Args:
        ssid: Network name
        password: Network password

    Returns:
        True if connected successfully
    """
    try:
        # Using nmcli (NetworkManager CLI)
        subprocess.run([
            "nmcli", "dev", "wifi", "connect", ssid,
            "password", password
        ], check=True, capture_output=True, text=True)

        # Wait for connection
        time.sleep(5)

        # Verify connection
        return check_wifi_connection()

    except subprocess.CalledProcessError as e:
        print(f"[WiFi] Connection failed: {e.stderr}")
        return False

def check_wifi_connection() -> bool:
    """Check if WiFi is connected."""
    try:
        result = subprocess.run([
            "nmcli", "-t", "-f", "STATE", "general"
        ], capture_output=True, text=True, check=True)

        state = result.stdout.strip()
        return "connected" in state.lower()

    except subprocess.CalledProcessError:
        return False

def get_ip_address() -> Optional[str]:
    """Get current IP address."""
    try:
        result = subprocess.run([
            "hostname", "-I"
        ], capture_output=True, text=True, check=True)

        # Return first IP address
        ips = result.stdout.strip().split()
        return ips[0] if ips else None

    except subprocess.CalledProcessError:
        return None
```

#### Network Mode Switching

**New File:** `client/setup/network_manager.py`

```python
"""Network mode switching (AP <-> Client)."""

import time
from . import hotspot
from . import wifi_client

class NetworkMode:
    """Network mode constants."""
    AP = "ap"
    CLIENT = "client"

def switch_to_ap_mode(device_uuid: str) -> bool:
    """Switch to AP mode (hotspot)."""
    print("[Network] Switching to AP mode...")

    # Generate SSID
    ssid = hotspot.generate_ssid(device_uuid)

    # Stop any existing WiFi connections
    # (NetworkManager will handle this automatically)

    # Create hotspot
    success = hotspot.create_hotspot(ssid)

    if success:
        print(f"[Network] AP mode active: {ssid}")

    return success

def switch_to_client_mode(ssid: str, password: str) -> bool:
    """Switch to client mode (connect to WiFi)."""
    print("[Network] Switching to client mode...")

    # Stop hotspot
    hotspot.stop_hotspot()

    # Small delay for network interface to settle
    time.sleep(2)

    # Connect to WiFi
    success = wifi_client.connect_to_wifi(ssid, password)

    if success:
        ip = wifi_client.get_ip_address()
        print(f"[Network] Client mode active, IP: {ip}")

    return success
```

---

### Phase 4: Client-Side State Machine & Setup Flow (2-3 hours)

#### State Machine

**New File:** `client/states.py`

```python
"""Device state machine."""

from enum import Enum
import json
from pathlib import Path
from typing import Optional

STATE_FILE = Path("/home/pi/streamscene-client/device_state.json")

class DeviceState(Enum):
    """Device states."""
    WIFI_SETUP = "wifi_setup"
    CONNECTING = "connecting"
    AWAITING_REGISTRATION = "awaiting_registration"
    CHECKING_UPDATES = "checking_updates"
    UPDATING = "updating"
    READY = "ready"
    ERROR = "error"

class StateMachine:
    """Manage device state."""

    def __init__(self):
        self.current_state = self.load_state()
        self.error_message = ""

    def load_state(self) -> DeviceState:
        """Load state from persistent storage."""
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    return DeviceState(data.get("state", "wifi_setup"))
            else:
                # First boot
                return DeviceState.WIFI_SETUP
        except Exception as e:
            print(f"[State] Error loading state: {e}")
            return DeviceState.WIFI_SETUP

    def save_state(self):
        """Save state to persistent storage."""
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump({
                    "state": self.current_state.value,
                    "error_message": self.error_message
                }, f)
        except Exception as e:
            print(f"[State] Error saving state: {e}")

    def transition(self, new_state: DeviceState, error_message: str = ""):
        """Transition to new state."""
        print(f"[State] {self.current_state.value} -> {new_state.value}")
        self.current_state = new_state
        self.error_message = error_message
        self.save_state()

    def get_state(self) -> DeviceState:
        """Get current state."""
        return self.current_state

    def set_error(self, message: str):
        """Set error state."""
        self.transition(DeviceState.ERROR, message)
```

#### Setup Flow Manager

**New File:** `client/setup/setup_manager.py`

```python
"""Coordinate device setup flow."""

import time
from ..states import StateMachine, DeviceState
from . import network_manager
from . import wifi_client
from . import portal_server
from . import registration
from ..config import DEVICE_ID
import multiprocessing

def run_wifi_setup(state_machine: StateMachine) -> bool:
    """Run WiFi setup flow (AP mode + captive portal)."""
    print("[Setup] Starting WiFi setup...")

    # Switch to AP mode
    if not network_manager.switch_to_ap_mode(DEVICE_ID):
        state_machine.set_error("Failed to create WiFi hotspot")
        return False

    # Start captive portal server in background
    portal_process = multiprocessing.Process(
        target=portal_server.start_portal_server,
        args=(80,)
    )
    portal_process.start()

    # Wait for credentials
    print("[Setup] Waiting for WiFi credentials...")
    while True:
        credentials = wifi_client.load_credentials()
        if credentials:
            print("[Setup] Credentials received")
            break
        time.sleep(2)

    # Stop portal server
    portal_process.terminate()
    portal_process.join()

    # Transition to connecting state
    state_machine.transition(DeviceState.CONNECTING)

    # Switch to client mode
    if network_manager.switch_to_client_mode(
        credentials["ssid"],
        credentials["password"]
    ):
        print("[Setup] WiFi connected!")
        return True
    else:
        state_machine.set_error("Failed to connect to WiFi")
        return False

def run_registration_flow(state_machine: StateMachine, api_client) -> bool:
    """Run device registration flow."""
    print("[Setup] Waiting for device registration...")

    state_machine.transition(DeviceState.AWAITING_REGISTRATION)

    # Poll for registration (check every 10 seconds)
    max_attempts = 180  # 30 minutes
    for attempt in range(max_attempts):
        if registration.check_registration(api_client):
            print("[Setup] Device registered!")
            return True

        time.sleep(10)

        if attempt % 6 == 0:  # Every minute
            print(f"[Setup] Still waiting for registration... ({attempt * 10}s)")

    state_machine.set_error("Registration timeout (30 minutes)")
    return False
```

#### Registration Checker

**New File:** `client/setup/registration.py`

```python
"""Check device registration status."""

from typing import Optional

def check_registration(api_client) -> bool:
    """
    Check if device is registered.

    Returns:
        True if device is registered to a user
    """
    try:
        config = api_client.get_config()

        if config:
            # Device is registered if it has a user assigned
            # (server only returns config for registered devices)
            return True
        else:
            return False

    except Exception as e:
        print(f"[Registration] Error checking: {e}")
        return False
```

---

### Phase 5: E Ink Display for Setup States (2 hours)

**New File:** `client/setup/setup_renderer.py`

```python
"""Render setup screens for E Ink display."""

from PIL import Image, ImageDraw, ImageFont
import qrcode
from ..config import DISPLAY_WIDTH, DISPLAY_HEIGHT, COLORS

def render_wifi_setup_screen(ssid: str, password: str) -> Image.Image:
    """Render WiFi setup instructions."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), COLORS["WHITE"])
    draw = ImageDraw.Draw(img)

    # Load fonts
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        font_title = font_large = font_medium = ImageFont.load_default()

    y = 60

    # Title
    draw.text((60, y), "Welcome to StreamScene!", fill=COLORS["BLUE"], font=font_title)
    y += 100

    # Instructions
    draw.text((60, y), "Connect your phone to:", fill=COLORS["BLACK"], font=font_medium)
    y += 50

    draw.text((60, y), f"Network: {ssid}", fill=COLORS["BLACK"], font=font_large)
    y += 60

    draw.text((60, y), f"Password: {password}", fill=COLORS["BLACK"], font=font_large)
    y += 80

    draw.text((60, y), "Then open browser to:", fill=COLORS["BLACK"], font=font_medium)
    y += 50

    draw.text((60, y), "http://192.168.4.1", fill=COLORS["BLUE"], font=font_large)

    return img

def render_registration_screen(device_uuid: str, base_url: str) -> Image.Image:
    """Render QR code for registration."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), COLORS["WHITE"])
    draw = ImageDraw.Draw(img)

    # Generate QR code
    qr_url = f"{base_url}/setup?device={device_uuid}"
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    # Resize QR code
    qr_size = 300
    qr_img = qr_img.resize((qr_size, qr_size))

    # Paste QR code
    qr_x = (DISPLAY_WIDTH - qr_size) // 2
    qr_y = 100
    img.paste(qr_img, (qr_x, qr_y))

    # Instructions
    try:
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        font_medium = ImageFont.load_default()

    text = "Scan to complete setup"
    bbox = draw.textbbox((0, 0), text, font=font_medium)
    text_width = bbox[2] - bbox[0]

    draw.text(
        ((DISPLAY_WIDTH - text_width) // 2, qr_y + qr_size + 40),
        text,
        fill=COLORS["BLACK"],
        font=font_medium
    )

    return img

def render_status_screen(message: str, color_name: str = "BLACK") -> Image.Image:
    """Render simple status message."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), COLORS["WHITE"])
    draw = ImageDraw.Draw(img)

    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
    except:
        font_large = ImageFont.load_default()

    # Center text
    bbox = draw.textbbox((0, 0), message, font=font_large)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (DISPLAY_WIDTH - text_width) // 2
    y = (DISPLAY_HEIGHT - text_height) // 2

    draw.text((x, y), message, fill=COLORS[color_name], font=font_large)

    return img
```

---

### Phase 6: OTA Update Client (2-3 hours)

**New File:** `client/updater/update_client.py`

```python
"""OTA update client."""

import requests
import hashlib
import tarfile
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict

UPDATE_DIR = Path("/home/pi/streamscene-client/updates")
BACKUP_DIR = Path("/home/pi/streamscene-client/backup")

def check_for_updates(api_client) -> Optional[Dict]:
    """Check if update is available."""
    try:
        update_info = api_client.fetch_update_check()

        if update_info and update_info.get("has_update"):
            print(f"[Update] Update available: {update_info['version']}")
            return update_info
        else:
            print("[Update] No updates available")
            return None

    except Exception as e:
        print(f"[Update] Error checking for updates: {e}")
        return None

def download_update(download_url: str, expected_checksum: str) -> Optional[Path]:
    """Download update package and verify checksum."""
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)

    filename = download_url.split("/")[-1]
    filepath = UPDATE_DIR / filename

    try:
        print(f"[Update] Downloading {filename}...")

        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Verify checksum
        actual_checksum = calculate_checksum(filepath)

        if actual_checksum != expected_checksum:
            print(f"[Update] Checksum mismatch!")
            print(f"  Expected: {expected_checksum}")
            print(f"  Actual: {actual_checksum}")
            filepath.unlink()
            return None

        print(f"[Update] Download verified")
        return filepath

    except Exception as e:
        print(f"[Update] Download failed: {e}")
        return None

def calculate_checksum(filepath: Path) -> str:
    """Calculate SHA256 checksum."""
    sha256_hash = hashlib.sha256()

    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()

def install_update(package_path: Path) -> bool:
    """Install update package."""
    try:
        print("[Update] Installing update...")

        # Create backup
        client_dir = Path("/home/pi/streamscene-client")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        print("[Update] Creating backup...")
        if BACKUP_DIR.exists():
            shutil.rmtree(BACKUP_DIR)
        shutil.copytree(client_dir, BACKUP_DIR, dirs_exist_ok=True)

        # Extract update
        extract_dir = UPDATE_DIR / "extracted"
        extract_dir.mkdir(exist_ok=True)

        print("[Update] Extracting package...")
        with tarfile.open(package_path, "r:gz") as tar:
            tar.extractall(extract_dir)

        # Run install script
        install_script = extract_dir / "install.sh"

        if install_script.exists():
            print("[Update] Running install script...")
            result = subprocess.run(
                ["bash", str(install_script)],
                cwd=extract_dir,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(f"[Update] Install script failed: {result.stderr}")
                return False

        print("[Update] Installation complete")
        return True

    except Exception as e:
        print(f"[Update] Installation failed: {e}")
        return False

def rollback_update():
    """Rollback to previous version."""
    try:
        print("[Update] Rolling back to previous version...")

        client_dir = Path("/home/pi/streamscene-client")

        if BACKUP_DIR.exists():
            # Remove current version
            shutil.rmtree(client_dir)

            # Restore backup
            shutil.copytree(BACKUP_DIR, client_dir)

            print("[Update] Rollback complete")
            return True
        else:
            print("[Update] No backup found for rollback")
            return False

    except Exception as e:
        print(f"[Update] Rollback failed: {e}")
        return False

def report_update_status(api_client, version: str, success: bool, error: Optional[str] = None):
    """Report update status to server."""
    try:
        response = api_client.session.post(
            f"{api_client.base_url}/api/devices/{api_client.device_id}/updates/confirm",
            json={
                "version": version,
                "success": success,
                "error_message": error
            }
        )
        response.raise_for_status()
        print(f"[Update] Status reported: {'success' if success else 'failed'}")

    except Exception as e:
        print(f"[Update] Failed to report status: {e}")
```

**Update API Client:** Add to `client/api_client.py`

```python
def fetch_update_check(self) -> Optional[Dict[str, Any]]:
    """Check for available updates."""
    url = f"{self.base_url}/api/devices/{self.device_id}/updates/check"

    try:
        response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[API Client] Error checking updates: {e}")
        return None
```

---

### Phase 7: Main Loop Integration (1-2 hours)

**Update:** `client/main.py`

```python
"""StreamScene E Ink Client - Main Loop with State Machine."""

import sys
import time
import signal
from pathlib import Path

from .config import validate_config, POLL_INTERVAL, HEARTBEAT_INTERVAL, DEVICE_ID, API_BASE_URL
from .api_client import StreamSceneAPIClient
from .display import get_display
from .renderer import ContentRenderer
from .states import StateMachine, DeviceState
from .setup import setup_manager, setup_renderer, network_manager
from .updater import update_client

class StreamSceneClient:
    """Main client application with state machine."""

    def __init__(self):
        print("=" * 60)
        print("StreamScene E Ink Client v1.0.0")
        print("=" * 60)

        # Validate configuration
        try:
            validate_config()
            print("✓ Configuration validated")
        except ValueError as e:
            print(f"✗ Configuration error: {e}")
            sys.exit(1)

        # Initialize components
        print("\n[Client] Initializing components...")

        self.state_machine = StateMachine()
        self.api_client = StreamSceneAPIClient()
        self.renderer = ContentRenderer()
        self.display = get_display()

        self.running = False
        self.last_heartbeat = 0

        print("[Client] Initialization complete\n")

    def run(self):
        """Run the main client loop with state machine."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        print(f"[Client] Starting in state: {self.state_machine.get_state().value}")
        self.running = True

        while self.running:
            try:
                current_state = self.state_machine.get_state()

                if current_state == DeviceState.WIFI_SETUP:
                    self.handle_wifi_setup()

                elif current_state == DeviceState.CONNECTING:
                    self.handle_connecting()

                elif current_state == DeviceState.AWAITING_REGISTRATION:
                    self.handle_registration()

                elif current_state == DeviceState.CHECKING_UPDATES:
                    self.handle_update_check()

                elif current_state == DeviceState.UPDATING:
                    self.handle_updating()

                elif current_state == DeviceState.READY:
                    self.handle_ready()

                elif current_state == DeviceState.ERROR:
                    self.handle_error()

            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[Client] Error in main loop: {e}")
                self.state_machine.set_error(str(e))
                time.sleep(30)

        print("\n[Client] Shutting down...")
        self._cleanup()

    def handle_wifi_setup(self):
        """Handle WiFi setup state."""
        # Show WiFi setup screen
        ssid = network_manager.hotspot.generate_ssid(DEVICE_ID)
        img = setup_renderer.render_wifi_setup_screen(ssid, "streamscene")
        self.display.show(img)

        # Run WiFi setup flow
        if setup_manager.run_wifi_setup(self.state_machine):
            self.state_machine.transition(DeviceState.AWAITING_REGISTRATION)

    def handle_connecting(self):
        """Handle connecting state."""
        img = setup_renderer.render_status_screen("Connecting to WiFi...")
        self.display.show(img)

        # Already connected by setup manager
        self.state_machine.transition(DeviceState.AWAITING_REGISTRATION)

    def handle_registration(self):
        """Handle registration state."""
        # Show QR code
        img = setup_renderer.render_registration_screen(DEVICE_ID, API_BASE_URL)
        self.display.show(img)

        # Wait for registration
        if setup_manager.run_registration_flow(self.state_machine, self.api_client):
            self.state_machine.transition(DeviceState.CHECKING_UPDATES)

    def handle_update_check(self):
        """Handle update check state."""
        img = setup_renderer.render_status_screen("Checking for updates...")
        self.display.show(img)

        update_info = update_client.check_for_updates(self.api_client)

        if update_info:
            self.state_machine.transition(DeviceState.UPDATING)
        else:
            self.state_machine.transition(DeviceState.READY)

    def handle_updating(self):
        """Handle updating state."""
        img = setup_renderer.render_status_screen(
            "Updating...\nDO NOT UNPLUG",
            "RED"
        )
        self.display.show(img)

        update_info = update_client.check_for_updates(self.api_client)

        if not update_info:
            self.state_machine.transition(DeviceState.READY)
            return

        # Download update
        package_path = update_client.download_update(
            update_info["download_url"],
            update_info["checksum"]
        )

        if not package_path:
            update_client.report_update_status(
                self.api_client,
                update_info["version"],
                False,
                "Download failed"
            )
            self.state_machine.set_error("Update download failed")
            return

        # Install update
        if update_client.install_update(package_path):
            update_client.report_update_status(
                self.api_client,
                update_info["version"],
                True
            )

            # Reboot
            print("[Client] Update installed, rebooting...")
            import subprocess
            subprocess.run(["sudo", "reboot"])
        else:
            update_client.report_update_status(
                self.api_client,
                update_info["version"],
                False,
                "Installation failed"
            )
            self.state_machine.set_error("Update installation failed")

    def handle_ready(self):
        """Handle ready state (normal operation)."""
        # Fetch and display content (existing logic)
        content = self.api_client.fetch_content()

        if content:
            image = self.renderer.render_content(content)
            self.display.show(image)

        # Send heartbeat if needed
        if time.time() - self.last_heartbeat >= HEARTBEAT_INTERVAL:
            if self.api_client.send_heartbeat():
                self.last_heartbeat = time.time()

        # Sleep
        time.sleep(POLL_INTERVAL)

    def handle_error(self):
        """Handle error state."""
        error_msg = self.state_machine.error_message or "Unknown error"
        img = self.renderer.render_error(error_msg)
        self.display.show(img)

        # Wait and retry
        time.sleep(60)

        # Reset to WiFi setup
        self.state_machine.transition(DeviceState.WIFI_SETUP)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n[Client] Received signal {signum}, shutting down...")
        self.running = False

    def _cleanup(self):
        """Clean up resources."""
        print("[Client] Cleaning up...")
        try:
            self.display.sleep()
        except Exception as e:
            print(f"[Client] Error during cleanup: {e}")
        print("[Client] Goodbye!")

def main():
    """Entry point."""
    client = StreamSceneClient()
    client.run()

if __name__ == "__main__":
    main()
```

---

### Phase 8: SD Card Image & Build Process (2 hours)

**New File:** `tools/create-base-image.sh`

```bash
#!/bin/bash
# Create base SD card image for StreamScene devices

set -e

echo "=== StreamScene Base Image Creator ==="

# Install system dependencies
echo "Installing system packages..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-pil \
    python3-numpy \
    hostapd \
    dnsmasq \
    network-manager \
    git

# Create streamscene-client directory
echo "Setting up client directory..."
mkdir -p /home/pi/streamscene-client
cd /home/pi/streamscene-client

# Copy client code (assume running from repo)
# Or clone from git:
# git clone https://github.com/yourusername/streamscene.git
# cp -r streamscene/client/* /home/pi/streamscene-client/

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/streamscene-client.service > /dev/null <<EOF
[Unit]
Description=StreamScene E Ink Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/streamscene-client
Environment="PATH=/home/pi/streamscene-client/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/pi/streamscene-client/venv/bin/python -m client.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable service
sudo systemctl daemon-reload
sudo systemctl enable streamscene-client

echo "✓ Base image setup complete"
echo ""
echo "Next steps:"
echo "1. Run provision-device.sh to add device UUID"
echo "2. Test the setup"
echo "3. Clone SD card for additional devices"
```

**New File:** `tools/provision-device.sh`

```bash
#!/bin/bash
# Provision individual device with unique UUID

set -e

echo "=== StreamScene Device Provisioning ==="

# Generate UUID
DEVICE_UUID=$(uuidgen)

echo "Generated UUID: $DEVICE_UUID"

# Write to boot partition
echo "$DEVICE_UUID" > /boot/streamscene-device.txt

echo "✓ Device UUID written to /boot/streamscene-device.txt"

# Generate QR code for reference (requires qrencode)
if command -v qrencode &> /dev/null; then
    echo "Generating QR code sticker..."
    qrencode -o "device-$DEVICE_UUID.png" \
        "https://streamscene.dataandstories.com/setup?device=$DEVICE_UUID"
    echo "✓ QR code saved as device-$DEVICE_UUID.png"
    echo "  Print this and stick on device"
fi

echo ""
echo "Device provisioning complete!"
echo "UUID: $DEVICE_UUID"
echo ""
echo "Next steps:"
echo "1. Boot device"
echo "2. Connect to WiFi hotspot shown on screen"
echo "3. Configure home WiFi at 192.168.4.1"
echo "4. Scan QR code to register device"
```

---

### Phase 9: Testing & Documentation (1-2 hours)

#### Testing Checklist

**Server-Side Testing:**
- [ ] Database migrations run successfully
- [ ] API endpoints respond correctly (test with curl)
- [ ] Web UI pages load and render
- [ ] QR code generation works
- [ ] Update package upload works

**Client-Side Testing (Headless Mode):**
- [ ] State machine transitions work
- [ ] WiFi credentials save/load correctly
- [ ] QR code renders to PNG
- [ ] Update download and verification works
- [ ] State persists across restarts

**WiFi Hotspot Testing:**
- [ ] Pi creates hotspot successfully
- [ ] SSID is correct format
- [ ] Can connect from phone
- [ ] Captive portal loads
- [ ] Form submission works
- [ ] Switches to client mode correctly

**E Ink Integration Testing:**
- [ ] Display driver initializes
- [ ] Setup screens render correctly
- [ ] QR code is scannable
- [ ] State transitions show correct screens
- [ ] Update screens display properly

**End-to-End Testing:**
- [ ] Full setup flow from boot to ready
- [ ] Registration via QR code
- [ ] Update download and installation
- [ ] Reboot after update
- [ ] Resume normal operation

#### User Documentation

Create simple setup guide for recipients:

**File:** `docs/USER_SETUP_GUIDE.md`

---

## Technology Stack

**Server-Side:**
- Python/Reflex (existing web app)
- FastAPI (existing device API)
- PostgreSQL (existing database)
- Nginx (static file serving for updates)

**Client-Side (Raspberry Pi):**
- Python 3.11+ (no JavaScript)
- `hostapd` - WiFi access point
- `dnsmasq` - DHCP + DNS for captive portal
- `NetworkManager` - WiFi client
- `http.server` - Captive portal web server (pure Python)
- PIL, qrcode - QR code generation
- Waveshare EPD library - E Ink display

---

## File Changes Summary

### New Files Created (25 files):

**Server-Side:**
1. `streamscene/core/updates.py` - OTA business logic
2. `streamscene/api/routes/updates.py` - Update API endpoints
3. `streamscene/utils/qr_code.py` - QR generation
4. `streamscene/pages/setup.py` - Device setup page
5. `streamscene/pages/devices.py` - Device management
6. `alembic/versions/XXXX_add_ota_updates.py` - Migration

**Client-Side:**
7. `client/states.py` - State machine
8. `client/setup/hotspot.py` - WiFi AP mode
9. `client/setup/portal_server.py` - Captive portal server
10. `client/setup/wifi_client.py` - WiFi client connection
11. `client/setup/network_manager.py` - Network mode switching
12. `client/setup/setup_manager.py` - Setup flow coordination
13. `client/setup/registration.py` - Registration polling
14. `client/setup/setup_renderer.py` - Setup screen rendering
15. `client/updater/update_client.py` - OTA update client

**Tools:**
16. `tools/create-base-image.sh` - SD card image builder
17. `tools/provision-device.sh` - Device provisioning script

**Documentation:**
18. `docs/USER_SETUP_GUIDE.md` - User-facing setup instructions
19. `docs/DEPLOYMENT_GUIDE.md` - Admin deployment guide
20. `docs/UPDATE_CREATION_GUIDE.md` - How to create updates

### Modified Files (4 files):

1. `streamscene/core/models.py` - Add OTAUpdate, DeviceUpdate models, update Device model
2. `streamscene/api/schemas.py` - Add update-related schemas
3. `client/main.py` - Integrate state machine and setup flows
4. `client/api_client.py` - Add update check method

---

## Estimated Timeline

**Total: 16-20 hours of development work**

### Breakdown by Phase:

1. **Phase 1** (Server Infrastructure): 2-3 hours
2. **Phase 2** (Web UI): 1-2 hours
3. **Phase 3** (WiFi Hotspot): 3-4 hours
4. **Phase 4** (State Machine): 2-3 hours
5. **Phase 5** (E Ink Setup Screens): 2 hours
6. **Phase 6** (OTA Updates): 2-3 hours
7. **Phase 7** (Main Loop): 1-2 hours
8. **Phase 8** (SD Card Tools): 2 hours
9. **Phase 9** (Testing): 1-2 hours

### Realistic Schedule:

**Day 1** (6-8 hours):
- Phases 1-2: Server-side complete
- Begin Phase 3: WiFi hotspot work

**Day 2** (6-8 hours):
- Complete Phase 3: WiFi hotspot
- Phases 4-5: State machine + E Ink screens

**Day 3** (4-6 hours):
- Phases 6-7: OTA updates + main loop integration
- Phase 8: SD card tools
- Phase 9: Testing and polish

---

## Update Package Structure

```
update-v1.1.0.tar.gz:
  ├── manifest.json
  │     {
  │       "version": "1.1.0",
  │       "min_version": "1.0.0",
  │       "checksum": "sha256...",
  │       "release_date": "2025-11-10",
  │       "changelog": "Bug fixes and improvements"
  │     }
  ├── client/
  │     ├── main.py
  │     ├── config.py
  │     ├── ... (all updated Python files)
  ├── requirements.txt
  └── install.sh
        #!/bin/bash
        # Stop client service
        sudo systemctl stop streamscene-client

        # Backup handled by update_client.py

        # Install dependencies
        pip install -r requirements.txt

        # Copy new files
        cp -r client/* /home/pi/streamscene-client/

        # Restart service
        sudo systemctl start streamscene-client
```

---

## Next Steps

1. **Review and approve this plan**
2. **Create feature branch:** `git checkout -b feature/device-setup-ota`
3. **Implement phases sequentially** (Server → Client → Testing)
4. **Test on real Raspberry Pi hardware** after Phase 3
5. **Build prototype device** after Phase 7
6. **Refine based on testing**
7. **Build additional devices** after validation
8. **Document and ship**

---

**Last Updated:** November 9, 2025
