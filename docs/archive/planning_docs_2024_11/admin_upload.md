# Admin Backgrounds Management Interface - Implementation Plan

**Status:** Planning Phase
**Created:** 2025-11-24
**Purpose:** Admin interface to manage Meme It background images

---

## Overview

Create `/admin/backgrounds` page to manage background images for the "Meme It" feature with full CRUD operations (Create, Read, Update, Delete).

---

## Current System Architecture

### Database Schema
**Table:** `background_images`
- `id: UUID` - Primary key
- `filename: str` - Background image filename (unique, indexed)
- `display_name: str` - Human-readable name (e.g., "Blue to Purple")
- `is_active: bool` - Whether background is available for use
- `sort_order: int` - Display order in UI
- `created_at: datetime` - Creation timestamp

### File Storage
- **Location:** `/root/streamscene/backgrounds/`
- **Format:** PNG files (800x480px recommended)
- **Current count:** 13 default backgrounds

### Existing Functions
**File:** `streamscene/core/backgrounds.py`
- `get_all_backgrounds(db, active_only=True)` - List backgrounds
- `get_background_by_filename(db, filename)` - Lookup by filename
- `get_background_path(filename)` - Get filesystem path
- `create_background(db, filename, display_name, is_active, sort_order)` - Add new
- `update_background(db, background_id, ...)` - Update existing
- `delete_background(db, background_id)` - Remove from DB (keeps file)
- `seed_default_backgrounds(db)` - Scan filesystem and add to DB

### Current User-Facing UI
**Component:** `streamscene/components/post_creator/background_selector.py`
- Grid layout (3-6 columns responsive)
- 80px thumbnail previews
- Shows active backgrounds only
- Used in Meme It post creation

---

## Implementation Plan

### 1. Create Admin State Class

**File:** `streamscene/pages/admin_backgrounds.py`

**State Variables:**
```python
class BackgroundsAdminState(BaseState):
    state_auto_setters = True

    # List data
    backgrounds: List[dict] = []

    # Loading states
    is_loading: bool = False
    is_uploading: bool = False
    is_saving: bool = False
    is_deleting: bool = False

    # Messages
    error_message: str = ""
    success_message: str = ""

    # Modal states
    is_add_modal_open: bool = False
    is_edit_modal_open: bool = False
    is_delete_modal_open: bool = False

    # Form fields (Add/Edit)
    edit_background_id: str = ""
    form_display_name: str = ""
    form_sort_order: int = 0
    form_is_active: bool = True

    # Upload state
    uploaded_filename: str = ""
    upload_preview_url: str = ""
```

**Methods:**
```python
def on_mount(self):
    """Load backgrounds on page load."""
    if redirect := self.require_auth():
        return redirect
    yield from self.load_backgrounds()

def load_backgrounds(self):
    """Fetch all backgrounds from database (including inactive)."""
    # Call get_all_backgrounds(db, active_only=False)

def open_add_modal(self):
    """Open modal to add new background."""

def open_edit_modal(self, background_id: str):
    """Open modal to edit background."""

def open_delete_modal(self, background_id: str):
    """Open modal to delete background."""

def handle_upload_success(self, filename: str, url: str):
    """Called after file upload completes."""
    # Copy file from uploads → backgrounds directory
    # Store filename for later save

def save_new_background(self):
    """Create new background in database."""
    # Call create_background()
    # Copy uploaded file to backgrounds dir
    # Reload list

def save_edit_background(self):
    """Update existing background."""
    # Call update_background()
    # Reload list

def toggle_active(self, background_id: str):
    """Quick toggle active status."""
    # Call update_background() with flipped is_active

def confirm_delete(self):
    """Delete background from database."""
    # Call delete_background()
    # NOTE: Keeps file on disk for historical posts

def reseed_from_filesystem(self):
    """Scan filesystem and add any missing backgrounds."""
    # Call seed_default_backgrounds()
```

---

### 2. Core Features

#### List View (Grid Display)
- **Layout:** Responsive grid (3-6 columns based on screen size)
- **Card Content:**
  - Thumbnail preview (100x100px)
  - Display name
  - Active status badge (green "Active" / gray "Inactive")
  - Sort order number
  - Action buttons: Edit, Toggle Active, Delete
- **Header:**
  - "Background Images" title
  - "Add Background" button (primary action)
  - "Refresh" button
  - "Reseed from Filesystem" button (secondary action)
- **Feedback:**
  - Success callout (green, auto-dismiss after 5s)
  - Error callout (red, stays until dismissed)
  - Loading spinner during data fetch

