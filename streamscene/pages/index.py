"""Landing page for StreamScene."""

import reflex as rx


def index() -> rx.Component:
    """Landing page with login and about information."""
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("StreamScene", size="9"),
            rx.text(
                "Family E Ink Message Board",
                size="6",
                color="gray",
            ),
            rx.text(
                "Share messages with your family on beautiful E Ink displays.",
                size="4",
                text_align="center",
                max_width="600px",
            ),
            rx.spacer(height="2em"),
            rx.link(
                rx.button(
                    "Sign In",
                    size="3",
                    color_scheme="blue",
                ),
                href="/login",
            ),
            spacing="5",
            justify="center",
            align="center",
            min_height="85vh",
        ),
    )
