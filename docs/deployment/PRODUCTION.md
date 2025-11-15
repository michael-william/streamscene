# Production Deployment Guide

Complete guide for deploying StreamScene to production.

## Infrastructure Overview

### Homelab Resources

- **Proxmox Host:** http://192.168.1.30
- **LXC Container (StreamScene):** 192.168.1.118
  - OS: Debian 12
  - Resources: 4 cores, 4GB RAM, 50GB storage
- **LXC Container (Authentik):** 192.168.1.108:9000
  - OAuth provider
- **LXC Container (Nginx Proxy Manager):** 192.168.1.104:81
  - Reverse proxy + SSL termination
- **Domain:** dataandstories.com

### System Services

Running on StreamScene container (192.168.1.118):
- PostgreSQL 15
- Redis Server
- Reflex web server
  - Frontend (React SPA): Port 3000
  - Backend (FastAPI): Port 8000
- Celery worker (systemd service - not yet configured)
- Celery beat scheduler (systemd service - not yet configured)

## Reflex Production Setup

### Port Configuration

```
Frontend (React SPA):  Port 3000
Backend (FastAPI):     Port 8000
```

### Reflex Configuration

File: `rxconfig.py`

```python
import os
import reflex as rx

config = rx.Config(
    app_name="streamscene",
    backend_host="0.0.0.0",
    backend_port=8000,
    frontend_port=3000,
    api_url="https://streamscene.dataandstories.com",
    deploy_url="https://streamscene.dataandstories.com",
    plugins=[...]
)
```

### Running Reflex in Production

```bash
# Production mode
reflex run --env prod

# Or use restart script for reliability
./restart-reflex.sh
```

## Nginx Proxy Manager Configuration

### Main Proxy Host Settings

**Details Tab:**
- **Scheme:** `http`
- **Forward Hostname/IP:** `192.168.1.118` (StreamScene container IP)
- **Forward Port:** `3000` (frontend)
- **Cache Assets:** Enabled
- **Block Common Exploits:** Enabled
- **WebSockets Support:** Enabled

### Advanced Configuration

**Advanced Tab:**

```nginx
# WebSocket support for Reflex
location /_event/ {
    proxy_pass http://192.168.1.118:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 86400;
}

# API routes to backend
location /api/ {
    proxy_pass http://192.168.1.118:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### SSL Configuration

**SSL Tab:**
- **SSL Certificate:** Let's Encrypt (auto-renewal enabled)
- **Force SSL:** Enabled
- **HTTP/2 Support:** Enabled
- **HSTS Enabled:** Yes
- **HSTS Subdomains:** Yes

### How It Works

1. **Main proxy** forwards ALL traffic to frontend (port 3000) by default
2. **Advanced config** routes specific paths to backend (port 8000):
   - `/_event/` → WebSocket endpoint (port 8000)
   - `/api/` → REST API endpoints (port 8000)
3. **Container IP required:** Use 192.168.1.118, NOT 127.0.0.1
   - Nginx runs in different container, can't use localhost

## Restart Script

File: `./restart-reflex.sh`

```bash
#!/bin/bash
# Cleanly restart Reflex by killing processes on ports 3000 and 8000

# Kill processes on port 3000 (frontend)
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Kill processes on port 8000 (backend)
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Wait for ports to be freed
sleep 2

# Verify ports are free
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null ; then
    echo "ERROR: Port 3000 still in use"
    exit 1
fi

if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "ERROR: Port 8000 still in use"
    exit 1
fi

# Clear Python cache
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Start Reflex
reflex run --env prod
```

Make executable:
```bash
chmod +x ./restart-reflex.sh
```

## Device Client Deployment

### Deploy to Raspberry Pi

Using the provided deployment script:

```bash
# From development machine
./deploy_to_pi.sh

# Or manual deployment
sshpass -p 'password' scp -r client/ badgy@192.168.1.40:~/streamscene-client/
```

### Initial Device Setup (One-Time)

```bash
# SSH into Raspberry Pi
ssh badgy@192.168.1.40  # Or streamscene.local

# Install system dependencies
sudo apt-get update
sudo apt-get install -y hostapd dnsmasq python3-pip

# Disable services (manual control only)
sudo systemctl disable hostapd dnsmasq
sudo systemctl stop hostapd dnsmasq

# Generate device UUID
DEVICE_UUID=$(uuidgen)
echo "DEVICE_UUID=$DEVICE_UUID" | sudo tee /boot/firmware/streamscene-device.txt
cat /boot/firmware/streamscene-device.txt  # Verify

# Test WiFi setup
cd ~/streamscene-client
sudo python3 test_wifi_setup.py
```

### Testing WiFi Setup

1. Run test script (creates hotspot + portal)
2. Connect phone to StreamScene-XXXX network
3. Enter home WiFi credentials in captive portal
4. Verify device connects to home WiFi
5. Check IP address: `ip addr show wlan0`
6. Test internet: `ping -c 3 8.8.8.8`

### Reset WiFi Credentials (for re-testing)

```bash
rm ~/streamscene-client/wifi_credentials.json
sudo python3 ~/streamscene-client/test_wifi_setup.py
```

## Systemd Services (Future)

### Celery Worker Service

File: `/etc/systemd/system/streamscene-worker.service`

```ini
[Unit]
Description=StreamScene Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=forking
User=streamscene
Group=streamscene
WorkingDirectory=/opt/streamscene
Environment="PATH=/opt/streamscene/venv/bin"
ExecStart=/opt/streamscene/venv/bin/celery -A streamscene.core.tasks worker --loglevel=info --detach
ExecStop=/opt/streamscene/venv/bin/celery -A streamscene.core.tasks control shutdown
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Celery Beat Service

