"""Markdown editor component with live preview."""

import reflex as rx


def markdown_editor(
    value: rx.Var[str],
    on_change: callable,
    placeholder: str = "Enter your text...",
    max_length: int = 160,
) -> rx.Component:
    """
    Markdown editor with side-by-side preview.

    Features:
    - Live markdown preview (client-side, instant)
    - Formatting hints
    - Character count
    - E Ink-friendly formatting (bold, italic, simple)

    Args:
        value: Current text content (markdown)
        on_change: Handler for text changes
        placeholder: Placeholder text
        max_length: Maximum character length

    Returns:
        Reflex component with editor and preview
    """
    return rx.vstack(
        # Editor + Preview (side by side on larger screens, stacked on mobile)
        rx.box(
            rx.grid(
                # Left: Editor
                rx.vstack(
                    rx.text(
                        "Text Editor",
                        size="2",
                        weight="medium",
                        color="gray",
                    ),
                    rx.text_area(
                        value=value,
                        on_change=on_change,
                        placeholder=placeholder,
                        max_length=max_length,
                        rows="6",
                        width="100%",
                    ),
                    # Character count
                    rx.hstack(
                        rx.text(
                            f"{value.length()} / {max_length}",
                            size="1",
                            color=rx.cond(
                                value.length() > max_length,
                                "red",
                                "gray",
                            ),
                        ),
                        spacing="2",
                        justify="end",
                        width="100%",
                    ),
                    spacing="2",
                    width="100%",
                    align="start",
                ),

                # Right: Preview
                rx.vstack(
                    rx.text(
                        "Preview",
                        size="2",
                        weight="medium",
                        color="gray",
                    ),
                    rx.box(
                        rx.cond(
                            value,
                            rx.markdown(
                                value,
                                component_map={
                                    # Customize markdown rendering for E Ink
                                    "p": lambda text: rx.text(text, size="2"),
                                    "strong": lambda text: rx.text(text, weight="bold"),
                                    "em": lambda text: rx.text(text, as_="i"),
                                },
                            ),
                            rx.text(
                                "Preview will appear here...",
                                size="2",
                                color="gray",
                                as_="i",
                            ),
                        ),
                        padding="12px",
                        border="1px solid var(--gray-6)",
                        border_radius="8px",
                        min_height="150px",
                        width="100%",
                        background="var(--gray-1)",
                    ),
                    spacing="2",
                    width="100%",
                    align="start",
                ),

                columns=rx.breakpoints(initial="1", md="2"),
                spacing="4",
                width="100%",
            ),
            width="100%",
        ),

        # Formatting hints
        rx.box(
            rx.hstack(
                rx.icon("info", size=14, color="gray"),
                rx.text(
                    "Formatting: ",
                    size="1",
                    color="gray",
                    weight="medium",
                ),
                rx.code("**bold**", size="1"),
                rx.code("*italic*", size="1"),
                rx.code("[link](url)", size="1"),
                spacing="2",
                wrap="wrap",
            ),
            padding="8px",
            background="var(--gray-2)",
            border_radius="6px",
            width="100%",
        ),

        spacing="3",
        width="100%",
        align="start",
    )
