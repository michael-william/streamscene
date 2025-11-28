"""Admin page for managing background images."""

import shutil
from pathlib import Path
from typing import List
from uuid import UUID

import reflex as rx
from sqlalchemy import func

from streamscene.core.database import get_db_session
from streamscene.core.models import BackgroundImage
from streamscene.core.backgrounds import (
    get_all_backgrounds,
    create_background,
    update_background,
    delete_background,
    seed_default_backgrounds,
    BACKGROUNDS_DIR,
)
from streamscene.components.layout import authenticated_layout
from .base_state import BaseState


class BackgroundsAdminState(BaseState):
    """State for background image management."""

    state_auto_setters = True

    # Data
    backgrounds: List[dict] = []

    # Loading states
    is_loading: bool = True
    is_saving: bool = False
    is_deleting: bool = False

    # Messages
    error_message: str = ""
    success_message: str = ""

    # Add Modal
    is_add_modal_open: bool = False
    js_uploaded_filename: str = ""
    js_uploaded_url: str = ""
    add_display_name: str = ""
    add_is_active: bool = True

    # Edit Modal
    is_edit_modal_open: bool = False
    edit_background_id: str = ""
    edit_filename: str = ""
    edit_display_name: str = ""
    edit_sort_order: int = 0
    edit_is_active: bool = True

    # Delete Dialog
    is_delete_dialog_open: bool = False
    delete_background_id: str = ""
    delete_background_name: str = ""

    def on_mount(self):
        """Load backgrounds when page loads."""
        print("[BACKGROUNDS] on_mount() called")

        if not self.user_id:
            print("[BACKGROUNDS] No user_id, redirecting to /")
            return rx.redirect("/")

        print(f"[BACKGROUNDS] Loading backgrounds for user {self.user_id}")
        self.load_backgrounds()

    def load_backgrounds(self):
        """Load all backgrounds (including inactive)."""
        print("[BACKGROUNDS] load_backgrounds() called")

        self.is_loading = True
        self.error_message = ""

        try:
            with get_db_session() as session:
                bgs = get_all_backgrounds(session, active_only=False)
                print(f"[BACKGROUNDS] Found {len(bgs)} backgrounds")

                self.backgrounds = [
                    {
                        "id": str(bg.id),
                        "filename": bg.filename,
                        "display_name": bg.display_name,
                        "is_active": bg.is_active,
                        "sort_order": bg.sort_order,
                    }
                    for bg in bgs
                ]

        except Exception as e:
            print(f"[BACKGROUNDS] Error loading backgrounds: {e}")
            self.error_message = f"Error loading backgrounds: {str(e)}"

        finally:
            self.is_loading = False

    # === Add Modal ===

    def open_add_modal(self):
        """Open the add background modal."""
        print("[BACKGROUNDS] Opening add modal")
        self.is_add_modal_open = True
        self.js_uploaded_filename = ""
        self.js_uploaded_url = ""
        self.add_display_name = ""
        self.add_is_active = True
        self.error_message = ""

    def close_add_modal(self):
        """Close the add background modal."""
        self.is_add_modal_open = False
        self.js_uploaded_filename = ""
        self.js_uploaded_url = ""
        self.add_display_name = ""
        self.add_is_active = True

    def set_js_uploaded_url(self, url: str):
        """Called when JS upload completes (via hidden input sync)."""
        self.js_uploaded_url = url
        print(f"[BACKGROUNDS] Upload URL set: {url}")

    def save_new_background(self):
        """Create new background from uploaded file."""
        print(f"[BACKGROUNDS] Saving new background: {self.js_uploaded_filename}")

        if not self.js_uploaded_filename:
            self.error_message = "Please upload an image first"
            return

        if not self.add_display_name or not self.add_display_name.strip():
            self.error_message = "Display name is required"
            return

        self.is_saving = True
        self.error_message = ""
        self.success_message = ""
        yield

        try:
            # Copy file from uploads to backgrounds directory
            source = Path(f"/root/streamscene/.web/build/client/uploads/{self.js_uploaded_filename}")
            dest = BACKGROUNDS_DIR / self.js_uploaded_filename

            if not source.exists():
                self.error_message = "Uploaded file not found"
                self.is_saving = False
                return

            # Ensure backgrounds directory exists
            BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)

            # Copy to backgrounds directory
            shutil.copy(source, dest)
            print(f"[BACKGROUNDS] Copied {source} -> {dest}")

            # Also copy to public for immediate serving
            public_dest = Path(f"/root/streamscene/.web/public/backgrounds/{self.js_uploaded_filename}")
            public_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source, public_dest)
            print(f"[BACKGROUNDS] Copied to public: {public_dest}")

            # Create DB record
            with get_db_session() as session:
                # Get next sort order
                max_order = session.query(func.max(BackgroundImage.sort_order)).scalar() or 0

                create_background(
                    session,
                    filename=self.js_uploaded_filename,
                    display_name=self.add_display_name.strip(),
                    is_active=self.add_is_active,
                    sort_order=max_order + 1
                )

            # Cleanup temp file
            source.unlink(missing_ok=True)

            self.success_message = "Background added successfully!"
            self.close_add_modal()
            print("[BACKGROUNDS] Background created successfully")

            # Reload list
            self.load_backgrounds()

        except ValueError as e:
            print(f"[BACKGROUNDS] Validation error: {e}")
            self.error_message = str(e)
        except Exception as e:
            print(f"[BACKGROUNDS] Error saving background: {e}")
            self.error_message = f"Error: {str(e)}"
        finally:
            self.is_saving = False

    # === Edit Modal ===

    def open_edit_modal(self, background_id: str):
        """Open the edit modal for a background."""
        print(f"[BACKGROUNDS] Opening edit modal for {background_id}")

        bg = next((b for b in self.backgrounds if b["id"] == background_id), None)
        if not bg:
            self.error_message = "Background not found"
            return

        self.edit_background_id = background_id
        self.edit_filename = bg["filename"]
        self.edit_display_name = bg["display_name"]
        self.edit_sort_order = bg["sort_order"]
        self.edit_is_active = bg["is_active"]
        self.is_edit_modal_open = True
        self.error_message = ""

    def close_edit_modal(self):
        """Close the edit modal."""
        self.is_edit_modal_open = False
        self.edit_background_id = ""
        self.edit_filename = ""
        self.edit_display_name = ""
        self.edit_sort_order = 0
        self.edit_is_active = True

    def set_edit_sort_order_from_input(self, value: str):
        """Set sort order from input, handling string conversion."""
        try:
            int_value = int(value) if value else 0
            self.edit_sort_order = max(0, int_value)
        except (ValueError, TypeError):
            self.edit_sort_order = 0

    def save_edit_background(self):
        """Update existing background."""
        print(f"[BACKGROUNDS] Saving edit for {self.edit_background_id}")

        if not self.edit_background_id:
            self.error_message = "No background selected"
            return

        if not self.edit_display_name or not self.edit_display_name.strip():
            self.error_message = "Display name is required"
            return

        self.is_saving = True
        self.error_message = ""
        self.success_message = ""
        yield

        try:
            background_uuid = UUID(self.edit_background_id)

            with get_db_session() as session:
                updated = update_background(
                    session,
                    background_id=background_uuid,
                    display_name=self.edit_display_name.strip(),
                    is_active=self.edit_is_active,
                    sort_order=self.edit_sort_order,
                )

                if not updated:
                    self.error_message = "Background not found"
                    self.is_saving = False
                    return

            self.success_message = "Background updated successfully!"
            self.close_edit_modal()
            print("[BACKGROUNDS] Background updated successfully")

            # Reload list
            self.load_backgrounds()

        except ValueError as e:
            print(f"[BACKGROUNDS] Validation error: {e}")
            self.error_message = str(e)
        except Exception as e:
            print(f"[BACKGROUNDS] Error updating background: {e}")
            self.error_message = f"Error: {str(e)}"
        finally:
            self.is_saving = False

    # === Toggle Active ===

    def toggle_active(self, background_id: str):
        """Quick toggle active status."""
        print(f"[BACKGROUNDS] Toggling active for {background_id}")

        bg = next((b for b in self.backgrounds if b["id"] == background_id), None)
        if not bg:
            return

        try:
            with get_db_session() as session:
                update_background(
                    session,
                    background_id=UUID(background_id),
                    is_active=not bg["is_active"]
                )

            # Reload list
            self.load_backgrounds()

        except Exception as e:
            print(f"[BACKGROUNDS] Error toggling active: {e}")
            self.error_message = f"Error: {str(e)}"

    # === Delete Dialog ===

    def open_delete_dialog(self, background_id: str):
        """Open the delete confirmation dialog."""
        print(f"[BACKGROUNDS] Opening delete dialog for {background_id}")

        bg = next((b for b in self.backgrounds if b["id"] == background_id), None)
        if not bg:
            return

        self.delete_background_id = background_id
        self.delete_background_name = bg["display_name"]
        self.is_delete_dialog_open = True
        self.error_message = ""

    def close_delete_dialog(self):
        """Close the delete confirmation dialog."""
        self.is_delete_dialog_open = False
        self.delete_background_id = ""
        self.delete_background_name = ""

    def confirm_delete(self):
        """Delete background (DB record only, keeps file)."""
        print(f"[BACKGROUNDS] Deleting {self.delete_background_id}")

        if not self.delete_background_id:
            return

        self.is_deleting = True
        self.error_message = ""
        self.success_message = ""
        yield

        try:
            deleted = delete_background(
                get_db_session().__enter__(),
                UUID(self.delete_background_id)
            )

            if not deleted:
                self.error_message = "Background not found"
                self.is_deleting = False
                return

            self.success_message = f"Background '{self.delete_background_name}' deleted"
            self.close_delete_dialog()
            print("[BACKGROUNDS] Background deleted successfully")

            # Reload list
            self.load_backgrounds()

        except Exception as e:
            print(f"[BACKGROUNDS] Error deleting background: {e}")
            self.error_message = f"Error: {str(e)}"
        finally:
            self.is_deleting = False

    # === Reseed ===

    def reseed_from_filesystem(self):
        """Scan filesystem and add missing backgrounds."""
        print("[BACKGROUNDS] Reseeding from filesystem")

        self.error_message = ""
        self.success_message = ""

        try:
            with get_db_session() as session:
                added_count = seed_default_backgrounds(session)

            if added_count > 0:
                self.success_message = f"Added {added_count} new background(s) from filesystem"
                self.load_backgrounds()
            else:
                self.success_message = "No new backgrounds found"

            print(f"[BACKGROUNDS] Reseed complete, added {added_count}")

        except Exception as e:
            print(f"[BACKGROUNDS] Error reseeding: {e}")
            self.error_message = f"Error: {str(e)}"


