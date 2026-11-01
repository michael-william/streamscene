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
import signal
import time
import logging

from PIL import Image

import config

# Get logger for display operations
display_logger = logging.getLogger("streamscene.display")


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
    Automatically cleans up old frames to prevent disk space issues.
    """

    def __init__(self, output_dir: Optional[Path] = None, max_frames: int = 50):
        """
        Initialize headless display.

        Args:
            output_dir: Directory to save PNG files (default: config.OUTPUT_DIR)
            max_frames: Maximum frames to keep (default: 50, ~2.5MB)
        """
        self.output_dir = output_dir or config.OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.frame_count = 0
        self.max_frames = max_frames

        print(f"[Display] Headless mode - saving to {self.output_dir} (max {max_frames} frames)")

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

        # Cleanup old frames to prevent disk space issues
        self._cleanup_old_frames()

    def _cleanup_old_frames(self) -> None:
        """Remove old frame files, keeping only the most recent ones."""
        try:
            # Get all frame files (exclude latest.png)
            frames = sorted(
                [f for f in self.output_dir.glob("frame_*.png")],
                key=lambda f: f.stat().st_mtime
            )

            # Remove oldest frames if over limit
            if len(frames) > self.max_frames:
                to_remove = frames[:-self.max_frames]
                for f in to_remove:
                    f.unlink()
                print(f"[Display] Cleaned up {len(to_remove)} old frames")
        except Exception as e:
            print(f"[Display] Warning: cleanup failed: {e}")

    def clear(self) -> None:
        """Clear (simulated)."""
        print("[Display] Clear display (headless - no-op)")

    def sleep(self) -> None:
        """Sleep (simulated)."""
        print("[Display] Sleep mode (headless - no-op)")


# ============================================================================
# E INK DISPLAY ADAPTER (FOR HARDWARE)
# ============================================================================

class TimeoutError(Exception):
    """Raised when operation times out."""
    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise TimeoutError("Operation timed out")


class EInkDisplay(DisplayAdapter):
    """
    E Ink display adapter for Waveshare 7.3" 7-color E-Paper HAT.

    Requires:
    - Raspberry Pi (tested on Pi Zero 2 WH)
    - Waveshare 7.3inch e-Paper HAT (E variant - 7 colors)
    - waveshare-epd library installed
    - SPI enabled in raspi-config
    - Run with sudo for GPIO access
    """

    def __init__(self):
        """Initialize E Ink display with timeout and retry logic."""
        try:
            # Import Waveshare library (only when this class is used)
            from waveshare_epd import epd7in3e
            self.epd = epd7in3e.EPD()

            display_logger.info("Initializing Waveshare 7.3\" E Ink display (E variant - 7 colors)")
            print("[Display] Initializing Waveshare 7.3\" E Ink display (E variant - 7 colors)...")

            # Initialize display with timeout and retry
            self._init_with_retry(max_attempts=3, timeout_seconds=60)

            display_logger.info("E Ink display initialized successfully")
            print("[Display] E Ink display ready")

        except ImportError:
            error_msg = "waveshare-epd library not installed. Install with: pip install waveshare-epd"
            display_logger.error(error_msg)
            raise ImportError(error_msg)
        except Exception as e:
            error_msg = f"Failed to initialize E Ink display: {e}"
            display_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def _init_with_retry(self, max_attempts: int = 3, timeout_seconds: int = 60):
        """
        Initialize E Ink display with timeout and retry logic.

        Args:
            max_attempts: Maximum number of initialization attempts
            timeout_seconds: Timeout for each attempt in seconds

        Raises:
            TimeoutError: If initialization times out on all attempts
            RuntimeError: If initialization fails on all attempts
        """
        for attempt in range(1, max_attempts + 1):
            try:
                display_logger.info(f"Initialization attempt {attempt}/{max_attempts}")

                # Set up timeout alarm
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout_seconds)

                try:
                    # Initialize display (this can hang without network/NTP)
                    display_logger.debug("Calling epd.init()...")
                    self.epd.init()
                    display_logger.debug("epd.init() completed")

                    # Clear display (takes ~30 seconds)
                    display_logger.debug("Calling epd.Clear()...")
                    self.epd.Clear()
                    display_logger.debug("epd.Clear() completed")

                    # Success - cancel alarm and return
                    signal.alarm(0)
                    display_logger.info(f"Display initialized successfully on attempt {attempt}")
                    return

                finally:
                    # Always cancel alarm
                    signal.alarm(0)

            except TimeoutError:
                display_logger.warning(
                    f"Display initialization timed out after {timeout_seconds}s "
                    f"(attempt {attempt}/{max_attempts})"
                )

                if attempt < max_attempts:
                    # Wait before retry with exponential backoff
                    wait_time = 2 ** attempt
                    display_logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    # Final attempt failed
                    error_msg = (
                        f"E Ink display initialization failed after {max_attempts} attempts. "
                        "This may be caused by missing network connection (NTP time sync required). "
                        "Ensure network is available or check hardware connections."
                    )
                    display_logger.error(error_msg)
                    raise RuntimeError(error_msg)

            except Exception as e:
                display_logger.warning(
                    f"Display initialization error on attempt {attempt}/{max_attempts}: {e}"
                )

                if attempt < max_attempts:
                    wait_time = 2 ** attempt
                    display_logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    error_msg = f"E Ink display initialization failed after {max_attempts} attempts: {e}"
                    display_logger.error(error_msg)
                    raise RuntimeError(error_msg)

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


class InkyDisplay(DisplayAdapter):
    """
    Pimoroni Inky Impression adapter (e.g. 7.3" Spectra, E673 panel).

    The board carries an ID EEPROM on I2C, so the exact model is read with
    inky.auto. Requires dtparam=i2c_arm=on and dtoverlay=spi0-0cs (the
    library drives chip-select on GPIO8 itself).
    """

    # inky's quantisation saturation: 0.5 is its default; Spectra panels look
    # washed out below that.
    SATURATION = float(__import__("os").getenv("STREAMSCENE_INKY_SATURATION", "0.5"))

    def __init__(self):
        try:
            from inky.auto import auto
        except ImportError as e:
            raise ImportError(f"inky library not installed: {e}")

        self.inky = auto()
        self.model = type(self.inky).__module__.rsplit(".", 1)[-1]
        display_logger.info(
            f"Inky display initialised: {self.model} {self.inky.width}x{self.inky.height}"
        )
        print(f"[Display] Inky {self.model} {self.inky.width}x{self.inky.height} ready")

    def show(self, image: Image.Image) -> None:
        print("[Display] Updating Inky display (takes ~30 seconds)...")
        size = (self.inky.width, self.inky.height)
        if image.size != size:
            image = image.resize(size, Image.Resampling.LANCZOS)
        if image.mode != "RGB":
            image = image.convert("RGB")
        self.inky.set_image(image, saturation=self.SATURATION)
        self.inky.show()
        print("[Display] Inky display updated")

    def clear(self) -> None:
        print("[Display] Clearing Inky display...")
        self.inky.set_image(Image.new("RGB", (self.inky.width, self.inky.height), "white"))
        self.inky.show()

    def sleep(self) -> None:
        # The Inky driver powers the panel off after each refresh; nothing to do.
        pass


def detect_eink_driver() -> str:
    """
    Decide which E Ink driver to use.

    STREAMSCENE_DISPLAY_DRIVER=waveshare|inky forces one. Otherwise ("auto"),
    a Pimoroni Inky is recognised by its ID EEPROM at I2C 0x50; anything else
    is assumed to be the Waveshare HAT, which has no ID chip.
    """
    forced = config.DISPLAY_DRIVER
    if forced in ("waveshare", "inky"):
        display_logger.info(f"Display driver forced: {forced}")
        return forced
    if forced != "auto":
        display_logger.warning(f"Unknown STREAMSCENE_DISPLAY_DRIVER={forced!r}, auto-detecting")

    try:
        from inky.eeprom import read_eeprom
        ee = read_eeprom()
    except Exception as e:  # no I2C bus, inky missing, ...
        display_logger.info(f"Inky EEPROM probe failed ({e}); assuming Waveshare")
        return "waveshare"
    if ee is None:
        display_logger.info("No Inky EEPROM on I2C; assuming Waveshare")
        return "waveshare"
    display_logger.info(f"Inky EEPROM found: {ee.get_variant()}")
    return "inky"


def get_display(mode: Optional[str] = None) -> DisplayAdapter:
    """
    Factory function to get appropriate display adapter.

    Args:
        mode: "headless", "eink" (auto-detect panel), "waveshare" or "inky";
              defaults to config.DISPLAY_MODE

    Raises:
        ValueError: If mode is invalid
    """
    mode = mode or config.DISPLAY_MODE

    if mode == "headless":
        return HeadlessDisplay()
    if mode == "eink":
        mode = detect_eink_driver()
    if mode == "waveshare":
        return EInkDisplay()
    if mode == "inky":
        return InkyDisplay()
    raise ValueError(
        f"Invalid display mode: {mode}. Must be 'headless', 'eink', 'waveshare' or 'inky'"
    )
