"""Responsive sidebar navigation component."""

import reflex as rx
from streamscene.pages.base_state import BaseState


class SidebarState(BaseState):
    """State for sidebar navigation."""

    is_mobile_menu_open: bool = False

    def toggle_mobile_menu(self):
        """Toggle mobile menu drawer."""
        self.is_mobile_menu_open = not self.is_mobile_menu_open

    def close_mobile_menu(self):
        """Close mobile menu drawer."""
        self.is_mobile_menu_open = False


def nav_link(text: str, href: str, current_page: str, icon: str = "") -> rx.Component:
    """Navigation link with active state highlighting."""
    is_active = current_page == href.strip("/")

    return rx.link(
        rx.hstack(
            rx.cond(
                icon != "",
                rx.icon(icon, size=20),
                rx.box(),
            ),
            rx.text(
                text,
                size="3",
                weight="medium" if is_active else "regular",
            ),
            spacing="3",
            align="center",
            width="100%",
            padding_x="4",
            padding_y="3",
            border_radius="md",
            bg=rx.cond(
                is_active,
                "var(--accent-3)",
                "transparent",
            ),
            _hover={"bg": "var(--accent-2)"},
        ),
        href=href,
        text_decoration="none",
        color="inherit",
        on_click=SidebarState.close_mobile_menu,
    )


def sidebar_content(current_page: str = "") -> rx.Component:
    """Sidebar navigation content (used in both desktop and mobile)."""
    return rx.vstack(
        # Logo/Brand
        rx.heading("StreamScene", size="7", padding_bottom="4"),
        rx.divider(),
        # Navigation Links
        rx.vstack(
            nav_link("Dashboard", "/dashboard", current_page, "layout_dashboard"),
            nav_link("Streams", "/streams", current_page, "radio"),
            nav_link("Profile", "/profile", current_page, "user"),
            # Future links can be added here:
            # nav_link("Devices", "/devices", current_page, "tablet"),
            # nav_link("Settings", "/settings", current_page, "settings"),
            spacing="1",
            width="100%",
        ),
        rx.spacer(),
        # User section
        rx.divider(),
        rx.vstack(
            # Theme toggle
            rx.hstack(
                rx.icon("palette", size=18),
                rx.text("Theme", size="3"),
                rx.spacer(),
                rx.color_mode.button(
                    size="2",
                ),
                spacing="2",
                align="center",
                width="100%",
                padding_x="4",
                padding_y="3",
            ),
            # Logout button
            rx.button(
                rx.hstack(
                    rx.icon("log_out", size=18),
                    rx.text("Logout", size="3"),
                    spacing="2",
                ),
                on_click=SidebarState.logout,
                variant="ghost",
                width="100%",
                justify="start",
            ),
            spacing="2",
            width="100%",
        ),
        height="100vh",
        width="250px",
        class_name="rt-r-p-2",
        bg="var(--gray-2)",
        border_right="1px solid var(--gray-5)",
        spacing="4",
    )


def desktop_sidebar(current_page: str = "") -> rx.Component:
    """Fixed sidebar for desktop/tablet (≥768px)."""
    return rx.box(
        sidebar_content(current_page),
        display=["none", "none", "block"],  # Hidden on mobile, visible on tablet+
        position="fixed",
        left="0",
        top="0",
        height="100vh",
        z_index="10",
    )


def mobile_header(current_page: str = "") -> rx.Component:
    """Mobile header with hamburger menu (<768px)."""
    return rx.hstack(
        rx.icon_button(
            rx.icon("menu", size=24),
            on_click=SidebarState.toggle_mobile_menu,
            variant="ghost",
            size="3",
        ),
        rx.heading("StreamScene", size="6"),
        rx.spacer(),
        spacing="3",
        width="100%",
        padding="3",
        bg="var(--gray-2)",
        border_bottom="1px solid var(--gray-5)",
        display=["flex", "flex", "none"],  # Visible on mobile, hidden on tablet+
        position="sticky",
        top="0",
        z_index="20",
    )


def mobile_drawer(current_page: str = "") -> rx.Component:
    """Mobile navigation drawer overlay."""
    return rx.drawer.root(
        rx.drawer.overlay(z_index="30"),
        rx.drawer.portal(
            rx.drawer.content(
                sidebar_content(current_page),
                padding="0",
                side="left",
                width="250px",
            ),
        ),
        open=SidebarState.is_mobile_menu_open,
        on_open_change=SidebarState.set_is_mobile_menu_open,
    )


def sidebar(current_page: str = "") -> rx.Component:
    """Responsive sidebar navigation (desktop) + mobile drawer."""
    return rx.fragment(
        desktop_sidebar(current_page),
        mobile_header(current_page),
        mobile_drawer(current_page),
    )