# === UI Components ===

def background_card(bg: dict) -> rx.Component:
    """Render a single background card."""
    return rx.card(
        rx.vstack(
            # Preview image
            rx.image(
                src=f"/backgrounds/{bg['filename']}",
                width="100%",
                height="100px",
                object_fit="cover",
                border_radius="4px",
            ),
            # Display name
            rx.text(bg["display_name"], weight="bold", size="2"),
            # Status badge
            rx.cond(
                bg["is_active"],
                rx.badge("Active", color_scheme="green", size="1"),
                rx.badge("Inactive", color_scheme="gray", size="1"),
            ),
            # Sort order
            rx.text(f"Order: {bg['sort_order']}", size="1", color="gray"),
            # Action buttons
            rx.hstack(
                rx.button(
                    rx.icon("pencil", size=14),
                    size="1",
                    variant="soft",
                    on_click=lambda: BackgroundsAdminState.open_edit_modal(bg["id"]),
                ),
                rx.button(
                    rx.cond(bg["is_active"], rx.icon("eye_off", size=14), rx.icon("eye", size=14)),
                    size="1",
                    variant="soft",
                    on_click=lambda: BackgroundsAdminState.toggle_active(bg["id"]),
                ),
                rx.button(
                    rx.icon("trash_2", size=14),
                    size="1",
                    variant="soft",
                    color_scheme="red",
                    on_click=lambda: BackgroundsAdminState.open_delete_dialog(bg["id"]),
                ),
                spacing="1",
            ),
            spacing="2",
            align="center",
            padding="2",
        ),
    )


