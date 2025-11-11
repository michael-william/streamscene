# E Ink Frame Preview Implementation Plan

**Created:** November 8, 2025
**Feature Branch:** `feature/eink-preview`
**Status:** Planning Phase

---

## Overview

Implement a real-time preview showing how posts will appear on the StreamScene E Ink frame (800x480px, 6-color display). Users should see exactly how their message will be formatted, sized, and positioned on the physical device before posting.

---

## Display Specifications

### Hardware Constraints
- **Resolution:** 800×480 pixels
- **Colors:** 6 colors only (Black, White, Red, Yellow, Blue, Green)
- **Display Mode:** Monochrome text (black on white background for MVP)
- **Refresh Time:** ~30 seconds (informational, not affecting preview)

### Layout Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │ ← Top margin: 40px
│   Stream Name                                      Nov 8, 2025      │ ← Header: 60px
│                                                    2:34 PM          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│                                                                     │
│   Message content goes here with proper wrapping                   │
│   and sizing. This is the main focus area.                         │
│                                                                     │ ← Content area: 280px
│   Text should be large, readable, and centered                     │
│   vertically within the available space.                           │
│                                                                     │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Posted by: John Doe                                              │ ← Footer: 60px
│                                                                     │
│                                                                     │ ← Bottom margin: 40px
└─────────────────────────────────────────────────────────────────────┘

Total Height Breakdown:
- Top margin: 40px
- Header: 60px (stream name + timestamp)
- Divider: 2px
- Content area: 280px (main message)
- Divider: 2px
- Footer: 60px (author name)
- Bottom margin: 40px
─────────────
Total: 484px (leaves 4px buffer, actual display is 480px)

Width Breakdown:
- Left margin: 60px
- Content width: 680px
- Right margin: 60px
─────────────
Total: 800px
```

---

## Typography Specifications

### Font Sizing Strategy

Text should **dynamically resize** based on content length to maximize readability:

#### Character Count Thresholds
1. **Short messages (< 100 chars):**
   - Font size: 48px
   - Line height: 1.4
   - Max lines: 4

2. **Medium messages (100-200 chars):**
   - Font size: 36px
   - Line height: 1.4
   - Max lines: 6

3. **Long messages (200-300 chars):**
   - Font size: 28px
   - Line height: 1.3
   - Max lines: 8

4. **Very long messages (300-400 chars):**
   - Font size: 22px
   - Line height: 1.3
   - Max lines: 10

5. **Extreme length (> 400 chars):**
   - Font size: 18px
   - Line height: 1.2
   - Max lines: 12
   - Show warning: "Message is very long and may be hard to read on device"

### Header/Footer Typography
- **Stream name:** 20px, bold, truncate with ellipsis if > 40 chars
- **Timestamp:** 18px, regular
- **Author name:** 18px, regular, prefix "Posted by: "

### Font Family
- **Preview font:** `"Courier New", "Courier", monospace` (monospaced for accurate character counting)
- **Actual device:** Will use system fonts available on Raspberry Pi (likely DejaVu Sans)

---

## Text Wrapping & Overflow

### Word Wrapping Algorithm
1. Split message into words
2. Build lines by adding words until width exceeds `content_width - padding`
3. Break to new line when width exceeded
4. Continue until all text placed or max lines reached

### Overflow Handling
- **If text exceeds max lines:**
  - Truncate at last complete word that fits
  - Add "..." to indicate truncation
  - Show warning: "Message will be truncated on device. Consider shortening."
  - Display character count: "387 / 400 recommended"

### Character Limits (Recommendations)
- **Soft limit:** 400 characters (warning shown)
- **Hard limit:** None (user can post, but truncation warning shown)

---

## Preview Component Architecture (Composable Design)

### Design Principles
1. **Separation of Concerns:** Layout, content, and theming are separate
2. **Composable:** Header, content, and footer are independent components
3. **Theme-Ready:** Colors and styles abstracted into theme system
4. **Content-Agnostic:** Easy to add image support without refactoring

### File Structure
```
streamscene/components/
├── eink/
│   ├── __init__.py
│   ├── preview.py           # Main preview container
│   ├── layout.py            # Layout components (header, footer, content area)
│   ├── theme.py             # Theme definitions and color schemes
│   ├── content_renderers.py # Text and image content renderers
│   └── text_utils.py        # Text measurement utilities
```

---

## Theme System

### Theme Structure

**Location:** `streamscene/components/eink/theme.py`

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class EInkTheme:
    """Theme definition for E Ink display preview."""

    # Theme identification
    name: str
    description: str

    # Colors (using E Ink 6-color palette)
    background_color: str  # white, black, red, yellow, blue, green
    text_color: str        # white, black, red, yellow, blue, green
    header_color: str      # Optional accent color for headers
    divider_color: str     # Divider line color

    # Typography
    font_family: str       # Font family for preview
    header_weight: str     # bold, normal

    # Visual style
    show_dividers: bool    # Show dividers between sections
    border_style: str      # "solid", "none", "rounded"


# Pre-defined themes
CLASSIC_THEME = EInkTheme(
    name="classic",
    description="Black text on white background (default)",
    background_color="white",
    text_color="black",
    header_color="black",
    divider_color="#cccccc",
    font_family="monospace",
    header_weight="bold",
    show_dividers=True,
    border_style="solid",
)

DARK_MODE_THEME = EInkTheme(
    name="dark",
    description="White text on black background",
    background_color="black",
    text_color="white",
    header_color="white",
    divider_color="#444444",
    font_family="monospace",
    header_weight="bold",
    show_dividers=True,
    border_style="solid",
)

ACCENT_RED_THEME = EInkTheme(
    name="accent_red",
    description="Black text with red header accents",
    background_color="white",
    text_color="black",
    header_color="red",
    divider_color="#ffcccc",
    font_family="monospace",
    header_weight="bold",
    show_dividers=True,
    border_style="solid",
)

# Theme registry
THEMES = {
    "classic": CLASSIC_THEME,
    "dark": DARK_MODE_THEME,
    "accent_red": ACCENT_RED_THEME,
}

def get_theme(name: str = "classic") -> EInkTheme:
    """Get theme by name, fallback to classic."""
    return THEMES.get(name, CLASSIC_THEME)
```

