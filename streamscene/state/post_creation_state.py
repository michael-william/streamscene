"""State management for post creation forms."""

import logging
import base64
import io
import json
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
        if self.post_type == "picture" and not self.uploaded_files:
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
        return len(self.uploaded_files) > 0

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

        # Clear uploaded image when switching to Meme (free memory)
        if post_type == "meme":
            self.image_bytes = b""
            self.image_preview_url = ""
            logger.info("[POST_CREATE] Cleared uploaded image (switched to Meme)")

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
    # IMAGE UPLOAD (Picture posts) - Standard Reflex pattern
    # ========================================

    def test_upload_button(self):
        """Simple test to verify event binding works."""
        print("=" * 80)
        print("[TEST] BUTTON CLICKED - Event binding IS working!")
        print("=" * 80)
        logger.info("[TEST] Button test successful - event binding works")
        self.error_message = "Test button clicked! Event binding is working."
        yield

    def test_upload_button_click(self):
        """Test if the Upload button itself can trigger a handler."""
        print("=" * 80)
        print("[UPLOAD BUTTON] CLICKED! This proves the Upload button works.")
        print("=" * 80)
        logger.info("[UPLOAD BUTTON] Button clicked successfully")
        self.error_message = "Upload button clicked! Button itself works fine."
        yield

    def handle_upload_manual(self):
        """
        Handle upload by manually reading from upload directory.

        Bypasses rx.upload_files() entirely - just reads newest file from upload dir.
        """
        print("=" * 80)
        print("[UPLOAD] Manual handler called!")
        print("=" * 80)

        self.is_uploading_image = True
        self.error_message = ""
        yield

        try:
            upload_dir = rx.get_upload_dir()
            print(f"[UPLOAD] Upload directory: {upload_dir}")

            # Get all files in upload directory
            if not upload_dir.exists():
                print("[UPLOAD] Upload directory doesn't exist!")
                self.error_message = "Upload directory not found"
                self.is_uploading_image = False
                yield
                return

            files = list(upload_dir.glob("*"))
            print(f"[UPLOAD] Found {len(files)} files in upload directory")

            if not files:
                print("[UPLOAD] No files found in upload directory")
                self.error_message = "No file found - please select a file first"
                self.is_uploading_image = False
                yield
                return

            # Get the most recently modified file
            latest_file = max(files, key=lambda p: p.stat().st_mtime)
            print(f"[UPLOAD] Processing latest file: {latest_file.name}")

            # Read file
            upload_data = latest_file.read_bytes()
            print(f"[UPLOAD] Read {len(upload_data)} bytes")

            # Validate image
            try:
                img = Image.open(io.BytesIO(upload_data))
                img.verify()
                print(f"[UPLOAD] Image validated: {img.size}")
            except Exception as e:
                print(f"[UPLOAD] Image validation failed: {e}")
                self.error_message = "Invalid image file"
                self.is_uploading_image = False
                yield
                return

            # Store filename
            self.uploaded_files = [latest_file.name]

            # Generate preview URL
            self.image_preview_url = rx.get_upload_url(latest_file.name)
            print(f"[UPLOAD] Success! File: {latest_file.name}")
            logger.info(f"[POST_CREATE] Upload complete: {latest_file.name}")

        except Exception as e:
            print(f"[UPLOAD] Error: {e}")
            logger.error(f"[POST_CREATE] Upload error: {e}", exc_info=True)
            self.error_message = f"Upload failed: {str(e)}"

        finally:
            self.is_uploading_image = False
            yield

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle image upload - proper Reflex async pattern."""
        print("=" * 80)
        print(f"[UPLOAD] Handler called! Files: {len(files) if files else 0}")
        print("=" * 80)

        if not files:
            print("[UPLOAD] No files provided")
            self.error_message = "No file selected"
            return

        file = files[0]
        print(f"[UPLOAD] Processing: {file.filename}")

        self.is_uploading_image = True
        self.error_message = ""
        yield

        try:
            # Read file data
            upload_data = await file.read()
            print(f"[UPLOAD] Read {len(upload_data)} bytes")

            # Validate image
            img = Image.open(io.BytesIO(upload_data))
            img.verify()
            print(f"[UPLOAD] Image valid!")

            # Save to upload directory
            outfile = rx.get_upload_dir() / file.filename
            outfile.write_bytes(upload_data)
            print(f"[UPLOAD] Saved to {outfile}")

            # Store filename and generate preview
            self.uploaded_files = [file.filename]
            self.image_preview_url = rx.get_upload_url(file.filename)

            print(f"[UPLOAD] SUCCESS! Preview: {self.image_preview_url}")
            logger.info(f"[POST_CREATE] Upload complete: {file.filename}")

        except Exception as e:
            print(f"[UPLOAD] Error: {e}")
            self.error_message = f"Upload failed: {str(e)}"
            self.uploaded_files = []

        finally:
            self.is_uploading_image = False
            yield

    def clear_uploaded_image(self):
        """Clear uploaded image and delete from disk."""
        logger.info("[POST_CREATE] Clearing uploaded image")

        # Delete uploaded file from disk
        if self.uploaded_files:
            filename = self.uploaded_files[0]
            file_path = rx.get_upload_dir() / filename
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.info(f"[POST_CREATE] Deleted uploaded file: {file_path}")
                except Exception as e:
                    logger.error(f"[POST_CREATE] Failed to delete file: {e}")

        # Clear state
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
                if not self.uploaded_files:
                    logger.warning("[POST_CREATE] No image to preview")
                    self.error_message = "Please upload an image to see preview"
                    self.preview_image_data = ""
                    self.is_generating_preview = False
                    return

                # Get uploaded file path
                filename = self.uploaded_files[0]
                uploaded_file_path = rx.get_upload_dir() / filename

                rendered = renderer.render_picture_post(
                    image_path=str(uploaded_file_path),
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

        uploaded_file_path = None
        try:
            user_uuid = UUID(self.user_id)
            stream_uuid = UUID(stream_id)

            # Read image bytes from uploaded file if picture post
            image_bytes = b""
            if self.post_type == "picture":
                filename = self.uploaded_files[0]
                uploaded_file_path = rx.get_upload_dir() / filename

                logger.info(f"[POST_CREATE] Reading uploaded file: {uploaded_file_path}")
                with open(uploaded_file_path, 'rb') as f:
                    image_bytes = f.read()

                # Validate image
                try:
                    img = Image.open(io.BytesIO(image_bytes))
                    img.verify()
                    logger.info(f"[POST_CREATE] Image validated: {img.size}, mode: {img.mode}")
                except Exception as e:
                    self.error_message = "Invalid image file"
                    logger.error(f"[POST_CREATE] Image validation failed: {e}")
                    return

            with get_db_session() as session:
                # Create post with appropriate parameters
                if self.post_type == "picture":
                    post = stream_ops.create_post(
                        session=session,
                        stream_id=stream_uuid,
                        author_id=user_uuid,
                        text_content=self.text_content,
                        content_type="picture",
                        image_bytes=image_bytes,
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

                # Delete uploaded file after successful post creation
                if uploaded_file_path and uploaded_file_path.exists():
                    try:
                        uploaded_file_path.unlink()
                        logger.info(f"[POST_CREATE] Deleted uploaded file: {uploaded_file_path}")
                    except Exception as cleanup_err:
                        logger.error(f"[POST_CREATE] Failed to delete uploaded file: {cleanup_err}")

                # Set success message
                self.success_message = "Post created successfully!"

                # Clear form
                self.text_content = ""
                self.uploaded_files = []
                self.image_preview_url = ""
                self.preview_image_data = ""
                self.show_preview = False

                # Trigger reload of stream posts (late import to avoid circular dependency)
                from streamscene.pages.stream_posts import StreamPostsState
                yield StreamPostsState.load_stream_and_posts(stream_id)

                # Auto-dismiss success message after 5 seconds
                yield from self.auto_dismiss_success()

        except Exception as e:
            logger.error(f"[POST_CREATE] Error creating post: {e}", exc_info=True)
            self.error_message = f"Error creating post: {str(e)}"

        finally:
            self.is_submitting = False
            yield

    # ========================================
    # AUTO-DISMISS
    # ========================================

    def auto_dismiss_success(self):
        """Auto-dismiss success message after 5 seconds."""
        import time
        time.sleep(5)
        self.success_message = ""
        yield
