"""Device setup and registration page."""

from uuid import UUID
import reflex as rx

from streamscene.core.database import get_db_session
from streamscene.core import streams as stream_ops
from streamscene.components.layout import authenticated_layout
from .base_state import BaseState


class SetupState(BaseState):
    """State for device setup and registration."""

    state_auto_setters = True  # Enable auto-generation of setter methods

    # Device information
    device_uuid: str = ""
    device_nickname: str = "My StreamScene Frame"

    # UI state
    is_loading: bool = True
    is_registering: bool = False
    error_message: str = ""
    success_message: str = ""

    # Registration result
    device_id: str = ""
    api_key: str = ""
    registration_complete: bool = False

    def on_load(self):
        """Load device UUID from query parameters."""
        print("[Setup] on_load() called")

        # Check authentication
        if not self.user_id:
            print("[Setup] No user_id, redirecting to /")
            return rx.redirect("/")

        # Get device_uuid from query params (new API)
        device_uuid = self.router.url.query_parameters.get("device_uuid", "") if self.router.url.query_parameters else ""

        # Fallback to session query params
        if not device_uuid:
            query_params = self.router.session.client_query_params
            device_uuid = query_params.get("device_uuid", [""])[0] if query_params else ""

        print(f"[Setup] Device UUID from params: {device_uuid}")

        if device_uuid:
            self.device_uuid = device_uuid
            self.is_loading = False
        else:
            self.error_message = "No device UUID provided. Please scan the QR code on your device."
            self.is_loading = False

    def set_device_nickname(self, value: str):
        """Set device nickname."""
        self.device_nickname = value

    def register_device(self):
        """Register device with authenticated user."""
        print(f"[Setup] register_device() called")
        print(f"[Setup] Device UUID: {self.device_uuid}")
        print(f"[Setup] User ID: {self.user_id}")
        print(f"[Setup] Nickname: {self.device_nickname}")

        # Validate inputs
        if not self.device_uuid:
            self.error_message = "Device UUID is required"
            return

        if not self.user_id:
            self.error_message = "You must be logged in to register a device"
            return

        # Start registration
        self.is_registering = True
        self.error_message = ""
        self.success_message = ""

        try:
            # Parse UUIDs
            try:
                device_uuid_obj = UUID(self.device_uuid)
                user_uuid_obj = UUID(self.user_id)
            except ValueError as e:
                self.error_message = f"Invalid UUID format: {e}"
                self.is_registering = False
                return

            # Register device
            with get_db_session() as session:
                device, api_key = stream_ops.register_device(
                    session,
                    device_uuid=device_uuid_obj,
                    user_id=user_uuid_obj,
                    nickname=self.device_nickname or "My StreamScene Frame"
                )
                session.commit()

                # Update state with registration results
                self.device_id = str(device.id)
                self.api_key = api_key
                self.registration_complete = True
                self.success_message = "Device registered successfully!"

                print(f"[Setup] Registration successful!")
                print(f"[Setup] Device ID: {self.device_id}")

        except Exception as e:
            print(f"[Setup] Registration error: {e}")
            self.error_message = f"Registration error: {str(e)}"

        finally:
            self.is_registering = False


def loading_view() -> rx.Component:
    """Loading spinner."""
    return rx.container(
        rx.vstack(
            rx.spinner(size="3"),
            rx.text("Loading...", size="3"),
            spacing="4",
            align="center",
            justify="center",
            min_height="50vh",
        ),
        max_width=["95vw", "600px"],
        padding_x=["4", "6", "8"],
        padding_y="4",
    )


def registration_form() -> rx.Component:
    """Device registration form."""
    return rx.vstack(
        # Header
        rx.heading("Register Your StreamScene Device", size="8"),
        rx.text(
            "Connect this device to your account to start displaying content.",
            size="3",
            color="gray",
        ),

        rx.divider(),

        # Device info
        rx.vstack(
            rx.heading("Device Information", size="6"),

            rx.hstack(
                rx.text("Device UUID:", weight="bold", size="2"),
                rx.code(SetupState.device_uuid, size="2"),
                spacing="2",
                align="center",
            ),

            rx.vstack(
                rx.text("Device Nickname:", weight="bold", size="2"),
                rx.input(
                    placeholder="My StreamScene Frame",
                    value=SetupState.device_nickname,
                    on_change=SetupState.set_device_nickname,
                    size="3",
                    width="100%",
                ),
                rx.text(
                    "Choose a name to identify this device (e.g., 'Kitchen Frame', 'Mom\\'s Device')",
                    size="1",
                    color="gray",
                ),
                spacing="2",
                width="100%",
                align="start",
            ),

            spacing="4",
            width="100%",
            align="start",
        ),

        rx.divider(),

        # Error message
        rx.cond(
            SetupState.error_message,
            rx.callout(
                SetupState.error_message,
                icon="triangle_alert",
                color_scheme="red",
                size="2",
            ),
        ),

        # Success message
        rx.cond(
            SetupState.success_message,
            rx.callout(
                SetupState.success_message,
                icon="check",
                color_scheme="green",
                size="2",
            ),
        ),

        # Register button
        rx.button(
            rx.cond(
                SetupState.is_registering,
                rx.hstack(
                    rx.spinner(size="1"),
                    rx.text("Registering..."),
                    spacing="2",
                ),
                rx.text("Register This Device"),
            ),
            on_click=SetupState.register_device,
            disabled=SetupState.is_registering | SetupState.registration_complete,
            size="3",
            width="100%",
        ),

        spacing="6",
        width="100%",
        align="start",
    )


