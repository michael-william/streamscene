"""Text measurement and wrapping utilities for E Ink preview.

This module provides utilities for calculating optimal font sizes,
estimating text dimensions, and wrapping text to fit within the
E Ink display constraints.
"""

from typing import List, Tuple


def calculate_font_size(text: str) -> int:
    """Calculate optimal font size based on text length.

    Uses character count to determine appropriate font size that
    maximizes readability while ensuring text fits in the content area.

    Args:
        text: Text content to size

    Returns:
        Font size in pixels

    Example:
        >>> calculate_font_size("Short")
        48
        >>> calculate_font_size("A" * 250)
        28
    """
    char_count = len(text)

    if char_count < 100:
        return 48  # Large font for short messages
    elif char_count < 200:
        return 36  # Medium font
    elif char_count < 300:
        return 28  # Smaller font
    elif char_count < 400:
        return 22  # Even smaller
    else:
        return 18  # Minimum readable size


def calculate_line_height(font_size: int) -> float:
    """Calculate line height based on font size.

    Args:
        font_size: Font size in pixels

    Returns:
        Line height multiplier

    Example:
        >>> calculate_line_height(48)
        1.4
        >>> calculate_line_height(18)
        1.2
    """
    if font_size >= 36:
        return 1.4  # More spacing for large text
    elif font_size >= 22:
        return 1.3  # Medium spacing
    else:
        return 1.2  # Tighter spacing for small text


def get_max_lines(font_size: int, content_height: int = 280) -> int:
    """Calculate maximum number of lines that fit in content area.

    Args:
        font_size: Font size in pixels
        content_height: Available height in pixels (default: 280)

    Returns:
        Maximum number of lines

    Example:
        >>> get_max_lines(48)
        4
        >>> get_max_lines(18)
        12
    """
    line_height = calculate_line_height(font_size)
    line_height_px = font_size * line_height
    return int(content_height / line_height_px)


def estimate_text_width(text: str, font_size: int, font_family: str = "monospace") -> int:
    """Estimate text width in pixels using average character widths.

    Since we can't measure exact text width in Python backend, we use
    approximations based on font characteristics.

    Args:
        text: Text to measure
        font_size: Font size in pixels
        font_family: Font family ("monospace" or "proportional")

    Returns:
        Estimated width in pixels

    Example:
        >>> estimate_text_width("Hello", 24, "monospace")
        72
    """
    if font_family == "monospace":
        # Monospace fonts: each character is ~0.6 × font_size
        char_width = font_size * 0.6
    else:
        # Proportional fonts: average character is ~0.5 × font_size
        char_width = font_size * 0.5

    return int(len(text) * char_width)


def wrap_text(
    text: str,
    max_width: int,
    font_size: int,
    font_family: str = "monospace"
) -> List[str]:
    """Wrap text to fit within max_width pixels.

    Breaks text into lines by wrapping at word boundaries to fit within
    the specified width constraint.

    Args:
        text: Text to wrap
        max_width: Maximum width in pixels (default: 680 for E Ink content area)
        font_size: Font size in pixels
        font_family: Font family for width calculation

    Returns:
        List of wrapped lines

    Example:
        >>> wrap_text("Hello world this is a test", 200, 24)
        ['Hello world', 'this is a', 'test']
    """
    # Handle empty text
    if not text.strip():
        return [""]

    # Split into words
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        # Try adding word to current line
        test_line = " ".join(current_line + [word])
        test_width = estimate_text_width(test_line, font_size, font_family)

        if test_width <= max_width:
            # Word fits, add it
            current_line.append(word)
        else:
            # Word doesn't fit
            if current_line:
                # Save current line and start new one
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                # Single word is too long, add it anyway
                # (will be truncated or overflow)
                current_line.append(word)

    # Add final line
    if current_line:
        lines.append(" ".join(current_line))

    return lines


def truncate_to_max_lines(lines: List[str], max_lines: int) -> Tuple[List[str], bool]:
    """Truncate lines to max_lines, adding ellipsis if needed.

    Args:
        lines: List of text lines
        max_lines: Maximum number of lines to keep

    Returns:
        Tuple of (truncated_lines, was_truncated)

    Example:
        >>> lines = ["Line 1", "Line 2", "Line 3", "Line 4"]
        >>> truncate_to_max_lines(lines, 2)
        (['Line 1', 'Line 2...'], True)
    """
    if len(lines) <= max_lines:
        return lines, False

    # Truncate and add ellipsis to last line
    truncated = lines[:max_lines]
    truncated[-1] = truncated[-1].rstrip() + "..."

    return truncated, True


def get_text_warnings(text: str, font_size: int, max_width: int = 680) -> List[str]:
    """Get warning messages for text that may not display well.

    Args:
        text: Text content
        font_size: Font size in pixels
        max_width: Maximum width in pixels

    Returns:
        List of warning messages (empty if no warnings)

    Example:
        >>> get_text_warnings("A" * 500, 18)
        ['⚠️ Very long message (500 chars). May be hard to read on device.']
    """
    warnings = []
    char_count = len(text)

    # Warn about very long messages
    if char_count > 400:
        warnings.append(
            f"⚠️ Very long message ({char_count} chars). May be hard to read on device."
        )

    # Check if text will be truncated
    lines = wrap_text(text, max_width, font_size)
    max_lines = get_max_lines(font_size)

    if len(lines) > max_lines:
        warnings.append(
            f"⚠️ Message will be truncated on device. Consider shortening to ~{max_lines * 10} chars."
        )

    return warnings
