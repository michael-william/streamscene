"""Composable layout components for E Ink display preview.

This module provides reusable layout components that can be composed together
to build E Ink display previews. Each component is independent and themed.
"""

import reflex as rx
from .theme import EInkTheme


# Layout constants (based on Waveshare 7.3" display)
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480
HEADER_HEIGHT = 60
FOOTER_HEIGHT = 60
TOP_MARGIN = 40
BOTTOM_MARGIN = 40
HORIZONTAL_MARGIN = 60
CONTENT_HEIGHT = 280  # 480 - 40 (top) - 60 (header) - 60 (footer) - 40 (bottom)
CONTENT_WIDTH = 680   # 800 - 60 (left) - 60 (right)


def eink_header(
    stream_name: str,
    timestamp: str,
    theme: EInkTheme
) -> rx.Component:
    """Render E Ink display header (stream name + timestamp).

    Args:
        stream_name: Name of the stream to display
        timestamp: Formatted timestamp string
        theme: EInkTheme object for styling

    Returns:
        Reflex component for the header

    Example:
        >>> from streamscene.components.eink.theme import CLASSIC_THEME
        >>> header = eink_header(
        ...     stream_name="Family Updates",
        ...     timestamp="Nov 8, 2025\\n2:30 PM",
        ...     theme=CLASSIC_THEME
        ... )
    """
    return rx.hstack(
        rx.text(
            stream_name,
            font_size="20px",
            font_weight=theme.header_weight,
            color=theme.header_color,
            font_family=theme.font_family,
            white_space="nowrap",
            overflow="hidden",
            text_overflow="ellipsis",
            max_width="500px",
        ),
        rx.spacer(),
        rx.text(
            timestamp,
            font_size="18px",
            color=theme.text_color,
            font_family=theme.font_family,
            text_align="right",
            white_space="pre-line",  # Allow line breaks in timestamp
        ),
        width="100%",
        height=f"{HEADER_HEIGHT}px",
        align="center",
        justify="between",
    )


def eink_footer(
    author_name: str,
    theme: EInkTheme,
    show_prefix: bool = True
) -> rx.Component:
    """Render E Ink display footer (author info).

    Args:
        author_name: Name of the post author
        theme: EInkTheme object for styling
        show_prefix: Whether to show "Posted by: " prefix

    Returns:
        Reflex component for the footer

    Example:
        >>> from streamscene.components.eink.theme import CLASSIC_THEME
        >>> footer = eink_footer(
        ...     author_name="John Doe",
        ...     theme=CLASSIC_THEME,
        ...     show_prefix=True
        ... )
    """
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
    """Render themed divider line.

    Args:
        theme: EInkTheme object for styling

    Returns:
        Reflex component for the divider (or empty box if dividers disabled)

    Example:
        >>> from streamscene.components.eink.theme import CLASSIC_THEME
        >>> divider = eink_divider(CLASSIC_THEME)
    """
    if not theme.show_dividers:
        return rx.box(height="0px")

    return rx.divider(
        border_color=theme.divider_color,
        margin_y="0",
        width="100%",
    )


def eink_content_area(
    content: rx.Component,
    theme: EInkTheme
) -> rx.Component:
    """Render content area container.

    This is a generic container that can hold any content
    (text, images, mixed content, etc.). The content is centered
    both horizontally and vertically within the available space.

    Args:
        content: Reflex component to render in content area
        theme: EInkTheme object for styling

    Returns:
        Reflex component wrapping the content

    Example:
        >>> from streamscene.components.eink.theme import CLASSIC_THEME
        >>> text_content = rx.text("Hello world!", font_size="48px")
        >>> content_area = eink_content_area(text_content, CLASSIC_THEME)
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
