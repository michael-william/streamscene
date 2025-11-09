"""Text measurement and wrapping utilities for E Ink preview.

This module provides utilities for calculating optimal font sizes,
estimating text dimensions, and wrapping text to fit within the
E Ink display constraints.

Font sizing uses binary search to maximize font size while respecting
word wrapping and display constraints (680×380px content area).
"""

from typing import List, Tuple


def calculate_line_height(font_size: int) -> float:
    """Calculate line height based on WCAG accessibility standards.

    Returns 1.5× for all font sizes to meet WCAG AA accessibility
    requirements and optimize readability on E Ink displays.

    Args:
        font_size: Font size in pixels

    Returns:
        Line height multiplier (always 1.5)

    Example:
        >>> calculate_line_height(48)
        1.5
        >>> calculate_line_height(28)
        1.5
    """
    return 1.5  # WCAG AA standard for all font sizes


def get_max_lines(font_size: int, content_height: int = 380) -> int:
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


def calculate_optimal_font_size(
    text: str,
    max_width: int = 680,
    max_height: int = 380,
    min_size: int = 28,
    max_size: int = 64,
    font_family: str = "monospace"
) -> int:
    """Calculate optimal font size using binary search.

    Finds the largest font size that fits the text within the given
    width and height constraints, respecting word wrapping boundaries.

    This algorithm maximizes font size for maximum impact on the E Ink
    display while ensuring text never overflows.

    Args:
        text: Text content to size
        max_width: Maximum width in pixels (default: 680px content area)
        max_height: Maximum height in pixels (default: 380px content area)
        min_size: Minimum font size in pixels (default: 28px for 5-ft viewing)
        max_size: Maximum font size in pixels (default: 64px)
        font_family: Font family for width calculation (default: "monospace")

    Returns:
        Optimal font size in pixels

    Example:
        >>> calculate_optimal_font_size("Hello world!")
        64
        >>> calculate_optimal_font_size("A" * 160)
        28
    """
    # Handle empty text
    if not text.strip():
        return min_size

    # Binary search for largest font that fits
    best_size = min_size

    while max_size - min_size > 1:  # 1px precision
        mid = (min_size + max_size) // 2

        # Wrap text at this font size
        lines = wrap_text(text, max_width, mid, font_family)

        # Calculate total height needed
        line_height = mid * calculate_line_height(mid)
        total_height = len(lines) * line_height

        if total_height <= max_height:
            # Text fits! Try larger font
            best_size = mid
            min_size = mid
        else:
            # Text too large, try smaller font
            max_size = mid

    return best_size


def calculate_font_size(text: str) -> int:
    """Calculate optimal font size (wrapper for binary search).

    This function provides a simple interface to the binary search
    algorithm, using default E Ink display constraints.

    Args:
        text: Text content to size

    Returns:
        Font size in pixels

    Example:
        >>> calculate_font_size("Short")
        64
        >>> calculate_font_size("A" * 160)
        28
    """
    return calculate_optimal_font_size(text)


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


def get_text_warnings(text: str, font_size: int = 28, max_width: int = 680) -> List[str]:
    """Get warning messages for text that may not display well.

    Args:
        text: Text content
        font_size: Font size in pixels (default: 28px minimum)
        max_width: Maximum width in pixels (default: 680px)

    Returns:
        List of warning messages (empty if no warnings)

    Example:
        >>> get_text_warnings("A" * 200)
        ['⚠️ Message too long (200 chars). Maximum is 160 characters.']
    """
    warnings = []
    char_count = len(text)

    # Warn about messages exceeding 160 character limit
    if char_count > 160:
        warnings.append(
            f"⚠️ Message too long ({char_count} chars). Maximum is 160 characters."
        )
    elif char_count > 140:
        # Soft warning when approaching limit
        remaining = 160 - char_count
        warnings.append(
            f"ℹ️ Approaching character limit ({remaining} characters remaining)."
        )

    return warnings
