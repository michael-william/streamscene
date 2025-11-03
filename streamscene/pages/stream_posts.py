"""Stream posts page - view and create posts for a specific stream."""

from typing import List
from uuid import UUID

import reflex as rx

from streamscene.core.database import get_db_session
from streamscene.core import streams as stream_ops
from streamscene.components.layout import authenticated_layout
from .base_state import BaseState


class StreamPostsState(BaseState):
    """State for viewing posts in a stream.

    Note: The dynamic route parameter 'slug' from /streams/[slug] is automatically
    available as self.slug - we don't need to define it here.
    """

    # Stream info
    stream_id: str = ""
    stream_name: str = ""
    stream_description: str = ""

    # Posts
    posts: List[dict] = []

    # Form fields
    new_post_content: str = ""

    # Messages
    error_message: str = ""
    success_message: str = ""

    def on_mount(self):
        """Load stream and posts when page mounts."""
        # Check authentication first
        if redirect := self.require_auth():
            return redirect

        # Load stream data using the slug from the URL
        yield from self.load_stream_and_posts(self.slug)

    def load_stream_and_posts(self, slug: str):
        """Load stream info and its posts by slug."""
        print(f"[STREAM_POSTS] Loading stream with slug: {slug}")
        print(f"[STREAM_POSTS] User ID: {self.user_id}")

        try:
            user_uuid = UUID(self.user_id)
        except ValueError as e:
            print(f"[STREAM_POSTS] Invalid user UUID: {e}")
            self.error_message = "Invalid session. Please log in again."
            return

        try:
            with get_db_session() as session:
                # Get stream by slug
                stream = stream_ops.get_stream_by_slug(session, slug)
                if not stream:
                    self.error_message = f"Stream not found: {slug}"
                    return

                # Store the stream UUID for later use (e.g., in create_post)
                self.stream_id = str(stream.id)

                # Check if user can view this stream
                if not stream_ops.can_user_view_stream(session, user_uuid, stream.id):
                    self.error_message = "You don't have permission to view this stream"
                    return

                self.stream_name = stream.name
                self.stream_description = stream.description

                # Load posts
                posts = stream_ops.get_stream_posts(session, stream.id, limit=50)
                self.posts = [
                    {
                        "id": str(post.id),
                        "text_content": post.text_content,
                        "created_at": post.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    for post in posts
                ]

                print(f"[STREAM_POSTS] Loaded stream '{self.stream_name}' with {len(self.posts)} posts")
                yield

        except Exception as e:
            print(f"[STREAM_POSTS] Error: {e}")
            import traceback
            traceback.print_exc()
            self.error_message = f"Error loading stream: {str(e)}"

    def create_post(self):
        """Create a new post in this stream."""
        if not self.new_post_content.strip():
            self.error_message = "Post content is required"
            return

        if not self.user_id:
            self.error_message = "You must be logged in to post. Please refresh the page."
            return

        if not self.stream_id:
            self.error_message = "No stream selected"
            return

        try:
            author_uuid = UUID(self.user_id)
            stream_uuid = UUID(self.stream_id)
        except ValueError:
            self.error_message = "Invalid session. Please refresh the page."
            return

        try:
            with get_db_session() as session:
                stream_ops.create_post(
                    session,
                    stream_id=stream_uuid,
                    author_id=author_uuid,
                    text_content=self.new_post_content,
                )
                session.commit()

                self.success_message = "Post created!"
                self.new_post_content = ""

                # Reload posts
                yield from self.load_stream_and_posts(self.stream_id)

        except Exception as e:
            self.error_message = f"Error creating post: {str(e)}"


def stream_posts_page() -> rx.Component:
    """Page for viewing and creating posts in a stream."""

    content = rx.container(
        rx.vstack(
            # Back button
            rx.link(
                rx.button(
                    "← Back to Streams",
                    variant="soft",
                    color_scheme="gray",
                    size="2",
                ),
                href="/streams",
            ),

            # Messages
            rx.cond(
                StreamPostsState.error_message,
                rx.callout(
                    StreamPostsState.error_message,
                    icon="triangle_alert",
                    color_scheme="red",
                ),
            ),
            rx.cond(
                StreamPostsState.success_message,
                rx.callout(
                    StreamPostsState.success_message,
                    icon="check",
                    color_scheme="green",
                ),
            ),

            # Stream header
            rx.card(
                rx.vstack(
                    rx.heading(StreamPostsState.stream_name, size="8"),
                    rx.cond(
                        StreamPostsState.stream_description,
                        rx.text(
                            StreamPostsState.stream_description,
                            color="gray",
                            size="3",
                        ),
                    ),
                    spacing="2",
                    align="start",
                ),
                size="3",
                width="100%",
            ),

            # Post creation form
            rx.card(
                rx.vstack(
                    rx.text("Create a new post", weight="medium", size="4", margin_bottom="2"),
                    rx.text_area(
                        placeholder="Write your message...",
                        value=StreamPostsState.new_post_content,
                        on_change=StreamPostsState.set_new_post_content,
                        size="3",
                        rows="4",
                    ),
                    rx.button(
                        "Post Message",
                        on_click=StreamPostsState.create_post,
                        color_scheme="blue",
                        size="3",
                    ),
                    spacing="3",
                    width="100%",
                ),
                size="3",
                width="100%",
            ),

            # Posts list
            rx.cond(
                StreamPostsState.posts.length() > 0,
                rx.vstack(
                    rx.heading("Posts", size="6", margin_bottom="3"),
                    rx.foreach(
                        StreamPostsState.posts,
                        lambda post: rx.card(
                            rx.vstack(
                                rx.text(post["text_content"], size="3"),
                                rx.text(
                                    post["created_at"],
                                    size="2",
                                    color="gray",
                                ),
                                spacing="2",
                                align="start",
                            ),
                            size="2",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
                rx.card(
                    rx.vstack(
                        rx.text(
                            "No posts yet. Be the first to post!",
                            color="gray",
                            size="3",
                            text_align="center",
                        ),
                        padding="8",
                        justify="center",
                        align="center",
                    ),
                    size="2",
                ),
            ),

            spacing="6",
            padding="4",
            width="100%",
        ),
        max_width="900px",
        on_mount=StreamPostsState.on_mount,
    )

    return authenticated_layout(content, current_page="streams")
