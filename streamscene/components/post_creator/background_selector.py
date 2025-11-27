"""Background selector component - thumbnail grid for meme backgrounds."""

import reflex as rx
from typing import Callable, List


def background_selector(
    backgrounds: rx.Var[List[dict]],
    selected: rx.Var[str],
    on_select: Callable[[str], None],
    is_loading: rx.Var[bool] = False
) -> rx.Component:
    """
    Grid of background thumbnails for meme posts.

    Responsive grid:
    - Mobile: 3 columns
    - Tablet: 3 columns
    - Desktop: 4 columns
    - Large: 6 columns

    Args:
        backgrounds: List of background dicts with filename and display_name
        selected: Currently selected background filename
        on_select: Callback when background clicked
        is_loading: Loading state

    Returns:
        Reflex component with background grid
    """

    def background_card(bg: dict) -> rx.Component:
        """Individual background card with selection indicator."""
        is_selected = bg["filename"] == selected

        return rx.box(
            # Background preview image
            rx.image(
                src=f"/backgrounds/{bg['filename']}",
                width="100%",
                height="80px",
                object_fit="cover",
                border_radius="6px",
                loading="lazy",  # Browser-native lazy loading
            ),

            # Display name
            rx.text(
                bg["display_name"],
                size="1",
                text_align="center",
                margin_top="1",
                font_weight=rx.cond(
                    is_selected,
                    "600",
                    "400"
                ),
            ),

            # Selection indicator (checkmark badge)
            rx.cond(
                is_selected,
                rx.badge(
                    rx.icon("check", size=12),
                    position="absolute",
                    top="4px",
                    right="4px",
                    color_scheme="blue",
                    variant="solid",
                ),
            ),

            # Container styling
            on_click=lambda _: on_select(bg["filename"]),
            cursor="pointer",
            border=rx.cond(
                is_selected,
                "2px solid var(--blue-9)",
                "2px solid transparent"
            ),
            border_radius="8px",
            padding="6px",
            transition="all 0.2s",
            _hover={
                "border_color": "var(--blue-7)",
                "background": "var(--gray-2)",
            },
            position="relative",
            tabindex="0",  # Keyboard accessible
            role="button",
            aria_pressed=is_selected,
            aria_label=f"Select {bg['display_name']} background",
        )

    return rx.vstack(
        # Header
        rx.hstack(
            rx.text(
                "Choose Background",
                size="3",
                weight="medium",
            ),
            rx.spacer(),
            rx.cond(
                is_loading,
                rx.spinner(size="1"),
            ),
            width="100%",
            align="center",
        ),

        # Background grid
        rx.cond(
            backgrounds.length() > 0,
            # Grid of backgrounds
            rx.box(
                rx.foreach(backgrounds, background_card),
                display="grid",
                grid_template_columns="repeat(3, 1fr)",  # Always 3 columns max
                gap="3",
                width="100%",
            ),
            # Loading/empty state
            rx.card(
                rx.vstack(
                    rx.cond(
                        is_loading,
                        rx.vstack(
                            rx.spinner(size="3"),
                            rx.text("Loading backgrounds...", size="2", color="gray"),
                            spacing="2",
                            align="center",
                        ),
                        rx.text("No backgrounds available", size="2", color="gray"),
                    ),
                    padding="8",
                    align="center",
                ),
                width="100%",
            ),
        ),

        spacing="3",
        width="100%",
        align="start",
    )
