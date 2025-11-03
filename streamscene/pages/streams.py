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
    streams: List[dict] = []
    current_stream_id: str = ""
    current_stream_posts: List[dict] = []

    # Form fields
    new_stream_name: str = ""
    new_stream_description: str = ""
    new_stream_is_public: bool = False
    new_post_content: str = ""

    error_message: str = ""
    success_message: str = ""

    def on_mount(self):
        """Load user's streams when page loads."""
        # Check if user is authenticated (cookie auto-loaded)
        if not self.user_id:
            return rx.redirect("/")

        self.load_streams()

    def load_streams(self):
        """Load all streams owned by the user."""
        # Validate user_id before attempting UUID conversion
        if not self.user_id:
            return rx.redirect("/")

        try:
            user_uuid = UUID(self.user_id)
        except ValueError:
            # Invalid UUID format - user needs to log in again
            return rx.redirect("/")

        try:
            with get_db_session() as session:
                user_streams = stream_ops.get_user_streams(
                    session, user_uuid
                )

                self.streams = [
                    {
                        "id": str(stream.id),
                        "name": stream.name,
                        "description": stream.description,
                        "is_public": stream.is_public,
                    }
                    for stream in user_streams
                ]
        except Exception as e:
            self.error_message = f"Error loading streams: {str(e)}"

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

                self.success_message = f"Stream '{self.new_stream_name}' created!"
                self.new_stream_name = ""
                self.new_stream_description = ""
                self.new_stream_is_public = False
                self.load_streams()
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


def stream_list() -> rx.Component:
    """Render the list of streams."""
    return rx.vstack(
        rx.heading("Your Streams", size="6"),
        rx.foreach(
            StreamsState.streams,
            lambda stream: rx.card(
                rx.vstack(
                    rx.heading(stream["name"], size="4"),
                    rx.text(stream["description"], color="gray"),
                    rx.badge(
                        rx.cond(stream["is_public"], "Public", "Private"),
                        color_scheme=rx.cond(stream["is_public"], "green", "gray"),
                    ),
                    rx.button(
                        "View Posts",
                        on_click=lambda: StreamsState.select_stream(stream["id"]),
                        size="2",
                    ),
                    spacing="2",
                    align="start",
                ),
            ),
        ),
        spacing="4",
        width="100%",
    )


def create_stream_form() -> rx.Component:
    """Form to create a new stream."""
    return rx.card(
        rx.vstack(
            rx.heading("Create New Stream", size="5"),
            rx.input(
                placeholder="Stream name",
                value=StreamsState.new_stream_name,
                on_change=StreamsState.set_new_stream_name,
            ),
            rx.text_area(
                placeholder="Description (optional)",
                value=StreamsState.new_stream_description,
                on_change=StreamsState.set_new_stream_description,
            ),
            rx.checkbox(
                "Make this stream public",
                checked=StreamsState.new_stream_is_public,
                on_change=StreamsState.set_new_stream_is_public,
            ),
            rx.button(
                "Create Stream",
                on_click=StreamsState.create_stream,
                color_scheme="blue",
            ),
            spacing="3",
            width="100%",
        ),
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
                rx.vstack(
                    stream_list(),
                    create_stream_form(),
                    spacing="6",
                    width="100%",
                ),
                post_view(),
                columns="2",
                spacing="6",
                width="100%",
            ),
            spacing="6",
            padding="4",
            width="100%",
        ),
        max_width="1200px",
    )

    return authenticated_layout(content, current_page="streams")
