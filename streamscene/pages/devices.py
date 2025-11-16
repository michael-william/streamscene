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


class StreamOption(rx.Base):
    """Stream option for selection."""
    id: str
    name: str


class DevicesState(BaseState):
    """State for device management."""

    state_auto_setters = True

    # Device list
    devices: List[DeviceInfo] = []

    # Available streams for assignment
    available_streams: List[StreamOption] = []

    # Loading states
    is_loading: bool = True

    # Messages
    error_message: str = ""
    success_message: str = ""

    # Rename modal state
    is_rename_modal_open: bool = False
    rename_device_id: str = ""
    rename_device_nickname: str = ""
    is_renaming: bool = False

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

                # Load user's streams for assignment
                user_streams = stream_ops.get_user_streams(session, user_uuid)
                self.available_streams = [
                    StreamOption(id=str(stream.id), name=stream.name)
                    for stream in user_streams
                ]

                print(f"[DEVICES] Loaded {len(self.devices)} devices and {len(self.available_streams)} streams")

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

    def open_rename_modal(self, device_id: str, current_nickname: str):
        """Open the rename modal for a device."""
        print(f"[DEVICES] Opening rename modal for device {device_id}")
        self.rename_device_id = device_id
        self.rename_device_nickname = current_nickname
        self.is_rename_modal_open = True
        self.error_message = ""

    def close_rename_modal(self):
        """Close the rename modal."""
        self.is_rename_modal_open = False
        self.rename_device_id = ""
        self.rename_device_nickname = ""

    def rename_device(self):
        """Rename the device."""
        print(f"[DEVICES] Renaming device {self.rename_device_id} to '{self.rename_device_nickname}'")

        if not self.rename_device_id:
            self.error_message = "No device selected"
            return

        if not self.rename_device_nickname or not self.rename_device_nickname.strip():
            self.error_message = "Nickname cannot be empty"
            return

        self.is_renaming = True
        self.error_message = ""
        self.success_message = ""

        try:
            device_uuid = UUID(self.rename_device_id)

            with get_db_session() as session:
                device = stream_ops.update_device_nickname(
                    session,
                    device_id=device_uuid,
                    nickname=self.rename_device_nickname,
                )

                if not device:
                    self.error_message = "Device not found"
                    self.is_renaming = False
                    return

                session.commit()

                # Update the device in the list
                for i, dev in enumerate(self.devices):
                    if dev.id == self.rename_device_id:
                        self.devices[i].nickname = self.rename_device_nickname
                        break

                self.success_message = f"Device renamed to '{self.rename_device_nickname}'"
                self.is_rename_modal_open = False
                print(f"[DEVICES] Device renamed successfully")

        except ValueError as e:
            print(f"[DEVICES] Validation error: {e}")
            self.error_message = str(e)
        except Exception as e:
            print(f"[DEVICES] Error renaming device: {e}")
            self.error_message = f"Error renaming device: {str(e)}"
        finally:
            self.is_renaming = False

    def assign_stream(self, device_id: str, stream_id: str):
        """Assign a stream to a device."""
        print(f"[DEVICES] Assigning stream {stream_id} to device {device_id}")

        self.error_message = ""
        self.success_message = ""

        try:
            device_uuid = UUID(device_id)
            # "none" is our special value for unassigning
            stream_uuid = UUID(stream_id) if stream_id and stream_id != "none" else None

            with get_db_session() as session:
                device = stream_ops.update_device_stream(
                    session,
                    device_id=device_uuid,
                    stream_id=stream_uuid,
                )

                if not device:
                    self.error_message = "Device not found"
                    return

                session.commit()

                # Update the device in the list
                from streamscene.core.models import Stream
                stream_name = "No stream"
                if stream_uuid:
                    stream = session.query(Stream).filter(Stream.id == stream_uuid).first()
                    if stream:
                        stream_name = stream.name

                for i, dev in enumerate(self.devices):
                    if dev.id == device_id:
                        self.devices[i].current_stream_id = stream_id if stream_id != "none" else None
                        self.devices[i].current_stream_name = stream_name
                        break

                self.success_message = f"Stream assigned successfully"
                print(f"[DEVICES] Stream assigned successfully")

        except ValueError as e:
            print(f"[DEVICES] Validation error: {e}")
            self.error_message = str(e)
        except Exception as e:
            print(f"[DEVICES] Error assigning stream: {e}")
            self.error_message = f"Error assigning stream: {str(e)}"


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
                rx.vstack(
                    rx.text("Assigned Stream:", weight="bold", size="2"),
                    rx.cond(
                        DevicesState.available_streams.length() > 0,
                        rx.select.root(
                            rx.select.trigger(placeholder="Select a stream..."),
                            rx.select.content(
                                rx.select.group(
                                    rx.select.item("(No stream)", value="none"),
                                    rx.foreach(
                                        DevicesState.available_streams,
                                        lambda stream: rx.select.item(stream.name, value=stream.id),
                                    ),
                                ),
                            ),
                            value=rx.cond(device.current_stream_id, device.current_stream_id, "none"),
                            on_change=lambda value: DevicesState.assign_stream(device.id, value),
                            size="2",
                        ),
                        rx.text("No streams available - create one first", size="2", color="gray"),
                    ),
                    spacing="1",
                    align="start",
                    width="100%",
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

            # Actions
            rx.hstack(
                rx.button(
                    rx.icon("pencil", size=16),
                    "Rename",
                    on_click=lambda: DevicesState.open_rename_modal(device.id, device.nickname),
                    variant="soft",
                    size="2",
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


def rename_device_modal() -> rx.Component:
    """Modal dialog for renaming a device."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Rename Device"),
                rx.dialog.description(
                    "Enter a new name for your device.",
                    size="2",
                ),

                rx.vstack(
                    rx.text("Device Nickname", weight="bold", size="2"),
                    rx.input(
                        placeholder="My StreamScene Frame",
                        value=DevicesState.rename_device_nickname,
                        on_change=DevicesState.set_rename_device_nickname,
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

                # Actions
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            size="3",
                            on_click=DevicesState.close_rename_modal,
                        ),
                    ),
                    rx.button(
                        rx.cond(
                            DevicesState.is_renaming,
                            rx.hstack(
                                rx.spinner(size="1"),
                                rx.text("Renaming..."),
                                spacing="2",
                            ),
                            rx.text("Rename Device"),
                        ),
                        on_click=DevicesState.rename_device,
                        disabled=DevicesState.is_renaming,
                        size="3",
                    ),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),

                spacing="4",
                width="100%",
            ),
            max_width="450px",
        ),
        open=DevicesState.is_rename_modal_open,
        on_open_change=DevicesState.set_is_rename_modal_open,
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
        rx.vstack(
            devices_list(),
            rename_device_modal(),
            spacing="0",
            width="100%",
        ),
        max_width="1200px",
        padding="4",
        on_mount=DevicesState.on_mount,
    )

    return authenticated_layout(content, current_page="devices")


# Export for app registration
devices = devices_page