---

## Composable Layout Components

### Location: `streamscene/components/eink/layout.py`

```python
"""Composable layout components for E Ink preview."""

import reflex as rx
from .theme import EInkTheme, get_theme

# Layout constants
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480
HEADER_HEIGHT = 60
FOOTER_HEIGHT = 60
TOP_MARGIN = 40
BOTTOM_MARGIN = 40
HORIZONTAL_MARGIN = 60
CONTENT_HEIGHT = 280
CONTENT_WIDTH = 680


def eink_header(
    stream_name: str,
    timestamp: str,
    theme: EInkTheme
) -> rx.Component:
    """Render E Ink display header (stream name + timestamp)."""
    return rx.hstack(
        rx.text(
            stream_name,
            font_size="20px",
            font_weight=theme.header_weight,
            color=theme.header_color,
            font_family=theme.font_family,
        ),
        rx.spacer(),
        rx.text(
            timestamp,
            font_size="18px",
            color=theme.text_color,
            font_family=theme.font_family,
        ),
        width="100%",
        height=f"{HEADER_HEIGHT}px",
        align="center",
    )


def eink_footer(
    author_name: str,
    theme: EInkTheme,
    show_prefix: bool = True
) -> rx.Component:
    """Render E Ink display footer (author info)."""
    text_content = f"Posted by: {author_name}" if show_prefix else author_name

    return rx.box(
        rx.text(
            text_content,
            font_size="18px",
            color=theme.text_color,
            font_family=theme.font_family,
        ),
        width="100%",
        height=f"{FOOTER_HEIGHT}px",
        display="flex",
        align_items="center",
    )


def eink_divider(theme: EInkTheme) -> rx.Component:
    """Render themed divider line."""
    if not theme.show_dividers:
        return rx.box(height="0px")

    return rx.divider(
        border_color=theme.divider_color,
        margin_y="0",
    )


def eink_content_area(
    content: rx.Component,
    theme: EInkTheme
) -> rx.Component:
    """
    Render content area container.

    This is a generic container that can hold any content
    (text, images, mixed content, etc.)
    """
    return rx.box(
        content,
        width=f"{CONTENT_WIDTH}px",
        height=f"{CONTENT_HEIGHT}px",
        display="flex",
        align_items="center",
        justify_content="center",
        overflow="hidden",
        color=theme.text_color,
        font_family=theme.font_family,
    )
```

