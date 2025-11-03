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

    current_stream_id: str = ""
    current_stream_posts: List[dict] = []

    # Form fields
    new_stream_name: str = ""
    new_stream_description: str = ""
    new_stream_is_public: bool = False
    new_post_content: str = ""

    # Search functionality
    search_query: str = ""

    # Modal control
    is_create_modal_open: bool = False

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
                    "description": stream.description,
                    "is_public": stream.is_public,
                })

                self.success_message = f"Stream '{self.new_stream_name}' created!"
                self.close_create_modal()  # Close modal and clear form
                yield  # Force UI update
        except Exception as e:
            self.error_message = f"Error creating stream: {str(e)}"

    def select_stream(self, stream_id: str):
        """Select a stream to view its posts."""
        self.current_stream_id = stream_id
        self.load_posts()

    def load_posts(self):
        """Load posts for the currently selected stream."""
        if not self.current_stream_id:
            return

        try:
            with get_db_session() as session:
                posts = stream_ops.get_stream_posts(
                    session, UUID(self.current_stream_id), limit=20
                )

                self.current_stream_posts = [
                    {
                        "id": str(post.id),
                        "text_content": post.text_content,
                        "created_at": post.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    for post in posts
                ]
        except Exception as e:
            self.error_message = f"Error loading posts: {str(e)}"

    def create_post(self):
        """Create a new post in the current stream."""
        if not self.current_stream_id:
            self.error_message = "No stream selected"
            return

        if not self.new_post_content.strip():
            self.error_message = "Post content is required"
            return

        # Validate user_id before attempting UUID conversion
        if not self.user_id:
            self.error_message = "You must be logged in to create a post"
            return rx.redirect("/")

        try:
            author_uuid = UUID(self.user_id)
        except ValueError:
            # Invalid UUID format - user needs to log in again
            self.error_message = "Invalid session. Please log in again."
            return rx.redirect("/")

        try:
            with get_db_session() as session:
                stream_ops.create_post(
                    session,
                    stream_id=UUID(self.current_stream_id),
                    author_id=author_uuid,
                    text_content=self.new_post_content,
                )
                session.commit()

                self.success_message = "Post created!"
                self.new_post_content = ""
                self.load_posts()
        except Exception as e:
            self.error_message = f"Error creating post: {str(e)}"

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
        rx.heading("Streams I Own", size="6"),
        rx.cond(
            StreamsState.filtered_owned_streams.length() > 0,
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
                                rx.button(
                                    "View Posts",
                                    on_click=lambda sid=stream["id"]: StreamsState.select_stream(sid),
                                    size="2",
                                    variant="soft",
                                )
                            ),
                        ),
                    ),
                ),
                variant="surface",
                size="3",
                width="100%",
            ),
            rx.text(
                "No streams yet. Click 'Add Stream' to create your first stream!",
                color="gray",
                size="3",
            ),
        ),
        spacing="3",
        width="100%",
        align="start",
    )


def subscribed_streams_table() -> rx.Component:
    """Table showing streams user is subscribed to."""
    return rx.vstack(
        rx.heading("Streams I'm Subscribed To", size="6"),
        rx.cond(
            StreamsState.filtered_subscribed_streams.length() > 0,
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
                                    rx.button(
                                        "View Posts",
                                        on_click=lambda sid=stream["id"]: StreamsState.select_stream(sid),
                                        size="2",
                                        variant="soft",
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
            rx.text(
                "You haven't subscribed to any streams yet.",
                color="gray",
                size="3",
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
                        )
                    ),
                    rx.button(
                        "Create Stream",
                        on_click=StreamsState.create_stream,
                        color_scheme="blue",
                        size="3",
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


def post_view() -> rx.Component:
    """View posts in the selected stream."""
    return rx.cond(
        StreamsState.current_stream_id,
        rx.vstack(
            rx.heading("Stream Posts", size="6"),
            # Post creation form
            rx.card(
                rx.vstack(
                    rx.text_area(
                        placeholder="Write your message...",
                        value=StreamsState.new_post_content,
                        on_change=StreamsState.set_new_post_content,
                    ),
                    rx.button(
                        "Post",
                        on_click=StreamsState.create_post,
                        color_scheme="blue",
                        size="2",
                    ),
                    spacing="2",
                    width="100%",
                ),
            ),
            # List of posts
            rx.foreach(
                StreamsState.current_stream_posts,
                lambda post: rx.card(
                    rx.vstack(
                        rx.text(post["text_content"]),
                        rx.text(
                            post["created_at"],
                            size="1",
                            color="gray",
                        ),
                        spacing="1",
                        align="start",
                    ),
                ),
            ),
            spacing="4",
            width="100%",
        ),
        rx.box(),  # Empty box when no stream selected
    )


def streams() -> rx.Component:
    """Main streams management page."""
    content = rx.container(
        rx.vstack(
            # Messages
            rx.cond(
                StreamsState.error_message,
                rx.callout(
                    StreamsState.error_message,
                    icon="triangle_alert",
                    color_scheme="red",
                ),
            ),
            rx.cond(
                StreamsState.success_message,
                rx.callout(
                    StreamsState.success_message,
                    icon="check",
                    color_scheme="green",
                ),
            ),

            # Main content in two columns
            rx.grid(
                # Left column: Streams section
                rx.vstack(
                    search_and_add_bar(),
                    owned_streams_table(),
                    subscribed_streams_table(),
                    spacing="6",
                    width="100%",
                ),

                # Right column: Post view (unchanged)
                post_view(),

                columns="2",
                spacing="6",
                width="100%",
            ),

            # Modal (rendered at root level)
            create_stream_modal(),

            spacing="6",
            padding="4",
            width="100%",
        ),
        max_width="1400px",  # Wider for tables
        on_mount=StreamsState.on_mount,  # Connect lifecycle handler
    )

    return authenticated_layout(content, current_page="streams")
