# StreamScene Architecture Decisions
**Date:** November 1, 2024
**Status:** Planning Phase

This document captures all architectural and technical decisions made for the StreamScene project.

---

## 🎯 Project Overview

StreamScene is a family message board system using E Ink displays on Raspberry Pi devices, allowing remote posting of messages and images through shared "Streams."

---

## 🖥️ Web Application Architecture

### **Framework Decision**
- **Choice:** Pure Reflex (Python full-stack framework)
- **Rationale:**
  - Single language (Python) throughout stack
  - Faster development for Python developers
  - Simpler deployment
  - Built-in WebSocket support
- **Risk Mitigation:**
  - Structure code defensively (separate business logic from UI)
  - Keep option to swap to FastAPI if Reflex limitations encountered
  - Test device API capabilities early (Week 1)

### **Code Structure**
```
streamscene/
├── core/              # Pure Python - framework-agnostic
│   ├── models.py      # SQLAlchemy models
│   ├── auth.py        # Authentication logic
│   ├── streams.py     # Stream business logic
│   └── devices.py     # Device business logic
├── api/               # API layer (Reflex-exposed endpoints)
│   ├── device_api.py  # Device endpoints
│   └── schemas.py     # Pydantic models
└── ui/                # Reflex UI components
    ├── pages/
    └── components/
```

### **Database**
- **Primary:** PostgreSQL
- **Rationale:** Performance, reliability, concurrent users
- **Connection Pooling:** SQLAlchemy pool (size: 20, overflow: 10)

### **Caching & Message Broker**
- **Technology:** Redis
- **Uses:**
  - WebSocket connection management
  - Session caching
  - Background task queue (Celery broker)
  - API response caching

### **Background Tasks**
- **Technology:** Celery + Redis
- **Uses:**
  - Image processing pipeline
  - Device notification delivery
  - Cleanup jobs
  - OTA update distribution

---

## 📱 Device-to-Server Communication

### **Primary Method: WebSockets**
- **Choice:** WebSocket connections for real-time updates
- **Fallback:** Polling if WebSocket proves problematic
- **Implementation:**
  - Persistent connection per device
  - Automatic reconnection with exponential backoff
  - Heartbeat every 30 seconds
  - Server-initiated content push
- **Rationale:**
  - Instant updates when stream posts created
  - Better UX for family members
- **Monitoring:** Track connection success rate, revert to polling if <90% stability

### **Polling Fallback Strategy**
If WebSockets prove unreliable:
- Device polls every 60 seconds: `GET /api/devices/{id}/content`
- Server returns latest content + ETag
- Acceptable latency for E Ink displays (30s refresh time)

### **Device Authentication**
- **Method:** API key authentication
- **Flow:**
  1. Device pre-configured with UUID
  2. User registers device via QR scan
  3. Server generates API key
  4. Device receives key via first connection
  5. All subsequent requests include API key header
- **Security:**
  - API keys stored hashed in database
  - Rotation every 90 days
  - Rate limiting: 10 requests/minute per device

---

## 🔧 StreamScene Frame (Device) Architecture

### **Operating System**
- **Choice:** Raspberry Pi OS Lite (Debian-based)
- **Version:** Latest stable (currently Bookworm)
- **Rationale:**
  - Official support
  - Stable drivers
  - Familiar ecosystem
  - Good balance of features vs size

### **Device Provisioning**
- **Method:** Pre-configured SD cards with unique UUIDs
- **Process:**
  1. Flash base "golden image" to SD card
  2. Mount `/boot` partition on laptop
  3. Edit `/boot/streamscene-device.txt` with unique UUID
  4. Generate QR code sticker with UUID
  5. Test boot device at homelab
  6. Shutdown, ship with QR code

### **WiFi Configuration Method**
- **Choice:** Bluetooth Low Energy (BLE) setup
- **Rationale:**
  - Pi Zero 2 WH has built-in Bluetooth
  - No WiFi mode switching complexity
  - Similar UX to smart home devices
  - More reliable than hotspot approach
- **Implementation:**
  - Device advertises BLE service on first boot
  - User connects via phone browser (Web Bluetooth API)
  - WiFi credentials sent over BLE
  - Device stores config and connects to WiFi

### **User Setup Flow**
```
1. User receives device with QR code sticker
2. Plug device into power
3. E Ink displays "Setup Needed - Visit setup.dataandstories.com"
4. User visits setup URL on phone
5. Login to StreamScene account
6. Click "Setup New Device"
7. Browser prompts for Bluetooth permission
8. Select "StreamScene-XXXX" from BLE devices
9. Enter home WiFi credentials
10. Credentials sent via Bluetooth
11. Device connects to WiFi
12. Scan QR code to link device to account
13. Device registered, begins showing content
```