---

## Content Renderers (Composable)

### Location: `streamscene/components/eink/content_renderers.py`

```python
"""Content renderers for different post types."""

import reflex as rx
from typing import List
from .theme import EInkTheme
from .text_utils import wrap_text, calculate_font_size


def text_content_renderer(
    text: str,
    theme: EInkTheme,
    max_width: int = 680,
    max_height: int = 280
) -> rx.Component:
    """
    Render text content with dynamic sizing.

    This is a pure function that takes text and theme,
    returns a rendered component.
    """
    # Calculate optimal font size
    font_size = calculate_font_size(text)
    line_height = calculate_line_height(font_size)

    return rx.text(
        text,
        font_size=f"{font_size}px",
        line_height=str(line_height),
        text_align="center",
        color=theme.text_color,
        font_family=theme.font_family,
        white_space="pre-wrap",
        word_wrap="break-word",
    )


def image_content_renderer(
    image_url: str,
    theme: EInkTheme,
    max_width: int = 680,
    max_height: int = 280
) -> rx.Component:
    """
    Render image content (future implementation).

    Will handle:
    - 6-color dithering preview
    - Image scaling to fit
    - Aspect ratio preservation
    """
    return rx.box(
        rx.image(
            src=image_url,
            max_width=f"{max_width}px",
            max_height=f"{max_height}px",
            object_fit="contain",
            # Future: Apply 6-color filter
            # filter="grayscale(1) contrast(1.2)"
        ),
        width="100%",
        height="100%",
        display="flex",
        align_items="center",
        justify_content="center",
    )


def mixed_content_renderer(
    text: str,
    image_url: str,
    theme: EInkTheme,
    max_width: int = 680,
    max_height: int = 280
) -> rx.Component:
    """
    Render mixed text + image content (future implementation).

    Layout options:
    - Image top, text bottom
    - Image left, text right
    - Image background with overlay text
    """
    return rx.vstack(
        # Image takes 60% of height
        rx.box(
            image_content_renderer(image_url, theme, max_width, int(max_height * 0.6)),
            height=f"{int(max_height * 0.6)}px",
        ),
        # Text takes 40% of height
        rx.box(
            text_content_renderer(text, theme, max_width, int(max_height * 0.4)),
            height=f"{int(max_height * 0.4)}px",
        ),
        spacing="0",
        width="100%",
        height="100%",
    )
```

---

## Main Preview Component (Composable)

### Location: `streamscene/components/eink/preview.py`

