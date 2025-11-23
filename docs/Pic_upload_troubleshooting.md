# Picture Upload Troubleshooting

**Date:** 2025-11-23
**Status:** UPLOAD HANDLER NOT BEING CALLED
**User Action:** Selected file, clicked Upload - no errors, but nothing happens

## Current State

### What We Fixed
✅ **WebSocket Connection** - This was the ROOT CAUSE blocking ALL event handlers
- Fixed Nginx proxy configuration at 192.168.1.104 (Nginx Proxy Manager)
- Added `proxy_http_version 1.1;`
- Added `proxy_buffering off;`
- WebSocket errors in browser console are now GONE

### What We Confirmed Working
✅ Event binding works - Test buttons successfully triggered handlers
✅ File selection works - `rx.selected_files("upload1")` displays selected filename
✅ Upload button works - Button click triggers simple handlers
✅ WebSocket is connected and functioning

### Current Problem
❌ **Upload handler is NOT being called when clicking Upload button**
- No `[UPLOAD] Handler called!` logs appear in journal
- No errors shown in UI
- Upload button shows spinner briefly then nothing happens
- Only logs: `[POST_CREATE] No image to preview` (repeating every 2 seconds)

## Code Implementation (Current)

### Handler in `/root/streamscene/streamscene/state/post_creation_state.py`

```python
async def handle_upload(self, files: list[rx.UploadFile]):
    """Handle image upload - proper Reflex async pattern."""
    print("=" * 80)
    print(f"[UPLOAD] Handler called! Files: {len(files) if files else 0}")
    print("=" * 80)

    if not files:
        print("[UPLOAD] No files provided")
        self.error_message = "No file selected"
        return

    file = files[0]
    print(f"[UPLOAD] Processing: {file.filename}")

    self.is_uploading_image = True
    self.error_message = ""
    yield

    try:
        # Read file data
        upload_data = await file.read()
        print(f"[UPLOAD] Read {len(upload_data)} bytes")

        # Validate image
        img = Image.open(io.BytesIO(upload_data))
        img.verify()
        print(f"[UPLOAD] Image valid!")

        # Save to upload directory
        outfile = rx.get_upload_dir() / file.filename
        outfile.write_bytes(upload_data)
        print(f"[UPLOAD] Saved to {outfile}")

        # Store filename and generate preview
        self.uploaded_files = [file.filename]
        self.image_preview_url = rx.get_upload_url(file.filename)

        print(f"[UPLOAD] SUCCESS! Preview: {self.image_preview_url}")
        logger.info(f"[POST_CREATE] Upload complete: {file.filename}")

    except Exception as e:
        print(f"[UPLOAD] Error: {e}")
        self.error_message = f"Upload failed: {str(e)}"
        self.uploaded_files = []

    finally:
        self.is_uploading_image = False
        yield
```

### UI in `/root/streamscene/streamscene/components/post_creator/picture_form.py`

```python
rx.upload(
    rx.vstack(
        rx.button("Select Image", size="3"),
        rx.text("Drag and drop or click to select", size="2", color="gray"),
    ),
    id="upload1",
    border="2px dashed var(--gray-6)",
    padding="3em",
    border_radius="8px",
    accept={
        "image/png": [".png"],
        "image/jpeg": [".jpg", ".jpeg"],
        "image/webp": [".webp"],
    },
    max_files=1,
    max_size=5_000_000,
),
# Debug: Show selected files
rx.vstack(
    rx.text("Selected files:", weight="bold", size="2"),
    rx.foreach(
        rx.selected_files("upload1"),
        lambda filename: rx.text(f"- {filename}", color="green"),
    ),
    spacing="1",
),
rx.button(
    "Upload",
    on_click=state.handle_upload(
        rx.upload_files(upload_id="upload1")
    ),
    size="3",
    loading=state.is_uploading_image,
),
```

## Nginx Configuration (Fixed)

**File:** Nginx Proxy Manager Advanced config for streamscene.dataandstories.com

