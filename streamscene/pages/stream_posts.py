"""Stream posts page - view and create posts for a specific stream."""

from typing import List
from uuid import UUID

import reflex as rx

from streamscene.core.database import get_db_session
from streamscene.core import streams as stream_ops
from streamscene.components.layout import authenticated_layout
from streamscene.components.eink import eink_preview, get_text_warnings
from .base_state import BaseState


class StreamPostsState(BaseState):
    """State for viewing posts in a stream.

    Stream ID is passed via query parameter: /stream-posts?id={uuid}
    """

    # Stream info
    stream_id: str = ""
    stream_name: str = ""
    stream_description: str = ""
    stream_theme_name: str = "classic"

    # Posts
    posts: List[dict] = []

    # Form fields
    new_post_content: str = ""

    # Edit state
    editing_post_id: str = ""
    edit_post_content: str = ""
    is_edit_modal_open: bool = False

    # Delete state
    deleting_post_id: str = ""
    is_delete_confirm_open: bool = False

    # Loading states
    is_loading: bool = False
    is_posting: bool = False
    is_saving_edit: bool = False
    is_deleting: bool = False

    # Messages
    error_message: str = ""
    success_message: str = ""

    # E Ink preview
    show_preview: bool = False

    @rx.var
    def preview_warnings(self) -> List[str]:
        """Get warning messages for preview."""
        if not self.new_post_content:
            return []
        return get_text_warnings(self.new_post_content, 48)  # Use default font size for warning calc

    @rx.var
    def char_count(self) -> int:
        """Get character count of new post content."""
        return len(self.new_post_content)

    @rx.var
    def theme_background(self) -> str:
        """Get background color for current stream theme."""
        from streamscene.components.eink.theme import get_theme
        theme = get_theme(self.stream_theme_name)
        return theme.background_color

    @rx.var
    def theme_text_color(self) -> str:
        """Get text color for current stream theme."""
        from streamscene.components.eink.theme import get_theme
        theme = get_theme(self.stream_theme_name)
        return theme.text_color

    @rx.var
    def theme_header_color(self) -> str:
        """Get header color for current stream theme."""
        from streamscene.components.eink.theme import get_theme
        theme = get_theme(self.stream_theme_name)
        return theme.header_color

    @rx.var
    def theme_divider_color(self) -> str:
        """Get divider color for current stream theme."""
        from streamscene.components.eink.theme import get_theme
        theme = get_theme(self.stream_theme_name)
        return theme.divider_color

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
                self.stream_theme_name = stream.theme_name

                print(f"[STREAM_POSTS] Loaded stream theme: '{self.stream_theme_name}'")

                # Load posts
                posts = stream_ops.get_stream_posts(session, stream.id, limit=50)
                self.posts = [
                    {
                        "id": str(post.id),
                        "text_content": post.text_content,
                        "author_id": str(post.author_id),
                        "created_at": post.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "author_name": (
                            post.author.display_name or
                            post.author.name or
                            post.author.username or
                            post.author.email or
                            "Unknown"
                        ) if post.author else "Unknown",
                        "is_edited": post.updated_at > post.created_at,
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

    def open_edit_modal(self, post_data: dict):
        """Open edit modal with post content."""
        self.editing_post_id = post_data["id"]
        self.edit_post_content = post_data["text_content"]
        self.is_edit_modal_open = True
        self.error_message = ""

    def cancel_edit(self):
        """Close edit modal and clear state."""
        self.is_edit_modal_open = False
        self.editing_post_id = ""
        self.edit_post_content = ""
        self.error_message = ""

    def save_edit(self):
        """Save edited post content."""
        if not self.edit_post_content.strip():
            self.error_message = "Post content cannot be empty"
            return

        if not self.user_id or not self.editing_post_id:
            self.error_message = "Invalid session. Please refresh the page."
            return

        try:
            user_uuid = UUID(self.user_id)
            post_uuid = UUID(self.editing_post_id)
        except ValueError:
            self.error_message = "Invalid session. Please refresh the page."
            return

        self.is_saving_edit = True
        self.error_message = ""
        yield

        try:
            with get_db_session() as session:
                # Check permission
                if not stream_ops.can_user_edit_post(session, user_uuid, post_uuid):
                    self.error_message = "You don't have permission to edit this post"
                    self.is_saving_edit = False
                    return

                # Update post
                updated_post = stream_ops.update_post(
                    session,
                    post_id=post_uuid,
                    text_content=self.edit_post_content,
                )

                if not updated_post:
                    self.error_message = "Post not found"
                    self.is_saving_edit = False
                    return

                session.commit()

                self.success_message = "Post updated successfully!"
                self.cancel_edit()  # Close modal

                # Reload posts
                if self.stream_id:
                    yield from self.load_stream_and_posts(self.stream_id)

                # Auto-dismiss success message
                yield from self.auto_dismiss_success()

        except Exception as e:
            self.error_message = f"Error updating post: {str(e)}"
        finally:
            self.is_saving_edit = False
            yield

    def open_delete_dialog(self, post_data: dict):
        """Open delete confirmation dialog."""
        self.deleting_post_id = post_data["id"]
        self.is_delete_confirm_open = True
        self.error_message = ""

    def cancel_delete(self):
        """Close delete confirmation dialog."""
        self.is_delete_confirm_open = False
        self.deleting_post_id = ""
        self.error_message = ""

    def confirm_delete(self):
        """Delete the post after confirmation."""
        if not self.user_id or not self.deleting_post_id:
            self.error_message = "Invalid session. Please refresh the page."
            return

        try:
            user_uuid = UUID(self.user_id)
            post_uuid = UUID(self.deleting_post_id)
        except ValueError:
            self.error_message = "Invalid session. Please refresh the page."
            return

        self.is_deleting = True
        self.error_message = ""
        yield

        try:
            with get_db_session() as session:
                # Check permission
                if not stream_ops.can_user_delete_post(session, user_uuid, post_uuid):
                    self.error_message = "You don't have permission to delete this post"
                    self.is_deleting = False
                    return

                # Delete post
                deleted = stream_ops.delete_post(session, post_uuid)

                if not deleted:
                    self.error_message = "Post not found"
                    self.is_deleting = False
                    return

                session.commit()

                self.success_message = "Post deleted successfully!"
                self.cancel_delete()  # Close dialog

                # Reload posts
                if self.stream_id:
                    yield from self.load_stream_and_posts(self.stream_id)

                # Auto-dismiss success message
                yield from self.auto_dismiss_success()

        except Exception as e:
            self.error_message = f"Error deleting post: {str(e)}"
        finally:
            self.is_deleting = False
            yield


def post_card(post: dict) -> rx.Component:
    """Render a single post card with edit/delete buttons."""
    return rx.card(
        rx.vstack(
            # Post content
            rx.text(
                post["text_content"],
                size="3",
                line_height="1.6",
            ),
            rx.divider(margin_y="2"),
            # Footer with author, timestamp, and actions
            rx.hstack(
                # Left side: author and timestamp
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
                    # Show "edited" badge if post was edited
                    rx.cond(
                        post["is_edited"],
                        rx.badge(
                            "edited",
                            size="1",
                            color_scheme="gray",
                            variant="soft",
                        ),
                    ),
                    spacing="3",
                    align="center",
                ),
                # Right side: Edit and Delete buttons (only for post author)
                rx.cond(
                    post["author_id"] == StreamPostsState.user_id,
                    rx.hstack(
                        rx.button(
                            "Edit",
                            on_click=StreamPostsState.open_edit_modal(post),
                            size="1",
                            variant="soft",
                            color_scheme="blue",
                        ),
                        rx.button(
                            "Delete",
                            on_click=StreamPostsState.open_delete_dialog(post),
                            size="1",
                            variant="soft",
                            color_scheme="red",
                        ),
                        spacing="2",
                    ),
                ),
                justify="between",
                width="100%",
                align="center",
            ),
            spacing="2",
            align="start",
        ),
        size="2",
        width="100%",
    )


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
                    # Header with title and character count
                    rx.hstack(
                        rx.text("Create a new post", weight="medium", size="4"),
                        rx.spacer(),
                        rx.text(
                            f"{StreamPostsState.char_count} characters",
                            size="2",
                            color=rx.cond(
                                StreamPostsState.char_count > 400,
                                "red",
                                "gray"
                            ),
                        ),
                        width="100%",
                        align="center",
                    ),

                    # Text area
                    rx.text_area(
                        placeholder="Write your message...",
                        value=StreamPostsState.new_post_content,
                        on_change=StreamPostsState.set_new_post_content,
                        size="3",
                        rows="4",
                    ),

                    # Preview toggle
                    rx.hstack(
                        rx.switch(
                            checked=StreamPostsState.show_preview,
                            on_change=StreamPostsState.set_show_preview,
                        ),
                        rx.text(
                            "Show E Ink preview",
                            size="2",
                            color="gray",
                        ),
                        spacing="2",
                        align="center",
                    ),

                    # E Ink Preview (conditional)
                    rx.cond(
                        StreamPostsState.show_preview,
                        rx.vstack(
                            rx.text(
                                "Preview (800×480px, scaled to fit)",
                                size="2",
                                color="gray",
                                margin_bottom="2",
                            ),
                            # Debug: Show what theme is being used
                            rx.text(
                                f"Active theme: {StreamPostsState.stream_theme_name}",
                                size="1",
                                color=StreamPostsState.theme_text_color,
                                font_weight="bold",
                                margin_bottom="2",
                                padding="4px 8px",
                                border_radius="4px",
                                style={"background": StreamPostsState.theme_background},
                            ),
                            rx.box(
                                id="eink-preview-wrapper",
                                # Build preview manually with reactive Vars
                                rx.box(
                                    id="eink-preview-container",
                                    rx.vstack(
                                        id="eink-preview-vstack",
                                        # Header (3-column: stream name, author, date)
                                        rx.hstack(
                                            id="eink-preview-header",
                                            # Left: Stream name
                                            rx.text(
                                                StreamPostsState.stream_name,
                                                font_size="20px",
                                                font_weight="bold",
                                                color=StreamPostsState.theme_header_color,
                                                font_family="monospace",
                                                white_space="nowrap",
                                                overflow="hidden",
                                                text_overflow="ellipsis",
                                                flex="1",
                                            ),
                                            # Center: Author name
                                            rx.text(
                                                "You",
                                                font_size="20px",
                                                color=StreamPostsState.theme_text_color,
                                                font_family="monospace",
                                                text_align="center",
                                                white_space="nowrap",
                                                overflow="hidden",
                                                text_overflow="ellipsis",
                                                flex="1",
                                            ),
                                            # Right: Date (short format)
                                            rx.text(
                                                rx.moment(format="ddd. YYYY-MM-DD"),
                                                font_size="18px",
                                                color=StreamPostsState.theme_text_color,
                                                font_family="monospace",
                                                text_align="right",
                                                white_space="nowrap",
                                                flex="1",
                                            ),
                                            width="100%",
                                            height="60px",
                                            align="center",
                                            justify="between",
                                        ),
                                        # Divider
                                        rx.divider(
                                            id="eink-preview-divider",
                                            border_color=StreamPostsState.theme_divider_color,
                                            margin_y="0",
                                        ),
                                        # Content
                                        rx.box(
                                            id="eink-preview-content",
                                            rx.cond(
                                                StreamPostsState.new_post_content,
                                                rx.text(
                                                    StreamPostsState.new_post_content,
                                                    font_size="36px",
                                                    text_align="center",
                                                    color=StreamPostsState.theme_text_color,
                                                    font_family="monospace",
                                                    font_style="italic",
                                                    white_space="pre-wrap",
                                                    padding="10px",
                                                ),
                                                rx.text(
                                                    "Type a message to see preview...",
                                                    font_size="24px",
                                                    color="gray",
                                                    font_style="italic",
                                                    text_align="center",
                                                ),
                                            ),
                                            height="380px",
                                            display="flex",
                                            align_items="center",
                                            justify_content="center",
                                        ),
                                        spacing="0",
                                        width="100%",
                                        height="100%",
                                    ),
                                    width="800px",
                                    height="480px",
                                    padding="0 60px",
                                    border=f"4px solid {StreamPostsState.theme_text_color}",
                                    border_radius="8px",
                                    overflow="hidden",
                                    box_shadow="0 4px 6px rgba(0, 0, 0, 0.1)",
                                ),
                                # Scale down to 70% for desktop, 50% for mobile
                                transform="scale(0.7)",
                                transform_origin="top left",
                                # Combined style: theme background + responsive scaling
                                style={
                                    "background": StreamPostsState.theme_background,
                                    "@media (max-width: 768px)": {
                                        "transform": "scale(0.5)",
                                    }
                                },
                            ),
                            spacing="2",
                            width="100%",
                            align="start",
                        ),
                    ),

                    # Warning messages (conditional)
                    rx.cond(
                        StreamPostsState.preview_warnings.length() > 0,
                        rx.vstack(
                            rx.foreach(
                                StreamPostsState.preview_warnings,
                                lambda warning: rx.callout(
                                    warning,
                                    icon="triangle_alert",
                                    color_scheme="yellow",
                                    size="2",
                                ),
                            ),
                            spacing="2",
                            width="100%",
                        ),
                    ),

                    # Post button
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
                        post_card,
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

            # Edit Modal
            rx.dialog.root(
                rx.dialog.content(
                    rx.vstack(
                        rx.dialog.title("Edit Post"),
                        rx.dialog.description(
                            "Update your post content below."
                        ),
                        rx.text_area(
                            placeholder="Edit your message...",
                            value=StreamPostsState.edit_post_content,
                            on_change=StreamPostsState.set_edit_post_content,
                            size="3",
                            rows="6",
                        ),
                        rx.cond(
                            StreamPostsState.error_message,
                            rx.callout(
                                StreamPostsState.error_message,
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
                                    on_click=StreamPostsState.cancel_edit,
                                )
                            ),
                            rx.button(
                                rx.cond(
                                    StreamPostsState.is_saving_edit,
                                    rx.spinner(size="3"),
                                    "Save Changes",
                                ),
                                on_click=StreamPostsState.save_edit,
                                color_scheme="blue",
                                size="3",
                                disabled=StreamPostsState.is_saving_edit,
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
                open=StreamPostsState.is_edit_modal_open,
                on_open_change=StreamPostsState.set_is_edit_modal_open,
            ),

            # Delete Confirmation Dialog
            rx.alert_dialog.root(
                rx.alert_dialog.content(
                    rx.vstack(
                        rx.alert_dialog.title("Delete Post"),
                        rx.alert_dialog.description(
                            "Are you sure you want to delete this post? This action cannot be undone."
                        ),
                        rx.cond(
                            StreamPostsState.error_message,
                            rx.callout(
                                StreamPostsState.error_message,
                                icon="triangle_alert",
                                color_scheme="red",
                                size="1",
                            ),
                        ),
                        rx.hstack(
                            rx.alert_dialog.cancel(
                                rx.button(
                                    "Cancel",
                                    variant="soft",
                                    color_scheme="gray",
                                    size="3",
                                    on_click=StreamPostsState.cancel_delete,
                                )
                            ),
                            rx.alert_dialog.action(
                                rx.button(
                                    rx.cond(
                                        StreamPostsState.is_deleting,
                                        rx.spinner(size="3"),
                                        "Delete",
                                    ),
                                    on_click=StreamPostsState.confirm_delete,
                                    color_scheme="red",
                                    size="3",
                                    disabled=StreamPostsState.is_deleting,
                                )
                            ),
                            spacing="3",
                            justify="end",
                            width="100%",
                        ),
                        spacing="4",
                        width="100%",
                    ),
                    size="3",
                    max_width="450px",
                ),
                open=StreamPostsState.is_delete_confirm_open,
                on_open_change=StreamPostsState.set_is_delete_confirm_open,
            ),

            spacing="8",
            padding="4",
            width="100%",
        ),
        max_width="900px",
        on_mount=StreamPostsState.on_load,  # Method named on_load, triggered by on_mount
    )

    return authenticated_layout(content, current_page="streams")