```python
"""Main E Ink preview component (composable architecture)."""

import reflex as rx
from datetime import datetime
from typing import Optional, Literal
from .theme import get_theme, EInkTheme
from .layout import (
    eink_header,
    eink_footer,
    eink_divider,
    eink_content_area,
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
    TOP_MARGIN,
    BOTTOM_MARGIN,
    HORIZONTAL_MARGIN,
)
from .content_renderers import (
    text_content_renderer,
    image_content_renderer,
    mixed_content_renderer,
)


def eink_preview(
    # Content
    text_content: str = "",
    image_url: Optional[str] = None,
    content_type: Literal["text", "image", "mixed"] = "text",

    # Metadata
    stream_name: str = "Stream Name",
    author_name: str = "Author",
    timestamp: Optional[str] = None,

    # Theming
    theme_name: str = "classic",
    custom_theme: Optional[EInkTheme] = None,

    # Display options
    show_header: bool = True,
    show_footer: bool = True,
    show_author_prefix: bool = True,

) -> rx.Component:
    """
    Composable E Ink preview component.

    Args:
        text_content: Text to display
        image_url: Image URL (for image/mixed content)
        content_type: Type of content ("text", "image", "mixed")
        stream_name: Stream name for header
        author_name: Author name for footer
        timestamp: Timestamp string (defaults to current time)
        theme_name: Theme name from registry
        custom_theme: Custom theme object (overrides theme_name)
        show_header: Whether to show header
        show_footer: Whether to show footer
        show_author_prefix: Whether to show "Posted by: " prefix

    Returns:
        Reflex component representing E Ink display
    """
    # Get theme
    theme = custom_theme or get_theme(theme_name)

    # Generate timestamp if not provided
    if timestamp is None:
        timestamp = datetime.now().strftime("%b %d, %Y\n%I:%M %p")

    # Select content renderer based on type
    if content_type == "text":
        content = text_content_renderer(text_content, theme)
    elif content_type == "image" and image_url:
        content = image_content_renderer(image_url, theme)
    elif content_type == "mixed" and image_url:
        content = mixed_content_renderer(text_content, image_url, theme)
    else:
        # Fallback to text
        content = text_content_renderer(text_content or "No content", theme)

    # Build layout
    return rx.box(
        rx.vstack(
            # Top margin
            rx.box(height=f"{TOP_MARGIN}px"),

            # Header (conditional)
            rx.cond(
                show_header,
                rx.fragment(
                    eink_header(stream_name, timestamp, theme),
                    eink_divider(theme),
                ),
            ),

            # Content area
            eink_content_area(content, theme),

            # Footer (conditional)
            rx.cond(
                show_footer,
                rx.fragment(
                    eink_divider(theme),
                    eink_footer(author_name, theme, show_author_prefix),
                ),
            ),

            # Bottom margin
            rx.box(height=f"{BOTTOM_MARGIN}px"),

            spacing="0",
            width="100%",
            height="100%",
        ),
        # Container styling
        width=f"{DISPLAY_WIDTH}px",
        height=f"{DISPLAY_HEIGHT}px",
        background=theme.background_color,
        padding=f"0 {HORIZONTAL_MARGIN}px",
        border=f"4px {theme.border_style} {theme.text_color}",
        border_radius="8px" if theme.border_style == "rounded" else "0",
        overflow="hidden",
    )
```

---

## Usage Examples

### Basic Text Preview (Current Use Case)

```python
from streamscene.components.eink.preview import eink_preview

# Simple text preview
preview = eink_preview(
    text_content="Hello family! This is a test message.",
    stream_name="Family Updates",
    author_name="John Doe",
)
```

### With Custom Theme

```python
# Dark mode preview
dark_preview = eink_preview(
    text_content="Good night everyone!",
    stream_name="Family Updates",
    author_name="Jane Doe",
    theme_name="dark",
)
```

### Future: Image Support

```python
# Image-only post
image_preview = eink_preview(
    image_url="/uploads/family_photo.jpg",
    content_type="image",
    stream_name="Photos",
    author_name="Mom",
)

# Mixed content post
mixed_preview = eink_preview(
    text_content="Check out this sunset!",
    image_url="/uploads/sunset.jpg",
    content_type="mixed",
    stream_name="Moments",
    author_name="Dad",
)
```

### Custom Theme Creation

```python
from streamscene.components.eink.theme import EInkTheme

# Create custom theme
beach_theme = EInkTheme(
    name="beach",
    description="Blue accents for beach vacation stream",
    background_color="white",
    text_color="black",
    header_color="blue",
    divider_color="#cce5ff",
    font_family="monospace",
    header_weight="bold",
    show_dividers=True,
    border_style="rounded",
)

# Use custom theme
preview = eink_preview(
    text_content="At the beach!",
    custom_theme=beach_theme,
)
```

---

## Text Measurement Utilities

**Location:** `streamscene/components/text_utils.py`

### Character Width Estimation

Since we can't measure exact text width in Python backend, we'll use **average character width approximations**:

```python
def estimate_text_width(text: str, font_size: int, font_family: str = "monospace") -> int:
    """
    Estimate text width in pixels using average character widths.

    For monospace fonts (Courier New):
    - Character width ≈ font_size * 0.6

    For proportional fonts (DejaVu Sans):
    - Average character width ≈ font_size * 0.5
    """
    if font_family == "monospace":
        char_width = font_size * 0.6
    else:
        char_width = font_size * 0.5

    return int(len(text) * char_width)


def wrap_text(
    text: str,
    max_width: int,
    font_size: int,
    font_family: str = "monospace"
) -> List[str]:
    """
    Wrap text to fit within max_width pixels.

    Args:
        text: Text to wrap
        max_width: Maximum width in pixels (680px for E Ink content area)
        font_size: Font size in pixels
        font_family: Font family for width calculation

    Returns:
        List of wrapped lines
    """
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        # Try adding word to current line
        test_line = " ".join(current_line + [word])
        test_width = estimate_text_width(test_line, font_size, font_family)

        if test_width <= max_width:
            current_line.append(word)
        else:
            # Start new line
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]

    # Add final line
    if current_line:
        lines.append(" ".join(current_line))

    return lines


def truncate_to_max_lines(lines: List[str], max_lines: int) -> List[str]:
    """
    Truncate lines to max_lines, adding ellipsis to last line if needed.
    """
    if len(lines) <= max_lines:
        return lines

    truncated = lines[:max_lines]
    truncated[-1] = truncated[-1].rstrip() + "..."

    return truncated
```

---

## Integration with Post Creation Form

### Modified: `streamscene/pages/stream_posts.py`

Add preview toggle and live preview below post creation textarea:

```python
# In stream_posts_page() function, modify post creation form:

rx.card(
    rx.vstack(
        rx.text("Create a new post", weight="medium", size="4"),

        # Textarea
        rx.text_area(
            placeholder="Write your message...",
            value=StreamPostsState.new_post_content,
            on_change=StreamPostsState.set_new_post_content,
            size="3",
            rows="4",
        ),

        # Character count
        rx.text(
            f"{len(StreamPostsState.new_post_content)} characters",
            size="2",
            color="gray",
        ),

        # Preview toggle
        rx.switch(
            checked=StreamPostsState.show_preview,
            on_change=StreamPostsState.set_show_preview,
            label="Show E Ink Preview",
        ),

        # Preview (conditional)
        rx.cond(
            StreamPostsState.show_preview,
            rx.box(
                eink_preview_component(
                    text_content=StreamPostsState.new_post_content,
                    stream_name=StreamPostsState.stream_name,
                    author_name="You",  # Current user
                ),
                margin_top="4",
                # Scale preview to fit screen (800px is wide)
                transform="scale(0.7)",
                transform_origin="top left",
            ),
        ),

        # Warning message (if any)
        rx.cond(
            StreamPostsState.preview_warning,
            rx.callout(
                StreamPostsState.preview_warning,
                icon="triangle_alert",
                color_scheme="yellow",
                size="2",
            ),
        ),

        # Post button
        rx.button(
            "Post Message",
            on_click=StreamPostsState.create_post,
        ),

        spacing="3",
        width="100%",
    ),
    size="3",
    width="100%",
)
```

### New State Variables

Add to `StreamPostsState`:

```python
# Preview state
show_preview: bool = False

@rx.var
def preview_warning(self) -> str:
    """Generate preview warning message."""
    char_count = len(self.new_post_content)
    if char_count > 400:
        return f"⚠️ Long message ({char_count} chars). May be hard to read on device."
    # Add more conditions as needed
    return ""
```

---

## Preview Scaling for Web UI

### Desktop View
- Preview at **70% scale** (560×336px) to fit comfortably in the UI
- Show actual dimensions label: "Preview (800×480px, scaled to fit)"

### Mobile View
- Preview at **50% scale** (400×240px)
- Consider hiding preview by default on mobile (toggle on demand)

### Scaling Implementation

```python
rx.box(
    rx.text(
        "E Ink Frame Preview (800×480px, scaled to fit)",
        size="2",
        color="gray",
        margin_bottom="2",
    ),
    rx.box(
        eink_preview_component(...),
        # Desktop scale
        transform="scale(0.7)",
        transform_origin="top left",
        # Mobile scale override
        _media={
            "@media (max-width: 768px)": {
                "transform": "scale(0.5)",
            }
        },
    ),
)
```