def background_upload_area() -> rx.Component:
    """Upload area for new background images."""
    return rx.fragment(
        # Hidden file input (native HTML)
        rx.el.input(
            type="file",
            id="bg-upload-input",
            accept="image/png",
            style={"display": "none"},
        ),

        # Hidden inputs for JavaScript to set (bound to state)
        rx.input(
            type="text",
            id="bg-uploaded-filename",
            value=BackgroundsAdminState.js_uploaded_filename,
            on_change=BackgroundsAdminState.set_js_uploaded_filename,
            style={"position": "absolute", "left": "-9999px"},
        ),
        rx.input(
            type="text",
            id="bg-uploaded-url",
            value=BackgroundsAdminState.js_uploaded_url,
            on_change=BackgroundsAdminState.set_js_uploaded_url,
            style={"position": "absolute", "left": "-9999px"},
        ),

        # Upload area (shown when no image uploaded)
        rx.cond(
            BackgroundsAdminState.js_uploaded_url == "",
            rx.html("""
                <div id="bg-upload-area" style="width: 100%;">
                    <div style="border: 2px dashed var(--gray-6); padding: 2em; border-radius: 8px; width: 100%; text-align: center;">
                        <button
                            type="button"
                            onclick="document.getElementById('bg-upload-input').click()"
                            style="background: var(--accent-9); color: white; border: none; padding: 0.5em 1em; border-radius: 6px; cursor: pointer; font-size: 1em; margin-bottom: 0.5em;"
                        >
                            Select PNG Image
                        </button>
                        <p style="color: var(--gray-11); font-size: 0.875em; margin: 0.5em 0;">800x480 recommended for E Ink display</p>
                        <div id="bg-loading" style="display: none; margin-top: 1em;">
                            <div style="border: 3px solid var(--gray-6); border-top: 3px solid var(--accent-9); border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; margin: 0 auto;"></div>
                        </div>
                        <div id="bg-error-message" style="display: none; color: var(--red-11); font-size: 0.875em; margin-top: 1em;"></div>
                    </div>
                </div>
                <style>
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                </style>
            """),
            # Preview when uploaded
            rx.vstack(
                rx.image(
                    src=BackgroundsAdminState.js_uploaded_url,
                    width="100%",
                    max_width="300px",
                    border_radius="8px",
                    border="1px solid var(--gray-6)",
                    object_fit="contain",
                ),
                rx.button(
                    "Remove",
                    on_click=lambda: [
                        BackgroundsAdminState.set_js_uploaded_filename(""),
                        BackgroundsAdminState.set_js_uploaded_url(""),
                    ],
                    color_scheme="red",
                    size="1",
                    variant="soft",
                ),
                spacing="2",
                align="center",
            ),
        ),

        # JavaScript upload handler
        rx.script("""
            (function() {
                const fileInput = document.getElementById('bg-upload-input');
                const errorDiv = document.getElementById('bg-error-message');
                const loadingDiv = document.getElementById('bg-loading');

                if (!fileInput || fileInput.hasAttribute('data-bg-listener-attached')) return;
                fileInput.setAttribute('data-bg-listener-attached', 'true');

                fileInput.addEventListener('change', async (e) => {
                    const file = e.target.files[0];
                    if (!file) return;

                    console.log('[BG UPLOAD] File selected:', file.name);

                    // Show loading state
                    if (loadingDiv) loadingDiv.style.display = 'block';
                    if (errorDiv) errorDiv.style.display = 'none';

                    try {
                        const formData = new FormData();
                        formData.append('file', file);

                        const response = await fetch('/api/custom-upload', {
                            method: 'POST',
                            body: formData
                        });

                        const data = await response.json();
                        console.log('[BG UPLOAD] Upload complete:', data);

                        if (data.success) {
                            const filenameInput = document.getElementById('bg-uploaded-filename');
                            const urlInput = document.getElementById('bg-uploaded-url');

                            if (filenameInput && urlInput) {
                                console.log('[BG UPLOAD] Setting filename:', data.filename);

                                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                nativeInputValueSetter.call(filenameInput, data.filename);
                                filenameInput.dispatchEvent(new Event('input', { bubbles: true }));

                                setTimeout(() => {
                                    console.log('[BG UPLOAD] Setting URL:', data.url);
                                    nativeInputValueSetter.call(urlInput, data.url);
                                    urlInput.dispatchEvent(new Event('input', { bubbles: true }));
                                    console.log('[BG UPLOAD] Both values set');
                                }, 50);
                            } else {
                                console.error('[BG UPLOAD] Hidden inputs not found!');
                            }

                            if (errorDiv) errorDiv.style.display = 'none';
                        } else {
                            if (errorDiv) {
                                errorDiv.textContent = `Upload failed: ${data.error || 'Unknown error'}`;
                                errorDiv.style.display = 'block';
                            }
                        }

                        fileInput.value = '';

                    } catch (error) {
                        console.error('[BG UPLOAD] Error:', error);
                        if (errorDiv) {
                            errorDiv.textContent = `Upload failed: ${error.message}`;
                            errorDiv.style.display = 'block';
                        }
                    } finally {
                        if (loadingDiv) loadingDiv.style.display = 'none';
                    }
                });
            })();
        """),
    )


