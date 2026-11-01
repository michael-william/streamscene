"""Base state with shared authentication for all pages."""

from uuid import UUID

import reflex as rx


def is_valid_uuid(value: str) -> bool:
    """True if value is a UUID. Guards device IDs taken from URLs and cookies
    before they are stored or put back into a redirect."""
    try:
        UUID(value)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


class BaseState(rx.State):
    """Base state class with shared authentication cookie.

    All page states should inherit from this to share the user_id cookie
    across the entire application.
    """

    user_id: str = rx.Cookie("")  # Single source of truth for authentication
    # Device UUID from a scanned QR, kept while the user logs in so the OAuth
    # callback can send them back to /setup for it. Short-lived.
    pending_setup_device: str = rx.Cookie("", max_age=1800)

    @rx.var
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return bool(self.user_id)

    def require_auth(self):
        """Redirect to login if not authenticated.

        Usage in page on_mount():
            def on_mount(self):
                if redirect := self.require_auth():
                    return redirect
                # ... rest of page logic
        """
        if not self.user_id:
            return rx.redirect("/")
        return None

    def logout(self):
        """Log out the user by clearing the cookie."""
        self.user_id = ""
        return rx.redirect("/")
