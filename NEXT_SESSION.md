# StreamScene - Current Status

**Last Updated:** November 2, 2025
**Project:** StreamScene - Family E Ink Message Board

---

## ✅ Phase 0: COMPLETED - Environment Setup

### **What We've Accomplished**
1. ✅ System dependencies installed (PostgreSQL 15, Redis 7, Python 3.11, build tools)
2. ✅ PostgreSQL database created and configured
3. ✅ Redis server running and tested
4. ✅ Python virtual environment created (`venv/`)
5. ✅ Reflex 0.8.17 project initialized
6. ✅ All Python dependencies installed (SQLAlchemy, Celery, etc.)
7. ✅ `.env` file created with all configuration
8. ✅ `CREDENTIALS.md` created with all passwords
9. ✅ Storage directories created (`/var/lib/streamscene/*`)
10. ✅ `.gitignore` updated to protect secrets
11. ✅ `requirements.txt` populated
12. ✅ `CLAUDE.md` created for future sessions

### **Infrastructure Status**

#### PostgreSQL
- **Status:** ✅ Running and tested
- **Database:** streamscene
- **User:** streamscene
- **Password:** Documented in `CREDENTIALS.md`
- **Connection String:** In `.env` file

#### Redis
- **Status:** ✅ Running and tested
- **URL:** redis://localhost:6379/0
- **Test:** `redis-cli ping` returns PONG

#### Python Environment
- **Virtual Environment:** `/root/streamscene/venv`
- **Python Version:** 3.11.2
- **Pip Version:** 25.3
- **Key Packages Installed:**
  - Reflex 0.8.17
  - SQLAlchemy 2.0.44
  - Alembic 1.17.1
  - Celery 5.5.3
  - Redis 6.4.0
  - Psycopg2-binary 2.9.11
  - Pillow, NumPy, QRCode, etc.

#### Project Structure
```
/root/streamscene/
├── streamscene/           # Reflex app directory
│   ├── __init__.py
│   └── streamscene.py     # Main app file (blank template)
├── assets/                # Static assets
├── venv/                  # Python virtual environment
├── .env                   # Environment configuration ✅
├── .gitignore            # Updated with secrets ✅
├── requirements.txt      # All dependencies ✅
├── rxconfig.py           # Reflex configuration ✅
├── CREDENTIALS.md        # Password documentation ✅
├── CLAUDE.md             # Claude Code guide ✅
├── Architecture_Decisions.md
├── StreamScene_Technical_Spec.md
└── StreamScene Overview.md
```

---

## 🚧 NEXT: Immediate Tasks

### **1. Configure Authentik OAuth (IN PROGRESS)**
- [ ] Login to Authentik at http://192.168.1.108:9000
- [ ] Create OAuth2/OIDC Provider
- [ ] Create Application "StreamScene"
- [ ] Update `.env` with Client ID and Secret
- [ ] Document credentials in `CREDENTIALS.md`

### **2. Generate OTA Signing Key**
```bash
openssl genrsa -out /etc/streamscene/signing.key 4096
chmod 600 /etc/streamscene/signing.key
```