```nginx
# WebSocket support for Reflex
location /_event/ {
    proxy_pass http://192.168.1.118:8000;
    proxy_http_version 1.1;  # Required for WebSocket

    # WebSocket headers
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Long timeouts for WebSocket
    proxy_read_timeout 86400;
    proxy_send_timeout 86400;

    # Disable buffering for WebSockets
    proxy_buffering off;  # Critical addition
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

## Next Troubleshooting Steps

### 1. Check Browser Console for Errors
- Open browser DevTools (F12)
- Go to Console tab
- Try uploading a file
- Look for:
  - JavaScript errors
  - WebSocket messages
  - Network errors in Network tab
- **IMPORTANT:** Check if `rx.upload_files()` is actually sending files to the handler

### 2. Test Simplified Handler (No File Processing)

Try replacing the handler with this minimal version to see if it's called at all:

```python
async def handle_upload(self, files: list[rx.UploadFile]):
    """Minimal test handler."""
    print("=" * 80)
    print("[UPLOAD] HANDLER WAS CALLED!")
    print(f"[UPLOAD] Files received: {files}")
    print(f"[UPLOAD] Files type: {type(files)}")
    print(f"[UPLOAD] Files length: {len(files) if files else 'None'}")
    print("=" * 80)

    self.error_message = f"Handler called! Files: {len(files) if files else 0}"
    yield
```

Restart: `sudo systemctl restart reflex && sleep 4`

### 3. Check Reflex Version and Upload Pattern

Verify Reflex version:
```bash
source venv/bin/activate
python -c "import reflex; print(reflex.__version__)"
```

Current version: **0.8.17**

Check if there are known issues with `rx.upload_files()` in this version:
- Check Reflex GitHub issues
- Check Reflex Discord
- Review Reflex 0.8.17 changelog

### 4. Try Alternative Upload Pattern

According to Reflex docs, there might be a different pattern needed. Try:

**Option A - Without upload_id in button:**
```python
rx.button(
    "Upload",
    on_click=rx.upload_files(),  # No upload_id parameter
    size="3",
    loading=state.is_uploading_image,
),
```

**Option B - Separate handler for upload completion:**
```python
# In state:
def handle_upload_complete(self, files: list[rx.UploadFile]):
    """Called when upload completes."""
    print(f"[UPLOAD] Upload complete! Files: {files}")
    # Process files...

# In UI:
rx.upload(
    ...,
    id="upload1",
    on_drop=state.handle_upload_complete(rx.upload_files()),  # Try on_drop
)
```

**Option C - Manual form submission:**
```python
# Try wrapping in a form and using on_submit
rx.form(
    rx.upload(...),
    rx.button("Upload", type="submit"),
    on_submit=state.handle_upload(rx.upload_files(upload_id="upload1")),
)
```

### 5. Check Upload Directory Permissions

```bash
# Check if upload directory exists and is writable
ls -la /root/streamscene/uploaded_files/
# Should show drwxr-xr-x with reflex user as owner
```

### 6. Enable Reflex Debug Mode

Add to `rxconfig.py`:
```python
config = rx.Config(
    app_name="streamscene",
    loglevel="debug",  # Add this
)
```

Restart and check logs for more details.

### 7. Test with Reflex CLI Example

Create a minimal test file to verify upload works at all:

```python
# test_upload.py
import reflex as rx

class UploadTestState(rx.State):
    async def handle_upload(self, files: list[rx.UploadFile]):
        print("=" * 80)
        print(f"[TEST] Handler called! Files: {len(files)}")
        print("=" * 80)

def index():
    return rx.vstack(
        rx.upload(
            rx.button("Select File"),
            id="test-upload",
        ),
        rx.button(
            "Upload",
            on_click=UploadTestState.handle_upload(
                rx.upload_files(upload_id="test-upload")
            ),
        ),
    )

