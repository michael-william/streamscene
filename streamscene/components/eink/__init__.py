"""E Ink display preview components.

This package provides composable components for previewing how posts
will appear on the StreamScene E Ink frames (800x480px, 6-color display).

Components:
    - theme: Theme system for customizing colors and styles
    - layout: Reusable layout components (header, footer, content area)
    - content_renderers: Renderers for text, images, and mixed content
    - preview: Main preview component
    - text_utils: Text measurement and wrapping utilities

Example usage:
    >>> from streamscene.components.eink import eink_preview
    >>> preview = eink_preview(
    ...     text_content="Hello family!",
    ...     stream_name="Family Updates",
    ...     author_name="John Doe",
    ...     theme_name="classic"
    ... )
"""

from .theme import EInkTheme, get_theme, THEMES, register_theme
from .preview import eink_preview
from .text_utils import get_text_warnings, calculate_font_size

__all__ = [
    # Theme system
    "EInkTheme",
    "get_theme",
    "THEMES",
    "register_theme",
    # Main preview component
    "eink_preview",
    # Utility functions
    "get_text_warnings",
    "calculate_font_size",
]
