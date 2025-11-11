"""Content rendering for E Ink display

Renders content (text, images, etc.) to 800x480 images optimized for
6-color E Ink displays.
"""

from typing import Optional, Tuple
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

import config


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
        Convert image to 4-color E Ink palette using PIL's fast quantize().

        The Waveshare 7.3" G variant (epd7in3g) supports:
        - Black, White, Yellow, Red (4 colors, not 6)

        This uses PIL's built-in quantize() with a custom palette, which is
        much faster than manual Floyd-Steinberg dithering in Python.

        Args:
            image: RGB image

        Returns:
            RGB image with colors quantized to E Ink palette
        """
        # Create a palette image with the 4 colors supported by epd7in3g
        pal_image = Image.new("P", (1, 1))
        # Palette format: (R, G, B) tuples for each color
        # BLACK=0x000000, WHITE=0xffffff, YELLOW=0x00ffff (BGR), RED=0x0000ff (BGR)
        # In RGB: BLACK=(0,0,0), WHITE=(255,255,255), YELLOW=(255,255,0), RED=(255,0,0)
        palette_colors = (
            0, 0, 0,           # Black
            255, 255, 255,     # White
            255, 255, 0,       # Yellow
            255, 0, 0          # Red
        )
        # Pad remaining 252 colors with black
        pal_image.putpalette(palette_colors + (0, 0, 0) * 252)

        # Convert to RGB and quantize using the palette with dithering
        image_quantized = image.convert("RGB").quantize(palette=pal_image, dither=Image.Dither.FLOYDSTEINBERG)

        # Convert back to RGB mode for consistency
        return image_quantized.convert("RGB")

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

    def render_message(
        self, title: str, message: str, color: str = "black"
    ) -> Image.Image:
        """
        Render a simple message with title and body text.

        Args:
            title: Title text
            message: Body message
            color: Color for title ("black", "red", "blue", "green")

        Returns:
            PIL Image (800x480, RGB mode)
        """
        image = Image.new("RGB", (self.width, self.height), config.COLORS["WHITE"])
        draw = ImageDraw.Draw(image)

        # Map color names to config colors
        color_map = {
            "black": config.COLORS["BLACK"],
            "red": config.COLORS["RED"],
            "blue": config.COLORS["BLUE"],
            "green": config.COLORS["GREEN"],
            "yellow": config.COLORS["YELLOW"],
        }
        title_color = color_map.get(color.lower(), config.COLORS["BLACK"])

        # Draw title at top
        bbox = draw.textbbox((0, 0), title, font=self.font_large)
        text_width = bbox[2] - bbox[0]

        draw.text(
            ((self.width - text_width) // 2, 80),
            title,
            fill=title_color,
            font=self.font_large,
        )

        # Draw horizontal line
        draw.line([(100, 150), (self.width - 100, 150)], fill=config.COLORS["BLACK"], width=2)

        # Draw message
        wrapped_lines = self._wrap_text(message, self.font_medium, self.width - 100)
        y = 180

        for line in wrapped_lines:
            bbox = draw.textbbox((0, 0), line, font=self.font_medium)
            text_width = bbox[2] - bbox[0]

            draw.text(
                ((self.width - text_width) // 2, y),
                line,
                fill=config.COLORS["BLACK"],
                font=self.font_medium,
            )
            y += 40

        return self._convert_to_eink_palette(image)

    def render_qr_code(
        self, url: str, title: str = "Scan QR Code", instructions: str = ""
    ) -> Image.Image:
        """
        Render a QR code with title and instructions.

        Args:
            url: URL to encode in QR code
            title: Title text above QR code
            instructions: Instructions text below QR code

        Returns:
            PIL Image (800x480, RGB mode)
        """
        try:
            import qrcode
        except ImportError:
            # If qrcode library not available, render error
            return self.render_error(
                "QR code library not installed.\nInstall with: pip install qrcode"
            )

        image = Image.new("RGB", (self.width, self.height), config.COLORS["WHITE"])
        draw = ImageDraw.Draw(image)

        # Draw title
        bbox = draw.textbbox((0, 0), title, font=self.font_large)
        title_width = bbox[2] - bbox[0]

        draw.text(
            ((self.width - title_width) // 2, 40),
            title,
            fill=config.COLORS["BLACK"],
            font=self.font_large,
        )

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=5,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Resize QR code to fit nicely (300x300 pixels)
        qr_size = 300
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.NEAREST)

        # Paste QR code in center
        qr_x = (self.width - qr_size) // 2
        qr_y = 120

        image.paste(qr_img, (qr_x, qr_y))

        # Draw instructions below QR code
        if instructions:
            wrapped_lines = self._wrap_text(instructions, self.font_small, self.width - 100)
            y = qr_y + qr_size + 20

            for line in wrapped_lines:
                # Left-align instructions
                draw.text(
                    (50, y),
                    line,
                    fill=config.COLORS["BLACK"],
                    font=self.font_small,
                )
                y += 25

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