### **3. Configure Nginx Proxy Manager**
- [ ] Login to NPM at http://192.168.1.104:81
- [ ] Add proxy host for streamscene.dataandstories.com
- [ ] Point to this LXC container IP
- [ ] Enable WebSocket support
- [ ] Setup SSL certificate (Let's Encrypt)

---

## 📋 Week 1 Checklist

**Day 1-2: Environment Setup** ✅ COMPLETED
- [x] Install all system dependencies
- [x] Setup PostgreSQL database
- [x] Setup Redis
- [x] Create Python virtual environment
- [x] Initialize Reflex project
- [ ] Configure Authentik OAuth application (IN PROGRESS)
- [ ] Configure Nginx Proxy Manager

**Day 3-4: Database & Core** (NEXT)
- [ ] Create project directory structure (core/, api/, ui/)
- [ ] Create SQLAlchemy models (users, devices, streams, posts)
- [ ] Setup Alembic migrations
- [ ] Create initial migration and apply to database
- [ ] Write core business logic functions
- [ ] Test Authentik integration with simple login

**Day 5: Device API Proof of Concept** ⚠️ CRITICAL
- [ ] Create one device API endpoint in Reflex
- [ ] Test with curl/Postman
- [ ] Verify WebSocket capability
- [ ] **DECISION POINT:** Does Reflex work for device API?
  - If YES → Continue with Reflex
  - If NO → Plan migration to FastAPI

---

## 🔑 Key Information

### **LXC Container**
- **IP Address:** TBD (need to check)
- **OS:** Debian 12 (Bookworm)
- **Resources:** Check allocation
- **Services Running:**
  - PostgreSQL (port 5432)
  - Redis (port 6379)

### **Homelab Resources**
- **Proxmox:** http://192.168.1.30
- **Authentik:** http://192.168.1.108:9000
- **Nginx Proxy Manager:** http://192.168.1.104:81
- **Domain:** dataandstories.com

### **Security Keys** (See CREDENTIALS.md)
- PostgreSQL password: Generated and documented ✅
- SECRET_KEY: Generated and documented ✅
- API_KEY_SALT: Generated and documented ✅
- Authentik credentials: Pending configuration

---

## 📝 Answers to Previous Questions

1. **LXC container IP address?** - Need to determine and document
2. **Separate subdomain for device API?** - Not initially; can use same domain with /api path
3. **Docker Compose instead?** - No, using direct LXC installation
4. **Git repository?** - Local git initialized; remote TBD
5. **PostgreSQL password strategy?** - Generated random token, stored in .env and CREDENTIALS.md ✅

---

## 🎯 Critical Architectural Decisions Made

### **Web Application**
- **Framework:** Pure Reflex (with defensive code structure)
- **Database:** PostgreSQL ✅ Installed
- **Cache/Broker:** Redis ✅ Installed
- **Background Tasks:** Celery ✅ Installed
- **Authentication:** Authentik (OAuth2) - Needs configuration
- **Communication:** WebSockets (fallback to polling if needed)

### **MVP Scope**
- Text-only posts (defer images to Phase 5)
- Full Bluetooth setup flow
- Device registration via QR code
- OTA update system
- Web UI for stream management
- Timeline: 7 weeks to first production device

### **Important Constraints**
- E Ink refresh time: ~30 seconds
- Minimum rotation interval: 60 seconds
- Pi Zero 2 WH: 512MB RAM (limited resources)
- Family project scale: 10-30 devices max

---

## 🚨 Potential Blockers to Watch

1. **Reflex Device API** - Week 1 Day 5 decision point
2. **WebSocket Stability** - Need >90% connection success
3. **Authentik Integration** - May need custom OAuth code for Reflex
4. **Bluetooth Setup** - Web Bluetooth API has limited browser support

---

## 💡 Quick Start Commands

### Activate Environment
```bash
cd /root/streamscene
source venv/bin/activate
```

### Run Development Server
```bash
source venv/bin/activate
reflex run
```

### Database Connection
```bash
# See CREDENTIALS.md for password
PGPASSWORD='<see-credentials>' psql -U streamscene -d streamscene -h localhost
```

### Redis Connection
```bash
redis-cli ping
```

---

## 🔗 Important Links

- **Reflex Documentation:** https://reflex.dev/docs
- **Authentik OAuth Setup:** https://docs.goauthentik.io/docs/providers/oauth2
- **SQLAlchemy ORM:** https://docs.sqlalchemy.org/en/20/
- **Alembic Migrations:** https://alembic.sqlalchemy.org/
- **Waveshare E-Paper:** https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT

---

## 📊 Project Status: Phase 0 Complete ✅

**Next Major Milestone:**
- Complete Authentik OAuth configuration
- Build database models and migrations
- Create basic Reflex UI with authentication
- Test device API capability (Day 5 decision point)

**Ready for Phase 1: Backend Core Development** 🚀