---

## Implementation Steps (Composable Architecture)

### Phase 1: Foundation - Theme System (Day 1)
1. Create `streamscene/components/eink/` directory structure
2. Implement `theme.py`:
   - `EInkTheme` dataclass
   - Pre-defined themes (CLASSIC, DARK, ACCENT_RED)
   - `get_theme()` helper function
3. Write unit tests for theme system

### Phase 2: Layout Components (Day 1)
1. Implement `layout.py`:
   - Layout constants (dimensions, margins)
   - `eink_header()` - Header component
   - `eink_footer()` - Footer component
   - `eink_divider()` - Themed divider
   - `eink_content_area()` - Generic content container
2. Test each layout component independently

### Phase 3: Text Utilities (Day 1)
1. Implement `text_utils.py`:
   - `estimate_text_width()` - Character width estimation
   - `calculate_font_size()` - Dynamic font sizing based on text length
   - `calculate_line_height()` - Line height calculation
   - `wrap_text()` - Word wrapping algorithm
   - `truncate_to_max_lines()` - Overflow handling
2. Write comprehensive unit tests for text utilities

### Phase 4: Content Renderers (Day 2)
1. Implement `content_renderers.py`:
   - `text_content_renderer()` - Text rendering with dynamic sizing
   - `image_content_renderer()` - Image placeholder (full implementation later)
   - `mixed_content_renderer()` - Mixed content placeholder (full implementation later)
2. Test text renderer with various lengths and themes

### Phase 5: Main Preview Component (Day 2)
1. Implement `preview.py`:
   - `eink_preview()` - Composable main component
   - Content type routing logic
   - Theme application
   - Conditional rendering (header/footer toggles)
2. Test with different content types and themes

### Phase 6: Integration with Post Creation (Day 2-3)
1. Update `stream_posts.py`:
   - Add `show_preview: bool` state variable
   - Add preview toggle switch
   - Add character counter
   - Integrate `eink_preview()` component
   - Add preview scaling for responsive design
2. Add warning messages for long content

### Phase 7: Polish & Testing (Day 3)
1. Test edge cases:
   - Empty message
   - Very short messages (< 10 chars)
   - Very long messages (> 500 chars)
   - Messages with newlines
   - Special characters and emoji
   - Different themes
2. Optimize performance (debounce text updates)
3. Responsive design testing (desktop + mobile)
4. User testing with real content

### Phase 8: Future-Proofing (Optional)
1. Add database field for stream theme preference
2. Create theme selector UI
3. Document how to add new themes
4. Document how to extend for image support

---

## Testing Checklist

### Unit Tests
- [ ] `estimate_text_width()` accuracy
- [ ] `wrap_text()` with various lengths
- [ ] `truncate_to_max_lines()` with ellipsis
- [ ] Font size calculation for different char counts

### Integration Tests
- [ ] Preview updates on text change
- [ ] Toggle show/hide preview
- [ ] Warning messages appear correctly
- [ ] Scaling works on desktop/mobile

### Manual Testing
- [ ] Short message (50 chars) → Large font
- [ ] Medium message (150 chars) → Medium font
- [ ] Long message (300 chars) → Small font
- [ ] Very long message (500 chars) → Truncation warning
- [ ] Message with line breaks
- [ ] Message with special characters
- [ ] Empty message handling

### Real-World Testing
- [ ] Test with actual family messages
- [ ] Compare preview to actual device display (when hardware available)
- [ ] Validate font sizes are readable on 7.3" display

---

## Future Enhancements (Enabled by Composable Architecture)

### 1. Stream-Specific Themes
**Database Schema Addition:**
```python
# Add to Stream model
theme_name: str = Column(String(50), default="classic", nullable=False)
```

**Usage:**
```python
# In stream_posts.py, pass stream's theme to preview
preview = eink_preview(
    text_content=StreamPostsState.new_post_content,
    theme_name=StreamPostsState.stream_theme,  # From stream settings
)
```

