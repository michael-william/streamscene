"""Image processing utilities for E Ink display (800×480)."""

from enum import Enum
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class ImageFitMode(Enum):
    """How to fit images to display dimensions."""
    COVER = "cover"      # Crop to fill (may lose edges)
    CONTAIN = "contain"  # Fit with bars (shows full image)
    SMART = "smart"      # Hybrid: crop if <20% loss, else contain


def process_image_for_display(
    img: Image.Image,
    target_width: int = 800,
    target_height: int = 480,
    fit_mode: ImageFitMode = ImageFitMode.SMART,
    background_color: tuple = (255, 255, 255)
) -> Image.Image:
    """
    Process uploaded image to fit E Ink display dimensions.

    Handles different aspect ratios (landscape, square, portrait)
    with configurable fit modes.

    Args:
        img: PIL Image object (any size/ratio)
        target_width: Display width (default 800)
        target_height: Display height (default 480)
        fit_mode: COVER, CONTAIN, or SMART
        background_color: RGB tuple for letterbox bars (default white)

    Returns:
        PIL Image at exact target dimensions (800×480)
    """
    target_ratio = target_width / target_height
    img_ratio = img.width / img.height

    if fit_mode == ImageFitMode.COVER:
        return _crop_to_fill(img, target_width, target_height)

    elif fit_mode == ImageFitMode.CONTAIN:
        return _fit_with_bars(img, target_width, target_height, background_color)

    elif fit_mode == ImageFitMode.SMART:
        # Calculate content loss percentage
        if img_ratio > target_ratio:
            # Wider than display (landscape)
            scale = target_height / img.height
            new_width = img.width * scale
            crop_loss = (new_width - target_width) / new_width
        else:
            # Taller than display (portrait/square)
            scale = target_width / img.width
            new_height = img.height * scale
            crop_loss = (new_height - target_height) / new_height

        # Smart decision: crop if minimal loss, else letterbox
        if crop_loss < 0.20:  # Less than 20% content loss
            logger.info(f"Smart fit: CROP (loss: {crop_loss*100:.1f}%)")
            return _crop_to_fill(img, target_width, target_height)
        else:
            logger.info(f"Smart fit: CONTAIN (loss would be: {crop_loss*100:.1f}%)")
            return _fit_with_bars(img, target_width, target_height, background_color)


def _crop_to_fill(img: Image.Image, width: int, height: int) -> Image.Image:
    """Crop image to fill dimensions (center crop)."""
    target_ratio = width / height
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        # Image wider, crop sides
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    else:
        # Image taller, crop top/bottom
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, img.width, top + new_height))

    return img.resize((width, height), Image.Resampling.LANCZOS)


def _fit_with_bars(img: Image.Image, width: int, height: int, bg: tuple) -> Image.Image:
    """Fit image within dimensions, add letterbox/pillarbox bars."""
    scale = min(width / img.width, height / img.height)
    new_width = int(img.width * scale)
    new_height = int(img.height * scale)

    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Create canvas with background
    canvas = Image.new('RGB', (width, height), bg)

    # Paste centered
    x_offset = (width - new_width) // 2
    y_offset = (height - new_height) // 2
    canvas.paste(img_resized, (x_offset, y_offset))

    return canvas
