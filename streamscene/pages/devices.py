"""Device management page."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta

import reflex as rx

from streamscene.core.database import get_db_session
from streamscene.core import streams as stream_ops
from streamscene.components.layout import authenticated_layout
from .base_state import BaseState


class DeviceInfo(rx.Base):
    """Device information for display."""
    id: str
    device_uuid: str
    nickname: str
    current_stream_id: Optional[str] = None
    current_stream_name: str = "No stream"
    current_version: str = "Unknown"
    last_seen: Optional[str] = None
    rotation_enabled: bool = False
    rotation_interval: int = 60
    is_online: bool = False


class DevicesState(BaseState):
    """State for device management."""

    state_auto_setters = True

    # Device list
    devices: List[DeviceInfo] = []

    # Loading states
    is_loading: bool = True

    # Messages
    error_message: str = ""
    success_message: str = ""

    def on_mount(self):
        """Load user's devices when page loads."""
        print(f"[DEVICES] on_mount() called")

        # Check if user is authenticated
        if not self.user_id:
            print(f"[DEVICES] No user_id, redirecting to /")
            return rx.redirect("/")

        print(f"[DEVICES] Loading devices for user {self.user_id}")
        self.load_devices()

    def load_devices(self):
        """Load devices owned by the user."""
        print(f"[DEVICES] load_devices() called")

        if not self.user_id:
            return

        self.is_loading = True
        self.error_message = ""

        try:
            user_uuid = UUID(self.user_id)

            with get_db_session() as session:
                user_devices = stream_ops.get_user_devices(session, user_uuid)
                print(f"[DEVICES] Found {len(user_devices)} devices")

                # Get stream names for devices
                from streamscene.core.models import Stream

                self.devices = []
                for device in user_devices:
                    # Get stream name if device has a current stream
                    stream_name = "No stream"
                    if device.current_stream_id:
                        stream = session.query(Stream).filter(Stream.id == device.current_stream_id).first()
                        if stream:
                            stream_name = stream.name

                    self.devices.append(
                        DeviceInfo(
                            id=str(device.id),
                            device_uuid=str(device.device_uuid),
                            nickname=device.nickname or "Unnamed Device",
                            current_stream_id=str(device.current_stream_id) if device.current_stream_id else None,
                            current_stream_name=stream_name,
                            current_version=device.current_version or "Unknown",
                            last_seen=device.last_seen.isoformat() if device.last_seen else None,
                            rotation_enabled=device.rotation_enabled,
                            rotation_interval=device.rotation_interval,
                            is_online=self._is_device_online(device.last_seen),
                        )
                    )

                print(f"[DEVICES] Loaded {len(self.devices)} devices")

        except Exception as e:
            print(f"[DEVICES] Error loading devices: {e}")
            self.error_message = f"Error loading devices: {str(e)}"

        finally:
            self.is_loading = False

    def _is_device_online(self, last_seen) -> bool:
        """Check if device is considered online (seen in last 10 minutes)."""
        if not last_seen:
            return False

        # Ensure last_seen is timezone-aware
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        return (now - last_seen) < timedelta(minutes=10)


