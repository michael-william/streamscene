# Post Creator UI - Implementation Plan

**Created:** 2025-11-23
**Status:** Planning Complete, Ready for Implementation
**Architecture:** Modular, Responsive, Extensible

---

## Executive Summary

This document provides a comprehensive implementation plan for the **Post Creator Web UI** - a responsive, modular interface for creating Picture and Meme posts in StreamScene.

### Requirements
- ✅ **Two post types:** "Post a Picture" (image + text) and "Meme It" (background + text)
- ✅ **Responsive design:** Mobile-first, works on all screen sizes
- ✅ **Minimal design:** Matches existing UI aesthetic
- ✅ **Live preview:** Real-time PIL-rendered preview
- ✅ **File uploads:** Drag-drop + file picker with validation
- ✅ **Color customization:** Text and outline color pickers
- ✅ **Background selection:** Thumbnail grid of 13 backgrounds
- ✅ **Testing:** Unit + integration tests
- ✅ **Logging:** Comprehensive debug logging
- ✅ **Extensibility:** Easy to add new post types

---

## Architecture Overview

### Design Principles
1. **Modular Components** - Each piece is reusable and self-contained
2. **Mobile-First Responsive** - Optimized for phones, scales to desktop
3. **Progressive Enhancement** - Works without JavaScript, better with it
4. **Defensive State Management** - Validation at every step
5. **Performance Optimized** - Lazy loading, debouncing, caching

### File Structure

```
streamscene/
├── components/
│   └── post_creator/
│       ├── __init__.py                 # Public API exports
│       ├── post_type_selector.py       # Tab/button selector
│       ├── picture_form.py             # Picture post form
│       ├── meme_form.py                # Meme post form
│       ├── color_picker.py             # Reusable color picker component
│       ├── background_selector.py      # Background thumbnail grid
│       ├── image_upload.py             # Drag-drop + file picker
│       ├── live_preview.py             # PIL-rendered preview display
│       └── utils.py                    # Shared utilities
├── state/
│   └── post_creation_state.py          # Dedicated state management
├── api/
│   └── routes/
│       └── preview.py                  # Preview generation endpoint
└── tests/
    └── test_post_creator.py            # Component tests
```

---

## Component Architecture

### 1. PostTypeSelector

**Purpose:** Toggle between Picture and Meme post modes

**Props:**
- `current_type: str` - Current post type ("picture" or "meme")
- `on_change: Callable` - Callback when type changes

**UI:**
```
Mobile:         Desktop:
┌─────────┐     ┌──────────┬──────────┐
│ Picture │     │ Picture  │ Meme It  │
├─────────┤     └──────────┴──────────┘
│ Meme It │
└─────────┘
```

**Responsive:**
- Mobile: Stacked buttons (full width)
- Desktop: Horizontal tabs

**Implementation:**
```python
def post_type_selector(
    current_type: rx.Var[str],
    on_change: Callable
) -> rx.Component:
    return rx.flex(
        rx.button(
            "📷 Post a Picture",
            on_click=lambda: on_change("picture"),
            color_scheme=rx.cond(
                current_type == "picture",
                "blue",
                "gray"
            ),
            variant=rx.cond(
                current_type == "picture",
                "solid",
                "soft"
            ),
            flex=["1", "1", "0 1 auto"],  # Full width mobile
        ),
        rx.button(
            "🎨 Meme It",
            on_click=lambda: on_change("meme"),
            color_scheme=rx.cond(
                current_type == "meme",
                "blue",
                "gray"
            ),
            variant=rx.cond(
                current_type == "meme",
                "solid",
                "soft"
            ),
            flex=["1", "1", "0 1 auto"],
        ),
        direction=["column", "column", "row"],
        spacing="3",
        width="100%",
    )
```

---

### 2. ColorPicker

**Purpose:** Select hex colors with visual preview

**Props:**
- `label: str` - Display label
- `value: str` - Current hex color
- `on_change: Callable` - Callback when color changes

**UI:**
```
┌─────────────────────────┐
│ Text Color              │
│ ┌────┐ ┌──────────────┐│
│ │████│ │ #000000      ││ <-- Swatch + Hex input
│ └────┘ └──────────────┘│
└─────────────────────────┘
```

**Features:**
- Visual color swatch
- Hex input field with validation
- Native color picker popup
- Real-time preview

**Implementation:**
```python
def color_picker(
    label: str,
    value: rx.Var[str],
    on_change: Callable
) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", weight="medium"),
        rx.hstack(
            # Color swatch with native picker
            rx.input(
                type="color",
                value=value,
                on_change=on_change,
                width="60px",
                height="40px",
                cursor="pointer",
                border="2px solid var(--gray-6)",
                border_radius="6px",
            ),
            # Hex value input
            rx.input(
                value=value,
                on_change=on_change,
                placeholder="#000000",
                max_length=7,
                pattern="^#[0-9A-Fa-f]{6}$",
                width="120px",
                font_family="monospace",
            ),
            spacing="2",
            align="center",
        ),
        spacing="2",
        align="start",
        width="100%",
    )
```

---

### 3. BackgroundSelector

**Purpose:** Grid of background thumbnails for meme posts

**Props:**
- `backgrounds: List[dict]` - Available backgrounds
- `selected: str` - Currently selected filename
- `on_select: Callable` - Callback when background clicked

**UI:**
```
Desktop (6 columns):
┌────┬────┬────┬────┬────┬────┐
│ ✓  │    │    │    │    │    │
│White│Blue│Red │Grn │Prpl│Orng│
├────┼────┼────┼────┼────┼────┤
│    │    │    │    │    │    │
│Grad│Grad│Grad│Line│... │... │
└────┴────┴────┴────┴────┴────┘

Mobile (3 columns):
┌────┬────┬────┐
│ ✓  │    │    │
│Whit│Blue│Red │
├────┼────┼────┤
│Grn │Prpl│Orng│
└────┴────┴────┘
```

