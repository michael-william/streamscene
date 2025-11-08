"""Theme system for E Ink display preview.

This module provides a composable theming system for customizing the appearance
of E Ink display previews. Themes define colors, typography, and visual styles
that can be applied to any preview component.

The E Ink display supports 6 colors: Black, White, Red, Yellow, Blue, Green
"""

from dataclasses import dataclass
from typing import Dict, Literal


@dataclass
class EInkTheme:
    """Theme definition for E Ink display preview.

    Attributes:
        name: Unique theme identifier
        description: Human-readable description
        background_color: Background color (CSS color or E Ink color name)
        text_color: Primary text color
        header_color: Header text color (can be used for accents)
        divider_color: Divider line color
        font_family: CSS font family
        header_weight: Font weight for headers ("bold" or "normal")
        show_dividers: Whether to show divider lines between sections
        border_style: Border style ("solid", "none", "rounded")

    Example:
        >>> theme = EInkTheme(
        ...     name="dark",
        ...     description="Dark mode theme",
        ...     background_color="black",
        ...     text_color="white",
        ...     header_color="white",
        ...     divider_color="#444444",
        ...     font_family="monospace",
        ...     header_weight="bold",
        ...     show_dividers=True,
        ...     border_style="solid"
        ... )
    """

    # Theme identification
    name: str
    description: str

    # Colors (using E Ink 6-color palette or CSS colors)
    background_color: str  # white, black, red, yellow, blue, green, or hex
    text_color: str        # white, black, red, yellow, blue, green, or hex
    header_color: str      # Optional accent color for headers
    divider_color: str     # Divider line color

    # Typography
    font_family: str       # Font family for preview
    header_weight: str     # bold, normal

    # Visual style
    show_dividers: bool    # Show dividers between sections
    border_style: str      # "solid", "none", "rounded"

    def to_dict(self) -> Dict[str, any]:
        """Convert theme to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "background_color": self.background_color,
            "text_color": self.text_color,
            "header_color": self.header_color,
            "divider_color": self.divider_color,
            "font_family": self.font_family,
            "header_weight": self.header_weight,
            "show_dividers": self.show_dividers,
            "border_style": self.border_style,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, any]) -> "EInkTheme":
        """Create theme from dictionary."""
        return cls(**data)


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

ACCENT_BLUE_THEME = EInkTheme(
    name="accent_blue",
    description="Black text with blue header accents",
    background_color="white",
    text_color="black",
    header_color="blue",
    divider_color="#cce5ff",
    font_family="monospace",
    header_weight="bold",
    show_dividers=True,
    border_style="solid",
)

MINIMAL_THEME = EInkTheme(
    name="minimal",
    description="Clean design without dividers",
    background_color="white",
    text_color="black",
    header_color="black",
    divider_color="transparent",
    font_family="monospace",
    header_weight="normal",
    show_dividers=False,
    border_style="none",
)


# Theme registry
THEMES: Dict[str, EInkTheme] = {
    "classic": CLASSIC_THEME,
    "dark": DARK_MODE_THEME,
    "accent_red": ACCENT_RED_THEME,
    "accent_blue": ACCENT_BLUE_THEME,
    "minimal": MINIMAL_THEME,
}


def get_theme(name: str = "classic") -> EInkTheme:
    """Get theme by name, fallback to classic.

    Args:
        name: Theme name from THEMES registry

    Returns:
        EInkTheme object

    Example:
        >>> theme = get_theme("dark")
        >>> theme.background_color
        'black'
        >>> theme = get_theme("nonexistent")  # Falls back to classic
        >>> theme.name
        'classic'
    """
    return THEMES.get(name, CLASSIC_THEME)


def register_theme(theme: EInkTheme) -> None:
    """Register a custom theme.

    Args:
        theme: EInkTheme object to register

    Example:
        >>> custom = EInkTheme(
        ...     name="custom",
        ...     description="My custom theme",
        ...     background_color="yellow",
        ...     text_color="black",
        ...     header_color="red",
        ...     divider_color="#ffddaa",
        ...     font_family="monospace",
        ...     header_weight="bold",
        ...     show_dividers=True,
        ...     border_style="rounded"
        ... )
        >>> register_theme(custom)
        >>> get_theme("custom").description
        'My custom theme'
    """
    THEMES[theme.name] = theme