#### Add New Background
**Modal Dialog:**
- Title: "Add Background Image"
- Fields:
  1. **File Upload:**
     - Reuse JavaScript upload handler from picture_form.py
     - Upload to `/api/custom-upload` endpoint
     - Show preview after upload
     - Accept PNG only
     - 5MB max size
  2. **Display Name:**
     - Text input (required)
     - Placeholder: "e.g., Blue Gradient"
     - Max 50 characters
  3. **Active:**
     - Checkbox (default: checked)
     - Label: "Make available immediately"
  4. **Sort Order:**
     - Auto-assigned (max + 1)
     - Can be edited later
- Buttons:
  - "Save Background" (primary, disabled until file uploaded)
  - "Cancel" (secondary)

**Flow:**
1. User clicks "Add Background" button
2. Modal opens with empty form
3. User uploads file → preview appears
4. User enters display name
5. User clicks "Save Background"
6. Backend:
   - Copy file: `.web/build/client/uploads/{uuid}.png` → `backgrounds/{uuid}.png`
   - Create DB record: `create_background(db, uuid.png, display_name, is_active=True, sort_order)`
   - Delete temp file from uploads
7. Modal closes, success message shown
8. List refreshes with new background

#### Edit Background
**Modal Dialog:**
- Title: "Edit Background"
- Fields:
  1. **Filename:** (read-only, display only)
  2. **Display Name:** (editable text input)
  3. **Sort Order:** (number input, min: 0)
  4. **Active:** (checkbox)
- Buttons:
  - "Save Changes" (primary)
  - "Cancel" (secondary)
- Note: Cannot change filename (would break existing posts)

**Flow:**
1. User clicks "Edit" button on background card
2. Modal opens with pre-filled values
3. User modifies fields
4. User clicks "Save Changes"
5. Backend calls `update_background()`
6. Modal closes, success message shown
7. List refreshes

#### Delete Background
**Confirmation Modal:**
- Title: "Delete Background?"
- Message: "This will remove '[Display Name]' from the list. The image file will be kept on disk for existing posts that use it."
- Warning: If background is used in any posts, show count: "⚠️ Used in 5 posts"
- Buttons:
  - "Delete" (danger, red)
  - "Cancel" (secondary)

**Flow:**
1. User clicks "Delete" button on background card
2. Confirmation modal opens
3. User confirms deletion
4. Backend calls `delete_background()` (removes DB record only)
5. File stays on disk at `/root/streamscene/backgrounds/{filename}`
6. Modal closes, success message shown
7. List refreshes

#### Toggle Active Status
**Quick Action:**
- Single button click (no modal)
- Icon changes: ✓ Active → × Inactive
- Immediately updates database
- Shows brief success message
- Useful for temporarily hiding backgrounds

**Use Case:**
- Disable seasonal backgrounds without deleting
- Hide backgrounds during testing
- Quick enable/disable without full edit modal

#### Reseed from Filesystem
**Batch Operation:**
- Scans `/root/streamscene/backgrounds/` directory
- Finds PNG files not in database
- Adds them with default settings:
  - Display name: filename without extension
  - Active: true
  - Sort order: auto-assigned
- Shows count of new backgrounds added
- Useful after manually copying files to server

---

### 3. File Upload Flow

**Reuse Existing Infrastructure:**
1. Use JavaScript upload handler from `picture_form.py`
2. POST to `/api/custom-upload` endpoint (already exists)
3. File saved to: `.web/build/client/uploads/{uuid}.png`
4. JavaScript updates hidden inputs → triggers Reflex state sync
5. `handle_upload_success()` called with filename and URL

**After Upload (on Save):**
```python
import shutil
from pathlib import Path

def save_new_background(self):
    # Copy uploaded file to backgrounds directory
    source = Path(f".web/build/client/uploads/{self.uploaded_filename}")
    dest = Path(f"/root/streamscene/backgrounds/{self.uploaded_filename}")
    shutil.copy(source, dest)

    # Create database record
    with get_db_session() as session:
        create_background(
            session,
            filename=self.uploaded_filename,
            display_name=self.form_display_name,
            is_active=self.form_is_active,
            sort_order=self._get_next_sort_order(session)
        )
        session.commit()

    # Delete temp file
    source.unlink()

    # Reload and show success
    yield from self.load_backgrounds()
    self.success_message = "Background added successfully!"
```

---

### 4. UI Layout