**Features:**
- Responsive grid (3 cols mobile, 6 desktop)
- Visual selection indicator
- Hover effects
- Lazy loaded images
- Accessible keyboard navigation

**Implementation:**
```python
def background_selector(
    backgrounds: rx.Var[List[dict]],
    selected: rx.Var[str],
    on_select: Callable
) -> rx.Component:
    def background_card(bg: dict) -> rx.Component:
        is_selected = bg["filename"] == selected

        return rx.box(
            rx.image(
                src=f"/backgrounds/{bg['filename']}",
                width="100%",
                height="80px",
                object_fit="cover",
                border_radius="6px",
            ),
            rx.text(
                bg["display_name"],
                size="1",
                text_align="center",
                margin_top="1",
            ),
            # Selection indicator
            rx.cond(
                is_selected,
                rx.badge(
                    "✓",
                    position="absolute",
                    top="4px",
                    right="4px",
                    color_scheme="blue",
                ),
            ),
            on_click=lambda: on_select(bg["filename"]),
            cursor="pointer",
            border=rx.cond(
                is_selected,
                "2px solid var(--blue-9)",
                "2px solid transparent"
            ),
            border_radius="8px",
            padding="6px",
            transition="all 0.2s",
            _hover={
                "border_color": "var(--blue-7)",
                "background": "var(--gray-2)",
            },
            position="relative",
        )

    return rx.vstack(
        rx.text("Choose Background", size="3", weight="medium"),
        rx.box(
            rx.foreach(backgrounds, background_card),
            display="grid",
            grid_template_columns=[
                "repeat(3, 1fr)",  # Mobile: 3 columns
                "repeat(3, 1fr)",  # Tablet: 3 columns
                "repeat(4, 1fr)",  # Desktop: 4 columns
                "repeat(6, 1fr)",  # Large: 6 columns
            ],
            gap="3",
            width="100%",
        ),
        spacing="3",
        width="100%",
    )
```

---

### 4. ImageUpload

**Purpose:** Drag-drop and file picker for picture uploads

**Props:**
- `on_upload: Callable` - Callback when image uploaded
- `preview_url: str` - Current image preview
- `is_uploading: bool` - Loading state

**UI:**
```
Empty state:
┌─────────────────────────┐
│   📷 Drag & Drop        │
│   or click to upload    │
│                         │
│   PNG, JPG (max 5MB)    │
└─────────────────────────┘

With preview:
┌─────────────────────────┐
│  ┌─────────────────┐   │
│  │                 │   │
│  │   [Preview]     │   │
│  │                 │   │
│  └─────────────────┘   │
│  [Change] [Remove]     │
└─────────────────────────┘
```

**Features:**
- Drag-drop zone with visual feedback
- File type validation (PNG, JPG, JPEG, WebP)
- Size limit validation (5MB)
- Image preview after upload
- Clear/replace functionality
- Progress indicator during upload
- Error messages

**Implementation:**
```python
def image_upload(
    on_upload: Callable,
    preview_url: rx.Var[str],
    is_uploading: rx.Var[bool]
) -> rx.Component:
    return rx.vstack(
        rx.text("Upload Image", size="3", weight="medium"),

        # Upload zone or preview
        rx.cond(
            preview_url,
            # Preview state
            rx.vstack(
                rx.image(
                    src=preview_url,
                    max_width="100%",
                    max_height="300px",
                    border_radius="8px",
                    border="2px solid var(--gray-6)",
                ),
                rx.hstack(
                    rx.button(
                        "Change Image",
                        on_click=on_upload,
                        size="2",
                        variant="soft",
                    ),
                    rx.button(
                        "Remove",
                        on_click=lambda: on_upload(None),
                        size="2",
                        variant="soft",
                        color_scheme="red",
                    ),
                    spacing="2",
                ),
                spacing="3",
                width="100%",
            ),
            # Upload zone
            rx.upload(
                rx.vstack(
                    rx.cond(
                        is_uploading,
                        rx.spinner(size="3"),
                        rx.icon("upload", size=32, color="gray"),
                    ),
                    rx.text(
                        "Drag & drop or click to upload",
                        size="3",
                        color="gray",
                    ),
                    rx.text(
                        "PNG, JPG, WebP (max 5MB)",
                        size="1",
                        color="gray",
                    ),
                    spacing="2",
                    align="center",
                    padding="8",
                ),
                id="image_upload",
                on_drop=on_upload,
                border="2px dashed var(--gray-6)",
                border_radius="8px",
                padding="4",
                width="100%",
                min_height="200px",
                display="flex",
                align_items="center",
                justify_content="center",
                cursor="pointer",
                transition="all 0.2s",
                _hover={
                    "border_color": "var(--blue-7)",
                    "background": "var(--gray-2)",
                },
                accept="image/png,image/jpeg,image/jpg,image/webp",
                max_files=1,
                max_size=5_000_000,  # 5MB
            ),
        ),
        spacing="3",
        width="100%",
    )
```

---

### 5. LivePreview

**Purpose:** Real-time PIL-rendered preview of post

**Props:**
- `preview_data: str` - Base64 data URL
- `is_generating: bool` - Loading state
- `stream_name: str` - Stream name for header
- `show: bool` - Toggle visibility

