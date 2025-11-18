"""Device management page."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta

import reflex as rx
from pydantic import BaseModel

from streamscene.core.database import get_db_session
from streamscene.core import streams as stream_ops
from streamscene.components.layout import authenticated_layout
from .base_state import BaseState


class DeviceInfo(BaseModel):
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
    rotation_post_count: int = 10
    is_online: bool = False


class StreamOption(BaseModel):
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

    # Rotation settings modal state
    is_rotation_modal_open: bool = False
    rotation_device_id: str = ""
    rotation_enabled: bool = False
    rotation_value: int = 2
    rotation_unit: str = "minutes"  # "minutes" or "hours"
    rotation_post_count: int = 10  # Number of posts to show (2-10)
    is_updating_rotation: bool = False

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
                            rotation_post_count=device.rotation_post_count,
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

    def open_rotation_modal(self, device_id: str, current_enabled: bool, current_interval: int, current_post_count: int):
        """Open the rotation settings modal for a device."""
        print(f"[DEVICES] Opening rotation modal for device {device_id}")
        self.rotation_device_id = device_id
        self.rotation_enabled = current_enabled
        self.rotation_post_count = current_post_count

        # Convert seconds to minutes or hours for display
        if current_interval >= 3600 and current_interval % 3600 == 0:
            # Show in hours if evenly divisible
            self.rotation_value = current_interval // 3600
            self.rotation_unit = "hours"
        else:
            # Show in minutes
            self.rotation_value = current_interval // 60
            self.rotation_unit = "minutes"

        self.is_rotation_modal_open = True
        self.error_message = ""

    def close_rotation_modal(self):
        """Close the rotation settings modal."""
        self.is_rotation_modal_open = False
        self.rotation_device_id = ""

    def set_rotation_value_from_input(self, value: str):
        """Set rotation value from input, handling string conversion."""
        try:
            int_value = int(value) if value else 1
            # Clamp between 1 and 24
            self.rotation_value = max(1, min(24, int_value))
        except (ValueError, TypeError):
            self.rotation_value = 1

    def set_rotation_post_count_from_input(self, value: str):
        """Set rotation post count from input, handling string conversion."""
        try:
            int_value = int(value) if value else 2
            # Clamp between 2 and 10
            self.rotation_post_count = max(2, min(10, int_value))
        except (ValueError, TypeError):
            self.rotation_post_count = 2

    def update_rotation_settings(self):
        """Update rotation settings for the device."""
        print(f"[DEVICES] Updating rotation for device {self.rotation_device_id}")

        if not self.rotation_device_id:
            self.error_message = "No device selected"
            return

        self.is_updating_rotation = True
        self.error_message = ""
        self.success_message = ""

        try:
            device_uuid = UUID(self.rotation_device_id)

            # Convert to seconds
            if self.rotation_unit == "hours":
                interval_seconds = self.rotation_value * 3600
            else:  # minutes
                interval_seconds = self.rotation_value * 60

            with get_db_session() as session:
                device = stream_ops.update_device_rotation(
                    session,
                    device_id=device_uuid,
                    rotation_enabled=self.rotation_enabled,
                    rotation_interval=interval_seconds,
                    rotation_post_count=self.rotation_post_count,
                )

                if not device:
                    self.error_message = "Device not found"
                    self.is_updating_rotation = False
                    return

                session.commit()

                # Update the device in the list
                for i, dev in enumerate(self.devices):
                    if dev.id == self.rotation_device_id:
                        self.devices[i].rotation_enabled = self.rotation_enabled
                        self.devices[i].rotation_interval = interval_seconds
                        self.devices[i].rotation_post_count = self.rotation_post_count if self.rotation_enabled else 1
                        break

                self.success_message = "Rotation settings updated successfully"
                self.is_rotation_modal_open = False
                print(f"[DEVICES] Rotation settings updated successfully")

        except ValueError as e:
            print(f"[DEVICES] Validation error: {e}")
            self.error_message = str(e)
        except Exception as e:
            print(f"[DEVICES] Error updating rotation: {e}")
            self.error_message = f"Error updating rotation: {str(e)}"
        finally:
            self.is_updating_rotation = False

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
                # Rotation status
                rx.cond(
                    device.rotation_enabled,
                    rx.hstack(
                        rx.text("Rotation:", weight="bold", size="2"),
                        rx.text(
                            rx.cond(
                                device.rotation_interval >= 3600,
                                (device.rotation_interval // 3600).to(str) + " hour(s), " + device.rotation_post_count.to(str) + " posts",
                                (device.rotation_interval // 60).to(str) + " min, " + device.rotation_post_count.to(str) + " posts",
                            ),
                            size="2",
                            color="green",
                        ),
                        spacing="2",
                    ),
                    rx.hstack(
                        rx.text("Rotation:", weight="bold", size="2"),
                        rx.text("Off (latest post only)", size="2", color="gray"),
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
                    rx.icon("refresh_cw", size=16),
                    "Rotation",
                    on_click=lambda: DevicesState.open_rotation_modal(
                        device.id,
                        device.rotation_enabled,
                        device.rotation_interval,
                        device.rotation_post_count,
                    ),
                    variant="soft",
                    size="2",
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


def rotation_settings_modal() -> rx.Component:
    """Modal dialog for configuring device rotation."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Rotation Settings"),
                rx.dialog.description(
                    "Configure how this device rotates through stream posts.",
                    size="2",
                ),

                rx.vstack(
                    # Enable rotation toggle
                    rx.hstack(
                        rx.switch(
                            checked=DevicesState.rotation_enabled,
                            on_change=DevicesState.set_rotation_enabled,
                        ),
                        rx.text("Enable rotation", weight="bold", size="3"),
                        spacing="3",
                        align="center",
                    ),

                    rx.cond(
                        DevicesState.rotation_enabled,
                        rx.vstack(
                            rx.divider(),

                            # Rotation interval
                            rx.vstack(
                                rx.text("Rotation Interval", weight="bold", size="2"),
                                rx.hstack(
                                    rx.input(
                                        type="number",
                                        value=DevicesState.rotation_value.to(str),
                                        on_change=DevicesState.set_rotation_value_from_input,
                                        min="1",
                                        max="24",
                                        size="3",
                                        width="100px",
                                    ),
                                    rx.select.root(
                                        rx.select.trigger(),
                                        rx.select.content(
                                            rx.select.item("Minutes", value="minutes"),
                                            rx.select.item("Hours", value="hours"),
                                        ),
                                        value=DevicesState.rotation_unit,
                                        on_change=DevicesState.set_rotation_unit,
                                        size="3",
                                    ),
                                    spacing="2",
                                    align="center",
                                ),
                                rx.text(
                                    "How long to show each post before rotating to the next",
                                    size="1",
                                    color="gray",
                                ),
                                spacing="2",
                                align="start",
                                width="100%",
                            ),

                            # Post count selector
                            rx.vstack(
                                rx.text("Number of Posts", weight="bold", size="2"),
                                rx.input(
                                    type="number",
                                    value=DevicesState.rotation_post_count.to(str),
                                    on_change=DevicesState.set_rotation_post_count_from_input,
                                    min="2",
                                    max="10",
                                    size="3",
                                    width="100px",
                                ),
                                rx.text(
                                    "How many recent posts to rotate through (2-10)",
                                    size="1",
                                    color="gray",
                                ),
                                spacing="2",
                                align="start",
                                width="100%",
                            ),

                            spacing="4",
                            width="100%",
                        ),
                    ),

                    spacing="4",
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
                            on_click=DevicesState.close_rotation_modal,
                        ),
                    ),
                    rx.button(
                        rx.cond(
                            DevicesState.is_updating_rotation,
                            rx.hstack(
                                rx.spinner(size="1"),
                                rx.text("Saving..."),
                                spacing="2",
                            ),
                            rx.text("Save Settings"),
                        ),
                        on_click=DevicesState.update_rotation_settings,
                        disabled=DevicesState.is_updating_rotation,
                        size="3",
                    ),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),

                spacing="4",
                width="100%",
            ),
            max_width="500px",
        ),
        open=DevicesState.is_rotation_modal_open,
        on_open_change=DevicesState.set_is_rotation_modal_open,
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
            rotation_settings_modal(),
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
