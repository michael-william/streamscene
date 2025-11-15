# Environment Configuration

Complete reference for StreamScene environment variables.

## Required Environment Variables

### Database Configuration

```bash
# PostgreSQL connection string
DATABASE_URL=postgresql://streamscene:password@localhost/streamscene

# Redis connection string
REDIS_URL=redis://localhost:6379/0
```

### Security

```bash
# Secret key for session encryption (generate with: openssl rand -hex 32)
SECRET_KEY=your-secret-key-here

# Salt for API key hashing (generate with: openssl rand -hex 16)
API_KEY_SALT=your-api-key-salt-here
```

### OAuth Configuration

#### Legacy Authentik Format (for reference)

```bash
AUTHENTIK_URL=http://192.168.1.108:9000
AUTHENTIK_CLIENT_ID=streamscene
AUTHENTIK_CLIENT_SECRET=your-client-secret
```

#### Current OAuth Format (used by Reflex pages)

```bash
OAUTH_CLIENT_ID=streamscene
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_AUTHORIZATION_URL=https://auth.dataandstories.com/application/o/authorize/
OAUTH_TOKEN_URL=https://auth.dataandstories.com/application/o/token/
OAUTH_USERINFO_URL=https://auth.dataandstories.com/application/o/userinfo/
OAUTH_REDIRECT_URI=https://streamscene.dataandstories.com/callback
```

### Application Settings

```bash
# Domain configuration
DOMAIN=streamscene.dataandstories.com
FRONTEND_URL=https://streamscene.dataandstories.com
BACKEND_URL=https://streamscene.dataandstories.com

# Environment (development, staging, production)
ENVIRONMENT=production
```

### Storage Paths

```bash
# File upload storage
UPLOAD_PATH=/var/lib/streamscene/uploads

# Processed E Ink images
PROCESSED_PATH=/var/lib/streamscene/processed

# Cache directory
CACHE_PATH=/var/lib/streamscene/cache
```

## Optional Environment Variables

### Development Settings

```bash
# Enable debug mode (DO NOT use in production)
DEBUG=false

# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Enable SQL query logging
SQL_ECHO=false
```

### Celery Configuration

```bash
# Celery broker URL (defaults to REDIS_URL)
CELERY_BROKER_URL=redis://localhost:6379/1

# Celery result backend (defaults to REDIS_URL)
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

### Rate Limiting

```bash
# Requests per minute for web users
WEB_RATE_LIMIT=100

# Requests per minute for devices
DEVICE_RATE_LIMIT=10
```

## Environment Files

### Development (.env.development)

```bash
# Database
DATABASE_URL=postgresql://streamscene:dev_password@localhost/streamscene_dev
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=dev-secret-key-not-for-production
API_KEY_SALT=dev-api-key-salt

# OAuth (local Authentik)
OAUTH_CLIENT_ID=streamscene-dev
OAUTH_CLIENT_SECRET=dev-client-secret
OAUTH_AUTHORIZATION_URL=http://localhost:9000/application/o/authorize/
OAUTH_TOKEN_URL=http://localhost:9000/application/o/token/
OAUTH_USERINFO_URL=http://localhost:9000/application/o/userinfo/
OAUTH_REDIRECT_URI=http://localhost:3000/callback

# Application
DOMAIN=localhost
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
ENVIRONMENT=development

# Storage (local paths)
UPLOAD_PATH=./uploads
PROCESSED_PATH=./processed
CACHE_PATH=./cache

# Debug
DEBUG=true
LOG_LEVEL=DEBUG
SQL_ECHO=true
```

### Production (.env.production)

```bash
# Database (production credentials)
DATABASE_URL=postgresql://streamscene:STRONG_PASSWORD@localhost/streamscene
REDIS_URL=redis://localhost:6379/0

# Security (MUST be strong random values)
SECRET_KEY=GENERATE_WITH_openssl_rand_hex_32
API_KEY_SALT=GENERATE_WITH_openssl_rand_hex_16

