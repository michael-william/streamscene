"""Dashboard home page for authenticated users."""

from typing import List
from uuid import UUID

import reflex as rx

from streamscene.core.database import get_db_session
from streamscene.core import streams as stream_ops
from streamscene.components.layout import authenticated_layout
from .base_state import BaseState


class DashboardState(BaseState):
    """State for the dashboard page."""

    state_auto_setters = True  # Enable auto-generation of setter methods

    stream_count: int = 0
    recent_posts_count: int = 0
    recent_streams: List[dict] = []
    recent_activity: List[dict] = []  # Recent posts across all streams
    error_message: str = ""

    # Getting Started modal state
    is_getting_started_open: bool = False

    def on_mount(self):
        """Load dashboard data when page loads."""
        # Check authentication
        if redirect := self.require_auth():
            return redirect

        yield from self.load_dashboard_stats()

    def open_getting_started(self):
        """Open the Getting Started modal."""
        self.is_getting_started_open = True

    def close_getting_started(self):
        """Close the Getting Started modal."""
        self.is_getting_started_open = False

    def load_dashboard_stats(self):
        """Load statistics for the dashboard."""
        # Validate user_id before proceeding
        if not self.user_id:
            self.error_message = "Not authenticated - please log in"
            return

        # Convert user_id to UUID with error handling
        try:
            user_uuid = UUID(self.user_id)
        except (ValueError, AttributeError) as e:
            self.error_message = f"Invalid user session: {str(e)}"
            return

        try:
            with get_db_session() as session:
                # Get stream count
                user_streams = stream_ops.get_user_streams(session, user_uuid)
                self.stream_count = len(user_streams)

                # Collect all recent posts across streams for activity feed
                all_posts = []
                total_posts = 0
                for stream in user_streams:
                    posts = stream_ops.get_stream_posts(session, stream.id, limit=10)
                    total_posts += len(posts)

                    # Add stream context to each post
                    for post in posts:
                        all_posts.append({
                            "post": post,
                            "stream_name": stream.name,
                            "stream_id": str(stream.id),
                        })

                self.recent_posts_count = total_posts

                # Sort all posts by creation time (newest first) and take top 10
                all_posts.sort(key=lambda x: x["post"].created_at, reverse=True)
                self.recent_activity = [
                    {
                        "id": str(item["post"].id),
                        "text_content": item["post"].text_content,
                        "created_at": item["post"].created_at.strftime("%b %d, %Y at %I:%M %p"),
                        "author_name": (
                            item["post"].author.display_name or
                            item["post"].author.name or
                            item["post"].author.username or
                            item["post"].author.email or
                            "Unknown"
                        ) if item["post"].author else "Unknown",
                        "stream_name": item["stream_name"],
                        "stream_id": item["stream_id"],
                    }
                    for item in all_posts[:5]
                ]

                # Store recent streams for display (top 5)
                self.recent_streams = [
                    {
                        "id": str(stream.id),
                        "name": stream.name,
                        "description": stream.description or "",
                        "is_public": stream.is_public,
                    }
                    for stream in user_streams[:5]
                ]

                yield  # Force UI update

        except Exception as e:
            self.error_message = f"Error loading dashboard: {str(e)}"


