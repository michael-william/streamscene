"""Main E Ink preview component (composable architecture).

This module provides the main eink_preview() function that composes
all layout and content components together to create a complete
E Ink display preview.
"""

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
    """Composable E Ink preview component.

    This function composes layout and content components together to create
    a preview of how content will appear on the E Ink display (800×480px).

    Args:
        text_content: Text to display
        image_url: Image URL (for image/mixed content)
        content_type: Type of content ("text", "image", "mixed")
        stream_name: Stream name for header
        author_name: Author name for footer
        timestamp: Timestamp string (defaults to current time)
        theme_name: Theme name from registry ("classic", "dark", etc.)
        custom_theme: Custom theme object (overrides theme_name)
        show_header: Whether to show header
        show_footer: Whether to show footer
        show_author_prefix: Whether to show "Posted by: " prefix

    Returns:
        Reflex component representing E Ink display

    Example:
        >>> # Basic text preview
        >>> preview = eink_preview(
        ...     text_content="Hello family!",
        ...     stream_name="Family Updates",
        ...     author_name="John Doe"
        ... )
        >>>
        >>> # Dark mode preview
        >>> preview = eink_preview(
        ...     text_content="Good night!",
        ...     stream_name="Family Updates",
        ...     author_name="Jane Doe",
        ...     theme_name="dark"
        ... )
        >>>
        >>> # Image preview (future)
        >>> preview = eink_preview(
        ...     image_url="/uploads/photo.jpg",
        ...     content_type="image",
        ...     stream_name="Photos",
        ...     author_name="Mom"
        ... )
    """
    # Get theme
    theme = custom_theme or get_theme(theme_name)

    # Debug logging
    print(f"[EINK_PREVIEW] theme_name parameter: '{theme_name}'")
    print(f"[EINK_PREVIEW] Retrieved theme: {theme.name}")
    print(f"[EINK_PREVIEW] Background color: {theme.background_color}")
    print(f"[EINK_PREVIEW] Text color: {theme.text_color}")

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
        # Fallback to text (or show placeholder for invalid state)
        content = text_content_renderer(
            text_content or "No content to preview",
            theme
        )

    # Build layout by composing components
    layout_components = []

    # Debug banner (temporary - shows active theme)
    layout_components.append(
        rx.box(
            rx.text(
                f"Theme: {theme.name}",
                font_size="12px",
                color="red",
                font_weight="bold",
                background="yellow",
                padding="2px 8px",
            ),
            width="100%",
            display="flex",
            justify_content="center",
        )
    )

    # Top margin
    layout_components.append(rx.box(height=f"{TOP_MARGIN}px"))

    # Header (conditional)
    if show_header:
        layout_components.extend([
            eink_header(stream_name, timestamp, theme),
            eink_divider(theme),
        ])

    # Content area (always shown)
    layout_components.append(eink_content_area(content, theme))

    # Footer (conditional)
    if show_footer:
        layout_components.extend([
            eink_divider(theme),
            eink_footer(author_name, theme, show_author_prefix),
        ])

    # Bottom margin
    layout_components.append(rx.box(height=f"{BOTTOM_MARGIN}px"))

    # Compose all components into vertical stack
    return rx.box(
        rx.vstack(
            *layout_components,
            spacing="0",
            width="100%",
            height="100%",
        ),
        # Container styling
        width=f"{DISPLAY_WIDTH}px",
        height=f"{DISPLAY_HEIGHT}px",
        padding=f"0 {HORIZONTAL_MARGIN}px",
        border=f"4px {theme.border_style} {theme.text_color}",
        border_radius="8px" if theme.border_style == "rounded" else "0",
        overflow="hidden",
        box_shadow="0 4px 6px rgba(0, 0, 0, 0.1)",  # Subtle shadow for depth
        style={
            "background": theme.background_color,  # Supports both solid colors and CSS gradients
        },
    )
