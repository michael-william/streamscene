"""Theme picker component for selecting E Ink display themes."""

import reflex as rx
from streamscene.components.eink.theme import THEMES


def theme_swatch(theme_name: str, selected_theme_var, on_click_handler) -> rx.Component:
    """Render a single theme swatch.

    Args:
        theme_name: Name of the theme
        selected_theme_var: Reflex Var for the currently selected theme
        on_click_handler: Function to call when swatch is clicked

    Returns:
        Clickable theme swatch component
    """
    theme = THEMES[theme_name]

    # Create a mini preview box with the theme's background
    swatch_box = rx.box(
        width="60px",
        height="60px",
        background=theme.background_color,
        border=rx.cond(
            selected_theme_var == theme_name,
            "3px solid #3b82f6",  # Blue border when selected
            "2px solid #d1d5db",   # Gray border when not selected
        ),
        border_radius="8px",
        cursor="pointer",
        transition="all 0.2s",
        _hover={
            "transform": "scale(1.05)",
            "border_color": "#3b82f6",
        },
        on_click=lambda: on_click_handler(theme_name),
    )

    # Theme name label
    label = rx.text(
        theme.description,
        size="1",
        color="gray",
        text_align="center",
        max_width="80px",
        overflow="hidden",
        text_overflow="ellipsis",
        white_space="nowrap",
    )

    return rx.vstack(
        swatch_box,
        label,
        spacing="2",
        align="center",
    )


def theme_picker(selected_theme_var, on_select_handler) -> rx.Component:
    """Visual theme picker component.

    Displays all available themes as clickable swatches.

    Args:
        selected_theme_var: Reflex Var for the currently selected theme
        on_select_handler: Function to call when a theme is selected (receives theme_name)

    Returns:
        Theme picker component

    Example:
        >>> # In your State class:
        >>> class MyState(rx.State):
        ...     selected_theme: str = "classic"
        >>>
        >>> # In your UI:
        >>> theme_picker(
        ...     selected_theme_var=MyState.selected_theme,
        ...     on_select_handler=MyState.set_selected_theme
        ... )
    """
    return rx.vstack(
        rx.text(
            "Theme",
            size="2",
            weight="medium",
            color="gray",
        ),
        rx.hstack(
            *[
                theme_swatch(theme_name, selected_theme_var, on_select_handler)
                for theme_name in THEMES.keys()
            ],
            spacing="4",
            wrap="wrap",
        ),
        spacing="2",
        align="start",
        width="100%",
    )
