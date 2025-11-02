"""Login page that redirects to Authentik OAuth."""

import os
from urllib.parse import urlencode

import reflex as rx


class LoginState(rx.State):
    """State for login page."""

    def on_mount(self):
        """Redirect to Authentik OAuth when page loads."""
        # Get OAuth configuration from environment
        client_id = os.getenv("OAUTH_CLIENT_ID")
        redirect_uri = os.getenv("OAUTH_REDIRECT_URI")
        auth_url = os.getenv("OAUTH_AUTHORIZATION_URL")

        if not all([client_id, redirect_uri, auth_url]):
            return rx.console_log("OAuth configuration is incomplete")

        # Build OAuth authorization URL
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid profile email",
        }
        oauth_url = f"{auth_url}?{urlencode(params)}"

        # Redirect to Authentik
        return rx.redirect(oauth_url)


def login() -> rx.Component:
    """Login page that redirects to OAuth provider."""
    return rx.container(
        rx.vstack(
            rx.spinner(size="3"),
            rx.text("Redirecting to sign in..."),
            spacing="4",
            justify="center",
            align="center",
            min_height="85vh",
        ),
    )
