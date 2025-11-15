# Common Gotchas & Best Practices

Comprehensive list of common pitfalls and their solutions, organized by category.

## Architecture & Design Patterns

### 1. Don't Bypass Business Logic

**Problem:** Duplicating logic in UI or API layers instead of using core functions.

**Solution:** Always call functions in `core/`, never duplicate logic in `ui/` or `api/`.

```python
# ❌ WRONG - Duplicating logic in UI
def create_stream_button_click(self):
    stream = Stream(name=self.name, owner_id=self.user_id)
    session.add(stream)
    session.commit()

# ✅ CORRECT - Using core business logic
def create_stream_button_click(self):
    from streamscene.core.streams import create_stream
    stream = create_stream(session, self.user_id, self.name, self.description)
```

### 2. Pre-Process Images Server-Side

**Problem:** Processing images on Raspberry Pi Zero (limited CPU).

**Solution:** Pre-process images on server before sending to device.

- Resize to exactly 800x480 pixels
- Cache processed images
- Client renders text/layout to RGB images
- **Waveshare driver automatically handles 7-color palette conversion and dithering** (optimized C code)

## Security

### 3. API Keys Must Be Hashed

**Problem:** Storing plaintext API keys in database.

**Solution:** Always hash API keys with bcrypt before storing.

```python
# ❌ WRONG - Plaintext storage
device.api_key = generated_key

# ✅ CORRECT - Hashed storage
import bcrypt
device.api_key = bcrypt.hashpw(generated_key.encode(), bcrypt.gensalt()).decode()
```

**Note:** Plaintext key is only exposed:
- In registration response to web user (shown once with warning)
- In one-time retrieval by device via `/registration-status`

## Database & ORM

### 4. Use UUIDs Everywhere

**Problem:** Using integer IDs for primary keys.

**Solution:** All primary keys are UUIDs, not integers.

```python
# ❌ WRONG
device_id = 123

# ✅ CORRECT
from uuid import UUID
device_id = UUID("550e8400-e29b-41d4-a716-446655440000")
```

### 5. Use Alembic for Schema Changes

**Problem:** Running manual SQL DDL commands.

**Solution:** Use Alembic for all schema changes.

```bash
# Create migration
alembic revision --autogenerate -m "add new field"

# Review migration file
# Edit if needed

# Apply migration
alembic upgrade head
```

## Reflex Framework

### 6. Reflex Session is Read-Only

**Problem:** Trying to assign values to `router.session`.

**Solution:** Use `rx.Cookie()` State variables for authentication.

```python
# ❌ WRONG - router.session is read-only
self.router.session.client_token["user_id"] = user_id

# ✅ CORRECT - Use Cookie State variable
class AuthState(rx.State):
    user_id: str = rx.Cookie("")

    def login(self, user_id):
        self.user_id = user_id  # Auto-synced to browser cookie
```

### 7. No Intermediate Login Page

**Problem:** Creating `/login` page that initializes WebSocket before redirect.

**Solution:** Link directly to OAuth URL from index page to avoid WebSocket initialization issues.

```python
# ❌ WRONG - Intermediate page with WebSocket issues
@rx.page(route="/login")
def login_page():
    return rx.redirect(oauth_url)  # WebSocket already initialized!

# ✅ CORRECT - Direct link from index
def index_page():
    return rx.link("Sign In", href=oauth_url)  # No WebSocket initialization
```

### 8. Reflex on_mount Must Be Connected AND Use yield from

**Problem:** Lifecycle methods don't execute or state updates don't render.

**Solution:** Must BOTH pass to component AND use `yield from` for generators.

```python
# ❌ WRONG - Method not connected
def index_page():
    return rx.container(...)  # on_mount not passed!

# ❌ WRONG - Not using yield from
def on_mount(self):
    self.load_data()  # Generator not yielded!

# ✅ CORRECT - Connected AND yielded
class MyState(rx.State):
    def on_mount(self):
        yield from self.load_data()  # Yields to trigger UI updates

def index_page():
    return rx.container(..., on_mount=MyState.on_mount)
```

