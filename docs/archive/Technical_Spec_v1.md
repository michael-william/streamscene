# StreamScene Technical Specification

## 📋 Project Summary
StreamScene is a family and friends physical message board system using color E Ink displays and Raspberry Pi devices. Users can remotely update messages and images through "Streams" - shared channels that display on physical E Ink frames.

---

## 🖥️ Hardware Specifications

### Display
- **Model**: Waveshare 7.3inch 6-Color E-Paper Screen With Driver Board (E Type)
- **Resolution**: 800x480 pixels
- **Colors**: 6 colors (Black, White, Red, Yellow, Blue, Green)
- **Communication**: SPI Interface
- **Power**: Low power consumption, perfect for always-on display
- **Refresh Rate**: ~30 seconds for full refresh (typical for color E-Paper)

### Computing
- **Device**: Raspberry Pi Zero 2 WH
- **Storage**: SanDisk Ultra MicroSDXC 64GB
- **Connectivity**: Built-in WiFi

---

## 🏗️ Architecture Decisions

### Backend Infrastructure
- **Container**: LXC on Proxmox (192.168.1.30)
- **Framework**: Python Reflex (full-stack web app)
- **Database**: PostgreSQL (recommended for performance and concurrent users)
- **Storage**: 
  - Images stored in LXC filesystem with database references
  - Pi devices cache recent images locally with automatic cleanup
- **Domain**: dataandstories.com
- **Reverse Proxy**: Nginx Proxy Manager (LXC 104 - 192.168.1.104:81)
- **Authentication**: Authentik (LXC 108 - 192.168.1.108:9000)

### Communication Architecture
- **Real-time Updates**: WebSocket/SSE for instant frame updates
- **API**: RESTful endpoints for device management and data retrieval
- **Device Auth**: API keys generated during device registration

### Device Identification Strategy
- **Hybrid Pre-configuration + Registration**:
  1. Pre-flash each Pi with unique device UUID
  2. Include QR code sticker with UUID on frame
  3. User scans QR during setup to link device to account
  4. Device receives API key upon successful registration

---

## 🎨 UI/UX Requirements

### Reflex Web App Design
- **Theming**: Custom theme implementation required
- **Responsive Design**:
  - **Desktop**: Side panel navigation
  - **Mobile**: Hamburger menu navigation
  - **Breakpoints**: Mobile (<768px), Tablet (768-1024px), Desktop (>1024px)
- **Layout Components**: 
  - Consistent use of Reflex layout components
  - Grid system for stream cards
  - Flex layouts for post displays
  - Container components for consistent spacing

### E Ink Display UI
- **Content Layout**:
  - Header: Stream name, timestamp
  - Body: Message/Image content (primary focus)
  - Footer: Author name, minimal metadata
- **Transitions**:
  - Preferred: Slide out/slide in effect
  - Fallback: Dissolve transition
  - Default rotation: 5 seconds (configurable per stream)

---

## 🔧 E Ink Image Processing Requirements

### Waveshare 7.3" 6-Color Processing Pipeline
1. **Resolution Scaling**: Resize to exactly 800x480 pixels
2. **Color Palette Reduction**:
   - Map to 6 colors: Black, White, Red, Yellow, Blue, Green
   - Implement Floyd-Steinberg dithering for smooth gradients
3. **Format Conversion**:
   - Convert to Waveshare-specific buffer format
   - Generate appropriate command sequences for SPI communication
4. **Optimization**:
   - Pre-process on server to reduce Pi CPU load
   - Cache processed images for repeated displays
   - Implement partial refresh where possible (text updates)

---

## 🗄️ Database Schema