**Page Structure:**
```
┌─────────────────────────────────────────────────────┐
│ Background Images                    [Add Background]│
│ [Refresh] [Reseed from Filesystem]                   │
├─────────────────────────────────────────────────────┤
│ ✓ Success: Background added successfully!           │ (auto-dismiss)
├─────────────────────────────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│ │[Preview]│ │[Preview]│ │[Preview]│ │[Preview]│   │
│ │  White  │ │  Black  │ │  Blue   │ │  Red    │   │
│ │ ✓Active │ │ ✓Active │ │ ✗Inactive│ │ ✓Active │   │
│ │ Sort: 0 │ │ Sort: 1 │ │ Sort: 2 │ │ Sort: 3 │   │
│ │[Edit][×]│ │[Edit][×]│ │[Edit][×]│ │[Edit][×]│   │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐               │
│ │[Preview]│ │[Preview]│ │[Preview]│               │
│ │  Green  │ │ Purple  │ │ Orange  │               │
│ │ ✓Active │ │ ✓Active │ │ ✓Active │               │
│ │ Sort: 4 │ │ Sort: 5 │ │ Sort: 6 │               │
│ │[Edit][×]│ │[Edit][×]│ │[Edit][×]│               │
│ └─────────┘ └─────────┘ └─────────┘               │
└─────────────────────────────────────────────────────┘
```

**Responsive Breakpoints:**
- Mobile (< md): 2 columns
- Tablet (md): 3 columns
- Desktop (lg): 4 columns
- Wide (xl): 6 columns

**Component Structure:**
```python
def admin_backgrounds_page() -> rx.Component:
    return authenticated_layout(
        rx.vstack(
            # Header
            rx.hstack(
                rx.heading("Background Images", size="8"),
                rx.spacer(),
                rx.button("Add Background", on_click=BackgroundsAdminState.open_add_modal),
                width="100%",
            ),

            # Action buttons
            rx.hstack(
                rx.button("Refresh", on_click=BackgroundsAdminState.load_backgrounds),
                rx.button("Reseed from Filesystem", on_click=BackgroundsAdminState.reseed_from_filesystem),
            ),

            # Success/Error messages
            rx.cond(
                BackgroundsAdminState.success_message,
                rx.callout(BackgroundsAdminState.success_message, icon="check", color_scheme="green"),
            ),
            rx.cond(
                BackgroundsAdminState.error_message,
                rx.callout(BackgroundsAdminState.error_message, icon="triangle_alert", color_scheme="red"),
            ),

            # Loading state
            rx.cond(
                BackgroundsAdminState.is_loading,
                rx.spinner(),
                # Background grid
                rx.grid(
                    rx.foreach(
                        BackgroundsAdminState.backgrounds,
                        background_card
                    ),
                    columns=rx.breakpoints(initial="2", md="3", lg="4", xl="6"),
                    spacing="4",
                ),
            ),

            # Modals
            add_background_modal(),
            edit_background_modal(),
            delete_confirmation_modal(),

            spacing="5",
            width="100%",
        )
    )
```

---

### 5. Access Control

**Current Plan:**
- Allow all authenticated users (uses `BaseState.require_auth()`)
- No admin-specific restrictions (can add later)

**Future Enhancement:**
Add `is_admin` field to User model:
```python
# In models.py
class User(Base):
    is_admin: bool = False  # Default: regular user
```

Then check in `on_mount()`:
```python
def on_mount(self):
    if redirect := self.require_auth():
        return redirect

    # Check admin status
    if not self.user_is_admin:
        return rx.redirect("/dashboard")

    yield from self.load_backgrounds()
```

---

## Technical Specifications

### Image Validation

**File Type:**
- PNG only (consistent with existing backgrounds)
- Validate MIME type: `image/png`

**File Size:**
- Max: 5MB (same as picture upload)
- Backend validates via FastAPI endpoint

**Dimensions:**
- Recommended: 800x480 (E Ink display size)
- Not enforced (allow flexibility)
- Warning if dimensions don't match

**Validation Code:**
```python
from PIL import Image
import io

def validate_background_image(file_data: bytes) -> tuple[bool, str]:
    """
    Validate uploaded background image.

    Returns: (is_valid, error_message)
    """
    try:
        img = Image.open(io.BytesIO(file_data))
        img.verify()

        # Check format
        if img.format != 'PNG':
            return False, "Only PNG format is supported"

        # Check dimensions (warning only)
        if img.size != (800, 480):
            # Still valid, just warn
            pass

        return True, ""

    except Exception as e:
        return False, f"Invalid image file: {str(e)}"
```