### **Device Software Stack**

#### **Core Components**
```python
streamscene-client/
├── display/
│   ├── waveshare_driver.py      # E Ink control (SPI)
│   ├── renderer.py              # Text/image layout
│   └── transitions.py           # Slide/fade effects
├── network/
│   ├── websocket_client.py      # WebSocket connection
│   ├── api_client.py            # REST API calls
│   └── heartbeat.py             # Keep-alive monitoring
├── setup/
│   ├── ble_server.py            # Bluetooth setup service
│   └── wifi_config.py           # WiFi credential management
├── storage/
│   ├── cache.py                 # Local content caching
│   └── cleanup.py               # Disk space management
├── updater/
│   ├── ota_client.py            # Over-the-air updates
│   └── version.py               # Version tracking
├── main.py                      # Main event loop
├── config.yaml                  # Device configuration
└── requirements.txt
```

#### **Main Loop Logic**
```python
while True:
    # 1. WiFi check
    if not wifi_connected():
        show_setup_screen()
        start_ble_service()
        wait_for_wifi_config()
        continue

    # 2. Registration check
    if not has_api_key():
        show_registration_qr()
        wait_for_registration()
        continue

    # 3. Check for updates
    if update_available():
        download_and_install_update()
        reboot()

    # 4. Connect WebSocket
    ws = connect_websocket()

    # 5. Listen for messages
    for message in ws:
        if message.type == "new_content":
            render_to_display(message.content)
        elif message.type == "config_update":
            update_config(message.config)

    # 6. Handle disconnection
    show_offline_message()
    time.sleep(30)  # Wait before reconnect
```

### **Python Dependencies (Device)**
```
websocket-client>=1.6.0
requests>=2.31.0
pillow>=10.0.0
numpy>=1.24.0
RPi.GPIO>=0.7.1
spidev>=3.6
pybluez>=0.23  # or bleak for BLE
python-wifi>=0.3.0
netifaces>=0.11.0
waveshare-epd  # from GitHub
```

---

## 🔄 Over-The-Air (OTA) Update System

### **Update Distribution**
- **Method:** Server-initiated push via WebSocket
- **Flow:**
  1. New version deployed to server
  2. Server detects devices with old version
  3. Sends update notification via WebSocket
  4. Device downloads update package from server
  5. Verifies signature/checksum
  6. Applies update and restarts

### **Update Package Structure**
```
update-v1.2.3.tar.gz
├── manifest.json          # Version, checksum, changelog
├── client/                # Updated Python code
│   └── ...
├── requirements.txt       # Dependency changes
└── install.sh             # Update script
```

### **Safety Mechanisms**
- **Rollback:** Keep previous version, rollback on failure
- **Staged rollout:** Update 10% of devices first
- **Manual override:** Admin can pause/resume updates
- **Health check:** Device phones home after update

### **Update API Endpoints**
```
GET  /api/updates/check?current_version=1.0.0&device_id=xxx
POST /api/updates/download
POST /api/updates/confirm  # Device confirms successful update
POST /api/updates/rollback # Device reports failure
```

---

## 🎨 E Ink Display Strategy

### **Hardware**
- **Model:** Waveshare 7.3inch 6-Color E-Paper (E Type)
- **Resolution:** 800x480 pixels
- **Colors:** Black, White, Red, Yellow, Blue, Green
- **Refresh Time:** ~30 seconds for full refresh

### **Update Frequency**
- **Minimum rotation interval:** 60 seconds
- **Rationale:** Display needs 30s to refresh, add buffer for processing
- **Configurable:** Users can set rotation speed (60s - 10min)

### **Content Rendering**
- **Text posts:** Rendered on device (faster, less bandwidth)
- **Image posts:** Pre-processed on server, cached locally
- **Transitions:** Slide effect (preferred), fade fallback

### **Display States**
```
1. Normal: Showing stream content
2. Setup: "Visit setup.dataandstories.com"
3. Offline: "Connecting..." + last known content
4. Error: "Error occurred - Contact support"
5. Update: "Updating software... Do not unplug"
```

---

## 🔐 Authentication & Authorization

