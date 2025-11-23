"""E Ink display rendering service using HTML/CSS templates and Playwright."""

import os
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright, Browser, Page
import logging

logger = logging.getLogger(__name__)

# Constants
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "eink"
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "rendered"


class EInkRenderer:
    """Renders content to PNG images using HTML/CSS templates."""

    def __init__(self):
        """Initialize the renderer with Jinja2 and Playwright."""
        self.template_env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=True,
        )
        self.browser: Optional[Browser] = None
        self.playwright = None

        # Ensure cache directory exists
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        logger.info(f"EInkRenderer initialized (templates: {TEMPLATE_DIR})")

    def _start_browser(self) -> None:
        """Start Playwright browser if not already running."""
        if self.browser is None:
            logger.info("Starting Playwright browser...")
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )
            logger.info("Playwright browser started")

    def _stop_browser(self) -> None:
        """Stop Playwright browser."""
        if self.browser:
            logger.info("Stopping Playwright browser...")
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
            logger.info("Playwright stopped")

    def _cache_key(self, content: dict, theme: str = "classic") -> str:
        """Generate cache key from content and theme."""
        # Create a unique hash from content that matters for rendering
        cache_data = {
            "stream_name": content.get("stream_name", ""),
            "text_content": content.get("text_content", ""),
            "author_name": content.get("author_name", ""),
            "timestamp": str(content.get("posted_at", "")),
            "has_content": content.get("has_content", False),
            "theme": theme,
        }
        cache_str = str(sorted(cache_data.items()))
        return hashlib.sha256(cache_str.encode('utf-8')).hexdigest()

    def _get_cached_image(self, cache_key: str) -> Optional[Path]:
        """Get cached image path if it exists."""
        cache_path = CACHE_DIR / f"{cache_key}.png"
        if cache_path.exists():
            logger.debug(f"Cache hit: {cache_key[:8]}...")
            return cache_path
        logger.debug(f"Cache miss: {cache_key[:8]}...")
        return None

    def render_post(
        self,
        content: dict,
        theme: str = "classic",
        use_cache: bool = True,
    ) -> Path:
        """
        Render a post to a PNG image.

        Args:
            content: Content dictionary with keys:
                - stream_name: Name of the stream
                - text_content: Message text
                - author_name: Optional author name
                - posted_at: Timestamp (datetime or string)
                - has_content: Whether there is actual content (vs system message)
            theme: Theme name (default: "classic")
            use_cache: Whether to use cached images (default: True)

        Returns:
            Path: Path to the rendered PNG file

        Example:
            content = {
                "stream_name": "Family Updates",
                "text_content": "Hello from the beach!",
                "author_name": "Dad",
                "posted_at": datetime.now(),
                "has_content": True,
            }
            image_path = renderer.render_post(content)
        """
        # Check cache first
        cache_key = self._cache_key(content, theme)
        if use_cache:
            cached_path = self._get_cached_image(cache_key)
            if cached_path:
                return cached_path

        # Format timestamp if it's a datetime object
        if isinstance(content.get("posted_at"), datetime):
            timestamp = content["posted_at"].strftime("%b %d, %Y %I:%M %p")
        else:
            timestamp = str(content.get("posted_at", ""))

        # Prepare template context
        context = {
            "stream_name": content.get("stream_name", "StreamScene"),
            "text_content": content.get("text_content", ""),
            "author_name": content.get("author_name", ""),
            "timestamp": timestamp,
            "has_content": content.get("has_content", True),
            "theme": theme,
        }

        # Render HTML from template
        template = self.template_env.get_template("post.html")
        html_content = template.render(**context)

        # Start browser if needed
        self._start_browser()

        # Render HTML to PNG using Playwright
        logger.info(f"Rendering post to PNG (theme: {theme})...")
        page = self.browser.new_page(
            viewport={"width": DISPLAY_WIDTH, "height": DISPLAY_HEIGHT}
        )

        try:
            # Load HTML content
            # We need to set the base URL so relative CSS paths work
            base_url = f"file://{TEMPLATE_DIR}/"
            page.set_content(html_content, wait_until="networkidle")

            # Take screenshot
            output_path = CACHE_DIR / f"{cache_key}.png"
            page.screenshot(
                path=str(output_path),
                full_page=False,
                type="png",
            )

            logger.info(f"Rendered successfully: {output_path.name}")
            return output_path

        finally:
            page.close()

    def cleanup(self) -> None:
        """Clean up resources (stop browser)."""
        self._stop_browser()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup browser."""
        self.cleanup()


# Global renderer instance (singleton pattern)
_renderer_instance: Optional[EInkRenderer] = None


def get_renderer() -> EInkRenderer:
    """Get or create the global renderer instance."""
    global _renderer_instance
    if _renderer_instance is None:
        _renderer_instance = EInkRenderer()
    return _renderer_instance


def render_device_content(content: dict, theme: str = "classic") -> Path:
    """
    Convenience function to render device content using the global renderer.

    Args:
        content: Content dictionary (see EInkRenderer.render_post for format)
        theme: Theme name (default: "classic")

    Returns:
        Path: Path to the rendered PNG file
    """
    renderer = get_renderer()
    return renderer.render_post(content, theme=theme)
