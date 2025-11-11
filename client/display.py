"""Display adapters for E Ink and testing

This module provides a clean abstraction for display output, allowing the client
to work in both testing mode (PNG output) and production mode (E Ink display).

# ============================================================================
# HARDWARE SWITCH INSTRUCTIONS
# ============================================================================
#
# TESTING MODE (current default):
#   - Uses HeadlessDisplay
#   - Saves images to client/output/ directory as PNG files
#   - No hardware required
#   - Perfect for development and testing
#
# HARDWARE MODE (when Raspberry Pi + E Ink arrives):
#   1. Install Waveshare library:
#      pip install waveshare-epd
#
#   2. Enable SPI on Raspberry Pi:
#      sudo raspi-config → Interface Options → SPI → Enable
#
#   3. In this file, uncomment the EInkDisplay class implementation
#      (search for "UNCOMMENT THIS SECTION")
#
#   4. In main.py, change:
#      display = HeadlessDisplay()
#      to:
#      display = EInkDisplay()
#
#   5. Run with sudo (GPIO access required):
#      sudo python3 main.py
#
# That's it! Everything else stays the same.
#
# ============================================================================
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image

import config


class DisplayAdapter(ABC):
    """Base class for display adapters."""

    @abstractmethod
    def show(self, image: Image.Image) -> None:
        """
        Display an image.

        Args:
            image: PIL Image object (800x480, RGB mode)
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear the display."""
        pass

    @abstractmethod
    def sleep(self) -> None:
        """Put display into low-power sleep mode."""
        pass


class HeadlessDisplay(DisplayAdapter):
    """
    Headless display adapter for testing without hardware.

    Saves images to the output directory as PNG files.
    Perfect for development and verifying layout/colors.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize headless display.

        Args:
            output_dir: Directory to save PNG files (default: config.OUTPUT_DIR)
        """
        self.output_dir = output_dir or config.OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.frame_count = 0

        print(f"[Display] Headless mode - saving to {self.output_dir}")

    def show(self, image: Image.Image) -> None:
        """Save image as PNG file."""
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"frame_{self.frame_count:04d}_{timestamp}.png"
        filepath = self.output_dir / filename

        # Save image
        image.save(filepath, "PNG")
        self.frame_count += 1

        print(f"[Display] Saved frame to {filepath}")

        # Also save as "latest.png" for easy viewing
        latest_path = self.output_dir / "latest.png"
        image.save(latest_path, "PNG")

    def clear(self) -> None:
        """Clear (simulated)."""
        print("[Display] Clear display (headless - no-op)")

    def sleep(self) -> None:
        """Sleep (simulated)."""
        print("[Display] Sleep mode (headless - no-op)")


# ============================================================================
# E INK DISPLAY ADAPTER (FOR HARDWARE)
# ============================================================================

class EInkDisplay(DisplayAdapter):
    """
    E Ink display adapter for Waveshare 7.3" 4-color E-Paper HAT.

    Requires:
    - Raspberry Pi (tested on Pi Zero 2 WH)
    - Waveshare 7.3inch e-Paper HAT (G variant - 4 colors)
    - waveshare-epd library installed
    - SPI enabled in raspi-config
    - Run with sudo for GPIO access
    """

    def __init__(self):
        """Initialize E Ink display."""
        try:
            # Import Waveshare library (only when this class is used)
            from waveshare_epd import epd7in3g
            self.epd = epd7in3g.EPD()

            print("[Display] Initializing Waveshare 7.3\" E Ink display (G variant)...")
            self.epd.init()
            self.epd.Clear()
            print("[Display] E Ink display ready")

        except ImportError:
            raise ImportError(
                "waveshare-epd library not installed. "
                "Install with: pip install waveshare-epd"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize E Ink display: {e}")

    def show(self, image: Image.Image) -> None:
        """Display image on E Ink screen."""
        print("[Display] Updating E Ink display...")
        print("[Display] (This takes ~30 seconds - E Ink refresh is slow)")

        # Ensure image is correct size
        if image.size != (config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT):
            image = image.resize(
                (config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT),
                Image.Resampling.LANCZOS
            )

        # Convert image to format expected by Waveshare library
        # The library expects RGB mode
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Display the image
        self.epd.display(self.epd.getbuffer(image))
        print("[Display] E Ink display updated")

    def clear(self) -> None:
        """Clear the E Ink display to white."""
        print("[Display] Clearing E Ink display...")
        self.epd.Clear()
        print("[Display] E Ink display cleared")

    def sleep(self) -> None:
        """Put E Ink display into low-power sleep mode."""
        print("[Display] Putting E Ink display to sleep...")
        self.epd.sleep()
        print("[Display] E Ink display in sleep mode")

    def __del__(self):
        """Cleanup on destruction."""
        try:
            if hasattr(self, 'epd'):
                self.epd.sleep()
        except:
            pass

# ============================================================================


def get_display(mode: Optional[str] = None) -> DisplayAdapter:
    """
    Factory function to get appropriate display adapter.

    Args:
        mode: Display mode ("headless" or "eink"), defaults to config.DISPLAY_MODE

    Returns:
        DisplayAdapter: Configured display adapter

    Raises:
        ValueError: If mode is invalid
    """
    mode = mode or config.DISPLAY_MODE

    if mode == "headless":
        return HeadlessDisplay()
    elif mode == "eink":
        return EInkDisplay()
    else:
        raise ValueError(f"Invalid display mode: {mode}. Must be 'headless' or 'eink'")