**UI:**
```
Desktop (70% scale):
┌──────────────────────────────┐
│ Preview (800×480, scaled)    │
│ ┌──────────────────────────┐ │
│ │ Stream  │ Author │ Date  │ │
│ │─────────────────────────│ │
│ │                          │ │
│ │      [Rendered           │ │
│ │       Content]           │ │
│ │                          │ │
│ └──────────────────────────┘ │
└──────────────────────────────┘

Mobile (50% scale):
┌─────────────────┐
│ Preview         │
│ ┌─────────────┐ │
│ │ Stream│Date │ │
│ │─────────────│ │
│ │   Content   │ │
│ └─────────────┘ │
└─────────────────┘
```

**Features:**
- Responsive scaling (40% mobile → 70% desktop)
- Loading spinner during generation
- Debounced updates (500ms)
- Error fallback
- Toggle show/hide

**Implementation:**
```python
def live_preview(
    preview_data: rx.Var[str],
    is_generating: rx.Var[bool],
    stream_name: rx.Var[str],
    show: rx.Var[bool]
) -> rx.Component:
    return rx.cond(
        show,
        rx.vstack(
            rx.hstack(
                rx.text(
                    "Live Preview",
                    size="3",
                    weight="medium",
                ),
                rx.badge(
                    "800×480px",
                    size="1",
                    color_scheme="gray",
                ),
                spacing="2",
                align="center",
            ),

            # Preview container
            rx.box(
                rx.cond(
                    is_generating,
                    # Loading state
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text("Generating preview...", size="2", color="gray"),
                        spacing="3",
                        justify="center",
                        align="center",
                        height="100%",
                    ),
                    # Preview image
                    rx.image(
                        src=preview_data,
                        width="800px",
                        height="480px",
                        border="4px solid var(--gray-6)",
                        border_radius="8px",
                        box_shadow="0 4px 6px rgba(0, 0, 0, 0.1)",
                    ),
                ),
                # Responsive scaling
                transform=[
                    "scale(0.4)",  # Mobile: 40%
                    "scale(0.5)",  # Tablet: 50%
                    "scale(0.6)",  # Desktop: 60%
                    "scale(0.7)",  # Large: 70%
                ],
                transform_origin="top left",
                width=["320px", "400px", "480px", "560px"],
                height=["192px", "240px", "288px", "336px"],
                overflow="hidden",
            ),

            spacing="3",
            width="100%",
            align="start",
        ),
    )
```

---

## State Management

### PostCreationState Class

**Location:** `streamscene/state/post_creation_state.py`

