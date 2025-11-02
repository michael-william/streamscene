"""Client configuration

Configuration is loaded from environment variables with sensible defaults.
"""

import os
from pathlib import Path

# ============================================================================
# API Configuration
# ============================================================================

API_BASE_URL = os.getenv("STREAMSCENE_API_URL", "http://localhost:8000")
DEVICE_ID = os.getenv("STREAMSCENE_DEVICE_ID", "")
API_KEY = os.getenv("STREAMSCENE_API_KEY", "")

# ============================================================================
# Display Configuration
# ============================================================================

# Display mode: "headless" or "eink"
# Use "headless" for testing without hardware (saves PNG files)
# Use "eink" when running on Raspberry Pi with E Ink display
DISPLAY_MODE = os.getenv("STREAMSCENE_DISPLAY_MODE", "headless")

# Output directory for headless mode
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# E Ink display specifications
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

# 6-color E Ink palette (Waveshare 7.3" 6-color)
COLORS = {
    "BLACK": (0, 0, 0),
    "WHITE": (255, 255, 255),
    "RED": (255, 0, 0),
    "YELLOW": (255, 255, 0),
    "BLUE": (0, 0, 255),
    "GREEN": (0, 255, 0),
}

# ============================================================================
# Polling Configuration
# ============================================================================

# How often to check for new content (seconds)
# Minimum 60 seconds due to ~30 second E Ink refresh time
POLL_INTERVAL = int(os.getenv("STREAMSCENE_POLL_INTERVAL", "60"))

# How often to send heartbeat (seconds)
HEARTBEAT_INTERVAL = int(os.getenv("STREAMSCENE_HEARTBEAT_INTERVAL", "300"))  # 5 minutes

# ============================================================================
# Network Configuration
# ============================================================================

# Request timeout (seconds)
REQUEST_TIMEOUT = int(os.getenv("STREAMSCENE_REQUEST_TIMEOUT", "10"))

# Maximum retry attempts
MAX_RETRIES = int(os.getenv("STREAMSCENE_MAX_RETRIES", "3"))

# Retry backoff multiplier
RETRY_BACKOFF = float(os.getenv("STREAMSCENE_RETRY_BACKOFF", "2.0"))

# ============================================================================
# Validation
# ============================================================================

def validate_config():
    """Validate configuration and raise errors if invalid."""
    errors = []

    if not DEVICE_ID:
        errors.append("STREAMSCENE_DEVICE_ID environment variable is required")

    if not API_KEY:
        errors.append("STREAMSCENE_API_KEY environment variable is required")

    if POLL_INTERVAL < 60:
        errors.append(f"POLL_INTERVAL must be at least 60 seconds (got {POLL_INTERVAL})")

    if DISPLAY_MODE not in ["headless", "eink"]:
        errors.append(f"DISPLAY_MODE must be 'headless' or 'eink' (got {DISPLAY_MODE})")

    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))


if __name__ == "__main__":
    # Test configuration
    try:
        validate_config()
        print("✓ Configuration valid")
        print(f"  API: {API_BASE_URL}")
        print(f"  Device ID: {DEVICE_ID}")
        print(f"  Display Mode: {DISPLAY_MODE}")
        print(f"  Poll Interval: {POLL_INTERVAL}s")
    except ValueError as e:
        print(f"✗ {e}")
