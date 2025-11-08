"""Theme system for E Ink display preview.

This module provides a composable theming system for customizing the appearance
of E Ink display previews. Themes define colors, typography, and visual styles
that can be applied to any preview component.

The E Ink display supports 6 colors: Black, White, Red, Yellow, Blue, Green

## Gradient Rendering Strategy

**Web Preview (Browser):**
Themes with CSS gradient backgrounds (conic-gradient, linear-gradient, etc.)
render beautifully in the web browser, showing smooth color transitions.

**E Ink Device Rendering:**
The physical E Ink display cannot show smooth gradients - it only supports
6 discrete colors. When content is sent to the device, gradient backgrounds
are converted using one of these strategies:

1. **Floyd-Steinberg Dithering**: Converts gradient to a dithered pattern
   using only the 6 E Ink colors, creating the illusion of color blending

2. **Dominant Color Selection**: Analyzes the gradient and selects the
   most prominent E Ink-compatible color as a solid background

3. **Radial/Circular Patterns**: For conic gradients, creates a pattern
   of concentric circles or wedges using alternating E Ink colors

The web preview shows the ideal gradient appearance. The device implementation
(handled by the E Ink processing pipeline) will approximate this using the
strategies above.

**Color Mapping for Gradients:**
- Reds, Oranges, Warm tones → RED + YELLOW dithered pattern
- Blues, Cyans → BLUE + WHITE dithered pattern
- Greens → GREEN + YELLOW dithered pattern
- Dark colors → BLACK
- Light colors → WHITE
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

SUNSET_THEME = EInkTheme(
    name="sunset",
    description="Warm swirling gradient (yellow and red)",
    background_color="conic-gradient(from 45deg at 50% 50%, #FFD700, #FF6347, #FFA500, #FF4500, #FFD700)",
    text_color="#1a1a1a",  # Almost black for strong contrast
    header_color="#8B0000",  # Dark red for accent
    divider_color="rgba(139, 0, 0, 0.3)",
    font_family="monospace",
    header_weight="bold",
    show_dividers=True,
    border_style="solid",
)

OCEAN_THEME = EInkTheme(
    name="ocean",
    description="Cool swirling gradient (blue and cyan)",
    background_color="conic-gradient(from 45deg at 50% 50%, #0000CD, #00CED1, #1E90FF, #008B8B, #0000CD)",
    text_color="#ffffff",  # Pure white for strong contrast
    header_color="#E0FFFF",  # Light cyan for accent
    divider_color="rgba(255, 255, 255, 0.4)",
    font_family="monospace",
    header_weight="bold",
    show_dividers=True,
    border_style="solid",
)

FOREST_THEME = EInkTheme(
    name="forest",
    description="Nature swirling gradient (green variations)",
    background_color="conic-gradient(from 45deg at 50% 50%, #228B22, #32CD32, #90EE90, #3CB371, #228B22)",
    text_color="#ffffff",  # Pure white for strong contrast
    header_color="#F0FFF0",  # Honeydew for accent
    divider_color="rgba(255, 255, 255, 0.4)",
    font_family="monospace",
    header_weight="bold",
    show_dividers=True,
    border_style="solid",
)


# Theme registry
THEMES: Dict[str, EInkTheme] = {
    "classic": CLASSIC_THEME,
    "dark": DARK_MODE_THEME,
    "sunset": SUNSET_THEME,
    "ocean": OCEAN_THEME,
    "forest": FOREST_THEME,
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
