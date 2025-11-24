"""Meme post form - background + text overlay."""

import reflex as rx

from .background_selector import background_selector
from .color_picker import color_picker
from .markdown_editor import markdown_editor


def meme_form(state) -> rx.Component:
    """
    Form for creating Meme posts (background + text overlay).

    Components:
    - Background selector (thumbnail grid)
    - Text area (160 char limit)
    - Color pickers (text + outline)
    - Character counter

    Args:
        state: PostCreationState instance

    Returns:
        Reflex component with meme post form
    """
    return rx.vstack(
        # Background selector
        background_selector(
            backgrounds=state.available_backgrounds,
            selected=state.selected_background,
            on_select=state.select_background,
            is_loading=state.is_loading_backgrounds,
        ),

        # Text content with markdown support
        rx.vstack(
            rx.text(
                "Meme Text",
                size="2",
                weight="medium",
            ),
            markdown_editor(
                value=state.text_content,
                on_change=state.set_text_content,
                placeholder="Write your meme text...",
                max_length=160,
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