def add_background_modal() -> rx.Component:
    """Modal dialog for adding a new background."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Add Background"),
                rx.dialog.description(
                    "Upload a new background image for Meme It posts.",
                    size="2",
                ),

                # Upload area
                background_upload_area(),

                # Display name input
                rx.vstack(
                    rx.text("Display Name", weight="bold", size="2"),
                    rx.input(
                        placeholder="e.g., Blue Gradient",
                        value=BackgroundsAdminState.add_display_name,
                        on_change=BackgroundsAdminState.set_add_display_name,
                        size="3",
                        width="100%",
                    ),
                    spacing="2",
                    width="100%",
                    align="start",
                ),

                # Active checkbox
                rx.hstack(
                    rx.checkbox(
                        checked=BackgroundsAdminState.add_is_active,
                        on_change=BackgroundsAdminState.set_add_is_active,
                    ),
                    rx.text("Make available immediately", size="2"),
                    spacing="2",
                    align="center",
                ),

                # Error message
                rx.cond(
                    BackgroundsAdminState.error_message,
                    rx.callout(
                        BackgroundsAdminState.error_message,
                        icon="triangle_alert",
                        color_scheme="red",
                        size="2",
                    ),
                ),

                # Actions
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            size="3",
                            on_click=BackgroundsAdminState.close_add_modal,
                        ),
                    ),
                    rx.button(
                        rx.cond(
                            BackgroundsAdminState.is_saving,
                            rx.hstack(
                                rx.spinner(size="1"),
                                rx.text("Saving..."),
                                spacing="2",
                            ),
                            rx.text("Save Background"),
                        ),
                        on_click=BackgroundsAdminState.save_new_background,
                        disabled=BackgroundsAdminState.is_saving,
                        size="3",
                    ),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),

                spacing="4",
                width="100%",
            ),
            max_width=["95vw", "500px"],
        ),
        open=BackgroundsAdminState.is_add_modal_open,
        on_open_change=BackgroundsAdminState.set_is_add_modal_open,
    )


def edit_background_modal() -> rx.Component:
    """Modal dialog for editing a background."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Edit Background"),

                # Filename (read-only)
                rx.vstack(
                    rx.text("Filename", weight="bold", size="2"),
                    rx.code(BackgroundsAdminState.edit_filename, size="2"),
                    spacing="1",
                    width="100%",
                    align="start",
                ),

                # Display name input
                rx.vstack(
                    rx.text("Display Name", weight="bold", size="2"),
                    rx.input(
                        value=BackgroundsAdminState.edit_display_name,
                        on_change=BackgroundsAdminState.set_edit_display_name,
                        size="3",
                        width="100%",
                    ),
                    spacing="2",
                    width="100%",
                    align="start",
                ),

                # Sort order input
                rx.vstack(
                    rx.text("Sort Order", weight="bold", size="2"),
                    rx.input(
                        type="number",
                        value=BackgroundsAdminState.edit_sort_order.to(str),
                        on_change=BackgroundsAdminState.set_edit_sort_order_from_input,
                        min="0",
                        size="3",
                        width="100px",
                    ),
                    rx.text("Lower numbers appear first", size="1", color="gray"),
                    spacing="2",
                    width="100%",
                    align="start",
                ),

                # Active checkbox
                rx.hstack(
                    rx.checkbox(
                        checked=BackgroundsAdminState.edit_is_active,
                        on_change=BackgroundsAdminState.set_edit_is_active,
                    ),
                    rx.text("Active (available for use)", size="2"),
                    spacing="2",
                    align="center",
                ),

                # Error message
                rx.cond(
                    BackgroundsAdminState.error_message,
                    rx.callout(
                        BackgroundsAdminState.error_message,
                        icon="triangle_alert",
                        color_scheme="red",
                        size="2",
                    ),
                ),

                # Actions
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            size="3",
                            on_click=BackgroundsAdminState.close_edit_modal,
                        ),
                    ),
                    rx.button(
                        rx.cond(
                            BackgroundsAdminState.is_saving,
                            rx.hstack(
                                rx.spinner(size="1"),
                                rx.text("Saving..."),
                                spacing="2",
                            ),
                            rx.text("Save Changes"),
                        ),
                        on_click=BackgroundsAdminState.save_edit_background,
                        disabled=BackgroundsAdminState.is_saving,
                        size="3",
                    ),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),

                spacing="4",
                width="100%",
            ),
            max_width=["95vw", "450px"],
        ),
        open=BackgroundsAdminState.is_edit_modal_open,
        on_open_change=BackgroundsAdminState.set_is_edit_modal_open,
    )


