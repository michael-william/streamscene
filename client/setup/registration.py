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

    Polls the /api/devices/{id}/config endpoint.
    - If returns 200: Device is registered
    - If returns 404/403: Device not registered yet
    - If returns other error: Connection/server issue

    Args:
        api_client: APIClient instance configured with device UUID

    Returns:
        True if device is registered, False otherwise
    """
    logger.debug("[Registration] Checking registration status...")

    try:
        # Try to fetch device config
        # This endpoint requires device to be registered
        config = api_client.fetch_config()

        if config:
            logger.info("[Registration] Device is registered!")
            logger.debug(f"[Registration] Device config: {config}")
            return True
        else:
            logger.debug("[Registration] Device not registered yet (no config returned)")
            return False

    except Exception as e:
        logger.debug(f"[Registration] Registration check failed: {e}")
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

    from api_client import APIClient
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