```python
"""State management for post creation forms."""

import logging
from typing import List, Optional
from uuid import UUID

import reflex as rx

from streamscene.core.database import get_db_session
from streamscene.core import streams as stream_ops
from streamscene.core.backgrounds import get_all_backgrounds
from streamscene.pages.base_state import BaseState

logger = logging.getLogger(__name__)


class PostCreationState(BaseState):
    """
    State for creating Picture and Meme posts.

    Handles:
    - Post type selection
    - Image uploads (Picture posts)
    - Background selection (Meme posts)
    - Color customization
    - Live preview generation
    - Form validation
    - Post submission
    """

    state_auto_setters = True

    # ========================================
    # FORM STATE
    # ========================================

    # Post type: "picture" or "meme"
    post_type: str = "meme"

    # Common fields
    text_content: str = ""
    text_color: str = "#000000"  # Black
    outline_color: str = "#FFFFFF"  # White

    # Picture post fields
    uploaded_files: list[str] = []  # rx.upload() file refs
    image_preview_url: str = ""
    image_bytes: bytes = b""  # Stored for submission

    # Meme post fields
    selected_background: str = "white.png"
    available_backgrounds: List[dict] = []

    # ========================================
    # UI STATE
    # ========================================

    show_preview: bool = False
    preview_image_data: str = ""  # Base64 data URL

    # Loading states
    is_loading_backgrounds: bool = False
    is_uploading_image: bool = False
    is_generating_preview: bool = False
    is_submitting: bool = False

    # Validation
    error_message: str = ""
    validation_errors: List[str] = []

    # ========================================
    # COMPUTED PROPERTIES
    # ========================================

    @rx.var
    def char_count(self) -> int:
        """Get character count of text content."""
        return len(self.text_content)

    @rx.var
    def is_valid(self) -> bool:
        """Check if form is valid for submission."""
        if not self.text_content.strip():
            return False
        if self.char_count > 160:
            return False
        if self.post_type == "picture" and not self.image_bytes:
            return False
        if self.post_type == "meme" and not self.selected_background:
            return False
        return True

    @rx.var
    def char_count_color(self) -> str:
        """Get color for character counter."""
        if self.char_count > 160:
            return "red"
        elif self.char_count > 140:
            return "yellow"
        return "gray"

    # ========================================
    # LIFECYCLE METHODS
    # ========================================

    def on_load(self):
        """Load backgrounds when component mounts."""
        logger.info("[POST_CREATE] Component mounted, loading backgrounds")
        yield from self.load_backgrounds()

    # ========================================
    # POST TYPE SELECTION
    # ========================================

    def select_post_type(self, post_type: str):
        """
        Switch between picture and meme post types.

        Args:
            post_type: "picture" or "meme"
        """
        if post_type not in ["picture", "meme"]:
            logger.error(f"[POST_CREATE] Invalid post type: {post_type}")
            return

        logger.info(f"[POST_CREATE] Switching post type: {self.post_type} -> {post_type}")
        self.post_type = post_type
        self.error_message = ""
        self.validation_errors = []

        # Clear preview when switching types
        self.preview_image_data = ""

    # ========================================
    # BACKGROUND MANAGEMENT
    # ========================================

    def load_backgrounds(self):
        """Load available backgrounds from database."""
        logger.info("[POST_CREATE] Loading backgrounds from database")
        self.is_loading_backgrounds = True
        yield

        try:
            with get_db_session() as session:
                backgrounds = get_all_backgrounds(session, active_only=True)

                self.available_backgrounds = [
                    {
                        "filename": bg.filename,
                        "display_name": bg.display_name,
                    }
                    for bg in backgrounds
                ]

                logger.info(f"[POST_CREATE] Loaded {len(self.available_backgrounds)} backgrounds")

                # Set default if not already set
                if not self.selected_background and self.available_backgrounds:
                    self.selected_background = self.available_backgrounds[0]["filename"]
                    logger.info(f"[POST_CREATE] Default background: {self.selected_background}")

        except Exception as e:
            logger.error(f"[POST_CREATE] Error loading backgrounds: {e}")
            self.error_message = f"Error loading backgrounds: {str(e)}"

        finally:
            self.is_loading_backgrounds = False
            yield

    def select_background(self, filename: str):
        """
        Select a background for meme posts.

        Args:
            filename: Background image filename
        """
        logger.info(f"[POST_CREATE] Background selected: {filename}")
        self.selected_background = filename

        # Regenerate preview if showing
        if self.show_preview:
            yield from self.generate_preview()

    # ========================================
    # IMAGE UPLOAD (Picture posts)
    # ========================================

    async def handle_image_upload(self, files: list[rx.UploadFile]):
        """
        Handle image upload for picture posts.

        Args:
            files: List of uploaded files (rx.upload returns list)
        """
        if not files:
            logger.warning("[POST_CREATE] No files uploaded")
            return

        file = files[0]  # Only handle first file
        logger.info(f"[POST_CREATE] Image upload started: {file.filename}")

        self.is_uploading_image = True
        self.error_message = ""
        yield

        try:
            # Read file bytes
            self.image_bytes = await file.read()
            file_size_mb = len(self.image_bytes) / (1024 * 1024)

            logger.info(f"[POST_CREATE] Image uploaded: {file.filename}, size: {file_size_mb:.2f}MB")

            # Validate size
            if file_size_mb > 5:
                self.error_message = "Image too large (max 5MB)"
                logger.error(f"[POST_CREATE] Image too large: {file_size_mb:.2f}MB")
                self.image_bytes = b""
                return

            # Validate type
            allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp"]
            if file.content_type not in allowed_types:
                self.error_message = f"Invalid file type: {file.content_type}"
                logger.error(f"[POST_CREATE] Invalid file type: {file.content_type}")
                self.image_bytes = b""
                return

            # Create preview URL (data URL)
            import base64
            b64_data = base64.b64encode(self.image_bytes).decode()
            self.image_preview_url = f"data:{file.content_type};base64,{b64_data}"

            logger.info("[POST_CREATE] Image preview generated")

            # Regenerate preview if showing
            if self.show_preview:
                yield from self.generate_preview()

        except Exception as e:
            logger.error(f"[POST_CREATE] Error uploading image: {e}")
            self.error_message = f"Error uploading image: {str(e)}"
            self.image_bytes = b""

        finally:
            self.is_uploading_image = False
            yield

    def clear_uploaded_image(self):
        """Clear uploaded image."""
        logger.info("[POST_CREATE] Clearing uploaded image")
        self.image_bytes = b""
        self.image_preview_url = ""
        self.uploaded_files = []
        self.preview_image_data = ""

    # ========================================
    # COLOR CUSTOMIZATION
    # ========================================

    def update_text_color(self, color: str):
        """
        Update text color.

        Args:
            color: Hex color code (e.g., "#000000")
        """
        # Validate hex format
        if not color.startswith("#") or len(color) != 7:
            logger.warning(f"[POST_CREATE] Invalid color format: {color}")
            return

        logger.info(f"[POST_CREATE] Text color updated: {self.text_color} -> {color}")
        self.text_color = color

        # Regenerate preview if showing
        if self.show_preview:
            yield from self.generate_preview()

    def update_outline_color(self, color: str):
        """
        Update outline color.

        Args:
            color: Hex color code (e.g., "#FFFFFF")
        """
        # Validate hex format
        if not color.startswith("#") or len(color) != 7:
            logger.warning(f"[POST_CREATE] Invalid color format: {color}")
            return

        logger.info(f"[POST_CREATE] Outline color updated: {self.outline_color} -> {color}")
        self.outline_color = color

        # Regenerate preview if showing
        if self.show_preview:
            yield from self.generate_preview()

    # ========================================
    # LIVE PREVIEW
    # ========================================

    def toggle_preview(self):
        """Toggle live preview visibility."""
        self.show_preview = not self.show_preview
        logger.info(f"[POST_CREATE] Preview toggled: {self.show_preview}")

        # Generate preview if enabled and not already generated
        if self.show_preview and not self.preview_image_data:
            yield from self.generate_preview()

    def generate_preview(self):
        """
        Generate live preview using PIL renderer.

        Calls backend API to render preview and returns base64 data URL.
        """
        logger.info("[POST_CREATE] Generating preview...")
        self.is_generating_preview = True
        yield

        try:
            # Import renderer here to avoid circular import
            from streamscene.core.image_renderer import ImageRenderer, hex_to_rgb
            from streamscene.core.backgrounds import get_background_path
            from datetime import datetime
            import base64
            import io

            renderer = ImageRenderer()

            # Parse colors
            text_color = hex_to_rgb(self.text_color)
            outline_color = hex_to_rgb(self.outline_color)

            # Get stream name (from parent state)
            stream_name = getattr(self, "stream_name", "Preview Stream")
            author_name = "You"
            post_date = datetime.now()

            # Render based on post type
            if self.post_type == "picture":
                if not self.image_bytes:
                    logger.warning("[POST_CREATE] No image to preview")
                    self.preview_image_data = ""
                    return

                # Save temp image for rendering
                from PIL import Image
                temp_img = Image.open(io.BytesIO(self.image_bytes))
                temp_path = "/tmp/preview_upload.png"
                temp_img.save(temp_path)

                rendered = renderer.render_picture_post(
                    image_path=temp_path,
                    text_content=self.text_content or "",
                    stream_name=stream_name,
                    author_name=author_name,
                    post_date=post_date,
                    text_color=text_color,
                    outline_color=outline_color
                )

            elif self.post_type == "meme":
                if not self.selected_background:
                    logger.warning("[POST_CREATE] No background selected")
                    self.preview_image_data = ""
                    return

                background_path = str(get_background_path(self.selected_background))

                rendered = renderer.render_meme_post(
                    background_image_path=background_path,
                    text_content=self.text_content or "",
                    stream_name=stream_name,
                    author_name=author_name,
                    post_date=post_date,
                    text_color=text_color,
                    outline_color=outline_color
                )

            # Convert to base64 data URL
            buffer = io.BytesIO()
            rendered.save(buffer, format="PNG")
            b64_data = base64.b64encode(buffer.getvalue()).decode()
            self.preview_image_data = f"data:image/png;base64,{b64_data}"

            logger.info("[POST_CREATE] Preview generated successfully")

        except Exception as e:
            logger.error(f"[POST_CREATE] Error generating preview: {e}")
            import traceback
            traceback.print_exc()
            self.error_message = f"Preview error: {str(e)}"
            self.preview_image_data = ""

        finally:
            self.is_generating_preview = False
            yield

    # ========================================
    # FORM VALIDATION
    # ========================================

    def validate_form(self) -> bool:
        """
        Validate form before submission.

        Returns:
            True if valid, False otherwise (sets validation_errors)
        """
        self.validation_errors = []

        # Check text content
        if not self.text_content.strip():
            self.validation_errors.append("Text content is required")

        if self.char_count > 160:
            self.validation_errors.append("Text is too long (max 160 characters)")

        # Check post-type specific requirements
        if self.post_type == "picture":
            if not self.image_bytes:
                self.validation_errors.append("Please upload an image")

        elif self.post_type == "meme":
            if not self.selected_background:
                self.validation_errors.append("Please select a background")

        # Check colors
        if not self.text_color.startswith("#") or len(self.text_color) != 7:
            self.validation_errors.append("Invalid text color")

        if not self.outline_color.startswith("#") or len(self.outline_color) != 7:
            self.validation_errors.append("Invalid outline color")

        is_valid = len(self.validation_errors) == 0

        if not is_valid:
            logger.warning(f"[POST_CREATE] Form validation failed: {self.validation_errors}")

        return is_valid

    # ========================================
    # POST SUBMISSION
    # ========================================

    def submit_post(self, stream_id: str):
        """
        Submit the post to the database.

        Args:
            stream_id: Stream UUID string
        """
        logger.info(f"[POST_CREATE] Submitting post to stream {stream_id}")

        # Validate form
        if not self.validate_form():
            self.error_message = "Please fix validation errors"
            return

        # Check authentication
        if not self.user_id:
            self.error_message = "You must be logged in to post"
            logger.error("[POST_CREATE] No user_id in state")
            return

        self.is_submitting = True
        self.error_message = ""
        yield

        try:
            user_uuid = UUID(self.user_id)
            stream_uuid = UUID(stream_id)

            with get_db_session() as session:
                # Create post with appropriate parameters
                if self.post_type == "picture":
                    post = stream_ops.create_post(
                        session=session,
                        stream_id=stream_uuid,
                        author_id=user_uuid,
                        text_content=self.text_content,
                        content_type="picture",
                        image_bytes=self.image_bytes,
                        text_color=self.text_color,
                        outline_color=self.outline_color,
                    )

                elif self.post_type == "meme":
                    post = stream_ops.create_post(
                        session=session,
                        stream_id=stream_uuid,
                        author_id=user_uuid,
                        text_content=self.text_content,
                        content_type="meme",
                        background_name=self.selected_background,
                        text_color=self.text_color,
                        outline_color=self.outline_color,
                    )

                session.commit()

                logger.info(f"[POST_CREATE] Post created successfully: {post.id}")

                # Clear form
                self.text_content = ""
                self.image_bytes = b""
                self.image_preview_url = ""
                self.preview_image_data = ""
                self.show_preview = False

                # Return success (parent state will handle navigation/reload)
                return rx.redirect(f"/stream-posts?id={stream_id}")

        except Exception as e:
            logger.error(f"[POST_CREATE] Error creating post: {e}")
            import traceback
            traceback.print_exc()
            self.error_message = f"Error creating post: {str(e)}"

        finally:
            self.is_submitting = False
            yield
```