app = rx.App()
app.add_page(index)
```

Run: `reflex run test_upload.py`

If this works, the issue is with our implementation. If this doesn't work, it's a Reflex configuration issue.

## What We've Already Tried

### ❌ Failed Approaches (Session 1 - Previous)

1. **JavaScript FileReader approach** - `rx.call_script()` callbacks don't work reliably
2. **Manual directory reading** - Files aren't uploaded to server until `rx.upload_files()` is called
3. **Different handler signatures** - Tried `def` vs `async def`, `list[str]` vs `list[rx.UploadFile]`
4. **State binding fixes** - Changed `PostCreationState.handle_upload` to `state.handle_upload`

### ❌ Failed Approaches (Session 2 - Current - 2025-11-23)

5. **Removed yield from async handler** - Removed both `yield` statements (lines 327, 358) from async handler
   - Rationale: Official Reflex pattern uses async/await WITHOUT yield
   - Result: Files still upload (XHR to /_upload succeeds) but handler never called
   - Evidence: `XHR finished loading: POST "/_upload"` in browser console, no logs in journalctl

6. **Moved handler to on_drop with rx.upload_files()** - Changed from button `on_click` to upload `on_drop`
   - Pattern tried: `on_drop=state.handle_upload(rx.upload_files(upload_id="upload1"))`
   - Rationale: Official docs show on_drop as primary pattern for file uploads
   - Result: Still nothing happens, handler never called
   - Evidence: No logs appear when selecting/dropping files

### 🔄 Currently Trying (Attempt #7)

7. **Remove rx.upload_files() from on_drop** - Use direct handler reference
   - Pattern: `on_drop=state.handle_upload` (no rx.upload_files wrapper)
   - Rationale: Official docs show on_drop passes files automatically, rx.upload_files() only for button clicks
   - Status: TESTING...

### ✅ What Fixed Earlier Issues

1. **WebSocket configuration** - Fixed Nginx proxy (this was THE breakthrough)
2. **Auto-dismiss success message** - Added 5-second timer (working)

## Environment Info

- **Reflex Version:** 0.8.17
- **Python Version:** (check with `python --version`)
- **Server:** LXC container at 192.168.1.118 (Debian 12, 4 cores, 4GB RAM)
- **Proxy:** Nginx Proxy Manager at 192.168.1.104
- **Domain:** streamscene.dataandstories.com
- **Backend:** http://0.0.0.0:8000
- **Frontend:** http://0.0.0.0:3000

## Key Questions to Answer

1. **Is the handler being called at all?** → NO (no logs appear)
2. **Is `rx.upload_files()` working correctly?** → UNKNOWN (need browser console check)
3. **Are files being sent to the backend?** → UNKNOWN (check Network tab)
4. **Is WebSocket connection stable during upload?** → Appears YES (no errors in console)
5. **Is there a Reflex version-specific issue?** → UNKNOWN (need to research)

## Useful Commands

```bash
# Restart service
sudo systemctl restart reflex && sleep 4

# Watch logs live
sudo journalctl -u reflex -f

# Check recent logs
sudo journalctl -u reflex -n 100 --no-pager

# Search for upload logs
sudo journalctl -u reflex -n 500 --no-pager | grep -i upload

# Check Reflex version
source venv/bin/activate
python -c "import reflex; print(reflex.__version__)"

# Check upload directory
ls -la /root/streamscene/uploaded_files/
```

## Session History Summary

This was an EXTENSIVE debugging session that went through:
1. Standard Reflex `rx.upload()` pattern - handler never called
2. JavaScript FileReader with `rx.call_script()` - callbacks broken
3. Manual directory reading - files not uploaded yet
4. **BREAKTHROUGH:** Discovered WebSocket failures in browser console
5. Fixed Nginx proxy configuration for WebSocket support
6. Reverted to proper Reflex async handler pattern
7. **CURRENT STATE:** Handler still not being called despite WebSocket fix

The user tried uploading after the latest restart and reported:
- No errors appeared
- Upload didn't work
- Nothing visible happened

## Resources

- [Reflex File Upload Docs](https://reflex.dev/docs/library/forms/upload/)
- [Reflex GitHub Issues](https://github.com/reflex-dev/reflex/issues)
- [Reflex Discord](https://discord.gg/reflex)
- Nginx Proxy Manager: http://192.168.1.104:81

---

**Next session:** Start with Step 1 (check browser console) and Step 2 (simplified handler test).
