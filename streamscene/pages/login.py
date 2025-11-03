"""Login page with Authentik OAuth button."""

import os
from urllib.parse import urlencode

import reflex as rx


class LoginState(rx.State):
    """State for login page."""

    error_message: str = ""

    def on_load(self):
        """Called when the page loads - immediately redirect to Authentik OAuth."""
        # Get OAuth configuration from environment
        client_id = os.getenv("OAUTH_CLIENT_ID")
        redirect_uri = os.getenv("OAUTH_REDIRECT_URI")
        auth_url = os.getenv("OAUTH_AUTHORIZATION_URL")

        # Debug logging
        print(f"DEBUG: Login page loaded, initiating OAuth redirect")
        print(f"DEBUG: client_id={client_id}")
        print(f"DEBUG: redirect_uri={redirect_uri}")
        print(f"DEBUG: auth_url={auth_url}")

        if not all([client_id, redirect_uri, auth_url]):
            print("ERROR: OAuth configuration is incomplete!")
            self.error_message = "OAuth configuration error. Please check server configuration."
            return

        # Build OAuth authorization URL
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid profile email",
        }
        oauth_url = f"{auth_url}?{urlencode(params)}"

        print(f"DEBUG: Redirecting to: {oauth_url}")

        # Redirect to Authentik
        return rx.redirect(oauth_url)


def login() -> rx.Component:
    """Login page - auto-redirects to Authentik OAuth."""
    return rx.container(
        rx.cond(
            LoginState.error_message,
            # Error state
            rx.vstack(
                rx.heading("Configuration Error", size="7", color="red"),
                rx.text(LoginState.error_message),
                rx.link(
                    rx.button("Back to Home"),
                    href="/",
                ),
                spacing="4",
                justify="center",
                align="center",
                min_height="85vh",
            ),
            # Loading state - will redirect immediately
            rx.vstack(
                rx.spinner(size="3"),
                rx.text("Redirecting to sign in..."),
                spacing="4",
                justify="center",
                align="center",
                min_height="85vh",
            ),
        ),
        max_width="600px",
        on_mount=LoginState.on_load,
    )
