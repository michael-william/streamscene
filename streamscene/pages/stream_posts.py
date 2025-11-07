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

    Stream ID is passed via query parameter: /stream-posts?id={uuid}
    """

    # Stream info
    stream_id: str = ""
    stream_name: str = ""
    stream_description: str = ""

    # Posts
    posts: List[dict] = []

    # Form fields
    new_post_content: str = ""

    # Loading states
    is_loading: bool = False
    is_posting: bool = False

    # Messages
    error_message: str = ""
    success_message: str = ""

    def on_load(self):
        """Load stream and posts when page loads.

        Using on_load (page-level) instead of on_mount (component-level)
        to ensure router.page.params is populated. See DEBUGGING_HISTORY.md.
        """
        # Check authentication first
        if redirect := self.require_auth():
            return redirect

        # Clear any previous error messages
        self.error_message = ""

        # Method 1: Get stream ID from router.page.params
        stream_id = self.router.page.params.get("id", "") if hasattr(self.router.page, "params") else ""

        print(f"[STREAM_POSTS] on_load called (page-level lifecycle)")
        print(f"[STREAM_POSTS] Method 1 (router.page.params): '{stream_id}'")

        # Method 2: Fallback to client_query_params (proven pattern from callback.py)
        if not stream_id:
            query_params = self.router.session.client_query_params
            stream_id = query_params.get("id", [""])[0] if query_params else ""
            print(f"[STREAM_POSTS] Method 2 (client_query_params): '{stream_id}'")

        print(f"[STREAM_POSTS] Final stream_id: '{stream_id}'")
        print(f"[STREAM_POSTS] User ID: {self.user_id}")

        if not stream_id:
            self.error_message = "No stream specified"
            print(f"[STREAM_POSTS] ERROR: No stream_id found via any method")
            return

        # Load stream data using the UUID from the query parameter
        yield from self.load_stream_and_posts(stream_id)

    def load_stream_and_posts(self, stream_id: str):
        """Load stream info and its posts by UUID."""
        print(f"[STREAM_POSTS] Loading stream with ID: {stream_id}")
        print(f"[STREAM_POSTS] User ID: {self.user_id}")

        try:
            user_uuid = UUID(self.user_id)
            stream_uuid = UUID(stream_id)
        except ValueError as e:
            print(f"[STREAM_POSTS] Invalid UUID: {e}")
            self.error_message = "Invalid stream ID or session. Please log in again."
            return

        try:
            with get_db_session() as session:
                # Get stream by ID
                stream = stream_ops.get_stream_by_id(session, stream_uuid)
                if not stream:
                    self.error_message = f"Stream not found: {stream_id}"
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
                        "author_name": (
                            post.author.display_name or
                            post.author.name or
                            post.author.username or
                            post.author.email or
                            "Unknown"
                        ) if post.author else "Unknown",
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

        self.is_posting = True
        self.error_message = ""
        yield

        try:
            with get_db_session() as session:
                stream_ops.create_post(
                    session,
                    stream_id=stream_uuid,
                    author_id=author_uuid,
                    text_content=self.new_post_content,
                )
                session.commit()

                self.success_message = "Post created successfully!"
                self.new_post_content = ""

                # Reload posts using the current stream_id
                if self.stream_id:
                    yield from self.load_stream_and_posts(self.stream_id)

                # Auto-dismiss success message after 3 seconds
                yield from self.auto_dismiss_success()

        except Exception as e:
            self.error_message = f"Error creating post: {str(e)}"
        finally:
            self.is_posting = False
            yield

    def auto_dismiss_success(self):
        """Auto-dismiss success message after 3 seconds."""
        import time

        # Wait 3 seconds
        time.sleep(3)

        # Clear success message
        self.success_message = ""
        yield


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
                margin_bottom="4",
            ),

            # Messages
            rx.cond(
                StreamPostsState.error_message,
                rx.callout(
                    StreamPostsState.error_message,
                    icon="triangle_alert",
                    color_scheme="red",
                    size="2",
                    margin_bottom="4",
                ),
            ),
            rx.cond(
                StreamPostsState.success_message,
                rx.callout(
                    StreamPostsState.success_message,
                    icon="check",
                    color_scheme="green",
                    size="2",
                    margin_bottom="4",
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
                        rx.cond(
                            StreamPostsState.is_posting,
                            rx.spinner(size="3"),
                            "Post Message",
                        ),
                        on_click=StreamPostsState.create_post,
                        color_scheme="blue",
                        size="3",
                        disabled=StreamPostsState.is_posting,
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
                    rx.heading("Recent Posts", size="6", margin_bottom="4"),
                    rx.foreach(
                        StreamPostsState.posts,
                        lambda post: rx.card(
                            rx.vstack(
                                rx.text(
                                    post["text_content"],
                                    size="3",
                                    line_height="1.6",
                                ),
                                rx.divider(margin_y="2"),
                                rx.hstack(
                                    rx.text(
                                        post["created_at"],
                                        size="2",
                                        color="gray",
                                        weight="medium",
                                    ),
                                    rx.text(
                                        post["author_name"],
                                        size="2",
                                        color="gray",
                                    ),
                                    justify="between",
                                    width="100%",
                                ),
                                spacing="2",
                                align="start",
                            ),
                            size="2",
                            width="100%",
                        ),
                    ),
                    spacing="4",
                    width="100%",
                ),
                rx.card(
                    rx.vstack(
                        rx.text(
                            "No posts yet",
                            size="4",
                            weight="medium",
                            color="gray",
                        ),
                        rx.text(
                            "Be the first to share a message in this stream!",
                            size="2",
                            color="gray",
                            text_align="center",
                        ),
                        spacing="2",
                        padding="8",
                        justify="center",
                        align="center",
                    ),
                    size="2",
                    width="100%",
                ),
            ),

            spacing="8",
            padding="4",
            width="100%",
        ),
        max_width="900px",
        on_mount=StreamPostsState.on_load,  # Method named on_load, triggered by on_mount
    )

    return authenticated_layout(content, current_page="streams")
