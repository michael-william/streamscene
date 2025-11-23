"""Post type selector component - toggle between Picture and Meme posts."""

import reflex as rx
from typing import Callable


def post_type_selector(
    current_type: rx.Var[str],
    on_change: Callable[[str], None]
) -> rx.Component:
    """
    Toggle selector for post type (Picture or Meme).

    Responsive design:
    - Mobile: Stacked buttons (full width)
    - Desktop: Horizontal tabs

    Args:
        current_type: Current post type ("picture" or "meme")
        on_change: Callback when type changes

    Returns:
        Reflex component with two toggle buttons
    """
    return rx.flex(
        # Picture button
        rx.button(
            rx.hstack(
                rx.icon("image", size=18),
                rx.text("Post a Picture"),
                spacing="2",
                align="center",
            ),
            on_click=lambda: on_change("picture"),
            color_scheme=rx.cond(
                current_type == "picture",
                "blue",
                "gray"
            ),
            variant=rx.cond(
                current_type == "picture",
                "solid",
                "soft"
            ),
            size="3",
            width=rx.breakpoints(initial="100%", md="auto"),  # Full width on mobile, auto on desktop
            cursor="pointer",
        ),

        # Meme button
        rx.button(
            rx.hstack(
                rx.icon("palette", size=18),
                rx.text("I Meme It"),
                spacing="2",
                align="center",
            ),
            on_click=lambda: on_change("meme"),
            color_scheme=rx.cond(
                current_type == "meme",
                "blue",
                "gray"
            ),
            variant=rx.cond(
                current_type == "meme",
                "solid",
                "soft"
            ),
            size="3",
            width=rx.breakpoints(initial="100%", md="auto"),
            cursor="pointer",
        ),

        # Responsive layout
        direction=rx.breakpoints(initial="column", md="row"),  # Column on mobile, row on desktop
        spacing="3",
        width="100%",
    )
