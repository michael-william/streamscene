"""State management for post creation forms."""

import logging
import base64
import io
from typing import List, Optional
from uuid import UUID

import reflex as rx
from PIL import Image

from streamscene.core.database import get_db_session
from streamscene.core import streams as stream_ops
from streamscene.core.backgrounds import get_all_backgrounds, get_background_path
from streamscene.core.image_renderer import ImageRenderer, hex_to_rgb
from streamscene.pages.base_state import BaseState
from streamscene.components.post_creator.utils import validate_hex_color, format_file_size

logger = logging.getLogger(__name__)


class PostCreationState(BaseState):
    """
    State for creating Picture and Meme posts.

    Handles:
    - Post type selection (picture/meme)
    - Image uploads (Picture posts)
    - Background selection (Meme posts)
    - Color customization (text + outline)
    - Live preview generation
    - Form validation
    - Post submission
    """

    state_auto_setters = True

    # ========================================
    # FORM STATE
    # ========================================

    # Post type: "picture" or "meme"
    post_type: str = "meme"

    # Common fields
    text_content: str = ""
    text_color: str = "#000000"  # Black
    outline_color: str = "#FFFFFF"  # White

    # Picture post fields
    uploaded_files: list[str] = []  # rx.upload() file refs
    image_preview_url: str = ""
    image_bytes: bytes = b""  # Stored for submission

    # Meme post fields
    selected_background: str = "white.png"
    available_backgrounds: List[dict] = []

    # ========================================
    # UI STATE
    # ========================================

    show_preview: bool = False
    preview_image_data: str = ""  # Base64 data URL

    # Loading states
    is_loading_backgrounds: bool = False
    is_uploading_image: bool = False
    is_generating_preview: bool = False
    is_submitting: bool = False

    # Validation & messages
    error_message: str = ""
    validation_errors: List[str] = []
    success_message: str = ""

    # ========================================
    # COMPUTED PROPERTIES
    # ========================================

    @rx.var
    def char_count(self) -> int:
        """Get character count of text content."""
        return len(self.text_content)

    @rx.var
    def is_valid(self) -> bool:
        """Check if form is valid for submission."""
        if not self.text_content.strip():
            return False
        if self.char_count > 160:
            return False
        if self.post_type == "picture" and not self.image_bytes:
            return False
        if self.post_type == "meme" and not self.selected_background:
            return False
        if not validate_hex_color(self.text_color):
            return False
        if not validate_hex_color(self.outline_color):
            return False
        return True

    @rx.var
    def char_count_color(self) -> str:
        """Get color for character counter."""
        if self.char_count > 160:
            return "red"
        elif self.char_count > 140:
            return "yellow"
        return "gray"

    @rx.var
    def has_uploaded_image(self) -> bool:
        """Check if image has been uploaded."""
        return len(self.image_bytes) > 0

    @rx.var
    def upload_button_text(self) -> str:
        """Get text for upload button based on state."""
        if self.is_uploading_image:
            return "Uploading..."
        elif self.has_uploaded_image:
            return "Change Image"
        else:
            return "Upload Image"

    # ========================================
    # LIFECYCLE METHODS
    # ========================================

    def on_load(self):
        """Load backgrounds when component mounts."""
        logger.info("[POST_CREATE] Component mounted, loading backgrounds")
        yield from self.load_backgrounds()

    # ========================================
    # POST TYPE SELECTION
    # ========================================

    def select_post_type(self, post_type: str):
        """
        Switch between picture and meme post types.

        Args:
            post_type: "picture" or "meme"
        """
        if post_type not in ["picture", "meme"]:
            logger.error(f"[POST_CREATE] Invalid post type: {post_type}")
            return

        logger.info(f"[POST_CREATE] Switching post type: {self.post_type} -> {post_type}")
        self.post_type = post_type
        self.error_message = ""
        self.validation_errors = []

        # Clear preview when switching types
        self.preview_image_data = ""

    # ========================================
    # BACKGROUND MANAGEMENT
    # ========================================

    def load_backgrounds(self):
        """Load available backgrounds from database."""
        logger.info("[POST_CREATE] Loading backgrounds from database")
        self.is_loading_backgrounds = True
        yield

        try:
            with get_db_session() as session:
                backgrounds = get_all_backgrounds(session, active_only=True)

                self.available_backgrounds = [
                    {
                        "filename": bg.filename,
                        "display_name": bg.display_name,
                    }
                    for bg in backgrounds
                ]

                logger.info(f"[POST_CREATE] Loaded {len(self.available_backgrounds)} backgrounds")

                # Set default if not already set
                if not self.selected_background and self.available_backgrounds:
                    self.selected_background = self.available_backgrounds[0]["filename"]
                    logger.info(f"[POST_CREATE] Default background: {self.selected_background}")

        except Exception as e:
            logger.error(f"[POST_CREATE] Error loading backgrounds: {e}", exc_info=True)
            self.error_message = f"Error loading backgrounds: {str(e)}"

        finally:
            self.is_loading_backgrounds = False
            yield

    def select_background(self, filename: str):
        """
        Select a background for meme posts.

        Args:
            filename: Background image filename
        """
        logger.info(f"[POST_CREATE] Background selected: {filename}")
        self.selected_background = filename

        # Clear preview so user re-toggles to regenerate
        self.preview_image_data = ""

    # ========================================
    # IMAGE UPLOAD (Picture posts)
    # ========================================

    async def handle_image_upload(self, files: list[rx.UploadFile]):
        """
        Handle image upload for picture posts.

        Args:
            files: List of uploaded files (rx.upload returns list)
        """
        if not files:
            logger.warning("[POST_CREATE] No files uploaded")
            return

        file = files[0]  # Only handle first file
        logger.info(f"[POST_CREATE] Image upload started: {file.filename}")

        self.is_uploading_image = True
        self.error_message = ""
        yield

        try:
            # Read file bytes
            self.image_bytes = await file.read()
            file_size_mb = len(self.image_bytes) / (1024 * 1024)

            logger.info(f"[POST_CREATE] Image uploaded: {file.filename}, size: {file_size_mb:.2f}MB")

            # Validate size
            if file_size_mb > 5:
                self.error_message = f"Image too large ({file_size_mb:.1f}MB, max 5MB)"
                logger.error(f"[POST_CREATE] Image too large: {file_size_mb:.2f}MB")
                self.image_bytes = b""
                return

            # Validate type
            allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp"]
            if file.content_type not in allowed_types:
                self.error_message = f"Invalid file type: {file.content_type}"
                logger.error(f"[POST_CREATE] Invalid file type: {file.content_type}")
                self.image_bytes = b""
                return

            # Validate it's actually an image
            try:
                img = Image.open(io.BytesIO(self.image_bytes))
                img.verify()
                logger.info(f"[POST_CREATE] Image verified: {img.size}, mode: {img.mode}")
            except Exception as e:
                self.error_message = "Invalid image file"
                logger.error(f"[POST_CREATE] Image verification failed: {e}")
                self.image_bytes = b""
                return

            # Re-open image (verify() closes it)
            img = Image.open(io.BytesIO(self.image_bytes))

            # Create preview URL (data URL)
            b64_data = base64.b64encode(self.image_bytes).decode()
            self.image_preview_url = f"data:{file.content_type};base64,{b64_data}"

            logger.info("[POST_CREATE] Image preview generated")

            # Note: Preview regeneration happens via user toggling preview
            # We don't auto-generate here to avoid async/yield conflicts

        except Exception as e:
            logger.error(f"[POST_CREATE] Error uploading image: {e}", exc_info=True)
            self.error_message = f"Error uploading image: {str(e)}"
            self.image_bytes = b""

        finally:
            self.is_uploading_image = False
            yield

    def clear_uploaded_image(self):
        """Clear uploaded image."""
        logger.info("[POST_CREATE] Clearing uploaded image")
        self.image_bytes = b""
        self.image_preview_url = ""
        self.uploaded_files = []
        self.preview_image_data = ""

    # ========================================
    # COLOR CUSTOMIZATION
    # ========================================

    def update_text_color(self, color: str):
        """
        Update text color.

        Args:
            color: Hex color code (e.g., "#000000")
        """
        # Validate hex format
        if not validate_hex_color(color):
            logger.warning(f"[POST_CREATE] Invalid text color format: {color}")
            return

        logger.info(f"[POST_CREATE] Text color updated: {self.text_color} -> {color}")
        self.text_color = color

        # Clear preview so user re-toggles to regenerate
        self.preview_image_data = ""

    def update_outline_color(self, color: str):
        """
        Update outline color.

        Args:
            color: Hex color code (e.g., "#FFFFFF")
        """
        # Validate hex format
        if not validate_hex_color(color):
            logger.warning(f"[POST_CREATE] Invalid outline color format: {color}")
            return

        logger.info(f"[POST_CREATE] Outline color updated: {self.outline_color} -> {color}")
        self.outline_color = color

        # Clear preview so user re-toggles to regenerate
        self.preview_image_data = ""

    # ========================================
    # LIVE PREVIEW
    # ========================================

    def toggle_preview(self):
        """Toggle live preview visibility."""
        self.show_preview = not self.show_preview
        logger.info(f"[POST_CREATE] Preview toggled: {self.show_preview}")

        # Always generate preview when showing (to reflect current state)
        if self.show_preview:
            yield from self.generate_preview()

    def generate_preview(self):
        """
        Generate live preview using PIL renderer.

        Creates a base64 data URL of the rendered post.
        """
        logger.info("[POST_CREATE] Generating preview...")
        self.is_generating_preview = True
        self.error_message = ""
        yield

        try:
            renderer = ImageRenderer()

            # Parse colors
            text_color = hex_to_rgb(self.text_color)
            outline_color = hex_to_rgb(self.outline_color)

            # Get metadata (from parent state if available)
            stream_name = getattr(self, "stream_name", "Preview Stream")
            author_name = "You"
            from datetime import datetime
            post_date = datetime.now()

            # Render based on post type
            if self.post_type == "picture":
                if not self.image_bytes:
                    logger.warning("[POST_CREATE] No image to preview")
                    self.preview_image_data = ""
                    self.is_generating_preview = False
                    return

                # Save temp image for rendering
                temp_img = Image.open(io.BytesIO(self.image_bytes))
                temp_path = "/tmp/preview_upload.png"
                temp_img.save(temp_path)

                rendered = renderer.render_picture_post(
                    image_path=temp_path,
                    text_content=self.text_content or "",
                    stream_name=stream_name,
                    author_name=author_name,
                    post_date=post_date,
                    text_color=text_color,
                    outline_color=outline_color
                )

            elif self.post_type == "meme":
                if not self.selected_background:
                    logger.warning("[POST_CREATE] No background selected")
                    self.preview_image_data = ""
                    self.is_generating_preview = False
                    return

                background_path = str(get_background_path(self.selected_background))

                rendered = renderer.render_meme_post(
                    background_image_path=background_path,
                    text_content=self.text_content or "",
                    stream_name=stream_name,
                    author_name=author_name,
                    post_date=post_date,
                    text_color=text_color,
                    outline_color=outline_color
                )

            # Convert to base64 data URL
            buffer = io.BytesIO()
            rendered.save(buffer, format="PNG")
            b64_data = base64.b64encode(buffer.getvalue()).decode()
            self.preview_image_data = f"data:image/png;base64,{b64_data}"

            logger.info("[POST_CREATE] Preview generated successfully")

        except Exception as e:
            logger.error(f"[POST_CREATE] Error generating preview: {e}", exc_info=True)
            self.error_message = f"Preview error: {str(e)}"
            self.preview_image_data = ""

        finally:
            self.is_generating_preview = False
            yield

    def auto_refresh_preview(self, _event=None):
        """
        Auto-refresh preview every 2 seconds.

        Called by rx.moment timer when preview is visible.
        Ignores event parameter from timer.
        """
        # Only regenerate if preview is visible and not already generating
        if self.show_preview and not self.is_generating_preview:
            logger.info("[POST_CREATE] Auto-refreshing preview")
            yield from self.generate_preview()

    # ========================================
    # FORM VALIDATION
    # ========================================

    def validate_form(self) -> bool:
        """
        Validate form before submission.

        Returns:
            True if valid, False otherwise (sets validation_errors)
        """
        self.validation_errors = []

        # Check text content
        if not self.text_content.strip():
            self.validation_errors.append("Text content is required")

        if self.char_count > 160:
            self.validation_errors.append("Text is too long (max 160 characters)")

        # Check post-type specific requirements
        if self.post_type == "picture":
            if not self.image_bytes:
                self.validation_errors.append("Please upload an image")

        elif self.post_type == "meme":
            if not self.selected_background:
                self.validation_errors.append("Please select a background")

        # Check colors
        if not validate_hex_color(self.text_color):
            self.validation_errors.append("Invalid text color")

        if not validate_hex_color(self.outline_color):
            self.validation_errors.append("Invalid outline color")

        is_valid = len(self.validation_errors) == 0

        if not is_valid:
            logger.warning(f"[POST_CREATE] Form validation failed: {self.validation_errors}")
        else:
            logger.info("[POST_CREATE] Form validation passed")

        return is_valid

    # ========================================
    # POST SUBMISSION
    # ========================================

    def submit_post(self, stream_id: str):
        """
        Submit the post to the database.

        Args:
            stream_id: Stream UUID string
        """
        logger.info(f"[POST_CREATE] Submitting {self.post_type} post to stream {stream_id}")

        # Validate form
        if not self.validate_form():
            self.error_message = "Please fix the errors above"
            return

        # Check authentication
        if not self.user_id:
            self.error_message = "You must be logged in to post"
            logger.error("[POST_CREATE] No user_id in state")
            return

        self.is_submitting = True
        self.error_message = ""
        yield

        try:
            user_uuid = UUID(self.user_id)
            stream_uuid = UUID(stream_id)

            with get_db_session() as session:
                # Create post with appropriate parameters
                if self.post_type == "picture":
                    post = stream_ops.create_post(
                        session=session,
                        stream_id=stream_uuid,
                        author_id=user_uuid,
                        text_content=self.text_content,
                        content_type="picture",
                        image_bytes=self.image_bytes,
                        text_color=self.text_color,
                        outline_color=self.outline_color,
                    )

                elif self.post_type == "meme":
                    post = stream_ops.create_post(
                        session=session,
                        stream_id=stream_uuid,
                        author_id=user_uuid,
                        text_content=self.text_content,
                        content_type="meme",
                        background_name=self.selected_background,
                        text_color=self.text_color,
                        outline_color=self.outline_color,
                    )

                session.commit()

                logger.info(f"[POST_CREATE] Post created successfully: {post.id}")

                # Set success message
                self.success_message = "Post created successfully!"

                # Clear form
                self.text_content = ""
                self.image_bytes = b""
                self.image_preview_url = ""
                self.preview_image_data = ""
                self.show_preview = False

                # Trigger reload of stream posts (late import to avoid circular dependency)
                from streamscene.pages.stream_posts import StreamPostsState
                return StreamPostsState.load_stream_and_posts(stream_id)

        except Exception as e:
            logger.error(f"[POST_CREATE] Error creating post: {e}", exc_info=True)
            self.error_message = f"Error creating post: {str(e)}"

        finally:
            self.is_submitting = False
            yield
