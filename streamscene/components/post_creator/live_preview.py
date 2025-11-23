"""Live preview component - shows PIL-rendered preview of post."""

import reflex as rx
from typing import Callable


def live_preview(
    preview_data: rx.Var[str],
    is_generating: rx.Var[bool],
    show: rx.Var[bool],
    on_auto_refresh: Callable = None
) -> rx.Component:
    """
    Live preview of rendered post (800×480px E Ink display).

    Features:
    - Responsive scaling (40%→50%→60%→70%)
    - Loading state during generation
    - Error fallback
    - Toggle visibility
    - Auto-refresh every 2 seconds when visible

    Args:
        preview_data: Base64 data URL of preview image
        is_generating: Loading state during preview generation
        show: Whether to show preview
        on_auto_refresh: Callback for auto-refresh timer (optional)

    Returns:
        Reflex component with live preview display
    """
    return rx.cond(
        show,
        rx.vstack(
            # Hidden timer for auto-refresh (updates every 2 seconds)
            rx.cond(
                on_auto_refresh is not None,
                rx.moment(
                    interval=2000,  # 2000ms = 2 seconds
                    on_change=lambda _: on_auto_refresh(),
                    display="none"  # Hidden from UI
                ),
            ),

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
                            width="800px",
                            height="480px",
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
                            height="100%",
                        ),
                    ),
                ),
                # Responsive scaling
                transform=rx.breakpoints(
                    initial="scale(0.4)",  # Mobile: 40%
                    sm="scale(0.5)",  # Small: 50%
                    md="scale(0.6)",  # Medium: 60%
                    lg="scale(0.7)",  # Large: 70%
                ),
                transform_origin="top left",
                width=rx.breakpoints(initial="320px", sm="400px", md="480px", lg="560px"),
                height=rx.breakpoints(initial="192px", sm="240px", md="288px", lg="336px"),
                overflow="hidden",
                background="var(--gray-1)",
                border_radius="8px",
                display="flex",
                align_items="center",
                justify_content="center",
            ),

            spacing="3",
            width="100%",
            align="start",
        ),
    )