### 9. Use on_load for Router Params, Not on_mount

**Problem:** `on_mount()` fires before `router.page.params` is populated.

**Solution:** Use method named `on_load()` to access router params reliably.

```python
# ❌ WRONG - Params not populated yet
def on_mount(self):
    device_id = self.router.page.params.get("id", "")  # Empty!

# ✅ CORRECT - Use on_load for router params
def on_load(self):
    device_id = self.router.page.params.get("id", "")  # Populated!

# Trigger with on_mount parameter
rx.container(..., on_mount=MyState.on_load)
```

### 10. Query Params vs Dynamic Routes

**Problem:** Dynamic routes have timing issues and auto-creation conflicts.

**Solution:** Use query params for UUID lookups (more reliable).

```python
# ❌ LESS RELIABLE - Dynamic route
@rx.page(route="/device/[id]")
def device_page():
    device_id = MyState.router.page.params.get("id")

# ✅ MORE RELIABLE - Query param
@rx.page(route="/device")
def device_page():
    # Access via: /device?id=uuid
    device_id = MyState.router.page.params.get("id", "")
```

### 11. Use Fallback Pattern for Router Params

**Problem:** Router params not always accessible.

**Solution:** Use fallback pattern from callback.py.

```python
# ✅ CORRECT - Robust fallback pattern
def get_param(self, key: str) -> str:
    # Primary method
    param = self.router.page.params.get(key, "") if hasattr(self.router.page, "params") else ""

    # Fallback for edge cases
    if not param:
        query_params = self.router.session.client_query_params
        param = query_params.get(key, [""])[0] if query_params else ""

    return param
```

### 12. Component Event Trigger Limitations

**Problem:** Not all components support all events.

**Solution:** Always trigger lifecycle via `on_mount` parameter, even if method is named `on_load`.

```python
# ❌ WRONG - rx.container doesn't support on_load event
rx.container(..., on_load=MyState.on_load)
# Error: "The Container does not take in an `on_load` event trigger"

# ✅ CORRECT - Use on_mount parameter
rx.container(..., on_mount=MyState.on_load)
```

### 13. Reflex Var Compatibility

**Problem:** Using Python `if`, `and`, `or`, `not` directly on Reflex Vars.

**Solution:** Use `rx.cond()` for conditional rendering.

```python
# ❌ WRONG - Python if doesn't work with Vars
if text.strip():
    return rx.text(text)
# Error: VarTypeError: Cannot convert Var to bool

# ✅ CORRECT - Use rx.cond()
return rx.cond(
    text,  # Condition (works with Vars)
    rx.text(text),  # If truthy
    rx.text("Empty")  # If falsy
)
```

**Reference:** See `streamscene/components/eink/content_renderers.py` for working examples.

## Device & Hardware

### 14. Respect E Ink Timing

**Problem:** Rotating content too fast for E Ink refresh.

**Solution:** Never rotate content faster than 60 seconds (30s refresh + buffer).

### 15. WebSocket Heartbeat Required

**Problem:** WebSocket connections timing out.

**Solution:** Devices must ping every 30 seconds or connection times out.

```python
# Device client must send heartbeat
async def heartbeat_loop():
    while connected:
        await websocket.send({"type": "heartbeat"})
        await asyncio.sleep(30)
```

### 16. WiFi Adapter Mode Conflicts (Raspberry Pi)

**Problem:** Single WiFi adapter can only be in ONE mode (AP or client).

**Solution:** Must stop and mask services before mode switch.

```python
# Before creating hotspot
subprocess.run(["systemctl", "stop", "wpa_supplicant"], timeout=10)
subprocess.run(["systemctl", "mask", "wpa_supplicant"], timeout=10)

# Before connecting as client
subprocess.run(["systemctl", "stop", "hostapd"], timeout=10)
subprocess.run(["systemctl", "stop", "dnsmasq"], timeout=10)
subprocess.run(["systemctl", "unmask", "wpa_supplicant"], timeout=10)
```