# OAuth (production Authentik)
OAUTH_CLIENT_ID=streamscene
OAUTH_CLIENT_SECRET=PRODUCTION_CLIENT_SECRET
OAUTH_AUTHORIZATION_URL=https://auth.dataandstories.com/application/o/authorize/
OAUTH_TOKEN_URL=https://auth.dataandstories.com/application/o/token/
OAUTH_USERINFO_URL=https://auth.dataandstories.com/application/o/userinfo/
OAUTH_REDIRECT_URI=https://streamscene.dataandstories.com/callback

# Application (production domain)
DOMAIN=streamscene.dataandstories.com
FRONTEND_URL=https://streamscene.dataandstories.com
BACKEND_URL=https://streamscene.dataandstories.com
ENVIRONMENT=production

# Storage (production paths)
UPLOAD_PATH=/var/lib/streamscene/uploads
PROCESSED_PATH=/var/lib/streamscene/processed
CACHE_PATH=/var/lib/streamscene/cache

# Debug (MUST be false in production)
DEBUG=false
LOG_LEVEL=INFO
SQL_ECHO=false
```

## Security Best Practices

### Generating Secure Keys

```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate API_KEY_SALT
openssl rand -hex 16

# Generate database password
openssl rand -base64 24
```

### File Permissions

```bash
# .env files should NOT be world-readable
chmod 600 .env
chmod 600 .env.production

# Ensure correct ownership
chown streamscene:streamscene .env
```

### Never Commit Secrets

Add to `.gitignore`:
```
.env
.env.*
!.env.example
credentials.json
*.key
*.pem
```

## Loading Environment Variables

### In Python Code

```python
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Access variables
database_url = os.getenv("DATABASE_URL")
secret_key = os.getenv("SECRET_KEY")

# With default value
log_level = os.getenv("LOG_LEVEL", "INFO")
```

### In Reflex Config

```python
# rxconfig.py
import os

config = rx.Config(
    app_name="streamscene",
    backend_host=os.getenv("BACKEND_HOST", "0.0.0.0"),
    backend_port=int(os.getenv("BACKEND_PORT", "8000")),
    frontend_port=int(os.getenv("FRONTEND_PORT", "3000")),
    api_url=os.getenv("BACKEND_URL"),
    deploy_url=os.getenv("FRONTEND_URL"),
)
```

## Validation

### Startup Validation Script

Create `scripts/validate_env.py`:

```python
import os
import sys
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = [
    "DATABASE_URL",
    "REDIS_URL",
    "SECRET_KEY",
    "API_KEY_SALT",
    "OAUTH_CLIENT_ID",
    "OAUTH_CLIENT_SECRET",
    "FRONTEND_URL",
    "BACKEND_URL",
]

missing = [var for var in REQUIRED_VARS if not os.getenv(var)]

if missing:
    print("ERROR: Missing required environment variables:")
    for var in missing:
        print(f"  - {var}")
    sys.exit(1)

print("✓ All required environment variables are set")
```

Run before starting the application:
```bash
python scripts/validate_env.py && reflex run
```

## Troubleshooting

### Common Issues

**"Database connection failed"**
- Check `DATABASE_URL` format: `postgresql://user:password@host:port/dbname`
- Verify PostgreSQL is running: `systemctl status postgresql`
- Test connection: `psql $DATABASE_URL`

**"Redis connection refused"**
- Check `REDIS_URL` format: `redis://host:port/db_number`
- Verify Redis is running: `systemctl status redis`
- Test connection: `redis-cli ping`

**"OAuth authentication failed"**
- Verify OAuth URLs are accessible
- Check client credentials match Authentik configuration
- Ensure redirect URI is whitelisted in Authentik

**"Secret key too short"**
- `SECRET_KEY` must be at least 32 characters
- Generate with: `openssl rand -hex 32`