### Sort Order Management

**Auto-Assignment:**
```python
def _get_next_sort_order(self, session) -> int:
    """Get next available sort order."""
    max_order = session.query(func.max(BackgroundImage.sort_order)).scalar()
    return (max_order or -1) + 1
```

**Manual Reordering:**
- User edits sort_order via edit modal
- No drag-and-drop for MVP (keep simple)
- Future enhancement: drag-and-drop with instant updates

### Delete Behavior

**File Preservation:**
- Delete database record only
- Keep file on disk at `/root/streamscene/backgrounds/{filename}`
- Rationale: Existing posts may reference this background
- Files can be manually cleaned later if needed

**Cascade Consideration:**
Currently, Post model has:
```python
background_name: str  # Stores filename as string
```

**If we add foreign key:**
```python
background_id: Optional[UUID] = ForeignKey('background_images.id', ondelete='SET NULL')
```
- Deleted backgrounds set to NULL in posts
- Can show placeholder background
- Better data integrity

**Current approach is fine for MVP** (string reference is flexible)

### Error Handling

**Upload Failures:**
- Network error → "Upload failed. Please try again."
- File too large → "File size exceeds 5MB limit."
- Invalid format → "Only PNG images are supported."

**Database Errors:**
- Duplicate filename → "A background with this filename already exists."
- Not found → "Background not found. It may have been deleted."
- Connection error → "Database error. Please try again."

**File System Errors:**
- Permission denied → "Cannot save file. Please check permissions."
- Disk full → "Not enough disk space."
- Copy failed → "Failed to copy file to backgrounds directory."

---

## Files to Create/Modify

### New Files
1. **`streamscene/pages/admin_backgrounds.py`**
   - BackgroundsAdminState class
   - Page layout and components
   - Modal dialogs
   - Background card component

### Existing Files (No Changes Needed)
- **`streamscene/api/__init__.py`** - Upload endpoint already exists
- **`streamscene/core/backgrounds.py`** - All CRUD functions ready
- **`streamscene/core/models.py`** - Database schema exists
- **`streamscene/components/post_creator/background_selector.py`** - Can reuse for previews

### Navigation Update
**File:** `streamscene/components/sidebar.py` or navigation config

Add link to admin page (under Admin section or Settings):
```python
rx.link("Background Images", href="/admin/backgrounds", icon="image")
```

---

## Testing Plan

### Manual Testing Checklist

**Add Background:**
- [ ] Upload PNG file successfully
- [ ] Upload non-PNG fails with error
- [ ] Upload >5MB fails with error
- [ ] Display name saves correctly
- [ ] Active checkbox works
- [ ] File copied to backgrounds directory
- [ ] Database record created
- [ ] Background appears in user-facing selector
- [ ] Background appears in E Ink preview

**Edit Background:**
- [ ] Modal pre-fills with current values
- [ ] Display name updates
- [ ] Sort order changes
- [ ] Active toggle works
- [ ] Cannot change filename
- [ ] Changes reflected in user-facing selector

**Delete Background:**
- [ ] Confirmation modal shows
- [ ] Cancel works
- [ ] Delete removes from database
- [ ] File remains on disk
- [ ] Background removed from user-facing selector
- [ ] Existing posts still reference background (no errors)

**Toggle Active:**
- [ ] Quick toggle works without modal
- [ ] Active backgrounds show in selector
- [ ] Inactive backgrounds hidden from selector
- [ ] Status badge updates immediately

**Reseed:**
- [ ] Manually add PNG to backgrounds directory
- [ ] Click "Reseed from Filesystem"
- [ ] New background appears in list
- [ ] Default values assigned correctly

**Error Handling:**
- [ ] Invalid file type shows error
- [ ] Network failure shows error
- [ ] Duplicate filename prevented
- [ ] Permission errors handled gracefully

**UI/UX:**
- [ ] Grid responsive on mobile/tablet/desktop
- [ ] Loading states show during operations
- [ ] Success messages auto-dismiss
- [ ] Error messages persist until dismissed
- [ ] Modals close on save/cancel
- [ ] Page doesn't reload unnecessarily

---

## Future Enhancements

### Phase 2 Features

1. **Drag-and-Drop Reordering:**
   - Visual reordering of backgrounds in grid
   - Instant save of new sort_order
   - Uses HTML5 drag-and-drop API

2. **Bulk Operations:**
   - Select multiple backgrounds (checkboxes)
   - Bulk enable/disable
   - Bulk delete
   - Bulk sort order adjustment