### **Web Users**
- **Provider:** Authentik (OAuth2/OIDC)
- **Location:** LXC 108 (192.168.1.108:9000)
- **Flow:**
  1. User clicks login on Reflex app
  2. Redirect to Authentik
  3. Authentik authenticates user
  4. Returns OAuth token to Reflex app
  5. Reflex creates session

### **User Data Strategy**
- **Single source of truth:** Authentik
- **Local storage:** User ID only (reference to Authentik)
- **No sync needed:** Query Authentik API for user details
- **Fallback:** Cache user data in Redis (15min TTL)

### **Device Authentication**
- **Method:** API key (not OAuth)
- **Generation:** On device registration
- **Storage:** Hashed in database
- **Transmission:** HTTP header: `X-Device-API-Key`

---

## 🗄️ Database Schema

### **Users** (Minimal - Authentik is source)
```sql
users
  - id (UUID, primary)
  - authentik_user_id (unique)
  - created_at
  - updated_at
```

### **Devices**
```sql
devices
  - id (UUID, primary)
  - device_uuid (unique, pre-configured)
  - user_id (foreign key)
  - nickname (string)
  - api_key_hash (string)
  - current_version (string)
  - last_seen (timestamp)
  - current_stream_id (foreign key, nullable)
  - rotation_enabled (boolean)
  - rotation_interval (integer, seconds)
  - registered_at (timestamp)
  - config (jsonb)
```

### **Streams**
```sql
streams
  - id (UUID, primary)
  - owner_id (foreign key to users)
  - name (string)
  - description (text)
  - is_public (boolean)
  - allow_text (boolean)
  - allow_images (boolean)
  - show_history (boolean)
  - max_history_items (integer)
  - created_at (timestamp)
  - updated_at (timestamp)
```

### **Stream Subscriptions**
```sql
stream_subscriptions
  - id (UUID, primary)
  - user_id (foreign key)
  - stream_id (foreign key)
  - is_approved (boolean)
  - subscribed_at (timestamp)
  - unique(user_id, stream_id)
```

### **Posts**
```sql
posts
  - id (UUID, primary)
  - stream_id (foreign key)
  - author_id (foreign key to users)
  - content_type (enum: text, image, mixed)
  - text_content (text)
  - image_path (string, nullable)
  - processed_image_path (string, nullable)
  - created_at (timestamp)
  - updated_at (timestamp)
```

### **Device Stream Settings**
```sql
device_stream_settings
  - id (UUID, primary)
  - device_id (foreign key)
  - stream_id (foreign key)
  - display_order (integer)
  - is_active (boolean)
```

### **Image Processing Jobs** (New)
```sql
image_processing_jobs
  - id (UUID, primary)
  - post_id (foreign key)
  - status (enum: pending, processing, complete, failed)
  - error_message (text, nullable)
  - created_at (timestamp)
  - completed_at (timestamp, nullable)
```

### **Device Logs** (New)
```sql
device_logs
  - id (UUID, primary)
  - device_id (foreign key)
  - event_type (string)
  - message (text)
  - metadata (jsonb)
  - created_at (timestamp)
```

### **OTA Updates** (New)
```sql
ota_updates
  - id (UUID, primary)
  - version (string, unique)
  - release_date (timestamp)
  - package_url (string)
  - package_checksum (string)
  - changelog (text)
  - is_active (boolean)
  - min_version (string)  # Minimum version that can update
  - rollout_percentage (integer)  # Staged rollout
```

### **Device Updates** (New)
```sql
device_updates
  - id (UUID, primary)
  - device_id (foreign key)
  - update_id (foreign key to ota_updates)
  - status (enum: pending, downloading, installing, complete, failed, rolled_back)
  - started_at (timestamp)
  - completed_at (timestamp, nullable)
  - error_message (text, nullable)
```

### **Performance Indexes**
```sql
CREATE INDEX idx_posts_stream_created ON posts(stream_id, created_at DESC);
CREATE INDEX idx_devices_user ON devices(user_id);
CREATE INDEX idx_stream_subs ON stream_subscriptions(user_id, stream_id);
CREATE INDEX idx_device_logs_device_time ON device_logs(device_id, created_at DESC);
CREATE INDEX idx_posts_author ON posts(author_id, created_at DESC);
```

---

## 🌐 Network & Infrastructure

### **Domain**
- **Primary:** dataandstories.com
- **Subdomains:**
  - `streamscene.dataandstories.com` - Main web app
  - `setup.dataandstories.com` - Device setup portal
  - `api.dataandstories.com` - Device API (optional, can be same as main)

