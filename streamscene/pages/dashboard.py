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

    stream_count: int = 0
    recent_posts_count: int = 0
    recent_streams: List[dict] = []
    error_message: str = ""

    def on_mount(self):
        """Load dashboard data when page loads."""
        # Check authentication
        if redirect := self.require_auth():
            return redirect

        self.load_dashboard_stats()

    def load_dashboard_stats(self):
        """Load statistics for the dashboard."""
        try:
            with get_db_session() as session:
                # Get stream count
                user_streams = stream_ops.get_user_streams(
                    session, UUID(self.user_id)
                )
                self.stream_count = len(user_streams)

                # Count recent posts across all streams
                total_posts = 0
                for stream in user_streams:
                    posts = stream_ops.get_stream_posts(session, stream.id, limit=10)
                    total_posts += len(posts)

                self.recent_posts_count = total_posts

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

        except Exception as e:
            self.error_message = f"Error loading dashboard: {str(e)}"


def dashboard() -> rx.Component:
    """Dashboard home page for authenticated users."""
    content = rx.container(
        rx.vstack(
            # Welcome message
            rx.card(
                rx.vstack(
                    rx.heading("Welcome to StreamScene!", size="6"),
                    rx.text(
                        "Your family message board with E Ink displays.",
                        color="gray",
                        size="3",
                    ),
                    spacing="2",
                ),
            ),
            # Error message
            rx.cond(
                DashboardState.error_message,
                rx.callout(
                    DashboardState.error_message,
                    icon="triangle_alert",
                    color_scheme="red",
                ),
            ),
            # Stats cards
            rx.grid(
                rx.card(
                    rx.vstack(
                        rx.heading("Streams", size="4", color="blue"),
                        rx.text(
                            DashboardState.stream_count,
                            size="8",
                            weight="bold",
                        ),
                        rx.text("Active streams", size="2", color="gray"),
                        spacing="2",
                        align="center",
                    ),
                ),
                rx.card(
                    rx.vstack(
                        rx.heading("Recent Posts", size="4", color="green"),
                        rx.text(
                            DashboardState.recent_posts_count,
                            size="8",
                            weight="bold",
                        ),
                        rx.text("Last 10 per stream", size="2", color="gray"),
                        spacing="2",
                        align="center",
                    ),
                ),
                columns="2",
                spacing="4",
                width="100%",
            ),
            # Your Streams List
            rx.card(
                rx.vstack(
                    rx.heading("Your Streams", size="5"),
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
                                            rx.button("View", size="1", variant="soft"),
                                            href="/streams",
                                        ),
                                        width="100%",
                                        align="center",
                                    ),
                                    size="1",
                                ),
                            ),
                            spacing="2",
                            width="100%",
                        ),
                        rx.text(
                            "No streams yet. Create your first stream below!",
                            color="gray",
                            size="2",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
            ),
            # Quick actions
            rx.card(
                rx.vstack(
                    rx.heading("Quick Actions", size="5"),
                    rx.hstack(
                        rx.link(
                            rx.button(
                                "Manage Streams",
                                size="3",
                                color_scheme="blue",
                            ),
                            href="/streams",
                        ),
                        rx.button(
                            "View Devices",
                            size="3",
                            variant="soft",
                            disabled=True,
                        ),
                        rx.button(
                            "Settings",
                            size="3",
                            variant="soft",
                            disabled=True,
                        ),
                        spacing="3",
                    ),
                    spacing="3",
                    width="100%",
                ),
            ),
            # Help text
            rx.card(
                rx.vstack(
                    rx.heading("Getting Started", size="4"),
                    rx.text("1. Create a stream for your family or friends", size="2"),
                    rx.text("2. Post messages to your streams", size="2"),
                    rx.text(
                        "3. Register your E Ink device (coming soon)", size="2"
                    ),
                    rx.text("4. Watch messages appear on your display!", size="2"),
                    spacing="2",
                    align="start",
                ),
                variant="surface",
            ),
            spacing="6",
            padding="4",
            width="100%",
        ),
        max_width="900px",
    )

    return authenticated_layout(content, current_page="dashboard")
