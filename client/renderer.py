"""Content rendering for E Ink display

Renders content (text, images, etc.) to 800x480 images optimized for
6-color E Ink displays.
"""

from typing import Optional, Tuple
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
import numpy as np

from . import config


class ContentRenderer:
    """Renders content for E Ink display."""

    def __init__(self):
        """Initialize renderer."""
        self.width = config.DISPLAY_WIDTH
        self.height = config.DISPLAY_HEIGHT

        # Try to load a nice font, fall back to default if not available
        self.font_large = self._load_font(size=48)
        self.font_medium = self._load_font(size=32)
        self.font_small = self._load_font(size=24)

        print(f"[Renderer] Initialized ({self.width}x{self.height})")

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        """
        Load a TrueType font.

        Args:
            size: Font size in points

        Returns:
            ImageFont object
        """
        # Try to load common system fonts
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
            "C:\\Windows\\Fonts\\arial.ttf",  # Windows
        ]

        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, size)
            except (OSError, IOError):
                continue

        # Fall back to default font
        print(f"[Renderer] Warning: Could not load TrueType font, using default")
        return ImageFont.load_default()

    def render_content(self, content: dict) -> Image.Image:
        """
        Render content to an image.

        Args:
            content: Content dict from API with keys:
                - content_type: "text", "image", "mixed"
                - text_content: Text to display
                - image_url: URL to image (optional)
                - posted_at: Timestamp
                - stream_name: Name of stream
                - has_content: Whether there is actual content

        Returns:
            PIL Image (800x480, RGB mode)
        """
        # Create blank white image
        image = Image.new("RGB", (self.width, self.height), config.COLORS["WHITE"])
        draw = ImageDraw.Draw(image)

        if not content.get("has_content", False):
            # No content - show system message
            self._draw_system_message(draw, content.get("text_content", "No content available"))
        else:
            # Has content - render it
            if content.get("content_type") == "text":
                self._draw_text_content(draw, content)
            # TODO: Add image support in Phase 5

        # Convert to 6-color palette
        image = self._convert_to_eink_palette(image)

        return image

    def _draw_system_message(self, draw: ImageDraw.ImageDraw, message: str):
        """Draw a system message (centered)."""
        # Draw message in center
        bbox = draw.textbbox((0, 0), message, font=self.font_medium)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (self.width - text_width) // 2
        y = (self.height - text_height) // 2

        draw.text((x, y), message, fill=config.COLORS["BLACK"], font=self.font_medium)

    def _draw_text_content(self, draw: ImageDraw.ImageDraw, content: dict):
        """
        Draw text content with stream name and timestamp.

        Layout:
        - Top: Stream name
        - Middle: Main text content (wrapped)
        - Bottom: Timestamp
        """
        margin = 40
        y = margin

        # Draw stream name at top
        stream_name = content.get("stream_name", "StreamScene")
        draw.text((margin, y), stream_name, fill=config.COLORS["BLUE"], font=self.font_medium)
        y += 50

        # Draw separator line
        draw.line([(margin, y), (self.width - margin, y)], fill=config.COLORS["BLACK"], width=2)
        y += 30

        # Draw main text content (wrapped)
        text = content.get("text_content", "")
        wrapped_lines = self._wrap_text(text, self.font_large, self.width - 2 * margin)

        for line in wrapped_lines:
            if y + 60 > self.height - 100:  # Leave room for timestamp
                draw.text((margin, y), "...", fill=config.COLORS["BLACK"], font=self.font_large)
                break

            draw.text((margin, y), line, fill=config.COLORS["BLACK"], font=self.font_large)
            y += 60

        # Draw timestamp at bottom
        posted_at = content.get("posted_at", "")
        if posted_at:
            try:
                # Parse ISO timestamp and format nicely
                dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
                timestamp_text = dt.strftime("%B %d, %Y at %I:%M %p")
            except:
                timestamp_text = posted_at

            bbox = draw.textbbox((0, 0), timestamp_text, font=self.font_small)
            text_width = bbox[2] - bbox[0]

            draw.text(
                (self.width - text_width - margin, self.height - 40),
                timestamp_text,
                fill=config.COLORS["BLACK"],
                font=self.font_small,
            )

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
        """
        Wrap text to fit within max_width.

        Args:
            text: Text to wrap
            font: Font to use for measuring
            max_width: Maximum width in pixels

        Returns:
            List of wrapped lines
        """
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = font.getbbox(test_line)
            width = bbox[2] - bbox[0]

            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return lines

    def _convert_to_eink_palette(self, image: Image.Image) -> Image.Image:
        """
        Convert image to 6-color E Ink palette using Floyd-Steinberg dithering.

        The Waveshare 7.3" 6-color display supports:
        - Black, White, Red, Yellow, Blue, Green

        Args:
            image: RGB image

        Returns:
            RGB image with colors quantized to E Ink palette
        """
        # Convert to numpy array for faster processing
        img_array = np.array(image, dtype=np.float32)
        height, width = img_array.shape[:2]

        # E Ink palette
        palette = np.array([
            config.COLORS["BLACK"],
            config.COLORS["WHITE"],
            config.COLORS["RED"],
            config.COLORS["YELLOW"],
            config.COLORS["BLUE"],
            config.COLORS["GREEN"],
        ], dtype=np.float32)

        # Floyd-Steinberg dithering
        for y in range(height):
            for x in range(width):
                old_pixel = img_array[y, x]

                # Find closest palette color
                distances = np.sum((palette - old_pixel) ** 2, axis=1)
                closest_idx = np.argmin(distances)
                new_pixel = palette[closest_idx]

                img_array[y, x] = new_pixel

                # Calculate quantization error
                quant_error = old_pixel - new_pixel

                # Distribute error to neighboring pixels
                if x + 1 < width:
                    img_array[y, x + 1] += quant_error * 7 / 16

                if y + 1 < height:
                    if x > 0:
                        img_array[y + 1, x - 1] += quant_error * 3 / 16
                    img_array[y + 1, x] += quant_error * 5 / 16
                    if x + 1 < width:
                        img_array[y + 1, x + 1] += quant_error * 1 / 16

        # Clip values and convert back to uint8
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)

        return Image.fromarray(img_array)

    def render_error(self, error_message: str) -> Image.Image:
        """
        Render an error message.

        Args:
            error_message: Error message to display

        Returns:
            PIL Image (800x480, RGB mode)
        """
        image = Image.new("RGB", (self.width, self.height), config.COLORS["WHITE"])
        draw = ImageDraw.Draw(image)

        # Draw "ERROR" in red at top
        error_text = "ERROR"
        bbox = draw.textbbox((0, 0), error_text, font=self.font_large)
        text_width = bbox[2] - bbox[0]

        draw.text(
            ((self.width - text_width) // 2, 100),
            error_text,
            fill=config.COLORS["RED"],
            font=self.font_large,
        )

        # Draw error message
        wrapped_lines = self._wrap_text(error_message, self.font_medium, self.width - 80)
        y = 200

        for line in wrapped_lines:
            bbox = draw.textbbox((0, 0), line, font=self.font_medium)
            text_width = bbox[2] - bbox[0]

            draw.text(
                ((self.width - text_width) // 2, y),
                line,
                fill=config.COLORS["BLACK"],
                font=self.font_medium,
            )
            y += 50

        return self._convert_to_eink_palette(image)


if __name__ == "__main__":
    # Test renderer
    renderer = ContentRenderer()

    # Test with sample content
    sample_content = {
        "has_content": True,
        "content_type": "text",
        "text_content": "Hello from the family! This is a test message to see how text wraps and displays on the E Ink screen. It should look pretty good!",
        "stream_name": "Family Updates",
        "posted_at": "2025-11-02T13:00:00Z",
    }

    print("Rendering sample content...")
    image = renderer.render_content(sample_content)
    output_path = config.OUTPUT_DIR / "test_render.png"
    image.save(output_path)
    print(f"✓ Sample rendered to {output_path}")

    # Test with no content
    empty_content = {
        "has_content": False,
        "text_content": "No stream configured",
    }

    print("Rendering empty content...")
    image = renderer.render_content(empty_content)
    output_path = config.OUTPUT_DIR / "test_empty.png"
    image.save(output_path)
    print(f"✓ Empty content rendered to {output_path}")

    # Test error rendering
    print("Rendering error...")
    image = renderer.render_error("Network connection failed. Please check your internet connection.")
    output_path = config.OUTPUT_DIR / "test_error.png"
    image.save(output_path)
    print(f"✓ Error rendered to {output_path}")
