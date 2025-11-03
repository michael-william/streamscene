"""Landing page for StreamScene."""

import os
from urllib.parse import urlencode
import reflex as rx

from .base_state import BaseState


class IndexState(BaseState):
    """State for landing page."""

    def on_mount(self):
        """Redirect authenticated users to dashboard."""
        if self.user_id:
            return rx.redirect("/dashboard")


def index() -> rx.Component:
    """Landing page with login and about information."""
    # Build OAuth URL directly (no WebSocket needed)
    client_id = os.getenv("OAUTH_CLIENT_ID")
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI")
    auth_url = os.getenv("OAUTH_AUTHORIZATION_URL")

    # Build OAuth authorization URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email",
    }
    oauth_url = f"{auth_url}?{urlencode(params)}"

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
                href=oauth_url,
                is_external=True,
            ),
            spacing="5",
            justify="center",
            align="center",
            min_height="85vh",
        ),
        on_mount=IndexState.on_mount,
    )