### **Reverse Proxy**
- **Technology:** Nginx Proxy Manager
- **Location:** LXC 104 (192.168.1.104:81)
- **SSL:** Let's Encrypt certificates
- **Configuration:**
  - HTTP → HTTPS redirect
  - WebSocket support enabled
  - Rate limiting configured

### **LXC Container Specifications**
```
Hostname: streamscene
IP: 192.168.1.XXX (TBD)
Resources:
  - CPU: 4 cores
  - RAM: 4GB
  - Storage: 50GB
OS: Debian 12 (Bookworm)
```

### **Network Topology**
- **Phase 1:** Local network only (192.168.1.x)
- **Phase 2:** External access via domain (for remote devices)
- **Device Access:**
  - Local devices: Direct to LXC IP
  - Remote devices: Via public domain + VPN (optional)

---

## 🚀 Development Phases

### **Phase 0: Environment Setup** (Week 1)
```
✅ Create LXC container
✅ Install system dependencies
✅ Setup PostgreSQL database
✅ Setup Redis
✅ Configure Nginx Proxy Manager
✅ Setup SSL certificates
✅ Initialize Git repository
✅ Setup development environment
```

### **Phase 1: Backend Core** (Weeks 1-2)
```
✅ SQLAlchemy models
✅ Database migrations (Alembic)
✅ Authentik integration
✅ Core business logic (streams, posts)
✅ Device registration API
✅ WebSocket server setup
✅ Basic API endpoints
```

### **Phase 2: Web UI** (Weeks 2-3)
```
✅ Reflex app structure
✅ Authentication flow
✅ Dashboard page
✅ Stream management (create, view, edit)
✅ Text post creation
✅ Stream subscription system
✅ Device management page
✅ Responsive design (mobile + desktop)
```

### **Phase 3: Device Client** (Weeks 3-4)
```
✅ Bluetooth setup service
✅ WiFi configuration
✅ WebSocket client
✅ E Ink display driver integration
✅ Content rendering engine
✅ Local caching
✅ Automatic reconnection
✅ Systemd service setup
```

### **Phase 4: OTA Updates** (Week 5)
```
✅ Update package creation
✅ Update distribution API
✅ Device update client
✅ Rollback mechanism
✅ Admin update dashboard
```

### **Phase 5: Image Support** (Weeks 5-6)
```
✅ Image upload handling
✅ 6-color palette reduction
✅ Image processing pipeline (Celery)
✅ Processed image caching
✅ Device image rendering
```

### **Phase 6: Polish & Testing** (Week 7+)
```
✅ Comprehensive testing
✅ Performance optimization
✅ Security hardening
✅ Documentation
✅ Build first production device
✅ 2-week field test
```

---

## 📊 MVP Scope (First Release)

### **Included Features**
- ✅ User registration/login (Authentik)
- ✅ Create and manage Streams
- ✅ Post text messages
- ✅ Subscribe to streams
- ✅ Device registration via QR code
- ✅ Bluetooth WiFi setup
- ✅ WebSocket real-time updates
- ✅ Basic device management
- ✅ OTA update system
- ✅ Responsive web UI

### **Deferred to v2**
- ❌ Image uploads/display
- ❌ Stream discovery page
- ❌ User profiles
- ❌ Stream analytics
- ❌ Advanced moderation tools
- ❌ Multi-image slideshows
- ❌ Weather widget

---

## 🔒 Security Considerations

### **API Security**
- Rate limiting: 100 req/min per user, 10 req/min per device
- Input validation on all endpoints
- SQL injection prevention (SQLAlchemy ORM)
- CORS properly configured

### **Device Security**
- API keys hashed (bcrypt)
- TLS/SSL required for all connections
- Device decommission flow (revoke API key)
- Bluetooth pairing security

### **Data Privacy**
- Minimal data collection
- User data export capability (GDPR)
- Account deletion cascade
- Image retention policy: 1 year

### **WebSocket Security**
- Authentication on connection
- Message validation
- Rate limiting per connection
- Automatic timeout for idle connections

---

## 🧪 Testing Strategy

### **Backend Testing**
```
- Unit tests: Models, business logic (pytest)
- Integration tests: API endpoints
- WebSocket tests: Connection handling
- Database tests: Migrations, constraints
- Load tests: 50+ concurrent devices
```

### **Frontend Testing**
```
- Component tests: Reflex components
- E2E tests: User flows (Playwright)
- Responsive design tests: Mobile/desktop
```