def registration_complete_view() -> rx.Component:
    """Success view after registration."""
    return rx.vstack(
        # Success header
        rx.vstack(
            rx.icon("circle_check", size=64, color="green"),
            rx.heading("Device Registered!", size="8"),
            rx.text(
                "Your StreamScene device is now connected to your account.",
                size="3",
                color="gray",
            ),
            spacing="3",
            align="center",
        ),

        rx.divider(),

        # Important information
        rx.callout(
            rx.vstack(
                rx.heading("Important: API Key", size="5"),
                rx.text(
                    "Your device API key is shown below. The device will use this key to authenticate.",
                    size="2",
                ),
                rx.text(
                    "This key is shown ONLY ONCE. The device should save it automatically during setup.",
                    size="2",
                    weight="bold",
                ),
                rx.code(SetupState.api_key, size="2"),
                spacing="2",
                align="start",
            ),
            icon="info",
            color_scheme="blue",
            size="2",
        ),

        # Device details
        rx.vstack(
            rx.heading("Device Details", size="5"),
            rx.hstack(
                rx.text("Device ID:", weight="bold", size="2"),
                rx.code(SetupState.device_id, size="2"),
                spacing="2",
            ),
            rx.hstack(
                rx.text("Nickname:", weight="bold", size="2"),
                rx.text(SetupState.device_nickname, size="2"),
                spacing="2",
            ),
            spacing="3",
            align="start",
        ),

        rx.divider(),

        # Next steps
        rx.vstack(
            rx.heading("What's Next?", size="5"),
            rx.ordered_list(
                rx.list_item("Your device will detect that it's been registered"),
                rx.list_item("It will connect to the server and fetch its configuration"),
                rx.list_item("You can start posting to streams, and the device will display them!"),
                spacing="2",
            ),
            spacing="3",
            align="start",
        ),

        # Navigation buttons
        rx.hstack(
            rx.link(
                rx.button(
                    "Go to Streams",
                    size="3",
                ),
                href="/streams",
            ),
            rx.link(
                rx.button(
                    "Manage Devices",
                    size="3",
                    variant="soft",
                ),
                href="/devices",
            ),
            spacing="3",
        ),

        spacing="6",
        width="100%",
        align="start",
    )


def error_view() -> rx.Component:
    """Error view when no device UUID provided."""
    return rx.container(
        rx.vstack(
            rx.icon("circle_x", size=64, color="red"),
            rx.heading("Invalid Setup Link", size="8"),
            rx.text(
                SetupState.error_message,
                size="3",
                color="gray",
            ),
            rx.text(
                "Please scan the QR code on your StreamScene device to get the correct setup link.",
                size="3",
            ),
            rx.link(
                rx.button("Back to Home", size="3"),
                href="/",
            ),
            spacing="4",
            align="center",
            min_height="50vh",
            justify="center",
        ),
        max_width=["95vw", "600px"],
        padding_x=["4", "6", "8"],
        padding_y="4",
    )


def setup_page() -> rx.Component:
    """Main setup page component."""

    # Determine which view to show
    content = rx.cond(
        SetupState.is_loading,
        loading_view(),
        rx.cond(
            SetupState.registration_complete,
            registration_complete_view(),
            rx.cond(
                SetupState.device_uuid,
                registration_form(),
                error_view(),
            ),
        ),
    )

    return rx.container(
        content,
        max_width=["95vw", "800px"],
        padding_x=["4", "6", "8"],
        padding_y="4",
        on_mount=SetupState.on_load,  # Trigger on_load when page mounts
    )


# Register the page route
setup = setup_page
