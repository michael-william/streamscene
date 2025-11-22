"""
Setup Manager

Coordinates device setup flows:
1. WiFi Setup Flow - Hotspot + Captive Portal
2. Registration Flow - Poll server until device is registered
"""

import logging
import time
from typing import Optional, Dict, Any, Tuple

from .network_manager import NetworkManager
from .portal_server import CaptivePortalServer
from .wifi_client import load_credentials

logger = logging.getLogger(__name__)


class SetupManager:
    """
    Coordinates device setup flows.

    Manages WiFi setup and registration processes.
    """

    def __init__(self, device_uuid: str, network_manager: Optional[NetworkManager] = None):
        """
        Initialize setup manager.

        Args:
            device_uuid: Device UUID
            network_manager: NetworkManager instance (creates new one if not provided)
        """
        self.device_uuid = device_uuid
        self.network_manager = network_manager or NetworkManager(device_uuid)

        logger.info(f"[SetupManager] Initialized for device {device_uuid}")

    def run_wifi_setup(self, timeout: int = 1800) -> Optional[Dict[str, str]]:
        """
        Run complete WiFi setup flow.

        Steps:
        1. Switch to AP mode (create hotspot)
        2. Start captive portal server
        3. Wait for user to submit WiFi credentials
        4. Stop captive portal and hotspot
        5. Return credentials

        Args:
            timeout: Maximum time to wait for credentials in seconds (default: 30 minutes)

        Returns:
            Dict with {"ssid": "...", "password": "..."} if successful
            None if timeout or error
        """
        logger.info("[SetupManager] Starting WiFi setup flow")

        # Step 1: Switch to AP mode
        logger.info("[SetupManager] Step 1: Switching to AP mode")

        if not self.network_manager.switch_to_ap_mode():
            logger.error("[SetupManager] Failed to create hotspot")
            return None

        # Verify hotspot is active
        time.sleep(3)  # Give services time to start

        if not self.network_manager.verify_ap_mode():
            logger.error("[SetupManager] Hotspot verification failed")
            return None

        # Step 2: Start captive portal
        logger.info("[SetupManager] Step 2: Starting captive portal server")

        portal = CaptivePortalServer(port=8080)

        try:
            portal.start()
            logger.info(f"[SetupManager] Captive portal running on 192.168.4.1:8080")
            logger.info(f"[SetupManager] Users can connect to: {self.network_manager.hotspot_ssid}")
            logger.info(f"[SetupManager] Password: {self.network_manager.hotspot_password}")

        except Exception as e:
            logger.error(f"[SetupManager] Failed to start captive portal: {e}")
            self.network_manager.cleanup_all_services()
            return None

        # Step 3: Wait for credentials
        logger.info(f"[SetupManager] Step 3: Waiting for credentials (timeout: {timeout}s)")

        start_time = time.time()
        credentials = None

        while time.time() - start_time < timeout:
            if portal.has_credentials():
                credentials = portal.get_credentials()
                logger.info(f"[SetupManager] Received credentials for network: {credentials.get('ssid')}")
                break

            # Check every 2 seconds
            time.sleep(2)

        if not credentials:
            logger.warning(f"[SetupManager] Timeout waiting for credentials after {timeout}s")

        # Step 4: Stop portal and hotspot
        logger.info("[SetupManager] Step 4: Stopping captive portal and hotspot")

        try:
            portal.stop()
            logger.info("[SetupManager] Captive portal stopped")
        except Exception as e:
            logger.warning(f"[SetupManager] Error stopping portal: {e}")

        # Give portal time to fully stop before stopping hotspot
        time.sleep(2)

        if not self.network_manager.cleanup_all_services():
            logger.warning("[SetupManager] Failed to cleanup network services completely")

        # Step 5: Return credentials
        if credentials:
            logger.info(f"[SetupManager] WiFi setup complete. SSID: {credentials.get('ssid')}")
        else:
            logger.error("[SetupManager] WiFi setup failed - no credentials received")

        return credentials

    def attempt_wifi_connection(self, ssid: str, password: str, timeout: int = 45) -> Tuple[bool, Optional[str]]:
        """
        Attempt to connect to WiFi network.

        Args:
            ssid: WiFi network SSID
            password: WiFi network password
            timeout: Connection timeout in seconds (default: 45s for carrier establishment)

        Returns:
            Tuple of (success: bool, error_reason: Optional[str])
            error_reason can be: "wrong_credentials", "network_not_found", "timeout", "exception", or None
        """
        logger.info(f"[SetupManager] Attempting to connect to WiFi: {ssid}")

        success, ip_address, error_reason = self.network_manager.switch_to_client_mode(ssid, password, timeout)

        if success:
            logger.info(f"[SetupManager] Successfully connected to {ssid}")
            logger.info(f"[SetupManager] IP Address: {ip_address}")
        else:
            logger.error(f"[SetupManager] Failed to connect to {ssid} (reason: {error_reason})")

        return success, error_reason

    def check_saved_credentials(self) -> Optional[Dict[str, str]]:
        """
        Check if WiFi credentials are saved from previous setup.

        Returns:
            Dict with credentials if found, None otherwise
        """
        logger.info("[SetupManager] Checking for saved WiFi credentials")

        credentials = load_credentials()

        if credentials:
            logger.info(f"[SetupManager] Found saved credentials for network: {credentials.get('ssid')}")
        else:
            logger.info("[SetupManager] No saved credentials found")

        return credentials

    def has_saved_credentials(self) -> bool:
        """
        Check if WiFi credentials are saved.

        Returns:
            True if credentials exist, False otherwise
        """
        credentials = load_credentials()
        return credentials is not None

    def get_saved_ssid(self) -> Optional[str]:
        """
        Get SSID from saved credentials.

        Returns:
            SSID string if credentials exist, None otherwise
        """
        credentials = load_credentials()
        return credentials.get("ssid") if credentials else None

    def clear_saved_credentials(self) -> bool:
        """
        Clear saved WiFi credentials.

        Used when WiFi connection fails and we need to prompt for new credentials.

        Returns:
            True if successfully cleared or no credentials exist, False on error
        """
        from pathlib import Path
        import os

        logger.info("[SetupManager] Clearing saved WiFi credentials")

        creds_file = Path.home() / "streamscene-client" / "wifi_credentials.json"

        try:
            if creds_file.exists():
                os.remove(creds_file)
                logger.info(f"[SetupManager] Credentials file removed: {creds_file}")
            else:
                logger.info("[SetupManager] No credentials file to clear")

            return True

        except Exception as e:
            logger.error(f"[SetupManager] Error clearing credentials: {e}")
            return False

    def run_registration_flow(self, api_client, poll_interval: int = 10, timeout: int = 1800) -> bool:
        """
        Run device registration flow.

        Polls server until device is registered (user scans QR and registers).

        Args:
            api_client: APIClient instance for polling server
            poll_interval: Seconds between polls (default: 10)
            timeout: Maximum time to wait for registration in seconds (default: 30 minutes)

        Returns:
            True if device successfully registered
        """
        logger.info("[SetupManager] Starting registration flow")
        logger.info(f"[SetupManager] Polling every {poll_interval}s for up to {timeout}s")

        start_time = time.time()
        poll_count = 0

        while time.time() - start_time < timeout:
            poll_count += 1
            logger.debug(f"[SetupManager] Registration check #{poll_count}")

            # Check registration status via registration.py
            from .registration import check_registration

            if check_registration(api_client):
                elapsed = time.time() - start_time
                logger.info(f"[SetupManager] Device registered successfully after {elapsed:.1f}s ({poll_count} checks)")
                return True

            # Wait before next poll
            time.sleep(poll_interval)

        # Timeout
        elapsed = time.time() - start_time
        logger.error(f"[SetupManager] Registration timeout after {elapsed:.1f}s ({poll_count} checks)")
        return False

    def __str__(self) -> str:
        """String representation."""
        return f"SetupManager(device={self.device_uuid})"


