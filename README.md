# StreamScene

**Family and Friends E Ink Message Board System**

StreamScene is a physical message board system using color E Ink displays (Waveshare 7.3" 6-color) on Raspberry Pi Zero 2 WH devices. Family members can remotely post messages and images through "Streams" - shared channels that display on physical E Ink frames.

---

## 🎯 Project Overview

### What is StreamScene?

StreamScene allows families and friends to stay connected through physical E Ink displays. Users create or subscribe to "Streams" (shared channels) and post text messages that appear on E Ink frames in real-time.

**Key Constraint:** E Ink displays have ~30 second refresh time, limiting content rotation to minimum 60 second intervals.

### Setup Process

1. Plug StreamScene Frame into power
2. Connect to device WiFi hotspot (StreamScene-XXXX)
3. Enter home WiFi credentials via captive portal
4. Scan QR code to register device
5. Start posting to Streams!

---

## ✨ Features

- 🌐 **Remote Posting:** Update from anywhere via web interface
- 👥 **Shared Streams:** Create private or public message channels
- 🎨 **E Ink Preview:** See exactly how posts will look before sending
- 📱 **Mobile Responsive:** Full-featured mobile and desktop UI
- 🔄 **Over-the-Air Updates:** Automatic device software updates
- 🔐 **Secure Authentication:** OAuth2 via Authentik
- 📊 **Stream Management:** Subscribe, create, and manage multiple streams
- 🎛️ **Customizable Themes:** Multiple E Ink display themes

---

## 🖥️ Hardware

- **Display:** Waveshare 7.3" 6-Color E-Paper (800x480px)
- **Computing:** Raspberry Pi Zero 2 WH
- **Storage:** SanDisk Ultra MicroSDXC 64GB
- **Connectivity:** Built-in WiFi

**Colors Supported:** Black, White, Red, Yellow, Blue, Green

---

## 🛠️ Tech Stack

### Backend
- **Framework:** Python Reflex (full-stack web framework)
- **Database:** PostgreSQL 15
- **Cache/Queue:** Redis + Celery
- **Authentication:** Authentik (OAuth2/OIDC)
- **Hosting:** LXC containers on Proxmox
- **Domain:** dataandstories.com

### Device Client
- **OS:** Raspberry Pi OS Lite (Debian Bookworm)
- **Language:** Python 3.11+
- **Display Driver:** Waveshare E-Paper library
- **Communication:** WebSocket + REST API

---

## 🚀 Quick Start for Developers

### Prerequisites
```bash
# System requirements
- Python 3.11+
- PostgreSQL 15
- Redis
- Git
```

### Environment Setup
```bash
# Clone repository
git clone <repository-url>
cd streamscene

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your database credentials and OAuth settings

# Run database migrations
alembic upgrade head
```

### Running the Application
```bash
# Development mode (with hot reload)
reflex run

# Production mode
reflex run --env prod

# Or use the restart script (handles port conflicts)
./restart-reflex.sh
```

The web app will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## 📂 Project Structure

```
streamscene/
├── streamscene/
│   ├── core/              # Pure Python business logic (framework-agnostic)
│   │   ├── models.py      # SQLAlchemy ORM models
│   │   ├── database.py    # Database connection & session management
│   │   ├── auth.py        # Authentication logic
│   │   ├── streams.py     # Stream business logic
│   │   ├── devices.py     # Device management logic
│   │   ├── ota.py         # OTA update logic
│   │   ├── qr_utils.py    # QR code generation
│   │   └── tasks.py       # Celery background tasks
│   ├── api/               # API layer (device endpoints)
│   │   ├── routes/        # API route handlers
│   │   └── schemas.py     # Pydantic request/response models
│   ├── pages/             # Reflex page components
│   │   ├── index.py       # Landing page
│   │   ├── callback.py    # OAuth callback
│   │   └── streams.py     # Stream management UI
│   └── components/        # Reusable UI components
│       ├── eink/          # E Ink preview system
│       └── layout.py      # Page layouts
├── client/                # Raspberry Pi device client
│   ├── setup/             # WiFi setup (hotspot + captive portal)
│   ├── main.py            # Device main loop
│   └── README.md          # Device client documentation
├── docs/                  # Documentation
│   ├── plans/             # Implementation roadmaps
│   ├── deployment/        # Setup & deployment guides
│   ├── reference/         # API examples & testing
│   └── archive/           # Historical documents
├── alembic/               # Database migrations
├── tests/                 # Test suite
├── CLAUDE.md              # Comprehensive developer guide
├── NEXT_SESSION.md        # Session continuity tracker
└── README.md              # This file
```

---

## 📖 Documentation

- **[CLAUDE.md](CLAUDE.md)** - Comprehensive developer guide (architecture, commands, gotchas)
- **[NEXT_SESSION.md](NEXT_SESSION.md)** - Current development status and next tasks
- **[docs/deployment/](docs/deployment/)** - Setup and deployment guides
- **[docs/plans/](docs/plans/)** - Implementation roadmaps and planning documents
- **[client/README.md](client/README.md)** - Raspberry Pi device client guide

---

## 🔧 Development

### Common Commands
```bash
# Database
alembic revision --autogenerate -m "description"  # Create migration
alembic upgrade head                               # Apply migrations
psql -U streamscene -d streamscene -h localhost   # Connect to DB

# Testing
pytest                                             # Run all tests
pytest --cov=streamscene --cov-report=html        # With coverage

# Background Tasks
celery -A streamscene.core.tasks worker --loglevel=info    # Start worker
celery -A streamscene.core.tasks beat --loglevel=info      # Start scheduler
```

### Deploy to Raspberry Pi
```bash
# Use the deployment script
./deploy_to_pi.sh

# Or manually with sshpass
sshpass -p 'password' scp -r client/ pi@device:~/streamscene-client/
```

---

## 🏗️ Architecture

### Code Structure Philosophy
The codebase uses **defensive architecture** - business logic is framework-agnostic (in `core/`) to enable easy framework migration if Reflex proves limiting.

### Communication Architecture
- **Web users → Server:** Reflex web interface + Authentik OAuth2
- **Devices → Server:** WebSocket connections (primary) with polling fallback
- **Real-time updates:** WebSocket server pushes content to devices
- **Device authentication:** API key (generated during device registration)
- **Background processing:** Celery + Redis for image processing, notifications

---

## 🌐 Infrastructure

**Homelab Resources:**
- **Proxmox:** http://192.168.1.30
- **LXC Container (StreamScene):** 192.168.1.118 (Debian 12, 4 cores, 4GB RAM)
- **LXC Container (Authentik):** 192.168.1.108:9000 (OAuth provider)
- **LXC Container (Nginx Proxy Manager):** 192.168.1.104:81 (reverse proxy + SSL)
- **Domain:** dataandstories.com

**Production URLs:**
- Web App: https://streamscene.dataandstories.com
- Authentication: https://auth.dataandstories.com

---

## 📊 Development Status

**Current Phase:** Phase 5 - Device State Machine & Registration

**Completed:**
- ✅ Phase 0: Infrastructure Setup
- ✅ Phase 1: Web App Core (streams, posts, auth)
- ✅ Phase 2-3: OTA Update Infrastructure
- ✅ Phase 4: WiFi Setup System (hotspot + captive portal)

**In Progress:**
- 🚧 Phase 5: Device State Machine & Registration

**Pending:**
- ⏳ Phase 6: E Ink Display Integration
- ⏳ Phase 7: WebSocket & Content Display
- ⏳ Phase 8: OTA Update Client
- ⏳ Phase 9: Production Deployment

See [NEXT_SESSION.md](NEXT_SESSION.md) for detailed current tasks and [docs/plans/DEVICE_SETUP_OTA.md](docs/plans/DEVICE_SETUP_OTA.md) for the complete implementation plan.

---

## 🤝 Contributing

This is currently a personal project. For questions or suggestions, please open an issue.

---

## 📝 License

[License information to be added]

---

**Last Updated:** November 11, 2025
**Version:** 1.0.0 (MVP Development)