def device_card(device: DeviceInfo) -> rx.Component:
    """Render a single device card."""
    return rx.card(
        rx.vstack(
            # Header with nickname and status
            rx.hstack(
                rx.heading(device.nickname, size="6"),
                rx.cond(
                    device.is_online,
                    rx.badge("Online", color_scheme="green", size="2"),
                    rx.badge("Offline", color_scheme="gray", size="2"),
                ),
                justify="between",
                width="100%",
            ),

            rx.divider(),

            # Device info
            rx.vstack(
                rx.hstack(
                    rx.text("Device ID:", weight="bold", size="2"),
                    rx.code(device.device_uuid, size="1"),
                    spacing="2",
                ),
                rx.hstack(
                    rx.text("Version:", weight="bold", size="2"),
                    rx.text(device.current_version, size="2"),
                    spacing="2",
                ),
                rx.hstack(
                    rx.text("Current Stream:", weight="bold", size="2"),
                    rx.text(device.current_stream_name, size="2"),
                    spacing="2",
                ),
                rx.cond(
                    device.last_seen,
                    rx.hstack(
                        rx.text("Last Seen:", weight="bold", size="2"),
                        rx.text(
                            rx.moment(
                                device.last_seen,
                                from_now=True,
                            ),
                            size="2",
                        ),
                        spacing="2",
                    ),
                    rx.hstack(
                        rx.text("Last Seen:", weight="bold", size="2"),
                        rx.text("Never", size="2", color="gray"),
                        spacing="2",
                    ),
                ),
                spacing="2",
                align="start",
                width="100%",
            ),

            rx.divider(),

            # Actions (placeholder for future features)
            rx.hstack(
                rx.button(
                    "View Details",
                    variant="soft",
                    size="2",
                    disabled=True,  # TODO: Implement device details page
                ),
                rx.button(
                    "Configure",
                    variant="soft",
                    size="2",
                    disabled=True,  # TODO: Implement configuration
                ),
                spacing="2",
            ),

            spacing="4",
            width="100%",
            align="start",
        ),
        width="100%",
    )


def devices_list() -> rx.Component:
    """Render list of devices."""
    return rx.vstack(
        # Header
        rx.hstack(
            rx.heading("My Devices", size="8"),
            rx.button(
                rx.icon("refresh_cw", size=16),
                "Refresh",
                on_click=DevicesState.load_devices,
                variant="soft",
                size="2",
            ),
            justify="between",
            width="100%",
        ),

        rx.text(
            "Manage your StreamScene E Ink display devices.",
            size="3",
            color="gray",
        ),

        rx.divider(),

        # Error message
        rx.cond(
            DevicesState.error_message,
            rx.callout(
                DevicesState.error_message,
                icon="triangle_alert",
                color_scheme="red",
                size="2",
            ),
        ),

        # Success message
        rx.cond(
            DevicesState.success_message,
            rx.callout(
                DevicesState.success_message,
                icon="check",
                color_scheme="green",
                size="2",
            ),
        ),

        # Device list or empty state
        rx.cond(
            DevicesState.is_loading,
            rx.vstack(
                rx.spinner(size="3"),
                rx.text("Loading devices...", size="3"),
                spacing="4",
                align="center",
                padding="8",
            ),
            rx.cond(
                DevicesState.devices.length() > 0,
                rx.vstack(
                    rx.foreach(
                        DevicesState.devices,
                        device_card,
                    ),
                    spacing="4",
                    width="100%",
                ),
                # Empty state
                rx.vstack(
                    rx.icon("monitor_off", size=64, color="gray"),
                    rx.heading("No Devices Yet", size="6"),
                    rx.text(
                        "You haven't registered any devices yet.",
                        size="3",
                        color="gray",
                    ),
                    rx.text(
                        "To register a device:",
                        size="3",
                        weight="bold",
                    ),
                    rx.ordered_list(
                        rx.list_item("Power on your StreamScene device"),
                        rx.list_item("Connect to the WiFi hotspot shown on the display"),
                        rx.list_item("Configure your home WiFi"),
                        rx.list_item("Scan the QR code displayed on the device"),
                        rx.list_item("Complete the registration form"),
                        spacing="2",
                    ),
                    rx.divider(),
                    rx.link(
                        rx.button(
                            "Learn More",
                            size="3",
                            variant="soft",
                        ),
                        href="https://github.com/yourusername/streamscene",
                        is_external=True,
                    ),
                    spacing="4",
                    align="center",
                    padding="8",
                ),
            ),
        ),

        spacing="6",
        width="100%",
        align="start",
    )


def devices_page() -> rx.Component:
    """Devices management page."""
    content = rx.container(
        devices_list(),
        max_width="1200px",
        padding="4",
        on_mount=DevicesState.on_mount,
    )

    return authenticated_layout(content, current_page="devices")


# Export for app registration
devices = devices_page
