"""Shared utilities for post creator components."""

import re
from typing import Tuple


def validate_hex_color(color: str) -> bool:
    """
    Validate hex color format.

    Args:
        color: Color string to validate

    Returns:
        True if valid hex color (#RRGGBB), False otherwise
    """
    pattern = r'^#[0-9A-Fa-f]{6}$'
    return bool(re.match(pattern, color))


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """
    Convert hex color to RGB tuple.

    Args:
        hex_color: Hex color string (e.g., "#FF5733")

    Returns:
        RGB tuple (e.g., (255, 87, 51))

    Raises:
        ValueError: If hex_color is invalid
    """
    if not validate_hex_color(hex_color):
        raise ValueError(f"Invalid hex color: {hex_color}")

    # Remove # prefix
    hex_color = hex_color.lstrip('#')

    # Convert to RGB
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    return (r, g, b)


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """
    Convert RGB tuple to hex color.

    Args:
        rgb: RGB tuple (e.g., (255, 87, 51))

    Returns:
        Hex color string (e.g., "#FF5733")
    """
    r, g, b = rgb
    return f"#{r:02X}{g:02X}{b:02X}"


def format_file_size(bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        bytes: File size in bytes

    Returns:
        Formatted string (e.g., "2.5 MB")
    """
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 * 1024:
        return f"{bytes / 1024:.1f} KB"
    else:
        return f"{bytes / (1024 * 1024):.1f} MB"