3. **Background Categories:**
   - Add `category` field (Solid, Gradient, Pattern, etc.)
   - Filter by category
   - Organize selector by category

4. **Image Editor:**
   - Crop/resize uploaded images
   - Apply filters (brightness, contrast)
   - Preview before save

5. **Usage Analytics:**
   - Show usage count per background
   - Most popular backgrounds
   - Prevent deletion of frequently used backgrounds

6. **Preview Generation:**
   - Auto-generate thumbnail (smaller file)
   - Store thumbnail separately
   - Faster grid loading

7. **Import/Export:**
   - Export backgrounds as ZIP
   - Import ZIP of backgrounds
   - Backup/restore functionality

### Admin System Expansion

Once this is working, can add similar admin pages for:
- **Device Management** (already exists at `/devices`, could enhance)
- **User Management** (view users, assign streams, permissions)
- **Stream Templates** (pre-configured stream settings)
- **System Settings** (global config, OTA settings, etc.)

---

## Implementation Timeline Estimate

**MVP (Minimum Viable Product):**
- **Time:** 4-6 hours
- **Features:** Add, Edit, Delete, Toggle Active, List View
- **Testing:** Manual testing of core flows

**Polished Version:**
- **Time:** +2-3 hours
- **Features:** Reseed, Better error handling, Responsive polish
- **Testing:** Comprehensive manual testing

**With Enhancements:**
- **Time:** +4-6 hours
- **Features:** Drag-and-drop, Categories, Usage analytics
- **Testing:** Unit tests, integration tests

---

## Security Considerations

### Authentication
- ✅ Required (via `BaseState.require_auth()`)
- ⚠️ No admin-specific check (add later)

### File Upload
- ✅ File type validation (PNG only)
- ✅ File size limit (5MB)
- ⚠️ No malware scanning (add if concerned)
- ⚠️ No dimension limits (flexible but could validate)

### Rate Limiting
- ⚠️ Consider rate limiting uploads (e.g., 10/hour)
- Prevents abuse
- Can add to FastAPI endpoint

### SQL Injection
- ✅ Using SQLAlchemy ORM (safe by default)
- ✅ No raw SQL queries

### Path Traversal
- ✅ Using UUID filenames (no user input in path)
- ✅ Copying to fixed directory

### Authorization
- ⚠️ Currently all authenticated users can manage
- Future: Add `is_admin` check

---

## Dependencies

### Python Packages
All already installed:
- `reflex` - UI framework
- `pillow` - Image validation
- `sqlalchemy` - Database ORM
- `fastapi` - API endpoints

### Frontend
All already available:
- Reflex components (rx.grid, rx.modal, etc.)
- Upload component (from picture_form.py)
- JavaScript upload handler (reusable)

### Database
- No schema changes needed
- `background_images` table already exists

---

## Questions to Consider

1. **Should we allow JPEG backgrounds?**
   - Pro: More flexible
   - Con: PNG is E Ink standard, keeps consistency
   - **Recommendation:** PNG only for now

2. **Should we validate 800x480 dimensions?**
   - Pro: Ensures E Ink compatibility
   - Con: Limits flexibility, some backgrounds work at other sizes
   - **Recommendation:** Warn but don't enforce

3. **Should we add admin role restriction?**
   - Pro: Better security, prevents accidental changes
   - Con: Extra complexity, need to manage admin users
   - **Recommendation:** Add `is_admin` check before public launch

4. **Should delete also remove the file?**
   - Pro: Cleaner filesystem
   - Con: Breaks existing posts that reference it
   - **Recommendation:** Keep file (current plan is correct)

5. **Should we auto-reseed on page load?**
   - Pro: Always in sync with filesystem
   - Con: Slower page load, unnecessary queries
   - **Recommendation:** Manual button only

---

## Success Criteria

**MVP is successful when:**
- [ ] Admin can upload new PNG backgrounds
- [ ] Admin can edit display name and sort order
- [ ] Admin can toggle active/inactive status
- [ ] Admin can delete backgrounds
- [ ] New backgrounds appear in user-facing selector
- [ ] Inactive backgrounds hidden from user-facing selector
- [ ] No errors in browser console or server logs
- [ ] Mobile responsive layout works
- [ ] Error messages helpful and clear

---

## Notes

- Reuses existing upload infrastructure (no new endpoints needed)
- Follows established patterns from devices page
- No database migrations required
- Can be implemented in a single session
- Low risk (doesn't affect existing functionality)
- Easy to test (no device hardware needed)

---

**Ready to implement when needed!**
