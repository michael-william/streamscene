"""
PIL-based E Ink image renderer for StreamScene posts.

This module generates 800x480 PNG images for Waveshare 7.3" E Ink displays.
Supports two post types:
1. Picture posts - uploaded image + text comment
2. Meme posts - text overlay on background image

Inspired by InkyPi's PIL rendering approach.
"""

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageEnhance
from typing import Optional, Tuple, Literal
from pathlib import Path
import textwrap
import re
from datetime import datetime

# Import new modular image processing
from streamscene.core.image_processing import process_image_for_display, ImageFitMode

# Display constants
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

# Layout constants
TOP_BAR_HEIGHT = 60
PADDING = 40
CONTENT_AREA_WIDTH = DISPLAY_WIDTH - (2 * PADDING)
CONTENT_AREA_HEIGHT = DISPLAY_HEIGHT - TOP_BAR_HEIGHT - PADDING

# Font size ranges
MIN_FONT_SIZE = 20
MAX_FONT_SIZE = 60  # Reduced from 72 for better proportions in narrow text column
TOP_BAR_FONT_SIZE = 24

# Portrait layout split (60/40)
PORTRAIT_IMAGE_WIDTH = 480
PORTRAIT_TEXT_WIDTH = 280  # Remaining space after padding


def parse_markdown_to_plain_text(text: str) -> str:
    """
    Convert markdown syntax to plain text for E Ink rendering.

    Removes markdown formatting characters while preserving content:
    - **bold** → bold
    - *italic* → italic
    - [link text](url) → link text

    Note: E Ink rendering currently uses single-font rendering.
    Future enhancement: Support actual bold/italic fonts with mixed text rendering.

    Args:
        text: Markdown-formatted text

    Returns:
        Plain text with markdown syntax removed
    """
    if not text:
        return ""

    # Remove bold: **text** → text
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)

    # Remove italic: *text* → text (but not ** from bold)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)

    # Remove links: [text](url) → text
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)

    return text