**Benefits:**
- Each stream can have its own visual identity
- Family streams = classic theme
- Kids streams = bright colored theme
- Night streams = dark theme

---

### 2. Image Support (Already Architected)

Since content renderers are separate from layout, adding images requires:

**Step 1:** Implement 6-color dithering in `content_renderers.py`
```python
def apply_eink_filter(image_url: str) -> str:
    """
    Apply 6-color E Ink filter to image.
    Returns URL to processed image.
    """
    # Server-side processing (already planned for Phase 5)
    pass
```

**Step 2:** Update `image_content_renderer()` (no layout changes needed)
```python
def image_content_renderer(image_url: str, theme: EInkTheme, ...):
    processed_url = apply_eink_filter(image_url)
    return rx.image(src=processed_url, ...)
```

**Step 3:** Use in preview
```python
preview = eink_preview(
    image_url="/uploads/photo.jpg",
    content_type="image",  # Already supported!
)
```

**No changes needed to:**
- Layout components
- Theme system
- Main preview component

---

### 3. Custom Theme Editor UI

**User Flow:**
1. Stream owner navigates to stream settings
2. Clicks "Customize Display Theme"
3. Opens theme editor modal with:
   - Background color picker (6 colors)
   - Text color picker (6 colors)
   - Header color picker (6 colors)
   - Live preview showing changes
4. Saves custom theme to database

**Implementation:**
```python
# In stream settings page
custom_theme = EInkTheme(
    name=f"custom_{stream_id}",
    background_color=selected_bg,
    text_color=selected_text,
    header_color=selected_header,
    # ... other settings
)

# Save to stream.theme_json column (new JSON field)
stream.theme_json = custom_theme.to_dict()
```

---

### 4. Rotation Preview (Multi-Post Preview)

**New Component:** `eink_rotation_preview.py`
```python
def eink_rotation_preview(
    posts: List[Post],
    stream_name: str,
    theme_name: str,
    interval_seconds: int = 5
) -> rx.Component:
    """
    Preview multiple posts rotating like on device.
    Reuses eink_preview() for each post!
    """
    return rx.box(
        rx.foreach(
            posts,
            lambda post: eink_preview(
                text_content=post.text_content,
                stream_name=stream_name,
                theme_name=theme_name,
            )
        ),
        # Add slideshow animation
    )
```

**Benefits of Composable Architecture:**
- Rotation preview just composes multiple `eink_preview()` calls
- No duplication of layout logic
- Changes to layout automatically apply to rotation view

---

### 5. Mixed Content Layouts

**Different layout modes for text + image:**

```python
# Top-aligned image with text below
mixed_preview = eink_preview(
    text_content="Family reunion!",
    image_url="/photo.jpg",
    content_type="mixed",
    layout_mode="image_top",  # Future parameter
)

# Side-by-side layout
mixed_preview = eink_preview(
    text_content="Beach day!",
    image_url="/photo.jpg",
    content_type="mixed",
    layout_mode="side_by_side",  # Future parameter
)

# Background image with overlay text
mixed_preview = eink_preview(
    text_content="Good morning!",
    image_url="/photo.jpg",
    content_type="mixed",
    layout_mode="overlay",  # Future parameter
)
```

**Implementation requires only updating:**
- `mixed_content_renderer()` in `content_renderers.py`
- No changes to theme system, layout components, or main preview

---

### 6. Per-User Display Name on Device

**Future Enhancement:**
```python
# Users can set custom display names for posts on their device
# (same post shows different author names on different devices)

# In device settings:
device.author_display_preferences = {
    "user_uuid_1": "Mom",
    "user_uuid_2": "Dad",
    "user_uuid_3": "Sarah",
}

# Preview uses device owner's preferences:
preview = eink_preview(
    text_content="Hello!",
    author_name=get_display_name(post.author_id, current_device_id),
)
```

---

## Why Composable Architecture Matters

### Traditional Monolithic Approach (What We Avoided)
```python
def eink_preview_monolithic(post, stream):
    """One giant function doing everything."""
    # 200+ lines of mixed layout, theming, and content logic
    # Hard to extend
    # Hard to test
    # Can't reuse parts
```