File: `/etc/systemd/system/streamscene-beat.service`

```ini
[Unit]
Description=StreamScene Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=streamscene
Group=streamscene
WorkingDirectory=/opt/streamscene
Environment="PATH=/opt/streamscene/venv/bin"
ExecStart=/opt/streamscene/venv/bin/celery -A streamscene.core.tasks beat --loglevel=info
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Reflex Service

File: `/etc/systemd/system/streamscene-reflex.service`

```ini
[Unit]
Description=StreamScene Reflex Server
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=streamscene
Group=streamscene
WorkingDirectory=/opt/streamscene
Environment="PATH=/opt/streamscene/venv/bin"
ExecStart=/opt/streamscene/venv/bin/reflex run --env prod
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable streamscene-reflex
sudo systemctl enable streamscene-worker
sudo systemctl enable streamscene-beat

sudo systemctl start streamscene-reflex
sudo systemctl start streamscene-worker
sudo systemctl start streamscene-beat
```

## Monitoring & Logs

### View Service Logs

```bash
# Reflex logs
journalctl -u streamscene-reflex -f

# Celery worker logs
journalctl -u streamscene-worker -f

# Celery beat logs
journalctl -u streamscene-beat -f
```

### Database Monitoring

```bash
# PostgreSQL connection count
psql -U streamscene -d streamscene -c "SELECT count(*) FROM pg_stat_activity;"

# Redis memory usage
redis-cli info memory
```

### WebSocket Connections

```bash
# Monitor active WebSocket connections
redis-cli keys "ws:*" | wc -l
```

## Backup & Restore

### Database Backup

```bash
# Backup database
pg_dump -U streamscene streamscene > backup_$(date +%Y%m%d).sql

# Compress backup
gzip backup_$(date +%Y%m%d).sql
```

### Database Restore

```bash
# Restore from backup
gunzip -c backup_20251114.sql.gz | psql -U streamscene streamscene
```

### Automated Backups (Cron)

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * pg_dump -U streamscene streamscene | gzip > /var/backups/streamscene/backup_$(date +\%Y\%m\%d).sql.gz

# Keep only 7 days of backups
0 3 * * * find /var/backups/streamscene/ -name "backup_*.sql.gz" -mtime +7 -delete
```

## Security Hardening

### Firewall Configuration

```bash
# Allow SSH (port 22)
ufw allow 22/tcp

# Allow HTTP/HTTPS (handled by Nginx Proxy Manager)
ufw allow 80/tcp
ufw allow 443/tcp

# Block direct access to Reflex ports (only allow from Nginx container)
ufw allow from 192.168.1.104 to any port 3000
ufw allow from 192.168.1.104 to any port 8000
ufw deny 3000/tcp
ufw deny 8000/tcp

# Enable firewall
ufw enable
```

### PostgreSQL Security

```bash
# Edit pg_hba.conf to restrict connections
sudo vim /etc/postgresql/15/main/pg_hba.conf

# Only allow local connections
local   streamscene     streamscene                     scram-sha-256
host    streamscene     streamscene     127.0.0.1/32    scram-sha-256
host    streamscene     streamscene     ::1/128         scram-sha-256
```

### Redis Security

```bash
# Edit redis.conf
sudo vim /etc/redis/redis.conf

# Bind to localhost only
bind 127.0.0.1 ::1

# Require password (generate strong password)
requirepass YOUR_STRONG_REDIS_PASSWORD

# Restart Redis
sudo systemctl restart redis
```

## Performance Tuning

### PostgreSQL Tuning

Edit `/etc/postgresql/15/main/postgresql.conf`:

```ini
# Memory settings (for 4GB RAM container)
shared_buffers = 1GB
effective_cache_size = 3GB
work_mem = 16MB
maintenance_work_mem = 256MB

# Connection settings
max_connections = 100

# Logging
log_min_duration_statement = 1000  # Log slow queries (>1s)
```

### Redis Tuning

Edit `/etc/redis/redis.conf`:

```ini
# Memory limit (512MB for WebSocket state)
maxmemory 512mb
maxmemory-policy allkeys-lru

# Persistence (for session data)
save 900 1
save 300 10
save 60 10000
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port
lsof -i :3000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or use restart script
./restart-reflex.sh
```

### Database Connection Errors

```bash
# Check PostgreSQL status
systemctl status postgresql

# Check connections
psql -U streamscene -d streamscene -c "SELECT count(*) FROM pg_stat_activity;"

# Restart if needed
sudo systemctl restart postgresql
```

### WebSocket Connection Issues

```bash
# Check Nginx config
nginx -t

# View Nginx error logs
tail -f /var/log/nginx/error.log

# Verify WebSocket route in Nginx config
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  https://streamscene.dataandstories.com/_event/
```

## Deployment Checklist

- [ ] Environment variables configured (.env.production)
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] Nginx reverse proxy configured
- [ ] SSL certificates installed
- [ ] Firewall rules configured
- [ ] Systemd services created and enabled
- [ ] Backup cron jobs configured
- [ ] Monitoring alerts configured
- [ ] Security hardening applied
- [ ] Load testing completed
- [ ] Documentation updated
