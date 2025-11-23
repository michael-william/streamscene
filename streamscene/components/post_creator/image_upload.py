"""Image upload component with drag-drop support."""

import reflex as rx
from typing import Callable


def image_upload(
    on_upload: Callable,
    on_clear: Callable,
    preview_url: rx.Var[str],
    is_uploading: rx.Var[bool],
    has_image: rx.Var[bool]
) -> rx.Component:
    """
    Image upload component with drag-drop and file picker.

    Features:
    - Drag & drop zone
    - File picker (click to browse)
    - File validation (type, size)
    - Image preview
    - Clear/replace functionality

    Args:
        on_upload: Callback for file upload
        on_clear: Callback to clear uploaded image
        preview_url: Current image preview data URL
        is_uploading: Loading state during upload
        has_image: Whether image has been uploaded

    Returns:
        Reflex component with upload UI
    """
    return rx.vstack(
        # Label
        rx.text(
            "Upload Image",
            size="3",
            weight="medium",
        ),

        # Upload zone or preview
        rx.cond(
            has_image,
            # Preview state
            rx.vstack(
                # Image preview
                rx.image(
                    src=preview_url,
                    max_width="100%",
                    max_height=rx.breakpoints(initial="200px", md="300px"),
                    border_radius="8px",
                    border="2px solid var(--gray-6)",
                    object_fit="contain",
                ),

                # Action buttons
                rx.hstack(
                    rx.upload(
                        rx.button(
                            rx.hstack(
                                rx.icon("refresh-cw", size=16),
                                rx.text("Change Image"),
                                spacing="2",
                            ),
                            size="2",
                            variant="soft",
                            color_scheme="blue",
                        ),
                        id="image_upload_change",
                        on_drop=on_upload,
                        accept="image/png,image/jpeg,image/jpg,image/webp",
                        max_files=1,
                        max_size=5_000_000,  # 5MB
                    ),
                    rx.button(
                        rx.hstack(
                            rx.icon("x", size=16),
                            rx.text("Remove"),
                            spacing="2",
                        ),
                        on_click=on_clear,
                        size="2",
                        variant="soft",
                        color_scheme="red",
                    ),
                    spacing="2",
                    justify="center",
                ),

                spacing="3",
                width="100%",
                align="center",
            ),

            # Upload zone
            rx.upload(
                rx.vstack(
                    rx.cond(
                        is_uploading,
                        # Uploading state
                        rx.vstack(
                            rx.spinner(size="3"),
                            rx.text(
                                "Uploading...",
                                size="3",
                                color="gray",
                            ),
                            spacing="2",
                            align="center",
                        ),
                        # Empty state
                        rx.vstack(
                            rx.icon(
                                "upload",
                                size=32,
                                color="gray",
                            ),
                            rx.text(
                                "Drag & drop or click to upload",
                                size="3",
                                color="gray",
                                weight="medium",
                            ),
                            rx.text(
                                "PNG, JPG, WebP (max 5MB)",
                                size="1",
                                color="gray",
                            ),
                            spacing="2",
                            align="center",
                        ),
                    ),
                    spacing="2",
                    align="center",
                    padding="8",
                ),
                id="image_upload",
                on_drop=on_upload,
                border="2px dashed var(--gray-6)",
                border_radius="8px",
                padding="4",
                width="100%",
                min_height=rx.breakpoints(initial="180px", md="220px"),
                display="flex",
                align_items="center",
                justify_content="center",
                cursor="pointer",
                transition="all 0.2s",
                _hover={
                    "border_color": "var(--blue-7)",
                    "background": "var(--gray-2)",
                },
                accept="image/png,image/jpeg,image/jpg,image/webp",
                max_files=1,
                max_size=5_000_000,  # 5MB
            ),
        ),

        spacing="3",
        width="100%",
        align="start",
    )
