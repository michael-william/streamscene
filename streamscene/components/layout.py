"""Authenticated page layout wrapper with responsive sidebar."""

import reflex as rx
from .sidebar import sidebar


def authenticated_layout(content: rx.Component, current_page: str = "") -> rx.Component:
    """
    Layout wrapper for authenticated pages with responsive sidebar.

    Args:
        content: The main page content to display
        current_page: Current page identifier for active nav highlighting
                     (e.g., "dashboard", "streams")

    Returns:
        Complete page layout with sidebar navigation
    """
    return rx.box(
        # Sidebar navigation (desktop + mobile)
        sidebar(current_page),
        # Main content area
        rx.box(
            content,
            # Responsive margin to account for fixed sidebar
            margin_left=["0", "0", "250px"],  # 0 on mobile, 250px on tablet+
            # Responsive padding-top for mobile header
            padding_top=["60px", "60px", "0"],  # Account for sticky mobile header
            min_height="100vh",
            # Responsive width to prevent horizontal scroll on desktop
            width=["100%", "100%", "calc(100% - 250px)"],  # Account for sidebar on desktop
        ),
    )