def delete_confirmation_dialog() -> rx.Component:
    """Confirmation dialog for deleting a background."""
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.vstack(
                rx.alert_dialog.title("Delete Background?"),
                rx.alert_dialog.description(
                    rx.vstack(
                        rx.text(
                            f"Are you sure you want to delete ",
                            rx.text(BackgroundsAdminState.delete_background_name, weight="bold"),
                            "?",
                        ),
                        rx.text(
                            "The image file will be kept on disk for existing posts.",
                            size="2",
                            color="gray",
                        ),
                        spacing="2",
                    ),
                ),

                rx.hstack(
                    rx.alert_dialog.cancel(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            size="3",
                            on_click=BackgroundsAdminState.close_delete_dialog,
                        ),
                    ),
                    rx.alert_dialog.action(
                        rx.button(
                            rx.cond(
                                BackgroundsAdminState.is_deleting,
                                rx.hstack(
                                    rx.spinner(size="1"),
                                    rx.text("Deleting..."),
                                    spacing="2",
                                ),
                                rx.text("Delete"),
                            ),
                            on_click=BackgroundsAdminState.confirm_delete,
                            disabled=BackgroundsAdminState.is_deleting,
                            color_scheme="red",
                            size="3",
                        ),
                    ),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),

                spacing="4",
                width="100%",
            ),
            max_width=["95vw", "400px"],
        ),
        open=BackgroundsAdminState.is_delete_dialog_open,
        on_open_change=BackgroundsAdminState.set_is_delete_dialog_open,
    )


