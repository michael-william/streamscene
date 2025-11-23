"""Picture post form - upload image + text comment."""

import reflex as rx

from .image_upload import image_upload
from .color_picker import color_picker


def picture_form(state) -> rx.Component:
    """
    Form for creating Picture posts (image + text comment).

    Components:
    - Image upload
    - Text area (160 char limit)
    - Color pickers (text + outline)
    - Character counter

    Args:
        state: PostCreationState instance

    Returns:
        Reflex component with picture post form
    """
    return rx.vstack(
        # Image upload
        image_upload(
            on_upload=state.handle_image_upload,
            on_clear=state.clear_uploaded_image,
            preview_url=state.image_preview_url,
            is_uploading=state.is_uploading_image,
            has_image=state.has_uploaded_image,
        ),

        # Text content
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
                columns=rx.breakpoints(initial="1", md="2"),  # 1 column mobile, 2 on desktop
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