### Core Tables
```sql
-- Users (managed by Authentik, referenced here)
users
  - id (UUID, primary)
  - email (unique)
  - username (unique)
  - created_at
  - updated_at

-- Devices
devices
  - id (UUID, primary)
  - device_uuid (unique)
  - user_id (foreign key)
  - nickname
  - api_key (unique, encrypted)
  - last_seen
  - current_stream_id
  - rotation_enabled (boolean)
  - rotation_interval (seconds)
  - registered_at

-- Streams
streams
  - id (UUID, primary)
  - owner_id (foreign key to users)
  - name
  - description
  - is_public (boolean)
  - allow_text (boolean)
  - allow_images (boolean)
  - show_history (boolean)
  - max_history_items (integer)
  - created_at
  - updated_at

-- Stream Subscriptions
stream_subscriptions
  - id (UUID, primary)
  - user_id (foreign key)
  - stream_id (foreign key)
  - is_approved (boolean)
  - subscribed_at

-- Posts
posts
  - id (UUID, primary)
  - stream_id (foreign key)
  - author_id (foreign key to users)
  - content_type (enum: text, image, mixed)
  - text_content
  - image_path
  - processed_image_path
  - created_at
  - updated_at

-- Device Stream Settings
device_stream_settings
  - id (UUID, primary)
  - device_id (foreign key)
  - stream_id (foreign key)
  - display_order (integer)
  - is_active (boolean)
```

---

## 📱 Authentication Flow

### Web Users
1. User visits web app
2. Redirected to Authentik OAuth2/OIDC flow
3. After successful auth, user session created in Reflex app
4. JWT tokens for API access

### Device Authentication
1. Device boots with pre-configured UUID
2. Creates WiFi hotspot for initial setup
3. User connects phone, opens captive portal
4. User logs in via web auth
5. Scans QR code to link device
6. Device receives API key
7. Device connects to home WiFi
8. Begins WebSocket connection with API key

---

## 🚀 Development Phases

### Phase 1: Web App Core (Days 1-3)
**Priority: HIGH - Start Here**

#### 1.1 Environment Setup
- [ ] Create LXC container for StreamScene
- [ ] Install Python 3.11+, PostgreSQL, Redis (for WebSocket)
- [ ] Configure Nginx Proxy Manager routing
- [ ] Setup SSL certificates via NPM

#### 1.2 Database & Models
- [ ] PostgreSQL database creation
- [ ] SQLAlchemy models for all tables
- [ ] Alembic migration setup
- [ ] Seed data for testing

#### 1.3 Reflex Web App Foundation
- [ ] Project structure with Reflex
- [ ] Custom theme implementation
- [ ] Responsive layout components
- [ ] Navigation system (side panel + hamburger)

#### 1.4 Core Features
- [ ] User registration/login (Authentik integration)
- [ ] Stream CRUD operations
- [ ] Post creation (text only initially)
- [ ] Stream subscription system
- [ ] Dashboard with user's streams
- [ ] Stream view with posts

### Phase 2: API Layer (Days 4-5)
**Priority: HIGH**

#### 2.1 REST API
- [ ] FastAPI integration with Reflex
- [ ] Device registration endpoints
- [ ] Stream data endpoints
- [ ] Post retrieval with pagination
- [ ] Image upload handling

#### 2.2 WebSocket Implementation
- [ ] WebSocket server setup
- [ ] Real-time post notifications
- [ ] Device heartbeat system
- [ ] Connection management

#### 2.3 Device Management
- [ ] QR code generation for devices
- [ ] Device registration flow
- [ ] API key generation and management
- [ ] Device settings endpoints

### Phase 3: Pi Client Software (Days 6-8)
**Priority: MEDIUM - After hardware arrives**

#### 3.1 Display Driver
- [ ] Waveshare 7.3" library integration
- [ ] Content rendering engine
- [ ] Text layout system
- [ ] Image display pipeline
- [ ] Transition effects implementation

#### 3.2 Network Client
- [ ] WebSocket client
- [ ] Message queue for offline mode
- [ ] Automatic reconnection
- [ ] Local content caching

#### 3.3 Setup Mode
- [ ] WiFi hotspot creation
- [ ] Captive portal web server
- [ ] Configuration storage
- [ ] Setup completion flow

### Phase 4: Image Processing (Days 9-10)
**Priority: MEDIUM**

#### 4.1 Server-side Processing
- [ ] Image upload validation
- [ ] 6-color palette reduction
- [ ] Floyd-Steinberg dithering
- [ ] 800x480 resolution scaling
- [ ] Waveshare format conversion

#### 4.2 Caching System
- [ ] Processed image storage
- [ ] Cache invalidation
- [ ] Cleanup policies

### Phase 5: Polish & Advanced Features (Days 11-12)
**Priority: LOW**

#### 5.1 Enhanced UI
- [ ] Stream discovery page
- [ ] User profiles
- [ ] Stream analytics
- [ ] Admin panel