def backgrounds_list() -> rx.Component:
    """Render the backgrounds grid and controls."""
    return rx.vstack(
        # Header
        rx.hstack(
            rx.heading("Background Images", size="8"),
            rx.spacer(),
            rx.button(
                rx.icon("plus", size=16),
                "Add Background",
                on_click=BackgroundsAdminState.open_add_modal,
                size="2",
            ),
            justify="between",
            width="100%",
        ),

        rx.text(
            "Manage background images for Meme It posts.",
            size="3",
            color="gray",
        ),

        # Action buttons
        rx.hstack(
            rx.button(
                rx.icon("refresh_cw", size=16),
                "Refresh",
                on_click=BackgroundsAdminState.load_backgrounds,
                variant="soft",
                size="2",
            ),
            rx.button(
                rx.icon("folder_sync", size=16),
                "Reseed from Filesystem",
                on_click=BackgroundsAdminState.reseed_from_filesystem,
                variant="soft",
                size="2",
            ),
            spacing="2",
        ),

        rx.divider(),

        # Success message
        rx.cond(
            BackgroundsAdminState.success_message,
            rx.callout(
                BackgroundsAdminState.success_message,
                icon="check",
                color_scheme="green",
                size="2",
            ),
        ),

        # Error message
        rx.cond(
            BackgroundsAdminState.error_message,
            rx.callout(
                BackgroundsAdminState.error_message,
                icon="triangle_alert",
                color_scheme="red",
                size="2",
            ),
        ),

        # Loading or Grid
        rx.cond(
            BackgroundsAdminState.is_loading,
            rx.vstack(
                rx.spinner(size="3"),
                rx.text("Loading backgrounds...", size="3"),
                spacing="4",
                align="center",
                padding="8",
            ),
            rx.cond(
                BackgroundsAdminState.backgrounds.length() > 0,
                rx.grid(
                    rx.foreach(
                        BackgroundsAdminState.backgrounds,
                        background_card,
                    ),
                    columns=rx.breakpoints(initial="2", sm="3", md="4", lg="5", xl="6"),
                    spacing="4",
                    width="100%",
                ),
                # Empty state
                rx.vstack(
                    rx.icon("image_off", size=64, color="gray"),
                    rx.heading("No Backgrounds", size="6"),
                    rx.text(
                        "No background images found. Add some or reseed from filesystem.",
                        size="3",
                        color="gray",
                    ),
                    spacing="4",
                    align="center",
                    padding="8",
                ),
            ),
        ),

        spacing="6",
        width="100%",
        align="start",
    )


def admin_backgrounds_page() -> rx.Component:
    """Admin backgrounds management page."""
    content = rx.container(
        rx.vstack(
            backgrounds_list(),
            add_background_modal(),
            edit_background_modal(),
            delete_confirmation_dialog(),
            spacing="0",
            width="100%",
        ),
        max_width="1200px",
        padding_x=["4", "6", "8"],
        padding_y="4",
        on_mount=BackgroundsAdminState.on_mount,
    )

    return authenticated_layout(content, current_page="admin/backgrounds")


# Export for app registration
admin_backgrounds = admin_backgrounds_page
