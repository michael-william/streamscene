"""User profile page with settings."""

from uuid import UUID

import reflex as rx

from ..components.layout import authenticated_layout
from ..core.auth import get_user_by_id
from ..core.database import get_db_session
from .base_state import BaseState


class ProfileState(BaseState):
    """State for profile page."""

    state_auto_setters = True  # Enable auto-generation of setter methods

    # User information
    email: str = ""
    username: str = ""
    name: str = ""
    display_name: str = ""
    profile_picture: str = ""

    # Form state
    edit_name: str = ""

    # UI state
    is_loading: bool = False
    error_message: str = ""
    success_message: str = ""
    upload_progress: int = 0

    @rx.var
    def avatar_initial(self) -> str:
        """Get first letter for avatar fallback."""
        if self.display_name:
            return self.display_name[0].upper()
        if self.name:
            return self.name[0].upper()
        if self.username:
            return self.username[0].upper()
        if self.email:
            return self.email[0].upper()
        return "U"

    def on_mount(self):
        """Load user profile data when page mounts."""
        # Check authentication
        if not self.user_id:
            return rx.redirect("/")

        yield from self.load_profile()

    def load_profile(self):
        """Load user profile from database."""
        try:
            user_uuid = UUID(self.user_id)
        except (ValueError, TypeError):
            self.error_message = "Invalid user ID"
            return

        try:
            with get_db_session() as session:
                user = get_user_by_id(session, user_uuid)

                if not user:
                    self.error_message = "User not found"
                    return

                # Load user data
                self.email = user.email or "No email"
                self.username = user.username or ""
                self.name = user.name or ""
                self.display_name = user.display_name or ""
                self.profile_picture = user.profile_picture or ""

                # Initialize edit field (username is read-only, managed by Authentik)
                # Prefer display_name, fallback to name from Authentik
                self.edit_name = self.display_name or self.name

                yield

        except Exception as e:
            self.error_message = f"Error loading profile: {str(e)}"
            yield

    def save_profile(self):
        """Save profile changes (display name only)."""
        self.error_message = ""
        self.success_message = ""

        # Validate name
        if self.edit_name and len(self.edit_name) > 100:
            self.error_message = "Name must be 100 characters or less"
            return

        try:
            user_uuid = UUID(self.user_id)

            with get_db_session() as session:
                user = get_user_by_id(session, user_uuid)

                if not user:
                    self.error_message = "User not found"
                    return

                # Update display name only (username is managed by Authentik)
                user.display_name = self.edit_name if self.edit_name else None
                session.commit()

                # Update state
                self.display_name = self.edit_name
                self.success_message = "Profile updated successfully!"
                yield

        except Exception as e:
            self.error_message = f"Error saving profile: {str(e)}"
            yield


def profile_picture_section() -> rx.Component:
    """Profile avatar section."""
    return rx.vstack(
        # Avatar with dynamic initial
        rx.avatar(
            size="7",
            radius="full",
            fallback=ProfileState.avatar_initial,
        ),
        rx.text(
            "Your avatar shows the first letter of your display name",
            size="1",
            color="gray",
        ),
        spacing="3",
        align="center",
    )


def profile_form() -> rx.Component:
    """Profile edit form."""
    return rx.vstack(
        # Email (Read-only)
        rx.vstack(
            rx.text("Email", size="2", weight="medium"),
            rx.input(
                value=ProfileState.email,
                placeholder="email@example.com",
                size="3",
                disabled=True,
                width="100%",
            ),
            spacing="1",
            width="100%",
            align="start",
        ),
        # Username (Read-only - managed by Authentik)
        rx.vstack(
            rx.text("Username", size="2", weight="medium"),
            rx.input(
                value=ProfileState.username,
                placeholder="username",
                size="3",
                disabled=True,
                width="100%",
            ),
            spacing="1",
            width="100%",
            align="start",
        ),
        # Display Name
        rx.vstack(
            rx.text("Display Name", size="2", weight="medium"),
            rx.input(
                value=ProfileState.edit_name,
                on_change=ProfileState.set_edit_name,
                placeholder="Your Name",
                size="3",
                width="100%",
            ),
            spacing="1",
            width="100%",
            align="start",
        ),
        # Save Button
        rx.button(
            "Save Changes",
            on_click=ProfileState.save_profile,
            size="3",
            width="100%",
            color_scheme="blue",
        ),
        spacing="4",
        width="100%",
    )


def profile_content() -> rx.Component:
    """Main profile content."""
    return rx.container(
        rx.vstack(
            # Page Title
            rx.heading("Profile Settings", size="8", margin_bottom="2"),
            rx.text(
                "Manage your profile information and settings",
                size="3",
                color="gray",
                margin_bottom="6",
            ),
            # Messages
            rx.cond(
                ProfileState.error_message != "",
                rx.callout(
                    ProfileState.error_message,
                    icon="triangle_alert",
                    color_scheme="red",
                    size="1",
                ),
            ),
            rx.cond(
                ProfileState.success_message != "",
                rx.callout(
                    ProfileState.success_message,
                    icon="check",
                    color_scheme="green",
                    size="1",
                ),
            ),
            # Main Content Card
            rx.card(
                rx.vstack(
                    profile_picture_section(),
                    rx.divider(margin_y="4"),
                    profile_form(),
                    spacing="4",
                    width="100%",
                    align="center",
                ),
                size="3",
                width="100%",
                max_width=["95vw", "500px"],
            ),
            spacing="4",
            padding_x=["4", "6", "8"],
            padding_y="4",
            width="100%",
            align="center",
        ),
        max_width="1200px",
        on_mount=ProfileState.on_mount,  # Connect lifecycle handler
    )


def profile() -> rx.Component:
    """Profile page component."""
    return authenticated_layout(
        profile_content(),
        current_page="profile",
    )
