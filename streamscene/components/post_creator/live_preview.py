"""Live preview component - shows PIL-rendered preview of post."""

import reflex as rx
from typing import Callable


def live_preview(
    preview_data: rx.Var[str],
    is_generating: rx.Var[bool],
    show: rx.Var[bool]
) -> rx.Component:
    """
    Live preview of rendered post (800×480px E Ink display).

    Features:
    - Responsive scaling (40%→50%→60%→70%)
    - Loading state during generation
    - Error fallback
    - Toggle visibility
    - Manual refresh only (no auto-refresh)

    Args:
        preview_data: Base64 data URL of preview image
        is_generating: Loading state during preview generation
        show: Whether to show preview

    Returns:
        Reflex component with live preview display
    """
    return rx.cond(
        show,
        rx.vstack(
            # Header
            rx.hstack(
                rx.text(
                    "Live Preview",
                    size="3",
                    weight="medium",
                ),
                rx.badge(
                    "800×480px",
                    size="1",
                    color_scheme="gray",
                    variant="soft",
                ),
                rx.spacer(),
                rx.text(
                    "Scaled to fit screen",
                    size="1",
                    color="gray",
                ),
                spacing="2",
                align="center",
                width="100%",
            ),

            # Preview container
            rx.box(
                rx.cond(
                    is_generating,
                    # Loading state
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text(
                            "Generating preview...",
                            size="2",
                            color="gray",
                        ),
                        spacing="3",
                        justify="center",
                        align="center",
                        height="100%",
                    ),
                    # Preview image or empty state
                    rx.cond(
                        preview_data,
                        # Show preview
                        rx.image(
                            src=preview_data,
                            width="100%",
                            aspect_ratio="800/480",
                            object_fit="contain",
                            border="4px solid var(--gray-6)",
                            border_radius="8px",
                            box_shadow="0 4px 6px rgba(0, 0, 0, 0.1)",
                        ),
                        # Empty state
                        rx.vstack(
                            rx.icon("eye-off", size=32, color="gray"),
                            rx.text(
                                "Fill in the form to see preview",
                                size="2",
                                color="gray",
                            ),
                            spacing="3",
                            justify="center",
                            align="center",
                            min_height="200px",
                        ),
                    ),
                ),
                # Responsive container - no transform scaling
                width="100%",
                max_width="560px",
                background="var(--gray-1)",
                border_radius="8px",
            ),

            spacing="3",
            width="100%",
            align="start",
        ),
    )
