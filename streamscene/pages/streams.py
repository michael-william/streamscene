"""Stream management page."""

from typing import List
from uuid import UUID

import reflex as rx

from streamscene.core.database import get_db_session
from streamscene.core import streams as stream_ops
from streamscene.components.layout import authenticated_layout
from .base_state import BaseState


class StreamsState(BaseState):
    """State for stream management."""

    # user_id inherited from BaseState

    # Separate stream lists for better organization
    owned_streams: List[dict] = []
    subscribed_streams: List[dict] = []

    # Form fields
    new_stream_name: str = ""
    new_stream_description: str = ""
    new_stream_is_public: bool = False

    # Search functionality
    search_query: str = ""

    # Modal control
    is_create_modal_open: bool = False
    is_edit_modal_open: bool = False
    is_delete_dialog_open: bool = False

    # Edit stream fields
    edit_stream_id: str = ""
    edit_stream_name: str = ""
    edit_stream_description: str = ""
    edit_stream_is_public: bool = False

    # Delete stream field
    delete_stream_id: str = ""
    delete_stream_name: str = ""

    # Loading states
    is_loading: bool = False
    is_creating: bool = False
    is_editing: bool = False
    is_deleting: bool = False

    error_message: str = ""
    success_message: str = ""

    def on_mount(self):
        """Load user's streams when page loads."""
        print(f"[STREAMS] on_mount() called")
        print(f"[STREAMS] user_id from cookie: '{self.user_id}'")
        print(f"[STREAMS] user_id type: {type(self.user_id)}")
        print(f"[STREAMS] user_id bool: {bool(self.user_id)}")

        # Check if user is authenticated (cookie auto-loaded)
        if not self.user_id:
            print(f"[STREAMS] No user_id, redirecting to /")
            return rx.redirect("/")

        print(f"[STREAMS] Calling load_all_streams()")
        yield from self.load_all_streams()  # Properly consume the generator

    def load_owned_streams(self):
        """Load streams owned by the user."""
        print(f"[LOAD_OWNED] Called with user_id: '{self.user_id}'")

        if not self.user_id:
            print(f"[LOAD_OWNED] user_id is empty, returning")
            return

        try:
            user_uuid = UUID(self.user_id)
            print(f"[LOAD_OWNED] Converted to UUID: {user_uuid}")
        except ValueError as e:
            print(f"[LOAD_OWNED] UUID conversion failed: {e}")
            return

        try:
            with get_db_session() as session:
                print(f"[LOAD_OWNED] DB session opened, calling get_user_streams")
                user_streams = stream_ops.get_user_streams(session, user_uuid)
                print(f"[LOAD_OWNED] Query returned {len(user_streams)} streams")

                for i, stream in enumerate(user_streams):
                    print(f"[LOAD_OWNED]   Stream {i}: id={stream.id}, name={stream.name}")

                streams_data = [
                    {
                        "id": str(stream.id),
                        "name": stream.name,
                        "slug": stream.slug,
                        "description": stream.description,
                        "is_public": stream.is_public,
                    }
                    for stream in user_streams
                ]
                print(f"[LOAD_OWNED] Converted to {len(streams_data)} dict objects")

                self.owned_streams = streams_data
                print(f"[LOAD_OWNED] Set self.owned_streams, length: {len(self.owned_streams)}")
                print(f"[LOAD_OWNED] self.owned_streams value: {self.owned_streams}")
                yield  # Force UI update
                print(f"[LOAD_OWNED] Yielded for UI update")
        except Exception as e:
            print(f"[LOAD_OWNED] Exception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self.error_message = f"Error loading owned streams: {str(e)}"

    def load_subscribed_streams(self):
        """Load streams user is subscribed to."""
        print(f"[LOAD_SUBSCRIBED] Called with user_id: '{self.user_id}'")

        if not self.user_id:
            print(f"[LOAD_SUBSCRIBED] user_id is empty, returning")
            return

        try:
            user_uuid = UUID(self.user_id)
            print(f"[LOAD_SUBSCRIBED] Converted to UUID: {user_uuid}")
        except ValueError as e:
            print(f"[LOAD_SUBSCRIBED] UUID conversion failed: {e}")
            return

        try:
            with get_db_session() as session:
                print(f"[LOAD_SUBSCRIBED] DB session opened, calling get_subscribed_streams")
                subscribed = stream_ops.get_subscribed_streams(session, user_uuid)
                print(f"[LOAD_SUBSCRIBED] Query returned {len(subscribed)} streams")

                for i, stream in enumerate(subscribed):
                    print(f"[LOAD_SUBSCRIBED]   Stream {i}: id={stream.id}, name={stream.name}")

                streams_data = [
                    {
                        "id": str(stream.id),
                        "name": stream.name,
                        "slug": stream.slug,
                        "description": stream.description,
                        "is_public": stream.is_public,
                        "owner_name": "Owner",  # TODO: Get actual owner name
                    }
                    for stream in subscribed
                ]
                print(f"[LOAD_SUBSCRIBED] Converted to {len(streams_data)} dict objects")

                self.subscribed_streams = streams_data
                print(f"[LOAD_SUBSCRIBED] Set self.subscribed_streams, length: {len(self.subscribed_streams)}")
                yield  # Force UI update
                print(f"[LOAD_SUBSCRIBED] Yielded for UI update")
        except Exception as e:
            print(f"[LOAD_SUBSCRIBED] Exception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self.error_message = f"Error loading subscribed streams: {str(e)}"

    def load_all_streams(self):
        """Load both owned and subscribed streams."""
        yield from self.load_owned_streams()
        yield from self.load_subscribed_streams()

    @rx.var
    def filtered_owned_streams(self) -> List[dict]:
        """Filter owned streams based on search query."""
        print(f"[FILTERED] Computing filtered_owned_streams")
        print(f"[FILTERED] owned_streams count: {len(self.owned_streams)}")
        print(f"[FILTERED] owned_streams: {self.owned_streams}")
        print(f"[FILTERED] search_query: '{self.search_query}'")

        if not self.search_query:
            print(f"[FILTERED] No search query, returning all {len(self.owned_streams)} streams")
            return self.owned_streams

        query = self.search_query.lower()
        filtered = [
            stream for stream in self.owned_streams
            if query in stream["name"].lower() or query in stream["description"].lower()
        ]
        print(f"[FILTERED] After filtering with '{query}': {len(filtered)} streams")
        return filtered

    @rx.var
    def filtered_subscribed_streams(self) -> List[dict]:
        """Filter subscribed streams based on search query."""
        if not self.search_query:
            return self.subscribed_streams

        query = self.search_query.lower()
        return [
            stream for stream in self.subscribed_streams
            if query in stream["name"].lower() or query in stream["description"].lower()
        ]

    def open_create_modal(self):
        """Open the create stream modal."""
        self.is_create_modal_open = True

    def close_create_modal(self):
        """Close the create stream modal and clear form."""
        self.is_create_modal_open = False
        self.new_stream_name = ""
        self.new_stream_description = ""
        self.new_stream_is_public = False
        self.error_message = ""

    def open_edit_modal(self, stream_id: str):
        """Open the edit stream modal with current stream data."""
        # Find the stream in owned_streams list
        stream = None
        for s in self.owned_streams:
            if s["id"] == stream_id:
                stream = s
                break

        if not stream:
            self.error_message = "Stream not found"
            return

        self.edit_stream_id = stream_id
        self.edit_stream_name = stream["name"]
        self.edit_stream_description = stream["description"]
        self.edit_stream_is_public = stream["is_public"]
        self.is_edit_modal_open = True
        self.error_message = ""

    def close_edit_modal(self):
        """Close the edit stream modal and clear form."""
        self.is_edit_modal_open = False
        self.edit_stream_id = ""
        self.edit_stream_name = ""
        self.edit_stream_description = ""
        self.edit_stream_is_public = False
        self.error_message = ""

    def open_delete_dialog(self, stream_id: str):
        """Open the delete confirmation dialog."""
        # Find the stream in owned_streams list
        stream = None
        for s in self.owned_streams:
            if s["id"] == stream_id:
                stream = s
                break

        if not stream:
            self.error_message = "Stream not found"
            return

        self.delete_stream_id = stream_id
        self.delete_stream_name = stream["name"]
        self.is_delete_dialog_open = True
        self.error_message = ""

    def close_delete_dialog(self):
        """Close the delete confirmation dialog."""
        self.is_delete_dialog_open = False
        self.delete_stream_id = ""
        self.delete_stream_name = ""

    def create_stream(self):
        """Create a new stream."""
        if not self.new_stream_name.strip():
            self.error_message = "Stream name is required"
            return

        # Validate user_id before attempting UUID conversion
        if not self.user_id:
            self.error_message = "You must be logged in to create a stream"
            return rx.redirect("/")

        try:
            owner_uuid = UUID(self.user_id)
        except ValueError:
            # Invalid UUID format - user needs to log in again
            self.error_message = "Invalid session. Please log in again."
            return rx.redirect("/")

        self.is_creating = True
        self.error_message = ""
        yield

        try:
            with get_db_session() as session:
                stream = stream_ops.create_stream(
                    session,
                    owner_id=owner_uuid,
                    name=self.new_stream_name,
                    description=self.new_stream_description,
                    is_public=self.new_stream_is_public,
                )
                session.commit()

                # Add to owned_streams for instant UI update
                self.owned_streams.append({
                    "id": str(stream.id),
                    "name": stream.name,
                    "slug": stream.slug,
                    "description": stream.description,
                    "is_public": stream.is_public,
                })

                self.success_message = f"Stream '{self.new_stream_name}' created successfully!"
                self.close_create_modal()  # Close modal and clear form
                yield  # Force UI update

                # Auto-dismiss success message after 3 seconds
                yield from self.auto_dismiss_success()
        except Exception as e:
            self.error_message = f"Error creating stream: {str(e)}"
        finally:
            self.is_creating = False
            yield

    def edit_stream(self):
        """Edit an existing stream."""
        if not self.edit_stream_name.strip():
            self.error_message = "Stream name is required"
            return

        if not self.edit_stream_id:
            self.error_message = "No stream selected for editing"
            return

        try:
            stream_uuid = UUID(self.edit_stream_id)
        except ValueError:
            self.error_message = "Invalid stream ID"
            return

        self.is_editing = True
        self.error_message = ""
        yield

        try:
            with get_db_session() as session:
                stream = stream_ops.update_stream(
                    session,
                    stream_id=stream_uuid,
                    name=self.edit_stream_name,
                    description=self.edit_stream_description,
                    is_public=self.edit_stream_is_public,
                )

                if not stream:
                    self.error_message = "Stream not found"
                    return

                session.commit()

                # Update the stream in owned_streams list for instant UI update
                for i, s in enumerate(self.owned_streams):
                    if s["id"] == self.edit_stream_id:
                        self.owned_streams[i] = {
                            "id": str(stream.id),
                            "name": stream.name,
                            "slug": stream.slug,
                            "description": stream.description,
                            "is_public": stream.is_public,
                        }
                        break

                self.success_message = f"Stream '{self.edit_stream_name}' updated successfully!"
                self.close_edit_modal()
                yield

                # Auto-dismiss success message after 3 seconds
                yield from self.auto_dismiss_success()
        except Exception as e:
            self.error_message = f"Error updating stream: {str(e)}"
        finally:
            self.is_editing = False
            yield

    def delete_stream(self):
        """Delete a stream."""
        if not self.delete_stream_id:
            self.error_message = "No stream selected for deletion"
            return

        try:
            stream_uuid = UUID(self.delete_stream_id)
        except ValueError:
            self.error_message = "Invalid stream ID"
            return

        self.is_deleting = True
        self.error_message = ""
        yield

        try:
            with get_db_session() as session:
                success = stream_ops.delete_stream(session, stream_uuid)

                if not success:
                    self.error_message = "Stream not found"
                    return

                session.commit()

                # Remove from owned_streams list for instant UI update
                self.owned_streams = [
                    s for s in self.owned_streams if s["id"] != self.delete_stream_id
                ]

                stream_name = self.delete_stream_name
                self.success_message = f"Stream '{stream_name}' deleted successfully!"
                self.close_delete_dialog()
                yield

                # Auto-dismiss success message after 3 seconds
                yield from self.auto_dismiss_success()
        except Exception as e:
            self.error_message = f"Error deleting stream: {str(e)}"
        finally:
            self.is_deleting = False
            yield

    def auto_dismiss_success(self):
        """Auto-dismiss success message after 3 seconds."""
        import asyncio
        import time

        # Wait 3 seconds
        time.sleep(3)

        # Clear success message
        self.success_message = ""
        yield

    # logout() method inherited from BaseState


def search_and_add_bar() -> rx.Component:
    """Search bar with Add Stream button."""
    return rx.hstack(
        rx.input(
            placeholder="Search streams...",
            value=StreamsState.search_query,
            on_change=StreamsState.set_search_query,
            size="3",
            width="100%",
        ),
        rx.button(
            "+ Add Stream",
            on_click=StreamsState.open_create_modal,
            color_scheme="blue",
            size="3",
        ),
        spacing="4",
        width="100%",
        justify="between",
        align="center",
    )


def owned_streams_table() -> rx.Component:
    """Table showing streams owned by the user."""
    return rx.vstack(
        rx.heading("Streams I Own", size="6", margin_bottom="3"),
        rx.cond(
            StreamsState.filtered_owned_streams.length() > 0,
            rx.card(
                rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("Description"),
                        rx.table.column_header_cell("Visibility"),
                        rx.table.column_header_cell("Actions"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(
                        StreamsState.filtered_owned_streams,
                        lambda stream: rx.table.row(
                            rx.table.cell(
                                rx.text(stream["name"], weight="medium")
                            ),
                            rx.table.cell(
                                rx.text(stream["description"], color="gray", size="2")
                            ),
                            rx.table.cell(
                                rx.badge(
                                    rx.cond(stream["is_public"], "Public", "Private"),
                                    color_scheme=rx.cond(stream["is_public"], "green", "gray"),
                                )
                            ),
                            rx.table.cell(
                                rx.hstack(
                                    rx.link(
                                        rx.button(
                                            "View Posts",
                                            size="2",
                                            variant="soft",
                                        ),
                                        href=f"/stream-posts?id={stream['id']}",
                                    ),
                                    rx.button(
                                        "Edit",
                                        size="2",
                                        variant="soft",
                                        color_scheme="blue",
                                        on_click=StreamsState.open_edit_modal(stream["id"]),
                                    ),
                                    rx.button(
                                        "Delete",
                                        size="2",
                                        variant="soft",
                                        color_scheme="red",
                                        on_click=StreamsState.open_delete_dialog(stream["id"]),
                                    ),
                                    spacing="2",
                                )
                            ),
                        ),
                    ),
                ),
                    variant="surface",
                    size="3",
                    width="100%",
                ),
                size="2",
            ),
            rx.card(
                rx.vstack(
                    rx.text(
                        "No streams yet",
                        size="4",
                        weight="medium",
                        color="gray",
                    ),
                    rx.text(
                        "Click 'Add Stream' above to create your first stream and start sharing messages!",
                        size="2",
                        color="gray",
                        text_align="center",
                    ),
                    spacing="2",
                    align="center",
                    padding="6",
                ),
                size="2",
                width="100%",
            ),
        ),
        spacing="3",
        width="100%",
        align="start",
    )


def subscribed_streams_table() -> rx.Component:
    """Table showing streams user is subscribed to."""
    return rx.vstack(
        rx.heading("Streams I'm Subscribed To", size="6", margin_bottom="3"),
        rx.cond(
            StreamsState.filtered_subscribed_streams.length() > 0,
            rx.card(
                rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("Owner"),
                        rx.table.column_header_cell("Description"),
                        rx.table.column_header_cell("Actions"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(
                        StreamsState.filtered_subscribed_streams,
                        lambda stream: rx.table.row(
                            rx.table.cell(
                                rx.text(stream["name"], weight="medium")
                            ),
                            rx.table.cell(
                                rx.text(stream["owner_name"], size="2")
                            ),
                            rx.table.cell(
                                rx.text(stream["description"], color="gray", size="2")
                            ),
                            rx.table.cell(
                                rx.hstack(
                                    rx.link(
                                        rx.button(
                                            "View Posts",
                                            size="2",
                                            variant="soft",
                                        ),
                                        href=f"/stream-posts?id={stream['id']}",
                                    ),
                                    rx.button(
                                        "Unsubscribe",
                                        size="2",
                                        color_scheme="red",
                                        variant="ghost",
                                        disabled=True,  # TODO: Implement unsubscribe
                                    ),
                                    spacing="2",
                                )
                            ),
                        ),
                    ),
                ),
                    variant="surface",
                    size="3",
                    width="100%",
                ),
                size="2",
            ),
            rx.card(
                rx.vstack(
                    rx.text(
                        "No subscriptions yet",
                        size="4",
                        weight="medium",
                        color="gray",
                    ),
                    rx.text(
                        "You can subscribe to streams shared by others to see their posts.",
                        size="2",
                        color="gray",
                        text_align="center",
                    ),
                    spacing="2",
                    align="center",
                    padding="6",
                ),
                size="2",
                width="100%",
            ),
        ),
        spacing="3",
        width="100%",
        align="start",
    )