### **Device Testing**
```
- Mock E Ink display for CI/CD
- Bluetooth setup flow
- WebSocket reconnection
- OTA update process
- Offline mode behavior
```

---

## 📝 Configuration Management

### **Environment Variables (.env)**
```bash
# Database
DATABASE_URL=postgresql://streamscene:password@localhost/streamscene

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
API_KEY_SALT=your-salt-here

# Authentik
AUTHENTIK_URL=http://192.168.1.108:9000
AUTHENTIK_CLIENT_ID=streamscene
AUTHENTIK_CLIENT_SECRET=your-client-secret

# Application
DOMAIN=streamscene.dataandstories.com
ENVIRONMENT=production
DEBUG=false

# Storage
UPLOAD_PATH=/var/lib/streamscene/uploads
PROCESSED_PATH=/var/lib/streamscene/processed
CACHE_PATH=/var/lib/streamscene/cache

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# OTA Updates
UPDATE_PACKAGE_PATH=/var/lib/streamscene/updates
UPDATE_SIGNING_KEY=/etc/streamscene/signing.key
```

### **Device Configuration (/boot/streamscene-device.txt)**
```ini
[device]
uuid=generated-uuid-here
name=DefaultDevice
version=1.0.0

[network]
wifi_ssid=
wifi_password=
bluetooth_enabled=true

[display]
rotation=0
brightness=100

[server]
api_url=https://streamscene.dataandstories.com
websocket_url=wss://streamscene.dataandstories.com/ws
```

---

## 🎯 Success Criteria

### **Technical Metrics**
- ✅ Web app page load: <2 seconds
- ✅ API response time: <200ms (p95)
- ✅ WebSocket latency: <100ms
- ✅ Image processing: <5 seconds
- ✅ Device setup time: <5 minutes
- ✅ WebSocket connection stability: >90%

### **User Experience**
- ✅ Setup process completion rate: >95%
- ✅ System uptime: >99%
- ✅ Support tickets per device: <2 per year
- ✅ OTA update success rate: >98%

---

## 🔄 Decision Review Process

### **When to Reconsider Decisions**

**Reflex Framework:**
- If device API can't be built in Week 1
- If WebSocket management proves impossible
- If performance is inadequate

**WebSockets:**
- If connection stability <90% after 1 week testing
- If server load is excessive (>80% CPU)
- Fallback: Switch to polling immediately

**Bluetooth Setup:**
- If implementation takes >1 week
- If success rate <90% in testing
- Fallback: Ethernet-assisted setup

**OTA Updates:**
- If complexity delays MVP
- Fallback: Manual updates (SSH) for Phase 1

---

## 📚 Key Dependencies

### **Server (Python)**
```
reflex>=0.6.0
sqlalchemy>=2.0
alembic>=1.13
psycopg2-binary>=2.9
celery>=5.3
redis>=5.0
pillow>=10.0
numpy>=1.24
python-jose[cryptography]>=3.3
passlib[bcrypt]>=1.7
qrcode[pil]>=7.4
python-dotenv>=1.0
httpx>=0.25
pydantic>=2.0
```

### **Device (Python)**
```
websocket-client>=1.6.0
requests>=2.31.0
pillow>=10.0.0
numpy>=1.24.0
RPi.GPIO>=0.7.1
spidev>=3.6
bleak>=0.21.0  # Bluetooth LE
waveshare-epd  # From GitHub
```

### **System Packages (LXC)**
```
postgresql-15
redis-server
python3.11
python3-pip
python3-dev
libpq-dev
build-essential
git
nginx (via NPM)
```

---

## 📞 Support & Monitoring

### **Device Diagnostics**
- Device logs sent to server (last 100 lines)
- Health check API endpoint
- E Ink diagnostic screen (button press)
- Remote SSH access (via VPN)

### **Server Monitoring**
- Application logs (structured JSON)
- Database connection pool monitoring
- WebSocket connection tracking
- Celery task queue monitoring
- Optional: Grafana + Prometheus

---

## 🎓 Learning Resources

- [Reflex Documentation](https://reflex.dev/docs)
- [Waveshare E-Paper Wiki](https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT)
- [Web Bluetooth API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Bluetooth_API)
- [Authentik OAuth2](https://docs.goauthentik.io/docs/providers/oauth2)
- [Celery Documentation](https://docs.celeryq.dev)

---

*This document is a living record of architectural decisions. Update as decisions are made or reconsidered.*

**Last Updated:** November 1, 2024
**Next Review:** After Phase 1 completion