**Problems:**
- ❌ Adding images requires refactoring entire component
- ❌ Adding themes requires modifying layout code
- ❌ Can't test layout separately from content
- ❌ Can't reuse header/footer in other views

### Our Composable Approach (What We Built)
```python
# Separate concerns
theme = get_theme("dark")
header = eink_header(stream.name, timestamp, theme)
content = text_content_renderer(post.text, theme)
footer = eink_footer(post.author.name, theme)

# Compose together
preview = eink_preview(
    text_content=post.text,
    theme_name="dark"
)
```

**Benefits:**
- ✅ Adding images = new content renderer only
- ✅ Adding themes = new theme definition only
- ✅ Each component testable independently
- ✅ Can reuse layout components elsewhere
- ✅ Easy to extend without breaking existing code

---

### Example: Adding a New Theme (5 minutes)

```python
# File: streamscene/components/eink/theme.py

SUNSET_THEME = EInkTheme(
    name="sunset",
    description="Warm sunset colors",
    background_color="yellow",  # Pale yellow background
    text_color="black",
    header_color="red",  # Red accents
    divider_color="#ffddaa",
    font_family="monospace",
    header_weight="bold",
    show_dividers=True,
    border_style="rounded",
)

# Add to registry
THEMES["sunset"] = SUNSET_THEME
```

**That's it!** Theme now works everywhere preview is used.

---

### Example: Adding Image Support (1 day of work)

**Step 1:** Implement image processing (already planned for Phase 5)
**Step 2:** Update `image_content_renderer()` in `content_renderers.py`
**Step 3:** Done!

**What DOESN'T need to change:**
- Layout components (header, footer, dividers)
- Theme system
- Main preview component
- Text rendering logic
- Integration with stream_posts.py

This is the power of composable architecture!

---

## Technical Considerations

### Performance
- Text wrapping calculations should be fast (<100ms)
- Use memoization/caching for expensive calculations
- Debounce preview updates on text input (300ms delay)

### Accessibility
- Preview should have alt text describing content
- Support keyboard navigation for preview toggle
- Ensure sufficient color contrast in preview

### Browser Compatibility
- Test CSS transforms (scale) on all major browsers
- Fallback for browsers without transform support
- Test on mobile Safari, Chrome, Firefox

---

## Git Workflow

### Feature Branch
```bash
# Create feature branch
git checkout -b feature/eink-preview

# Make commits with descriptive messages
git commit -m "Add text wrapping utilities for E Ink preview"
git commit -m "Implement EInkPreview component with dynamic font sizing"
git commit -m "Integrate preview into post creation form"

# Push to remote
git push -u origin feature/eink-preview

# Create pull request when ready
```

### Commit Message Convention
- **feat:** New features (e.g., "feat: add E Ink preview component")
- **fix:** Bug fixes
- **test:** Test additions
- **docs:** Documentation updates
- **refactor:** Code refactoring
- **style:** Formatting changes

---

## Success Criteria

1. ✅ Users can toggle preview on/off
2. ✅ Preview accurately reflects 800×480px layout
3. ✅ Text dynamically resizes based on length
4. ✅ Word wrapping works correctly
5. ✅ Truncation warnings appear when needed
6. ✅ Preview is responsive (desktop + mobile)
7. ✅ Character count shown in real-time
8. ✅ No performance issues (updates < 300ms)

---

## Questions to Resolve

1. **Font availability on Raspberry Pi:**
   - Need to confirm which fonts are installed on device
   - May need to install specific fonts for consistency

2. **Actual text rendering on E Ink:**
   - Preview uses web fonts; device uses system fonts
   - May have slight differences in layout
   - Plan to validate with real hardware when available

3. **User preference for always showing preview:**
   - Should preview default to on or off?
   - Store preference in user settings?

---

**Next Steps:**
1. Create feature branch
2. Start with Phase 1 (text utilities)
3. Build incrementally and test frequently
4. Document any deviations from plan

**Estimated Timeline:** 3 days for full implementation + testing
**Priority:** Medium (nice-to-have for MVP, essential for UX)

---

*Last Updated: November 8, 2025*