def create_stream_modal() -> rx.Component:
    """Modal dialog for creating a new stream."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Create New Stream"),
                rx.dialog.description(
                    "Create a new stream to share messages with family and friends."
                ),
                rx.input(
                    placeholder="Stream name",
                    value=StreamsState.new_stream_name,
                    on_change=StreamsState.set_new_stream_name,
                    size="3",
                ),
                rx.text_area(
                    placeholder="Description (optional)",
                    value=StreamsState.new_stream_description,
                    on_change=StreamsState.set_new_stream_description,
                    size="3",
                    rows="3",
                ),
                rx.checkbox(
                    "Make this stream public",
                    checked=StreamsState.new_stream_is_public,
                    on_change=StreamsState.set_new_stream_is_public,
                    size="3",
                ),
                rx.cond(
                    StreamsState.error_message,
                    rx.callout(
                        StreamsState.error_message,
                        icon="triangle_alert",
                        color_scheme="red",
                        size="1",
                    ),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            size="3",
                            on_click=StreamsState.close_create_modal,
                            disabled=StreamsState.is_creating,
                        )
                    ),
                    rx.button(
                        rx.cond(
                            StreamsState.is_creating,
                            rx.spinner(size="3"),
                            "Create Stream",
                        ),
                        on_click=StreamsState.create_stream,
                        color_scheme="blue",
                        size="3",
                        disabled=StreamsState.is_creating,
                    ),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            size="3",
            max_width="500px",
        ),
        open=StreamsState.is_create_modal_open,
        on_open_change=StreamsState.set_is_create_modal_open,
    )


def edit_stream_modal() -> rx.Component:
    """Modal dialog for editing a stream."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Edit Stream"),
                rx.dialog.description(
                    "Update your stream's name, description, or visibility."
                ),
                rx.input(
                    placeholder="Stream name",
                    value=StreamsState.edit_stream_name,
                    on_change=StreamsState.set_edit_stream_name,
                    size="3",
                ),
                rx.text_area(
                    placeholder="Description (optional)",
                    value=StreamsState.edit_stream_description,
                    on_change=StreamsState.set_edit_stream_description,
                    size="3",
                    rows="3",
                ),
                rx.checkbox(
                    "Make this stream public",
                    checked=StreamsState.edit_stream_is_public,
                    on_change=StreamsState.set_edit_stream_is_public,
                    size="3",
                ),
                rx.cond(
                    StreamsState.error_message,
                    rx.callout(
                        StreamsState.error_message,
                        icon="triangle_alert",
                        color_scheme="red",
                        size="1",
                    ),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            size="3",
                            on_click=StreamsState.close_edit_modal,
                            disabled=StreamsState.is_editing,
                        )
                    ),
                    rx.button(
                        rx.cond(
                            StreamsState.is_editing,
                            rx.spinner(size="3"),
                            "Save Changes",
                        ),
                        on_click=StreamsState.edit_stream,
                        color_scheme="blue",
                        size="3",
                        disabled=StreamsState.is_editing,
                    ),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            size="3",
            max_width="500px",
        ),
        open=StreamsState.is_edit_modal_open,
        on_open_change=StreamsState.set_is_edit_modal_open,
    )