class ImageRenderer:
    """Renders StreamScene posts to 800x480 PNG images using PIL."""

    def __init__(self, fonts_dir: str = "/root/streamscene/fonts"):
        """Initialize renderer with font directory."""
        self.fonts_dir = Path(fonts_dir)
        self._font_cache = {}

    def _get_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """Get cached font at specified size."""
        font_name = "OpenSans-Bold.ttf" if bold else "OpenSans-Regular.ttf"
        cache_key = (font_name, size)

        if cache_key not in self._font_cache:
            font_path = self.fonts_dir / font_name
            if not font_path.exists():
                # Fallback to default font if custom font not found
                self._font_cache[cache_key] = ImageFont.load_default()
            else:
                self._font_cache[cache_key] = ImageFont.truetype(str(font_path), size)

        return self._font_cache[cache_key]

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
        """
        Wrap text to fit within max_width, breaking at word boundaries.

        Returns multiline string with newlines.
        """
        words = text.split()
        lines = []
        current_line = []

        # Use a temporary draw object for text measurement
        temp_img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(temp_img)

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]

            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return "\n".join(lines)

    def _calculate_optimal_font_size(
        self,
        text: str,
        max_width: int,
        max_height: int,
        min_size: int = MIN_FONT_SIZE,
        max_size: int = MAX_FONT_SIZE
    ) -> Tuple[ImageFont.FreeTypeFont, str]:
        """
        Binary search for largest font size that fits text within constraints.

        Returns (font, wrapped_text) tuple.
        """
        temp_img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(temp_img)

        best_font = None
        best_wrapped = ""
        best_size = min_size

        # Binary search for optimal size
        low, high = min_size, max_size

        while low <= high:
            mid = (low + high) // 2
            font = self._get_font(mid)

            # Wrap text at this font size
            wrapped = self._wrap_text(text, font, max_width)

            # Measure wrapped text
            bbox = draw.multiline_textbbox((0, 0), wrapped, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Check if it fits
            if text_width <= max_width and text_height <= max_height:
                # This size works, try larger
                best_font = font
                best_wrapped = wrapped
                best_size = mid
                low = mid + 1
            else:
                # Too large, try smaller
                high = mid - 1

        # Return best fit (or minimum if nothing fits)
        if best_font is None:
            best_font = self._get_font(min_size)
            best_wrapped = self._wrap_text(text, best_font, max_width)

        return best_font, best_wrapped

    def _draw_top_bar(
        self,
        draw: ImageDraw.Draw,
        stream_name: str,
        author_name: str,
        date: datetime,
        text_color: Tuple[int, int, int] = (0, 0, 0)
    ):
        """
        Draw top info bar: Stream name (left), Author (center), Date (right).
        """
        font = self._get_font(TOP_BAR_FONT_SIZE, bold=True)

        # Handle None values
        stream_name = stream_name or "Stream"
        author_name = author_name or "Anonymous"

        # Stream name (left)
        draw.text(
            (PADDING, TOP_BAR_HEIGHT // 2),
            stream_name,
            font=font,
            anchor="lm",  # left-middle
            fill=text_color
        )

        # Author name (center)
        draw.text(
            (DISPLAY_WIDTH // 2, TOP_BAR_HEIGHT // 2),
            author_name,
            font=font,
            anchor="mm",  # middle-middle
            fill=text_color
        )

        # Date (right)
        date_str = date.strftime("%b %d, %Y")
        draw.text(
            (DISPLAY_WIDTH - PADDING, TOP_BAR_HEIGHT // 2),
            date_str,
            font=font,
            anchor="rm",  # right-middle
            fill=text_color
        )

    def _draw_text_with_outline(
        self,
        draw: ImageDraw.Draw,
        position: Tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont,
        text_color: Tuple[int, int, int],
        outline_color: Tuple[int, int, int],
        outline_width: int = 2,
        anchor: str = "mm"
    ):
        """
        Draw text with outline for better visibility on backgrounds.
        """
        # Handle None or empty text
        if not text:
            text = ""

        x, y = position

        # Draw outline (8-directional)
        for dx in [-outline_width, 0, outline_width]:
            for dy in [-outline_width, 0, outline_width]:
                if dx != 0 or dy != 0:
                    draw.multiline_text(
                        (x + dx, y + dy),
                        text,
                        font=font,
                        anchor=anchor,
                        fill=outline_color,
                        align="center"
                    )

        # Draw main text on top
        draw.multiline_text(
            position,
            text,
            font=font,
            anchor=anchor,
            fill=text_color,
            align="center"
        )

    def render_picture_post(
        self,
        image_path: Optional[str] = None,
        image: Optional[Image.Image] = None,
        text_content: str = "",
        stream_name: str = "",
        author_name: str = "",
        post_date: Optional[datetime] = None,
        text_color: Tuple[int, int, int] = (0, 0, 0),
        outline_color: Tuple[int, int, int] = (255, 255, 255)
    ) -> Image.Image:
        """
        Render 'Post a Picture' type post.

        Supports both file path (backward compat) and PIL Image (new flow).

        Layout (unified for all image orientations):
        - Left container (60%): Image centered within 480px wide area
        - Right container (40%): Text centered within 280px wide area
        - White background
        - Top bar with stream/author/date
        """
        # Load image from either path or provided PIL Image
        if image is not None:
            uploaded_img = image
        elif image_path is not None:
            uploaded_img = Image.open(image_path)
        else:
            raise ValueError("Must provide either image_path or image parameter")

        # Create white canvas
        canvas = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), "white")
        draw = ImageDraw.Draw(canvas)

        # Draw top bar
        if post_date is None:
            post_date = datetime.now()
        self._draw_top_bar(draw, stream_name, author_name, post_date)

        # Parse markdown to plain text for E Ink rendering
        plain_text = parse_markdown_to_plain_text(text_content)

        # Use unified layout for all image orientations
        self._render_unified_layout(
            canvas, draw, uploaded_img, plain_text,
            text_color, outline_color
        )

        return canvas

    def _render_unified_layout(
        self,
        canvas: Image.Image,
        draw: ImageDraw.Draw,
        uploaded_img: Image.Image,
        text_content: str,
        text_color: Tuple[int, int, int],
        outline_color: Tuple[int, int, int]
    ):
        """
        Unified layout for all image orientations (landscape, portrait, square).

        Layout:
        - Left container (60%): 480px wide, image centered within it
        - Right container (40%): 280px wide, text centered within it
        - 20px gap between containers
        """
        content_top = TOP_BAR_HEIGHT + PADDING
        content_height = DISPLAY_HEIGHT - content_top - PADDING

        # Left container: 480px wide (60% of display)
        image_container_width = PORTRAIT_IMAGE_WIDTH
        image_area_width = image_container_width - PADDING  # 440px for image with padding

        # Resize image to fit within left container
        resized_img = ImageOps.contain(uploaded_img, (image_area_width, content_height))

        # Center image within left container (both horizontally and vertically)
        img_x = PADDING + (image_area_width - resized_img.width) // 2
        img_y = content_top + (content_height - resized_img.height) // 2

        canvas.paste(resized_img, (img_x, img_y))

        # Right container: Text (280px wide with 20px gap)
        text_x = PORTRAIT_IMAGE_WIDTH + 20
        text_max_width = PORTRAIT_TEXT_WIDTH - 40  # 240px for text with padding

        font, wrapped_text = self._calculate_optimal_font_size(
            text_content,
            max_width=text_max_width,
            max_height=content_height
        )

        # Center text vertically in right container
        self._draw_text_with_outline(
            draw,
            position=(text_x + text_max_width // 2, content_top + content_height // 2),
            text=wrapped_text,
            font=font,
            text_color=text_color,
            outline_color=outline_color,
            anchor="mm"
        )

    def render_meme_post(
        self,
        background_image_path: str,
        text_content: str,
        stream_name: str,
        author_name: str,
        post_date: datetime,
        text_color: Tuple[int, int, int] = (255, 255, 255),
        outline_color: Tuple[int, int, int] = (0, 0, 0)
    ) -> Image.Image:
        """
        Render 'Meme It' type post.

        Layout:
        - Background image fills entire screen (800x480)
        - Text overlaid in center with outline
        - Top bar with stream/author/date (with outline for visibility)
        """
        # Load and resize background to fill display
        background = Image.open(background_image_path)
        background = ImageOps.fit(background, (DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.LANCZOS)

        # Convert to RGB if needed (some backgrounds might be RGBA/P)
        if background.mode != "RGB":
            background = background.convert("RGB")

        draw = ImageDraw.Draw(background)

        # Draw top bar with outline for visibility
        top_bar_font = self._get_font(TOP_BAR_FONT_SIZE, bold=True)

        # Stream name (left)
        self._draw_text_with_outline(
            draw,
            position=(PADDING, TOP_BAR_HEIGHT // 2),
            text=stream_name,
            font=top_bar_font,
            text_color=text_color,
            outline_color=outline_color,
            anchor="lm"
        )

        # Author name (center)
        self._draw_text_with_outline(
            draw,
            position=(DISPLAY_WIDTH // 2, TOP_BAR_HEIGHT // 2),
            text=author_name,
            font=top_bar_font,
            text_color=text_color,
            outline_color=outline_color,
            anchor="mm"
        )

        # Date (right)
        date_str = post_date.strftime("%b %d, %Y")
        self._draw_text_with_outline(
            draw,
            position=(DISPLAY_WIDTH - PADDING, TOP_BAR_HEIGHT // 2),
            text=date_str,
            font=top_bar_font,
            text_color=text_color,
            outline_color=outline_color,
            anchor="rm"
        )

        # Calculate text area (center of screen, below top bar)
        text_area_top = TOP_BAR_HEIGHT + PADDING
        text_area_height = DISPLAY_HEIGHT - text_area_top - PADDING
        text_area_width = DISPLAY_WIDTH - (2 * PADDING)

        # Parse markdown to plain text for E Ink rendering
        plain_text = parse_markdown_to_plain_text(text_content)

        # Calculate optimal font size for main text
        font, wrapped_text = self._calculate_optimal_font_size(
            plain_text,
            max_width=text_area_width,
            max_height=text_area_height
        )

        # Draw main text in center with outline
        self._draw_text_with_outline(
            draw,
            position=(DISPLAY_WIDTH // 2, text_area_top + text_area_height // 2),
            text=wrapped_text,
            font=font,
            text_color=text_color,
            outline_color=outline_color,
            outline_width=3,  # Thicker outline for memes
            anchor="mm"
        )

        return background

    def render_post(
        self,
        post_type: Literal["picture", "meme"],
        text_content: str,
        stream_name: str,
        author_name: str,
        post_date: datetime,
        image_path: Optional[str] = None,
        background_path: Optional[str] = None,
        text_color: Tuple[int, int, int] = (0, 0, 0),
        outline_color: Tuple[int, int, int] = (255, 255, 255)
    ) -> Image.Image:
        """
        Main entry point for rendering any post type.

        Args:
            post_type: "picture" or "meme"
            text_content: Post text (max 160 chars)
            stream_name: Name of the stream
            author_name: Post author display name
            post_date: When post was created
            image_path: Path to uploaded image (required for picture posts)
            background_path: Path to background image (required for meme posts)
            text_color: RGB tuple for text color
            outline_color: RGB tuple for outline color

        Returns:
            PIL Image object (800x480 RGB)
        """
        if post_type == "picture":
            if not image_path:
                raise ValueError("image_path required for picture posts")
            return self.render_picture_post(
                image_path, text_content, stream_name, author_name,
                post_date, text_color, outline_color
            )
        elif post_type == "meme":
            if not background_path:
                raise ValueError("background_path required for meme posts")
            return self.render_meme_post(
                background_path, text_content, stream_name, author_name,
                post_date, text_color, outline_color
            )
        else:
            raise ValueError(f"Unknown post_type: {post_type}")


# Utility functions for color conversion

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color (#RRGGBB) to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex color (#RRGGBB)."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)