def dashboard() -> rx.Component:
    """Dashboard home page for authenticated users."""
    content = rx.container(
        rx.vstack(
            # Compact Welcome Header with Info Button
            rx.hstack(
                rx.heading("Welcome to StreamScene", size="6", id="dashboard-welcome-heading"),
                rx.button(
                    rx.icon("info", size=20),
                    on_click=DashboardState.open_getting_started,
                    variant="ghost",
                    size="2",
                    color_scheme="gray",
                    id="dashboard-info-button",
                ),
                align="center",
                spacing="2",
                width="100%",
                id="dashboard-welcome-header",
            ),

            # Error message
            rx.cond(
                DashboardState.error_message,
                rx.callout(
                    DashboardState.error_message,
                    icon="triangle_alert",
                    color_scheme="red",
                    id="dashboard-error-message",
                ),
            ),

            # Main content area - horizontal on desktop, vertical on mobile
            rx.flex(
                # Your Streams List (Left Column)
                rx.card(
                    rx.vstack(
                        rx.heading("Your Streams", size="5", id="dashboard-streams-heading"),
                    rx.cond(
                        DashboardState.stream_count > 0,
                        rx.vstack(
                            rx.foreach(
                                DashboardState.recent_streams,
                                lambda stream: rx.card(
                                    rx.hstack(
                                        rx.vstack(
                                            rx.heading(stream["name"], size="3"),
                                            rx.text(
                                                stream["description"],
                                                size="1",
                                                color="gray",
                                            ),
                                            rx.badge(
                                                rx.cond(
                                                    stream["is_public"],
                                                    "Public",
                                                    "Private",
                                                ),
                                                color_scheme=rx.cond(
                                                    stream["is_public"], "green", "gray"
                                                ),
                                                size="1",
                                            ),
                                            align="start",
                                            spacing="1",
                                        ),
                                        rx.spacer(),
                                        rx.link(
                                            rx.button(
                                                "View Posts",
                                                size="1",
                                                variant="soft",
                                            ),
                                            href=f"/stream-posts?id={stream['id']}",
                                        ),
                                        width="100%",
                                        align="center",
                                    ),
                                    size="1",
                                ),
                            ),
                            rx.cond(
                                DashboardState.stream_count > 5,
                                rx.link(
                                    rx.button(
                                        "View All Streams",
                                        variant="soft",
                                        size="2",
                                    ),
                                    href="/streams",
                                ),
                            ),
                            spacing="2",
                            width="100%",
                        ),
                        rx.vstack(
                            rx.text(
                                "No streams yet.",
                                size="3",
                                weight="medium",
                                color="gray",
                            ),
                            rx.text(
                                "Create your first stream to start sharing!",
                                size="2",
                                color="gray",
                            ),
                            rx.link(
                                rx.button(
                                    "Create Stream",
                                    color_scheme="blue",
                                    size="2",
                                ),
                                href="/streams",
                            ),
                            spacing="2",
                            padding="4",
                            align="center",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
                    id="dashboard-streams-list",
                    flex="1",
                    min_width="300px",
                ),

                # Recent Activity Feed (Right Column)
                rx.card(
                    rx.vstack(
                        rx.heading("Recent Activity", size="5"),
                    rx.cond(
                        DashboardState.recent_activity.length() > 0,
                        rx.vstack(
                            rx.foreach(
                                DashboardState.recent_activity,
                                lambda activity: rx.card(
                                    rx.vstack(
                                        rx.text(
                                            activity["text_content"],
                                            size="2",
                                            line_height="1.5",
                                        ),
                                        rx.divider(margin_y="1"),
                                        rx.hstack(
                                            rx.hstack(
                                                rx.text(
                                                    activity["author_name"],
                                                    size="1",
                                                    weight="medium",
                                                    color="gray",
                                                ),
                                                rx.text("•", size="1", color="gray"),
                                                rx.link(
                                                    activity["stream_name"],
                                                    href=f"/stream-posts?id={activity['stream_id']}",
                                                    size="1",
                                                    color="blue",
                                                ),
                                                spacing="2",
                                                align="center",
                                            ),
                                            rx.text(
                                                activity["created_at"],
                                                size="1",
                                                color="gray",
                                            ),
                                            justify="between",
                                            width="100%",
                                            align="center",
                                        ),
                                        spacing="1",
                                        align="start",
                                    ),
                                    size="1",
                                    variant="surface",
                                ),
                            ),
                            rx.link(
                                rx.button(
                                    "View All Streams",
                                    variant="soft",
                                    size="2",
                                ),
                                href="/streams",
                            ),
                            spacing="2",
                            width="100%",
                        ),
                        rx.vstack(
                            rx.text(
                                "No activity yet.",
                                size="3",
                                weight="medium",
                                color="gray",
                            ),
                            rx.text(
                                "Create a stream and start posting to see activity here!",
                                size="2",
                                color="gray",
                                text_align="center",
                            ),
                            rx.link(
                                rx.button(
                                    "Create Your First Stream",
                                    color_scheme="blue",
                                    size="3",
                                ),
                                href="/streams",
                            ),
                            spacing="2",
                            padding="6",
                            align="center",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
                    id="dashboard-activity-feed",
                    flex="1",
                    min_width="300px",
                ),

                # Flex container settings
                direction="row",  # Horizontal on desktop, wraps to vertical on mobile
                spacing="5",
                width="100%",
                wrap="wrap",
            ),

            # Getting Started Modal
            rx.dialog.root(
                rx.dialog.content(
                    rx.vstack(
                        rx.dialog.title("Getting Started with StreamScene", id="dashboard-getting-started-title"),
                        rx.dialog.description(
                            "Follow these steps to set up your family message board:"
                        ),
                        rx.vstack(
                            rx.text("1. Create a stream for your family or friends", size="2"),
                            rx.text("2. Post messages to your streams", size="2"),
                            rx.text("3. Register your E Ink device (coming soon)", size="2"),
                            rx.text("4. Watch messages appear on your display!", size="2"),
                            spacing="2",
                            align="start",
                            width="100%",
                        ),
                        rx.hstack(
                            rx.dialog.close(
                                rx.button(
                                    "Got it!",
                                    color_scheme="blue",
                                    size="3",
                                )
                            ),
                            spacing="3",
                            justify="end",
                            width="100%",
                        ),
                        spacing="4",
                        width="100%",
                    ),
                    id="dashboard-getting-started-modal",
                    size="3",
                    max_width="450px",
                ),
                open=DashboardState.is_getting_started_open,
                on_open_change=DashboardState.set_is_getting_started_open,
            ),

            spacing="5",
            width="100%",
            padding="4",
            height="calc(100vh - 30px)",
            overflow_y="auto",
            id="dashboard-main-stack",
        ),
        max_width="1400px",  # Wider to accommodate horizontal layout
        on_mount=DashboardState.on_mount,  # Connect lifecycle handler
        id="dashboard-container",
    )

    return authenticated_layout(content, current_page="dashboard")