---

## Responsive Design Strategy

### Breakpoints
```python
# Mobile-first breakpoints (using Radix UI responsive arrays)
mobile = 0      # 0-767px
tablet = 768    # 768-1023px
desktop = 1024  # 1024-1439px
large = 1440    # 1440px+

# Responsive array format: [mobile, tablet, desktop, large]
```

### Layout Patterns

**1. Form Container Width:**
```python
max_width=["100%", "100%", "600px", "700px"]
padding=["4", "4", "6", "8"]
```

**2. Button Groups:**
```python
# Mobile: Stacked
# Desktop: Horizontal
direction=["column", "column", "row"]
spacing=["2", "2", "3"]
```

**3. Background Grid:**
```python
grid_template_columns=[
    "repeat(3, 1fr)",  # Mobile: 3 columns
    "repeat(3, 1fr)",  # Tablet: 3 columns
    "repeat(4, 1fr)",  # Desktop: 4 columns
    "repeat(6, 1fr)",  # Large: 6 columns
]
```

**4. Preview Scaling:**
```python
transform=[
    "scale(0.4)",  # Mobile: 40% (320px width)
    "scale(0.5)",  # Tablet: 50% (400px width)
    "scale(0.6)",  # Desktop: 60% (480px width)
    "scale(0.7)",  # Large: 70% (560px width)
]
```

