"""Picture post form - upload image + text comment (simplified with inline upload)."""

import reflex as rx

from .color_picker import color_picker
from streamscene.state.post_creation_state import PostCreationState


def picture_form(state) -> rx.Component:
    """
    Form for creating Picture posts (image + text comment).

    Uses inline rx.upload() for direct EventHandler binding (no abstraction layer).

    Components:
    - Image upload (inline, no wrapper)
    - Text area (160 char limit)
    - Color pickers (text + outline)
    - Character counter

    Args:
        state: PostCreationState instance

    Returns:
        Reflex component with picture post form
    """
    return rx.vstack(
        # Image upload section (inline - no wrapper function)
        rx.vstack(
            rx.text(
                "Upload Image",
                size="3",
                weight="medium",
            ),

            rx.cond(
                state.has_uploaded_image,
                # Has image: Show preview with remove button
                rx.vstack(
                    rx.image(
                        src=state.image_preview_url,
                        width="100%",
                        max_width="400px",
                        border_radius="8px",
                        border="1px solid var(--gray-6)",
                        object_fit="contain",
                    ),
                    rx.button(
                        "Remove Image",
                        on_click=state.clear_uploaded_image,
                        color_scheme="red",
                    ),
                    spacing="3",
                    width="100%",
                ),

                # No image: Standard Reflex upload pattern with on_drop handler
                rx.vstack(
                    rx.upload(
                        rx.vstack(
                            rx.button("Select Image", size="3", loading=state.is_uploading_image),
                            rx.text("Drag and drop or click to select", size="2", color="gray"),
                            rx.cond(
                                state.is_uploading_image,
                                rx.text("Uploading...", size="2", color="blue"),
                            ),
                        ),
                        id="upload1",
                        border="2px dashed var(--gray-6)",
                        padding="3em",
                        border_radius="8px",
                        accept={
                            "image/png": [".png"],
                            "image/jpeg": [".jpg", ".jpeg"],
                            "image/webp": [".webp"],
                        },
                        max_files=1,
                        max_size=5_000_000,
                        on_drop=state.handle_upload,
                    ),
                    # Debug: Show selected files
                    rx.vstack(
                        rx.text("Selected files:", weight="bold", size="2"),
                        rx.foreach(
                            rx.selected_files("upload1"),
                            lambda filename: rx.text(f"- {filename}", color="green"),
                        ),
                        spacing="1",
                    ),
                    spacing="3",
                    width="100%",
                ),
            ),

            spacing="3",
            width="100%",
        ),

        # Text content (caption)
        rx.vstack(
            rx.hstack(
                rx.text(
                    "Add a caption",
                    size="2",
                    weight="medium",
                ),
                rx.spacer(),
                rx.text(
                    f"{state.char_count} / 160",
                    size="1",
                    color=state.char_count_color,
                    font_family="monospace",
                ),
                width="100%",
                align="center",
            ),

            rx.text_area(
                placeholder="Write a caption for your picture...",
                value=state.text_content,
                on_change=state.set_text_content,
                size="3",
                rows="3",
                max_length=160,
                width="100%",
            ),

            spacing="2",
            width="100%",
        ),

        # Color pickers
        rx.vstack(
            rx.text(
                "Text Styling",
                size="3",
                weight="medium",
            ),

            rx.grid(
                color_picker(
                    label="Text Color",
                    value=state.text_color,
                    on_change=state.update_text_color,
                ),
                color_picker(
                    label="Outline Color",
                    value=state.outline_color,
                    on_change=state.update_outline_color,
                ),
                columns=rx.breakpoints(initial="1", md="2"),
                gap="4",
                width="100%",
            ),

            spacing="3",
            width="100%",
        ),

        spacing="5",
        width="100%",
        align="start",
    )
