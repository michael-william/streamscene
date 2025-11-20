"""Client configuration

Configuration is loaded from environment variables and boot partition files.
"""

import os
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# Device UUID Loading
# ============================================================================

# Device UUID file locations
DEVICE_UUID_FILE = Path("/boot/firmware/streamscene-device.txt")  # Primary (read-only after boot)
DEVICE_UUID_FALLBACK = Path.home() / "streamscene-client" / ".device-uuid"  # Fallback (writable)


def load_device_uuid() -> str:
    """
    Load device UUID from boot partition file.

    Falls back to environment variable for development.
    If UUID doesn't exist, generates a new one and saves it.

    Returns:
        Device UUID string

    Raises:
        ValueError: If UUID cannot be loaded or generated
    """
    # Try loading from boot partition file (production)
    if DEVICE_UUID_FILE.exists():
        try:
            with open(DEVICE_UUID_FILE, 'r') as f:
                content = f.read().strip()

            # Handle both formats:
            # 1. Just the UUID: "1c91d1e9-3cc9-44ba-a008-9cdee188d90c"
            # 2. Key=value format: "DEVICE_UUID=1c91d1e9-3cc9-44ba-a008-9cdee188d90c"
            if '=' in content:
                # Parse key=value format
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('DEVICE_UUID='):
                        device_uuid = line.split('=', 1)[1].strip()
                        logger.info(f"[Config] Loaded device UUID from {DEVICE_UUID_FILE}")
                        return device_uuid
            else:
                # Plain UUID format
                logger.info(f"[Config] Loaded device UUID from {DEVICE_UUID_FILE}")
                return content

            raise ValueError(f"Invalid format in {DEVICE_UUID_FILE}")

        except Exception as e:
            logger.warning(f"[Config] Error reading UUID file: {e}")
            # Fall through to environment variable or generation

    # Fallback to environment variable (development)
    env_uuid = os.getenv("STREAMSCENE_DEVICE_ID", "")

    if env_uuid:
        logger.info("[Config] Loaded device UUID from environment variable (development mode)")
        return env_uuid

    # Check fallback location before generating new UUID
    if DEVICE_UUID_FALLBACK.exists():
        try:
            with open(DEVICE_UUID_FALLBACK, 'r') as f:
                fallback_uuid = f.read().strip()
            logger.info(f"[Config] Loaded device UUID from fallback location: {DEVICE_UUID_FALLBACK}")
            return fallback_uuid
        except Exception as e:
            logger.warning(f"[Config] Error reading fallback UUID file: {e}")

    # Generate new UUID if none exists (first boot)
    logger.info("[Config] No UUID found - generating new device UUID")
    new_uuid = str(uuid.uuid4())

    # Try to save to boot partition file (primary location)
    try:
        DEVICE_UUID_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DEVICE_UUID_FILE, 'w') as f:
            f.write(new_uuid + '\n')
        os.chmod(DEVICE_UUID_FILE, 0o644)
        logger.info(f"[Config] Generated and saved new device UUID to {DEVICE_UUID_FILE}")
        return new_uuid
    except Exception as e:
        logger.warning(f"[Config] Could not write to {DEVICE_UUID_FILE}: {e}")

    # Fall back to user-writable location
    try:
        DEVICE_UUID_FALLBACK.parent.mkdir(parents=True, exist_ok=True)
        with open(DEVICE_UUID_FALLBACK, 'w') as f:
            f.write(new_uuid + '\n')
        os.chmod(DEVICE_UUID_FALLBACK, 0o600)
        logger.info(f"[Config] Saved device UUID to fallback location: {DEVICE_UUID_FALLBACK}")
        return new_uuid
    except Exception as e:
        logger.error(f"[Config] Failed to save UUID to fallback location: {e}")
        logger.warning("[Config] UUID will not persist across reboots!")
        return new_uuid


# ============================================================================
# API Configuration
# ============================================================================

API_BASE_URL = os.getenv("STREAMSCENE_API_URL", "https://streamscene.dataandstories.com")
BASE_URL = API_BASE_URL  # Alias for compatibility

# Load device UUID (with error handling for import-time)
try:
    DEVICE_ID = load_device_uuid()
except ValueError as e:
    logger.warning(f"[Config] {e}")
    DEVICE_ID = ""  # Will fail validation later

API_KEY = os.getenv("STREAMSCENE_API_KEY", "")

# API Key file location (saved after registration)
API_KEY_FILE = Path.home() / "streamscene-client" / "device_api_key.txt"


def load_api_key() -> str:
    """
    Load API key from file or environment.

    Returns:
        API key if found, empty string otherwise
    """
    # Try loading from file (post-registration)
    if API_KEY_FILE.exists():
        try:
            with open(API_KEY_FILE, 'r') as f:
                key = f.read().strip()
                if key:
                    logger.info(f"[Config] Loaded API key from {API_KEY_FILE}")
                    return key
        except Exception as e:
            logger.warning(f"[Config] Error reading API key file: {e}")

    # Fall back to environment variable
    key = os.getenv("STREAMSCENE_API_KEY", "")
    if key:
        logger.info("[Config] Loaded API key from environment variable")

    return key


def save_api_key(api_key: str) -> bool:
    """
    Save API key to file after registration.

    Args:
        api_key: API key to save

    Returns:
        True if saved successfully
    """
    try:
        # Ensure directory exists
        API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(API_KEY_FILE, 'w') as f:
            f.write(api_key)

        # Set restrictive permissions (owner read/write only)
        API_KEY_FILE.chmod(0o600)

        logger.info(f"[Config] Saved API key to {API_KEY_FILE}")
        return True

    except Exception as e:
        logger.error(f"[Config] Error saving API key: {e}")
        return False


# Try to load API key (but don't fail if not present during setup)
if not API_KEY:
    API_KEY = load_api_key()

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

# 7-color E Ink palette (Waveshare 7.3" E variant - epd7in3e)
# Waveshare driver handles palette conversion - these are RGB reference colors
COLORS = {
    "BLACK": (0, 0, 0),
    "WHITE": (255, 255, 255),
    "RED": (255, 0, 0),
    "YELLOW": (255, 255, 0),
    "BLUE": (0, 0, 255),
    "GREEN": (0, 255, 0),
    "ORANGE": (255, 165, 0),
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

def validate_config(require_api_key: bool = False):
    """
    Validate configuration and raise errors if invalid.

    Args:
        require_api_key: If True, API key is required. If False, only warn if missing.
                        Set to False during setup phase before device registration.
    """
    errors = []
    warnings = []

    if not DEVICE_ID:
        errors.append("Device UUID is required (file /boot/firmware/streamscene-device.txt or STREAMSCENE_DEVICE_ID env var)")

    if not API_KEY:
        if require_api_key:
            errors.append("API key is required (device must be registered)")
        else:
            warnings.append("API key not found (device not yet registered)")

    if POLL_INTERVAL < 60:
        errors.append(f"POLL_INTERVAL must be at least 60 seconds (got {POLL_INTERVAL})")

    if DISPLAY_MODE not in ["headless", "eink"]:
        errors.append(f"DISPLAY_MODE must be 'headless' or 'eink' (got {DISPLAY_MODE})")

    if warnings:
        logger.warning("Configuration warnings:\n" + "\n".join(f"  - {w}" for w in warnings))

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