**5. Typography:**
```python
# Headings
size=["5", "6", "7", "8"]  # Mobile smallest, large biggest

# Body text
size=["2", "2", "3", "3"]  # Consistent across tablet+
```

---

## Testing Strategy

### Unit Tests

**File:** `tests/test_post_creator.py`

```python
"""Tests for post creator components."""

import pytest
from streamscene.state.post_creation_state import PostCreationState


class TestPostCreationState:
    """Test post creation state management."""

    def test_char_count(self):
        """Test character counting."""
        state = PostCreationState()
        assert state.char_count == 0

        state.text_content = "Hello"
        assert state.char_count == 5

        state.text_content = "a" * 160
        assert state.char_count == 160

    def test_char_count_color(self):
        """Test character counter color logic."""
        state = PostCreationState()

        state.text_content = "short"
        assert state.char_count_color == "gray"

        state.text_content = "a" * 150
        assert state.char_count_color == "yellow"

        state.text_content = "a" * 161
        assert state.char_count_color == "red"

    def test_validation_text_required(self):
        """Test validation requires text."""
        state = PostCreationState()
        state.post_type = "meme"
        state.selected_background = "white.png"

        assert not state.validate_form()
        assert "required" in state.validation_errors[0].lower()

    def test_validation_char_limit(self):
        """Test validation enforces 160 char limit."""
        state = PostCreationState()
        state.post_type = "meme"
        state.text_content = "a" * 161
        state.selected_background = "white.png"

        assert not state.validate_form()
        assert "too long" in state.validation_errors[0].lower()

    def test_validation_picture_requires_image(self):
        """Test picture posts require image."""
        state = PostCreationState()
        state.post_type = "picture"
        state.text_content = "Test"

        assert not state.validate_form()
        assert "image" in state.validation_errors[0].lower()

    def test_validation_meme_requires_background(self):
        """Test meme posts require background."""
        state = PostCreationState()
        state.post_type = "meme"
        state.text_content = "Test"
        state.selected_background = ""

        assert not state.validate_form()
        assert "background" in state.validation_errors[0].lower()

    def test_color_validation(self):
        """Test color hex validation."""
        state = PostCreationState()
        state.post_type = "meme"
        state.text_content = "Test"
        state.selected_background = "white.png"

        # Valid colors
        state.text_color = "#000000"
        state.outline_color = "#FFFFFF"
        assert state.validate_form()

        # Invalid color format
        state.text_color = "000000"  # Missing #
        assert not state.validate_form()

        state.text_color = "#00"  # Too short
        assert not state.validate_form()

    def test_post_type_switching(self):
        """Test switching between post types."""
        state = PostCreationState()

        assert state.post_type == "meme"  # Default

        state.select_post_type("picture")
        assert state.post_type == "picture"

        state.select_post_type("invalid")
        assert state.post_type == "picture"  # Unchanged
```

### Integration Tests

```python
class TestPostCreationIntegration:
    """Test post creation end-to-end flows."""

    @pytest.mark.asyncio
    async def test_create_meme_post(self):
        """Test creating a meme post."""
        # Setup
        state = PostCreationState()
        state.user_id = "test-user-uuid"
        await state.load_backgrounds()

        # Fill form
        state.select_post_type("meme")
        state.text_content = "Test meme"
        state.select_background("blue_purple_gradient.png")
        state.update_text_color("#FFFFFF")
        state.update_outline_color("#000000")

        # Validate
        assert state.validate_form()

        # Submit
        await state.submit_post("test-stream-uuid")

        # Verify
        assert not state.error_message
        assert state.text_content == ""  # Form cleared

    @pytest.mark.asyncio
    async def test_create_picture_post(self):
        """Test creating a picture post."""
        # Setup
        state = PostCreationState()
        state.user_id = "test-user-uuid"

        # Load test image
        with open("test_images/landscape.jpg", "rb") as f:
            image_bytes = f.read()

        # Fill form
        state.select_post_type("picture")
        state.text_content = "Check out this pic!"
        state.image_bytes = image_bytes

        # Validate
        assert state.validate_form()

        # Submit
        await state.submit_post("test-stream-uuid")

        # Verify
        assert not state.error_message
        assert state.image_bytes == b""  # Form cleared
```

---

## Logging Strategy

### Log Levels

```python
import logging

logger = logging.getLogger(__name__)

# INFO: Normal operations
logger.info(f"[POST_CREATE] User selected background: {filename}")

# WARNING: Recoverable issues
logger.warning(f"[POST_CREATE] Invalid color format: {color}")

# ERROR: Failures
logger.error(f"[POST_CREATE] Error uploading image: {error}")

# DEBUG: Detailed debugging
logger.debug(f"[POST_CREATE] Form state: {state.__dict__}")
```

### Log Format

```
[POST_CREATE] <action>: <details>

Examples:
[POST_CREATE] Component mounted, loading backgrounds
[POST_CREATE] Switching post type: meme -> picture
[POST_CREATE] Image uploaded: vacation.jpg, size: 2.34MB
[POST_CREATE] Background selected: blue_purple_gradient.png
[POST_CREATE] Text color updated: #000000 -> #FFFFFF
[POST_CREATE] Generating preview...
[POST_CREATE] Preview generated successfully
[POST_CREATE] Form validation failed: ['Text is too long']
[POST_CREATE] Submitting post to stream abc123
[POST_CREATE] Post created successfully: def456
[POST_CREATE] Error: Image too large (5.2MB > 5MB limit)
```

