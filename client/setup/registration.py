"""
Device Registration

Handles device registration status checking by polling the server.
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


def check_registration(api_client) -> bool:
    """
    Check if device is registered with the server.

    Polls the /api/devices/{id}/registration-status endpoint (unauthenticated).
    - If registered and API key available: saves API key and returns True
    - If not registered: returns False

    Args:
        api_client: APIClient instance configured with device UUID

    Returns:
        True if device is registered, False otherwise
    """
    logger.info("[Registration] Checking registration status...")

    try:
        # Check registration status (unauthenticated endpoint)
        status = api_client.check_registration_status()

        if not status:
            logger.warning(
                "[Registration] No response from registration-status endpoint - "
                "device may be offline or the server unreachable"
            )
            return False

        is_registered = status.get("is_registered", False)
        api_key = status.get("api_key")
        nickname = status.get("nickname")

        if is_registered:
            logger.info(f"[Registration] Device is registered! Nickname: {nickname}")

            # If API key is provided, save it locally
            if api_key:
                logger.info("[Registration] API key received, saving locally...")
                import config
                if config.save_api_key(api_key):
                    logger.info(f"[Registration] ✓ API key saved to {config.API_KEY_FILE}")
                else:
                    logger.error("[Registration] ✗ Failed to save API key!")

            return True
        else:
            logger.info("[Registration] Not registered yet (waiting for someone to scan the QR)")
            return False

    except Exception as e:
        # Was debug: a failing poll is the single most likely reason a device
        # sits on the QR screen forever, and at debug level it is invisible.
        logger.warning("[Registration] Registration check failed: %s", e)
        return False


def wait_for_registration(api_client, poll_interval: int = 10, timeout: int = 1800) -> bool:
    """
    Poll server until device is registered.

    Args:
        api_client: APIClient instance
        poll_interval: Seconds between polls (default: 10)
        timeout: Maximum time to wait in seconds (default: 30 minutes)

    Returns:
        True if device registered within timeout, False otherwise
    """
    logger.info(f"[Registration] Waiting for device registration (timeout: {timeout}s)")

    start_time = time.time()
    poll_count = 0

    while time.time() - start_time < timeout:
        poll_count += 1

        if check_registration(api_client):
            elapsed = time.time() - start_time
            logger.info(f"[Registration] Device registered after {elapsed:.1f}s ({poll_count} checks)")
            return True

        # Wait before next poll
        logger.debug(f"[Registration] Poll #{poll_count} - not registered yet, waiting {poll_interval}s...")
        time.sleep(poll_interval)

    # Timeout
    elapsed = time.time() - start_time
    logger.error(f"[Registration] Registration timeout after {elapsed:.1f}s ({poll_count} checks)")
    return False


def get_registration_url(device_uuid: str, base_url: str = "https://streamscene.dataandstories.com") -> str:
    """
    Generate device registration URL for QR code.

    Args:
        device_uuid: Device UUID
        base_url: Base URL of StreamScene web app (default: production URL)

    Returns:
        Full registration URL
    """
    url = f"{base_url}/setup?device_uuid={device_uuid}"
    logger.debug(f"[Registration] Generated registration URL: {url}")
    return url


def main():
    """Example usage and testing."""
    import sys
    from pathlib import Path

    # Add parent directory to path for imports
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from api_client import StreamSceneAPIClient
    import config

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    print("\n=== Registration Test ===")
    print("NOTE: This requires a device UUID and API key\n")

    # Check if device is configured
    if not config.DEVICE_ID:
        print("Error: DEVICE_ID not configured in config.py")
        print("Please set DEVICE_ID environment variable or configure device")
        sys.exit(1)

    print(f"Device UUID: {config.DEVICE_ID}")
    print(f"Server URL: {config.BASE_URL}\n")

    # Initialize API client
    api_client = APIClient()

    # Test registration check
    print("Checking registration status...")
    registered = check_registration(api_client)

    if registered:
        print("✓ Device is registered!\n")

        # Fetch and display config
        config_data = api_client.fetch_config()
        if config_data:
            print("Device configuration:")
            for key, value in config_data.items():
                print(f"  {key}: {value}")
    else:
        print("✗ Device is not registered\n")

        # Show registration URL
        url = get_registration_url(config.DEVICE_ID, config.BASE_URL)
        print(f"Registration URL: {url}")
        print("\nScan QR code or visit URL to register device")

        # Ask if user wants to wait for registration
        response = input("\nWait for registration? (y/n): ").strip().lower()

        if response == 'y':
            print("\nWaiting for device registration (60 second timeout for testing)...")
            if wait_for_registration(api_client, poll_interval=5, timeout=60):
                print("\n✓ Device registered successfully!")
            else:
                print("\n✗ Registration timeout - device not registered")

    print("\n=== Registration Test Complete ===\n")


if __name__ == "__main__":
    main()
