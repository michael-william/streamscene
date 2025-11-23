"""Color picker component with visual swatch and hex input."""

import reflex as rx
from typing import Callable


def color_picker(
    label: str,
    value: rx.Var[str],
    on_change: Callable[[str], None],
    description: str = ""
) -> rx.Component:
    """
    Color picker with visual swatch and hex input.

    Features:
    - Native color picker (click swatch)
    - Manual hex input
    - Visual preview
    - Validation

    Args:
        label: Display label
        value: Current hex color value
        on_change: Callback when color changes
        description: Optional description text

    Returns:
        Reflex component with color picker UI
    """
    return rx.vstack(
        # Label
        rx.text(
            label,
            size="2",
            weight="medium",
        ),

        # Color picker row
        rx.hstack(
            # Color swatch with native picker
            rx.box(
                rx.input(
                    type="color",
                    value=value,
                    on_change=on_change,
                    width="100%",
                    height="100%",
                    cursor="pointer",
                    border="none",
                    border_radius="6px",
                ),
                width="60px",
                height="40px",
                border="2px solid var(--gray-6)",
                border_radius="6px",
                overflow="hidden",
                flex_shrink="0",
            ),

            # Hex value input
            rx.input(
                value=value,
                on_change=on_change,
                placeholder="#000000",
                max_length=7,
                size="2",
                width="120px",
                font_family="monospace",
                text_transform="uppercase",
            ),

            # Color name/description (if provided)
            rx.cond(
                description != "",
                rx.text(
                    description,
                    size="1",
                    color="gray",
                ),
            ),

            spacing="2",
            align="center",
            width="100%",
        ),

        spacing="2",
        align="start",
        width="100%",
    )