def main():
    """Example usage and testing."""
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    print("\n=== Setup Manager Test ===")
    print("NOTE: This test requires root privileges!")
    print("It will create a WiFi hotspot and captive portal.")
    print("Press Ctrl+C to abort...\n")

    try:
        time.sleep(3)
    except KeyboardInterrupt:
        print("\nTest aborted by user")
        sys.exit(0)

    # Test device UUID
    device_uuid = "test-device-uuid-1234-5678"

    # Initialize setup manager
    sm = SetupManager(device_uuid)
    print(f"Setup Manager: {sm}\n")

    # Check for saved credentials
    print("Checking for saved credentials...")
    creds = sm.check_saved_credentials()

    if creds:
        print(f"Found saved credentials:")
        print(f"  SSID: {creds['ssid']}")
        print(f"  Password: {'*' * len(creds['password'])}\n")

        # Ask if user wants to use saved credentials
        response = input("Use saved credentials? (y/n): ").strip().lower()

        if response == 'y':
            print("\nAttempting connection with saved credentials...")
            if sm.attempt_wifi_connection(creds['ssid'], creds['password']):
                print("✓ Connected successfully!")
            else:
                print("✗ Connection failed")
                print("\nFalling back to WiFi setup flow...")
                creds = None
    else:
        print("No saved credentials found\n")

    # Run WiFi setup if no credentials or connection failed
    if not creds:
        print("Starting WiFi setup flow (60 second timeout for testing)...")
        print("Connect to the hotspot and enter credentials via captive portal\n")

        credentials = sm.run_wifi_setup(timeout=60)

        if credentials:
            print(f"\n✓ WiFi setup successful!")
            print(f"  SSID: {credentials['ssid']}")
            print(f"  Password: {'*' * len(credentials['password'])}\n")

            # Try to connect
            print("Attempting to connect...")
            if sm.attempt_wifi_connection(credentials['ssid'], credentials['password']):
                print("✓ Connected successfully!")
            else:
                print("✗ Connection failed")
        else:
            print("\n✗ WiFi setup failed (timeout or error)")

    print("\n=== Setup Manager Test Complete ===\n")


if __name__ == "__main__":
    main()