**Symptom:** Hotspot not visible or client won't connect = both services running simultaneously.

### 17. systemd Command Timeouts Are Critical

**Problem:** Ctrl+C can cause Pi to hang indefinitely on `systemctl stop`.

**Solution:** ALWAYS add timeout parameter to subprocess.run() for systemd commands.

```python
# ❌ WRONG - No timeout
subprocess.run(["systemctl", "stop", "wpa_supplicant"])

# ✅ CORRECT - With timeout
subprocess.run(["systemctl", "stop", "wpa_supplicant"], timeout=10, check=False)
```

Use `check=False` for cleanup operations (don't fail if service already stopped).

### 18. Manual wpa_supplicant Startup vs systemd Service

**Problem:** systemd wpa_supplicant service doesn't read config file by default.

**Solution:** Manual startup required.

```bash
# ❌ WRONG - Doesn't read config
systemctl start wpa_supplicant

# ✅ CORRECT - Manual startup with config
wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf
```

Verify connection:
```bash
wpa_cli -i wlan0 status  # Look for wpa_state=COMPLETED
```

### 19. Deploy to Pi Workflow

**Problem:** Manual deployment is error-prone.

**Solution:** Use automated deployment with sshpass.

```bash
# Automated deployment
sshpass -p 'password' scp -r client/ user@host:~/streamscene-client/

# Ethernet connection recommended for testing
# Maintains SSH during WiFi mode switching

# Always test WiFi setup end-to-end after deployment

# Reset test
rm ~/streamscene-client/wifi_credentials.json
sudo python3 ~/streamscene-client/test_wifi_setup.py
```

## Deployment & Infrastructure

### 20. Nginx Cross-Container Routing

**Problem:** Using 127.0.0.1 for proxy targets in multi-container setup.

**Solution:** Use container IP (192.168.1.118), not 127.0.0.1.

```nginx
# ❌ WRONG - localhost doesn't work across containers
proxy_pass http://127.0.0.1:8000;

# ✅ CORRECT - Use container IP
proxy_pass http://192.168.1.118:8000;
```

### 21. Port Conflicts on Restart

**Problem:** Old Reflex processes holding ports 3000/8000.

**Solution:** Use `./restart-reflex.sh` to cleanly kill processes by port.

```bash
# Don't just kill by name
# Use restart script instead
./restart-reflex.sh
```

The script:
- Finds processes by port (3000 and 8000)
- Kills them gracefully
- Verifies ports are free
- Clears Python cache
- Starts fresh instance

### 22. Cache Authentik User Data

**Problem:** Too many OAuth API calls to Authentik.

**Solution:** Reduce OAuth API calls with Redis caching.

```python
# Cache user info for 1 hour
cache_key = f"user_info:{user_id}"
user_info = redis.get(cache_key)

if not user_info:
    user_info = fetch_from_authentik(user_id)
    redis.setex(cache_key, 3600, json.dumps(user_info))
```

## Debugging

### Document Complex Debugging

**Problem:** Repeating failed approaches in future sessions.

**Solution:** For issues requiring multiple attempts, create debugging documentation.

Create `DEBUGGING_HISTORY.md` with:
- What was tried
- Why it failed
- Server logs
- Lessons learned
- Final solution

**Example:** See existing DEBUGGING_HISTORY.md for router params timing issues.

## Testing & Quality

### Write Tests in Core

**Problem:** Untested business logic leads to bugs.

**Solution:** Write tests for all `core/` functions.

```python
# tests/test_streams.py
def test_create_stream():
    stream = create_stream(session, user_id, "Test", "Description")
    assert stream.name == "Test"
    assert stream.owner_id == user_id
```

Run tests:
```bash
pytest
pytest --cov=streamscene --cov-report=html
```
