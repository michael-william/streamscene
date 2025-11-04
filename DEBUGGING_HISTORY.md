# StreamScene Debugging History

This document tracks debugging attempts and solutions for recurring issues. Use this to avoid repeating failed approaches.

---

## Issue: "No stream specified" Error on Stream Posts Page

**Date:** November 4, 2025
**Status:** 🔄 IN PROGRESS - Testing on_load() solution
**File:** `streamscene/pages/stream_posts.py`

### Problem Description

When navigating to `/stream-posts?id={uuid}`, users see "No stream specified" error message, even though they can create posts (indicating the stream eventually loads).

### Root Cause

Router query parameters (`self.router.page.params.get("id", "")`) are not reliably populated during component lifecycle methods.

---

### Attempt #1: Dynamic Routes with Slugs ❌ FAILED

**Approach:** Used dynamic route `/streams/[slug]` to access streams by readable slug instead of UUID.

**Implementation:**
- Route: `app.add_page(stream_posts_page, route="/streams/[slug]")`
- Access via: `self.slug` (auto-populated by Reflex)
- Database: Added `slug` field to streams, created migration

**Result:** FAILED

**Errors:**
```
DynamicRouteArgShadowsStateVarError: Dynamic route arg 'slug' is shadowing
an existing var in streamscene.pages.stream_posts.StreamPostsState
```

**Why it failed:**
- Reflex auto-creates state variables for dynamic route params
- Manually defining `slug: str = ""` conflicts with Reflex's auto-generated var
- Removing manual definition still resulted in empty slug during lifecycle methods
- Timing issues with when Reflex populates the auto-generated slug variable

**Lessons Learned:**
- Don't manually define state variables for dynamic route parameters
- Dynamic route parameters have same timing issues as query parameters
- Reflex's auto-population of route vars is not reliable in early lifecycle methods

---

### Attempt #2: Query Parameters with on_mount() ❌ FAILED

**Approach:** Switch to query parameters `/stream-posts?id={uuid}` using `on_mount()` lifecycle.

**Implementation:**
- Route: `app.add_page(stream_posts_page, route="/stream-posts")`
- Access via: `self.router.page.params.get("id", "")`
- Lifecycle: `on_mount()` method
- Links updated to: `href=f"/stream-posts?id={stream['id']}"`

**Result:** FAILED

**Server Logs:**
```
DeprecationWarning: RouterData.page has been deprecated in version 0.8.1.
Use RouterData.url instead.
[STREAM_POSTS] on_mount called
[STREAM_POSTS] stream_id from query params: ''
```

**Why it failed:**
- `on_mount()` is component-level, fires before router params are populated
- `router.page.params.get("id", "")` returns empty string
- Error message shown: "No stream specified"
- Posts can be created later (suggesting stream eventually loads via re-renders)

**Lessons Learned:**
- `on_mount()` is too early in lifecycle for router param access
- `router.page` API shows deprecation warnings (though still functional)
- Component-level lifecycle doesn't guarantee router state

---

### Attempt #3: Query Parameters with on_load() 🔄 TESTING

**Approach:** Use `on_load()` (page-level) instead of `on_mount()` (component-level).

**Implementation:**
```python
def on_load(self):
    """Load stream and posts when page loads."""
    # Clear previous errors
    self.error_message = ""

    # Method 1: router.page.params
    stream_id = self.router.page.params.get("id", "")

    # Method 2: Fallback to client_query_params (from callback.py pattern)
    if not stream_id:
        query_params = self.router.session.client_query_params
        stream_id = query_params.get("id", [""])[0] if query_params else ""

    if not stream_id:
        self.error_message = "No stream specified"
        return

    yield from self.load_stream_and_posts(stream_id)
```

**Rationale:**
- `callback.py` uses `on_load()` successfully with query params
- `on_load()` is page-level, should fire AFTER router is initialized
- Dual-method approach provides fallback robustness

**Expected Result:** Query parameters should be available in `on_load()`

**Testing Steps:**
1. Navigate to `/streams`
2. Click "View Posts" on any stream
3. Check server logs for populated stream_id
4. Verify no "No stream specified" error
5. Verify posts load correctly

**Status:** Testing in progress...

---

## Working Patterns (Reference)

### ✅ callback.py OAuth Flow (WORKING)

**File:** `streamscene/pages/callback.py`

```python
def on_load(self):
    """Called when the page loads - extract code from URL and process."""
    # Primary method
    code = self.router.page.params.get("code", "") if hasattr(self.router.page, "params") else ""

    # Fallback method
    if not code:
        query_params = self.router.session.client_query_params
        code = query_params.get("code", [""])[0] if query_params else ""

    # Process the code...
```

**Why it works:**
- Uses `on_load()` not `on_mount()`
- Has fallback to `client_query_params`
- Page-level lifecycle ensures router is ready

---

## Reflex Version Info

- **Current Version:** 0.8.17 (as of November 2025)
- **Relevant APIs:**
  - `self.router.page.params` - Access query string parameters
  - `self.router.session.client_query_params` - Alternative query param access (returns lists)
  - `on_load()` - Page-level lifecycle method
  - `on_mount()` - Component-level lifecycle method
- **Deprecation Notes:**
  - `RouterData.page` shows deprecation warnings but still functional
  - Recommended to use `RouterData.url` in future versions

---

## Decision Log

### Why Query Parameters Over Dynamic Routes?

**Decision:** Use `/stream-posts?id={uuid}` instead of `/streams/[slug]`

**Reasoning:**
1. Users click buttons, not type URLs - UX doesn't require pretty URLs
2. Direct UUID lookup is simpler than slug→stream lookup
3. Query params have proven pattern in callback.py
4. Eliminates need for slug generation and uniqueness logic
5. Avoids timing issues with Reflex's dynamic route parameter auto-population

### Why on_load() Over on_mount()?

**Decision:** Use `on_load()` for pages that need router params

**Reasoning:**
1. `on_load()` is page-level, `on_mount()` is component-level
2. callback.py successfully uses `on_load()` for OAuth query params
3. Page-level lifecycle runs after router is fully initialized
4. Reflex documentation suggests `on_load()` for page initialization

---

## Next Steps if on_load() Fails

If `on_load()` still shows empty query params:

1. **Try @rx.var Computed Property:**
   ```python
   @rx.var
   def stream_id(self) -> str:
       return self.router.page.params.get("id", "")
   ```

2. **Check Reflex Version:** Ensure we're on latest stable release

3. **Alternative Router Access:** Try `self.router.url` (new API)

4. **WebSocket State Issues:** Query params might not sync over WebSocket properly

5. **Consider Reflex Bug:** File GitHub issue if none of the above work

---

## Useful Commands

```bash
# Check Reflex version
pip show reflex

# View server logs in real-time
tail -f /root/streamscene/.web/reflex.log

# Restart server cleanly
./restart-reflex.sh

# Test specific URL with curl
curl -v "https://streamscene.dataandstories.com/stream-posts?id=4ffed4d7-d1df-4bf9-bd57-0a5df5f52874"
```

---

**Last Updated:** November 4, 2025
**Next Review:** After testing on_load() solution
