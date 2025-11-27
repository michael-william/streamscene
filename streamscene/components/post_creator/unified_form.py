"""Unified post form - shared template for Picture and Meme posts."""

import reflex as rx
from typing import Callable, List

from .background_selector import background_selector


def unified_form(state) -> rx.Component:
    """
    Unified form for creating Picture and Meme posts.

    Uses 2-column responsive layout:
    - Left column: Image upload (picture) OR Background selector (meme)
    - Right column: Simple text area (same for both)

    Args:
        state: PostCreationState instance

    Returns:
        Reflex component with unified post form
    """
    return rx.grid(
        # Left column: Content source (conditional)
        rx.cond(
            state.post_type == "picture",
            _image_upload_section(state),
            _background_section(state),
        ),

        # Right column: Text content (same for both)
        _text_input_section(state),

        # Grid configuration - responsive 2-column layout
        columns=rx.breakpoints(initial="1", md="2"),
        spacing="5",
        width="100%",
    )


def _image_upload_section(state) -> rx.Component:
    """Image upload section for Picture posts."""
    return rx.vstack(
        rx.text(
            "Upload Image",
            size="3",
            weight="medium",
        ),

        # Hidden file input (native HTML)
        rx.el.input(
            type="file",
            id="picture-upload-input",
            accept="image/png,image/jpeg,image/webp",
            style={"display": "none"},
        ),

        # Hidden inputs for JavaScript to set (bound to state)
        rx.input(
            type="text",
            id="js-uploaded-filename",
            value=state.js_uploaded_filename,
            on_change=state.set_js_uploaded_filename,
            style={"position": "absolute", "left": "-9999px"},
        ),
        rx.input(
            type="text",
            id="js-uploaded-url",
            value=state.js_uploaded_url,
            on_change=state.set_js_uploaded_url,
            style={"position": "absolute", "left": "-9999px"},
        ),

        # Upload area (shown when no image uploaded)
        rx.cond(
            state.image_preview_url == "",
            rx.html("""
                <div id="picture-upload-area" style="width: 100%;">
                    <div style="border: 2px dashed var(--gray-6); padding: 3em; border-radius: 8px; width: 100%; text-align: center;">
                        <button
                            type="button"
                            onclick="document.getElementById('picture-upload-input').click()"
                            style="background: var(--accent-9); color: white; border: none; padding: 0.5em 1em; border-radius: 6px; cursor: pointer; font-size: 1em; margin-bottom: 0.5em;"
                        >
                            Select Image
                        </button>
                        <p style="color: var(--gray-11); font-size: 0.875em; margin: 0.5em 0;">Click to select an image</p>
                        <div id="picture-loading" style="display: none; margin-top: 1em;">
                            <div style="border: 3px solid var(--gray-6); border-top: 3px solid var(--accent-9); border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; margin: 0 auto;"></div>
                        </div>
                        <div id="picture-error-message" style="display: none; color: var(--red-11); font-size: 0.875em; margin-top: 1em;"></div>
                    </div>
                </div>
                <style>
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                </style>
            """),
        ),

        # Preview area (shown when image_preview_url is set)
        rx.cond(
            state.image_preview_url != "",
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
                    size="2",
                ),
                spacing="2",
                width="100%",
            ),
        ),

        # JavaScript to handle upload via custom endpoint
        rx.script("""
            (function() {
                const fileInput = document.getElementById('picture-upload-input');
                const errorDiv = document.getElementById('picture-error-message');
                const loadingDiv = document.getElementById('picture-loading');

                if (!fileInput || fileInput.hasAttribute('data-listener-attached')) return;
                fileInput.setAttribute('data-listener-attached', 'true');

                fileInput.addEventListener('change', async (e) => {
                    const file = e.target.files[0];
                    if (!file) return;

                    console.log('[UPLOAD] File selected:', file.name);

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
                        console.log('[UPLOAD] Upload complete:', data);

                        if (data.success) {
                            // Update hidden inputs to trigger Reflex state changes
                            const filenameInput = document.getElementById('js-uploaded-filename');
                            const urlInput = document.getElementById('js-uploaded-url');

                            if (filenameInput && urlInput) {
                                console.log('[UPLOAD] Setting filename:', data.filename);

                                // Set filename first with React-compatible approach
                                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                nativeInputValueSetter.call(filenameInput, data.filename);
                                filenameInput.dispatchEvent(new Event('input', { bubbles: true }));

                                // Small delay then set URL (this triggers the sync)
                                setTimeout(() => {
                                    console.log('[UPLOAD] Setting URL:', data.url);
                                    nativeInputValueSetter.call(urlInput, data.url);
                                    urlInput.dispatchEvent(new Event('input', { bubbles: true }));
                                    console.log('[UPLOAD] Both values set, Reflex should sync now');
                                }, 50);
                            } else {
                                console.error('[UPLOAD] Hidden inputs not found!');
                            }

                            if (errorDiv) errorDiv.style.display = 'none';
                        } else {
                            // Show error
                            if (errorDiv) {
                                errorDiv.textContent = `Upload failed: ${data.error || 'Unknown error'}`;
                                errorDiv.style.display = 'block';
                            }
                        }

                        // Clear file input for next upload
                        fileInput.value = '';

                    } catch (error) {
                        console.error('[UPLOAD] Error:', error);
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

        spacing="3",
        width="100%",
        align="start",
    )


def _background_section(state) -> rx.Component:
    """Background selector section for Meme posts."""
    return background_selector(
        backgrounds=state.available_backgrounds,
        selected=state.selected_background,
        on_select=state.select_background,
        is_loading=state.is_loading_backgrounds,
    )


def _text_input_section(state) -> rx.Component:
    """Text input section (shared by both post types)."""
    return rx.vstack(
        rx.text(
            rx.cond(
                state.post_type == "picture",
                "Add a caption",
                "Add your text",
            ),
            size="3",
            weight="medium",
        ),
        rx.text_area(
            value=state.text_content,
            on_change=state.set_text_content,
            placeholder=rx.cond(
                state.post_type == "picture",
                "Write a caption for your picture...",
                "Write your meme text...",
            ),
            max_length=160,
            rows="6",
            width="100%",
        ),
        # Character counter
        rx.hstack(
            rx.text(
                f"{state.text_content.length()} / 160",
                size="1",
                color=rx.cond(
                    state.text_content.length() > 160,
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
    )
