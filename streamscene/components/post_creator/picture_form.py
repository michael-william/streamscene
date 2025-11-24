"""Picture post form - upload image + text comment (simplified with inline upload)."""

import reflex as rx

from .color_picker import color_picker
from .markdown_editor import markdown_editor
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
        # Image upload section (pure JavaScript/DOM - no Reflex state)
        rx.vstack(
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

            # Preview area (Reflex component - shown when image_preview_url is set)
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
        ),

        # Text content (caption) with markdown support
        rx.vstack(
            rx.text(
                "Add a caption",
                size="2",
                weight="medium",
            ),
            markdown_editor(
                value=state.text_content,
                on_change=state.set_text_content,
                placeholder="Write a caption for your picture...",
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