#### 5.2 Advanced Features
- [ ] Stream scheduling
- [ ] Emoji support for E Ink
- [ ] Weather widget integration
- [ ] Multiple image slideshow
- [ ] Stream moderation tools

---

## 🔌 API Endpoints

### Public Endpoints
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `POST /api/auth/refresh` - Token refresh

### Authenticated Endpoints
- `GET /api/streams` - List user's streams
- `POST /api/streams` - Create stream
- `GET /api/streams/{id}` - Get stream details
- `PUT /api/streams/{id}` - Update stream
- `DELETE /api/streams/{id}` - Delete stream
- `POST /api/streams/{id}/posts` - Create post
- `GET /api/streams/{id}/posts` - Get posts
- `POST /api/streams/{id}/subscribe` - Subscribe to stream

### Device Endpoints
- `POST /api/devices/register` - Register device with QR code
- `GET /api/devices/{id}/config` - Get device configuration
- `GET /api/devices/{id}/content` - Get current content
- `POST /api/devices/{id}/heartbeat` - Update last seen
- `WS /api/devices/{id}/stream` - WebSocket for real-time updates

---

## 🐍 Python Dependencies

### Backend (Reflex App)
```txt
reflex>=0.3.0
sqlalchemy>=2.0
alembic
psycopg2-binary
python-jose[cryptography]
passlib[bcrypt]
python-multipart
pillow
numpy
redis
asyncio
httpx
qrcode[pil]
python-dotenv
```

### Raspberry Pi Client
```txt
requests
websocket-client
pillow
numpy
RPi.GPIO
spidev
waveshare-epd
flask  # for setup portal
qrcode
python-wifi
netifaces
```

---

## 🔐 Security Considerations

1. **API Keys**: Store hashed, rotate periodically
2. **WebSocket**: Implement rate limiting
3. **Image Uploads**: Validate file types, scan for malware
4. **Device Communication**: TLS/SSL required
5. **QR Codes**: One-time use tokens
6. **User Data**: GDPR compliance, data minimization

---

## 📊 Performance Targets

- **Web App**: <2s page load time
- **API Response**: <200ms for standard requests
- **WebSocket Latency**: <100ms message delivery
- **Image Processing**: <5s for full pipeline
- **E Ink Refresh**: Optimize for partial refresh when possible
- **Database**: Index on frequently queried fields

---

## 🧪 Testing Strategy

1. **Unit Tests**: Models, image processing, API endpoints
2. **Integration Tests**: Auth flow, WebSocket, device registration
3. **E2E Tests**: Complete user journeys
4. **Load Tests**: 100+ concurrent devices
5. **Hardware Tests**: Mock E Ink display for CI/CD

---

## 📝 Configuration Files

### Environment Variables (.env)
```env
DATABASE_URL=postgresql://user:pass@localhost/streamscene
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key
AUTHENTIK_URL=http://192.168.1.108:9000
AUTHENTIK_CLIENT_ID=streamscene
AUTHENTIK_CLIENT_SECRET=your-client-secret
DOMAIN=dataandstories.com
UPLOAD_PATH=/var/lib/streamscene/uploads
PROCESSED_PATH=/var/lib/streamscene/processed
```

---

## 🚢 Deployment Checklist

- [ ] LXC container configured with adequate resources
- [ ] PostgreSQL database backed up regularly
- [ ] SSL certificates configured in NPM
- [ ] Authentik application configured
- [ ] Environment variables set
- [ ] Systemd service for Reflex app
- [ ] Log rotation configured
- [ ] Monitoring setup (optional: Grafana/Prometheus)
- [ ] Backup strategy implemented

---

## 📚 Additional Resources

- [Waveshare 7.3" E-Paper Documentation](https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT)
- [Reflex Documentation](https://reflex.dev/docs)
- [Authentik OAuth2 Setup](https://docs.goauthentik.io/docs/providers/oauth2)
- [PostgreSQL Best Practices](https://www.postgresql.org/docs/current/index.html)

---

## 🎯 Success Criteria

1. Users can create and manage streams via web interface
2. Multiple devices can display stream content simultaneously
3. Updates appear on E Ink displays within 5 seconds
4. System supports 50+ devices without degradation
5. Setup process takes less than 5 minutes
6. 99% uptime for core services

---

*Last Updated: November 2024*
*Version: 1.0*