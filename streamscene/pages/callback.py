"""OAuth callback handler."""

import os
import requests

import reflex as rx

from streamscene.core.database import get_db_session
from streamscene.core.auth import get_or_create_user


class CallbackState(rx.State):
    """State for OAuth callback handling."""

    error_message: str = ""
    is_loading: bool = True

    def handle_callback(self, code: str):
        """
        Handle OAuth callback with authorization code.

        Args:
            code: Authorization code from OAuth provider
        """
        if not code:
            self.error_message = "No authorization code received"
            self.is_loading = False
            return

        try:
            # Exchange authorization code for tokens
            token_url = os.getenv("OAUTH_TOKEN_URL")
            client_id = os.getenv("OAUTH_CLIENT_ID")
            client_secret = os.getenv("OAUTH_CLIENT_SECRET")
            redirect_uri = os.getenv("OAUTH_REDIRECT_URI")

            response = requests.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )

            if response.status_code != 200:
                self.error_message = f"Token exchange failed: {response.text}"
                self.is_loading = False
                return

            tokens = response.json()
            access_token = tokens.get("access_token")

            # Get user info from Authentik
            userinfo_url = os.getenv("OAUTH_USERINFO_URL")
            user_response = requests.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if user_response.status_code != 200:
                self.error_message = "Failed to get user information"
                self.is_loading = False
                return

            user_info = user_response.json()
            authentik_user_id = user_info.get("sub")  # Subject claim = user ID

            if not authentik_user_id:
                self.error_message = "Invalid user information received"
                self.is_loading = False
                return

            # Create or get user in our database
            with get_db_session() as session:
                user = get_or_create_user(session, authentik_user_id)
                session.commit()

                # Store user ID in session
                self.router.session.setdefault("user_id", str(user.id))

            # Redirect to streams page
            return rx.redirect("/streams")

        except Exception as e:
            self.error_message = f"Authentication error: {str(e)}"
            self.is_loading = False


def callback() -> rx.Component:
    """OAuth callback page."""
    return rx.container(
        rx.cond(
            CallbackState.error_message,
            # Error state
            rx.vstack(
                rx.heading("Authentication Error", size="7", color="red"),
                rx.text(CallbackState.error_message),
                rx.link(
                    rx.button("Back to Home"),
                    href="/",
                ),
                spacing="4",
                justify="center",
                align="center",
                min_height="85vh",
            ),
            # Loading state
            rx.vstack(
                rx.spinner(size="3"),
                rx.text("Completing sign in..."),
                spacing="4",
                justify="center",
                align="center",
                min_height="85vh",
            ),
        ),
    )
