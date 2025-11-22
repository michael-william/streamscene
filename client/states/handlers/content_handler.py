"""Content handling logic for READY state.

Extracts content fetching, rotation, and display refresh logic.
"""

import logging
from typing import Tuple, Optional, Any

logger = logging.getLogger("streamscene.content")


class ContentHandler:
    """Handles content fetching and display refresh logic for READY state."""

    def __init__(self, api_client, config_service, renderer, display):
        """Initialize content handler.

        Args:
            api_client: API client for fetching content
            config_service: Configuration service for rotation settings
            renderer: Content renderer
            display: Display driver
        """
        self.api_client = api_client
        self.config_service = config_service
        self.renderer = renderer
        self.display = display

    def fetch_and_display(
        self,
        rotation_index: int,
        last_displayed_post_id: Optional[str]
    ) -> Tuple[bool, int, Optional[str]]:
        """Fetch content and update display if needed.

        Args:
            rotation_index: Current rotation index
            last_displayed_post_id: Last displayed post ID (for change detection)

        Returns:
            Tuple of (success, new_rotation_index, new_post_id)
        """
        # Get rotation settings from config service
        rotation_enabled, rotation_interval, rotation_count = (
            self.config_service.get_rotation_settings()
        )

        # Fetch content with rotation if enabled
        try:
            if rotation_enabled:
                logger.info(f"Fetching content (rotation index: {rotation_index})")
                content = self.api_client.fetch_content(rotation_index=rotation_index)
            else:
                logger.info("Fetching content (static mode)")
                content = self.api_client.fetch_content()
        except Exception as e:
            logger.error(f"Error fetching content: {e}")
            return (False, rotation_index, last_displayed_post_id)

        if not content:
            logger.warning("Failed to fetch content from server")
            return (False, rotation_index, last_displayed_post_id)

        # Determine if display refresh is needed
        current_post_id = content.get("post_id")
        should_refresh = self._should_refresh_display(
            rotation_enabled=rotation_enabled,
            current_post_id=current_post_id,
            last_post_id=last_displayed_post_id
        )

        if should_refresh:
            # Render and display content
            try:
                logger.info("Rendering content to image")
                image = self.renderer.render_content(content)

                logger.info("Displaying image on E Ink display")
                self.display.show(image)

                logger.info("Content update complete")
            except Exception as e:
                logger.error(f"Error rendering/displaying content: {e}")
                return (False, rotation_index, last_displayed_post_id)

            # Calculate new rotation index
            new_rotation_index = rotation_index
            if rotation_enabled:
                new_rotation_index = (rotation_index + 1) % rotation_count
                logger.info(f"Rotation index advanced to {new_rotation_index}")

            return (True, new_rotation_index, current_post_id)
        else:
            logger.info("Display refresh skipped (content unchanged)")
            return (True, rotation_index, last_displayed_post_id)

    def render_error(self, message: str) -> bool:
        """Render and display error message.

        Args:
            message: Error message to display

        Returns:
            True if successful
        """
        try:
            logger.info("Rendering error message")
            image = self.renderer.render_error(message)
            self.display.show(image)
            return True
        except Exception as e:
            logger.error(f"Error rendering error message: {e}")
            return False

    def _should_refresh_display(
        self,
        rotation_enabled: bool,
        current_post_id: Optional[str],
        last_post_id: Optional[str]
    ) -> bool:
        """Determine if display should be refreshed.

        Args:
            rotation_enabled: Whether rotation mode is enabled
            current_post_id: Current post ID
            last_post_id: Last displayed post ID

        Returns:
            True if display should be refreshed
        """
        if rotation_enabled:
            # Rotation mode: always refresh to show next post
            logger.info("[Rotation] Displaying post (mode: rotating)")
            return True
        else:
            # Static mode: only refresh if content changed
            if current_post_id != last_post_id:
                logger.info(f"[Static] New content detected (post_id: {current_post_id})")
                return True
            else:
                logger.info("[Static] Content unchanged")
                return False
