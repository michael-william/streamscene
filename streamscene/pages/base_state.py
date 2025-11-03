"""Base state with shared authentication for all pages."""

import reflex as rx


class BaseState(rx.State):
    """Base state class with shared authentication cookie.

    All page states should inherit from this to share the user_id cookie
    across the entire application.
    """

    user_id: str = rx.Cookie("")  # Single source of truth for authentication

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