def delete_confirmation_dialog() -> rx.Component:
    """Dialog for confirming stream deletion."""
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Delete Stream"),
            rx.alert_dialog.description(
                rx.vstack(
                    rx.text(
                        f"Are you sure you want to delete this stream?",
                        size="3",
                    ),
                    rx.text(
                        rx.text.strong(StreamsState.delete_stream_name),
                        size="3",
                    ),
                    rx.text(
                        "This action cannot be undone. All posts in this stream will be permanently deleted.",
                        size="2",
                        color="red",
                    ),
                    spacing="2",
                    align="start",
                ),
            ),
            rx.hstack(
                rx.alert_dialog.cancel(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        size="3",
                        disabled=StreamsState.is_deleting,
                    )
                ),
                rx.alert_dialog.action(
                    rx.button(
                        rx.cond(
                            StreamsState.is_deleting,
                            rx.spinner(size="3"),
                            "Delete Stream",
                        ),
                        on_click=StreamsState.delete_stream,
                        color_scheme="red",
                        size="3",
                        disabled=StreamsState.is_deleting,
                    )
                ),
                spacing="3",
                justify="end",
                width="100%",
            ),
        ),
        open=StreamsState.is_delete_dialog_open,
        on_open_change=StreamsState.set_is_delete_dialog_open,
    )