---

## Performance Optimizations

### 1. Debounced Preview Generation

```python
import asyncio

class PostCreationState(BaseState):
    _preview_debounce_task = None

    def debounced_preview_update(self):
        """Debounce preview generation (500ms)."""
        if self._preview_debounce_task:
            self._preview_debounce_task.cancel()

        self._preview_debounce_task = asyncio.create_task(
            self._delayed_preview_update()
        )

    async def _delayed_preview_update(self):
        """Execute preview update after delay."""
        await asyncio.sleep(0.5)  # 500ms debounce
        await self.generate_preview()
```

### 2. Lazy Load Background Images

```python
def background_card(bg: dict) -> rx.Component:
    return rx.box(
        rx.image(
            src=f"/backgrounds/{bg['filename']}",
            loading="lazy",  # Browser-native lazy loading
            width="100%",
            height="80px",
        ),
        # ...
    )
```

### 3. Image Preview Optimization

```python
def optimize_preview_image(image_bytes: bytes) -> bytes:
    """Resize preview image for display."""
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(image_bytes))

    # Resize if larger than display size
    max_width = 800
    max_height = 600

    if img.width > max_width or img.height > max_height:
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

    # Save optimized version
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85, optimize=True)

    return buffer.getvalue()
```

### 4. Caching

```python
# Cache rendered previews
_preview_cache = {}

def get_cached_preview(cache_key: str) -> Optional[str]:
    """Get cached preview data URL."""
    return _preview_cache.get(cache_key)

def cache_preview(cache_key: str, data_url: str):
    """Cache preview data URL."""
    # Limit cache size
    if len(_preview_cache) > 50:
        _preview_cache.pop(next(iter(_preview_cache)))

    _preview_cache[cache_key] = data_url
```

---

## Security Considerations

### 1. File Upload Validation

```python
async def handle_image_upload(self, files: list[rx.UploadFile]):
    """Handle image upload with security checks."""
    file = files[0]

    # 1. File size limit (5MB)
    file_bytes = await file.read()
    if len(file_bytes) > 5_000_000:
        raise ValueError("File too large")

    # 2. File type validation
    allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp"]
    if file.content_type not in allowed_types:
        raise ValueError("Invalid file type")

    # 3. Image validation (verify it's actually an image)
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()
    except Exception:
        raise ValueError("Invalid image file")

    # 4. Sanitize filename
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")

    # 5. Check for malicious content (optional: use clamav, etc.)
    # ...
```

### 2. Color Input Validation

```python
import re

def validate_hex_color(color: str) -> bool:
    """Validate hex color format."""
    pattern = r'^#[0-9A-Fa-f]{6}$'
    return bool(re.match(pattern, color))

def update_text_color(self, color: str):
    """Update text color with validation."""
    if not validate_hex_color(color):
        logger.warning(f"Invalid color rejected: {color}")
        return

    self.text_color = color
```

### 3. XSS Prevention

- All user input is automatically escaped by Reflex
- No use of `dangerouslySetInnerHTML`
- Base64 data URLs are safe (no JavaScript execution)

### 4. CSRF Protection

- Reflex includes built-in CSRF protection
- All state methods require valid session token

---

## Accessibility (a11y)

### ARIA Labels

```python
rx.button(
    "Upload Image",
    aria_label="Upload image for picture post (max 5MB, PNG or JPG)",
    on_click=handle_upload,
)

rx.input(
    type="color",
    aria_label="Select text color",
    value=text_color,
    on_change=update_text_color,
)
```

### Keyboard Navigation

```python
# All interactive elements are keyboard accessible
rx.box(
    background_card(bg),
    tabindex=0,  # Allow keyboard focus
    on_key_down=lambda e: select_background(bg) if e.key == "Enter" else None,
    role="button",
    aria_pressed=is_selected,
)
```

### Screen Reader Support

```python
# Descriptive labels
rx.vstack(
    rx.text("Text Color", id="text-color-label"),
    rx.input(
        type="color",
        aria_labelledby="text-color-label",
    ),
)

# Status announcements
rx.box(
    rx.text(upload_status),
    role="status",
    aria_live="polite",
)
```

### Color Contrast

- All text meets WCAG AA standards (4.5:1 contrast)
- Color pickers allow custom colors for accessibility
- Visual indicators don't rely solely on color (icons + borders)

---

## Implementation Timeline

### Phase 1: Core State & Components (Day 1, 4-5 hours)

1. Create `post_creation_state.py` (2 hours)
   - All state management
   - Validation logic
   - Background loading
   - Image upload handling

2. Create base components (2 hours)
   - `post_type_selector.py`
   - `color_picker.py`
   - `background_selector.py`

3. Write unit tests (1 hour)
   - State validation tests
   - Component tests

### Phase 2: Forms & Upload (Day 2, 4-5 hours)

1. Create `image_upload.py` (2 hours)
   - Drag-drop zone
   - File validation
   - Preview display

2. Create `picture_form.py` (1 hour)
   - Integrate upload + colors + text

3. Create `meme_form.py` (1 hour)
   - Integrate backgrounds + colors + text

4. Integration testing (1 hour)

### Phase 3: Live Preview & Polish (Day 3, 4-5 hours)

1. Create `live_preview.py` (2 hours)
   - PIL rendering integration
   - Base64 conversion
   - Responsive scaling

2. Integrate into stream_posts.py (1 hour)
   - Replace existing form
   - Wire up state

3. Responsive testing (1 hour)
   - Mobile devices
   - Desktop browsers
   - Tablet sizes

