"""Content renderers for different post types.

This module provides pure rendering functions for different content types:
- Text content with dynamic sizing
- Image content (future implementation)
- Mixed text + image content (future implementation)
"""

import reflex as rx
from .theme import EInkTheme
from .text_utils import calculate_font_size, calculate_line_height


def text_content_renderer(
    text: str,
    theme: EInkTheme,
    max_width: int = 680,
    max_height: int = 280
) -> rx.Component:
    """Render text content with dynamic sizing.

    This is a pure function that takes text and theme,
    returns a rendered component with optimal font sizing.

    Args:
        text: Text content to render
        theme: EInkTheme object for styling
        max_width: Maximum width in pixels (default: 680)
        max_height: Maximum height in pixels (default: 280)

    Returns:
        Reflex component for the text content

    Example:
        >>> from streamscene.components.eink.theme import CLASSIC_THEME
        >>> content = text_content_renderer(
        ...     text="Hello family!",
        ...     theme=CLASSIC_THEME
        ... )
    """
    # Handle empty text
    if not text.strip():
        return rx.text(
            "No content",
            font_size="24px",
            color="gray",
            font_style="italic",
        )

    # Calculate optimal font size based on text length
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
        overflow="hidden",
        max_height=f"{max_height}px",
        width="100%",
        padding="10px",
    )


def image_content_renderer(
    image_url: str,
    theme: EInkTheme,
    max_width: int = 680,
    max_height: int = 280
) -> rx.Component:
    """Render image content (future implementation).

    Will handle:
    - 6-color dithering preview
    - Image scaling to fit
    - Aspect ratio preservation

    Args:
        image_url: URL to the image
        theme: EInkTheme object for styling
        max_width: Maximum width in pixels (default: 680)
        max_height: Maximum height in pixels (default: 280)

    Returns:
        Reflex component for the image content

    Example:
        >>> from streamscene.components.eink.theme import CLASSIC_THEME
        >>> content = image_content_renderer(
        ...     image_url="/uploads/photo.jpg",
        ...     theme=CLASSIC_THEME
        ... )
    """
    return rx.box(
        rx.image(
            src=image_url,
            max_width=f"{max_width}px",
            max_height=f"{max_height}px",
            object_fit="contain",
            # Future: Apply 6-color E Ink filter
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
    max_height: int = 280,
    layout_mode: str = "image_top"
) -> rx.Component:
    """Render mixed text + image content (future implementation).

    Layout options:
    - image_top: Image takes 60% of height, text below
    - image_left: Image on left, text on right (50/50 split)
    - overlay: Image background with overlay text

    Args:
        text: Text content
        image_url: URL to the image
        theme: EInkTheme object for styling
        max_width: Maximum width in pixels (default: 680)
        max_height: Maximum height in pixels (default: 280)
        layout_mode: Layout mode ("image_top", "image_left", "overlay")

    Returns:
        Reflex component for the mixed content

    Example:
        >>> from streamscene.components.eink.theme import CLASSIC_THEME
        >>> content = mixed_content_renderer(
        ...     text="Family reunion!",
        ...     image_url="/uploads/photo.jpg",
        ...     theme=CLASSIC_THEME,
        ...     layout_mode="image_top"
        ... )
    """
    if layout_mode == "image_top":
        # Image takes 60% of height, text takes 40%
        return rx.vstack(
            rx.box(
                image_content_renderer(
                    image_url,
                    theme,
                    max_width,
                    int(max_height * 0.6)
                ),
                height=f"{int(max_height * 0.6)}px",
                width="100%",
            ),
            rx.box(
                text_content_renderer(
                    text,
                    theme,
                    max_width,
                    int(max_height * 0.4)
                ),
                height=f"{int(max_height * 0.4)}px",
                width="100%",
            ),
            spacing="0",
            width="100%",
            height="100%",
        )
    elif layout_mode == "image_left":
        # Image on left, text on right (50/50 split)
        return rx.hstack(
            rx.box(
                image_content_renderer(
                    image_url,
                    theme,
                    int(max_width * 0.5),
                    max_height
                ),
                width=f"{int(max_width * 0.5)}px",
                height="100%",
            ),
            rx.box(
                text_content_renderer(
                    text,
                    theme,
                    int(max_width * 0.5),
                    max_height
                ),
                width=f"{int(max_width * 0.5)}px",
                height="100%",
            ),
            spacing="0",
            width="100%",
            height="100%",
        )
    else:
        # Default to image_top
        return mixed_content_renderer(
            text, image_url, theme, max_width, max_height, "image_top"
        )