def streams() -> rx.Component:
    """Main streams management page."""
    content = rx.container(
        rx.vstack(
            # Page header
            rx.heading("My Streams", size="8", margin_bottom="2"),
            rx.text(
                "Manage your streams and view subscriptions",
                size="3",
                color="gray",
                margin_bottom="4",
            ),

            # Messages
            rx.cond(
                StreamsState.error_message,
                rx.callout(
                    StreamsState.error_message,
                    icon="triangle_alert",
                    color_scheme="red",
                    size="2",
                    margin_bottom="4",
                ),
            ),
            rx.cond(
                StreamsState.success_message,
                rx.callout(
                    StreamsState.success_message,
                    icon="check",
                    color_scheme="green",
                    size="2",
                    margin_bottom="4",
                ),
            ),

            # Main content - streams section (full width)
            rx.vstack(
                search_and_add_bar(),
                owned_streams_table(),
                subscribed_streams_table(),
                spacing="8",
                width="100%",
                align="start",
            ),

            # Modals and dialogs (rendered at root level)
            create_stream_modal(),
            edit_stream_modal(),
            delete_confirmation_dialog(),

            spacing="6",
            padding="4",
            width="100%",
        ),
        max_width="1200px",  # Good width for single-column table view
        padding_x=["4", "6", "8"],  # Responsive horizontal padding
        on_mount=StreamsState.on_mount,  # Connect lifecycle handler
    )

    return authenticated_layout(content, current_page="streams")