4. Bug fixes & polish (1 hour)

### Phase 4: Testing & Documentation (Day 4, 2-3 hours)

1. E2E testing (1 hour)
   - Full create flows
   - Error scenarios

2. Performance testing (30 min)
   - Preview generation time
   - Upload speed

3. Update documentation (30 min)
   - CLAUDE.md
   - NEXT_SESSION.md

4. Final polish (30 min)

**Total: 14-18 hours**

---

## Success Criteria

### ✅ Phase 1 Complete When:
- [ ] PostCreationState fully implemented
- [ ] All state methods tested
- [ ] Base components rendered correctly
- [ ] Background loading works
- [ ] Unit tests passing (80%+ coverage)

### ✅ Phase 2 Complete When:
- [ ] Image upload works (drag-drop + picker)
- [ ] File validation works (size, type)
- [ ] Picture form fully functional
- [ ] Meme form fully functional
- [ ] Integration tests passing

### ✅ Phase 3 Complete When:
- [ ] Live preview generates correctly
- [ ] Preview updates on text/color changes
- [ ] Responsive scaling works on mobile/desktop
- [ ] Performance is acceptable (<500ms preview gen)
- [ ] Integrated into stream_posts.py

### ✅ Phase 4 Complete When:
- [ ] E2E tests passing
- [ ] Works on real mobile devices
- [ ] Works on desktop browsers
- [ ] No console errors
- [ ] Documentation updated
- [ ] Ready for production deployment

---

## Future Enhancements

### Post-MVP Features

1. **Advanced Image Editing**
   - Crop/resize tool
   - Filters (grayscale, sepia, etc.)
   - Rotation

2. **Custom Backgrounds**
   - User-uploaded backgrounds
   - Admin approval workflow
   - Background categories

3. **Text Formatting**
   - Bold, italic
   - Multiple text blocks
   - Text positioning

4. **Batch Operations**
   - Create multiple posts at once
   - Schedule posts
   - Draft system

5. **Analytics**
   - Preview generation time tracking
   - Upload success rate
   - Popular backgrounds

6. **Collaboration**
   - Comment on posts before publishing
   - Approval workflow
   - Version history

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| File upload failures | High | Retry logic, clear error messages, file validation |
| Preview generation slow | Medium | Debouncing, caching, loading indicators |
| Large file sizes crash browser | High | Size limits, client-side resize before upload |
| State management bugs | High | Comprehensive unit tests, logging |
| Mobile layout breaks | Medium | Mobile-first design, responsive testing |
| Color picker not supported | Low | Fallback to text input, polyfill |
| Background images don't load | Medium | Lazy loading, error fallbacks, retry |

---

## Monitoring & Metrics

### Key Metrics to Track

1. **Performance**
   - Preview generation time (target: <500ms)
   - Image upload time (target: <2s for 5MB)
   - Form submission time (target: <1s)

2. **Usage**
   - Picture vs Meme post ratio
   - Most popular backgrounds
   - Average text length
   - Color customization usage

3. **Errors**
   - Upload failure rate (target: <1%)
   - Validation error frequency
   - Preview generation failures

### Logging

```python
# Performance logging
logger.info(f"[PERF] Preview generated in {duration_ms}ms")
logger.info(f"[PERF] Image uploaded in {duration_ms}ms, size: {size_mb}MB")

# Usage logging
logger.info(f"[USAGE] Post created: type={post_type}, text_len={len(text)}")
logger.info(f"[USAGE] Background selected: {background_name}")

# Error logging
logger.error(f"[ERROR] Upload failed: {error}, file_size={size}, type={mime_type}")
```

---

## Appendix: Code Snippets

### Main Form Integration

```python
# streamscene/pages/stream_posts.py

from streamscene.components.post_creator import (
    post_type_selector,
    picture_form,
    meme_form,
    live_preview
)
from streamscene.state.post_creation_state import PostCreationState

def stream_posts_page() -> rx.Component:
    """Page for viewing and creating posts in a stream."""

    content = rx.container(
        rx.vstack(
            # ... existing header, messages, etc.

            # NEW: Post creation form
            rx.card(
                rx.vstack(
                    rx.heading("Create a Post", size="6"),

                    # Post type selector
                    post_type_selector(
                        current_type=PostCreationState.post_type,
                        on_change=PostCreationState.select_post_type,
                    ),

                    # Conditional form based on post type
                    rx.cond(
                        PostCreationState.post_type == "picture",
                        picture_form(PostCreationState),
                        meme_form(PostCreationState),
                    ),

                    # Live preview
                    live_preview(
                        preview_data=PostCreationState.preview_image_data,
                        is_generating=PostCreationState.is_generating_preview,
                        stream_name=StreamPostsState.stream_name,
                        show=PostCreationState.show_preview,
                    ),

                    # Submit button
                    rx.button(
                        rx.cond(
                            PostCreationState.is_submitting,
                            rx.spinner(size="3"),
                            "Create Post",
                        ),
                        on_click=lambda: PostCreationState.submit_post(
                            StreamPostsState.stream_id
                        ),
                        disabled=rx.cond(
                            PostCreationState.is_valid,
                            False,
                            True,
                        ),
                        size="3",
                        color_scheme="blue",
                    ),

                    spacing="4",
                    width="100%",
                ),
                size="3",
                width="100%",
            ),

            # ... existing posts list, etc.

            spacing="8",
            padding="4",
            width="100%",
        ),
        max_width="900px",
        on_mount=PostCreationState.on_load,
    )

    return authenticated_layout(content, current_page="streams")
```

---

**Last Updated:** 2025-11-23
**Next Review:** After implementation complete
**Owner:** Claude Code
