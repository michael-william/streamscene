"""
Network Manager

Manages WiFi network mode switching between Access Point (hotspot) and Client modes.
Coordinates with existing hotspot.py and wifi_client.py modules.
"""

import logging
import time
from typing import Optional, Tuple

from .hotspot import (
    generate_ssid,
    create_hotspot,
    stop_hotspot,
    is_hotspot_active
)
from .wifi_client import (
    connect_to_wifi,
    is_connected,
    get_ip_address,
    test_internet_connectivity
)

logger = logging.getLogger(__name__)


class NetworkMode:
    """Network mode constants."""
    AP = "access_point"
    CLIENT = "client"
    UNKNOWN = "unknown"


class NetworkManager:
    """
    Manages network mode switching.

    Coordinates between Access Point (hotspot) mode and Client (WiFi) mode.
    Ensures only one mode is active at a time.
    """

    def __init__(self, device_uuid: str, hotspot_password: str = "streamscene"):
        """
        Initialize network manager.

        Args:
            device_uuid: Device UUID for generating unique SSID
            hotspot_password: Password for hotspot (default: "streamscene")
        """
        self.device_uuid = device_uuid
        self.hotspot_password = hotspot_password
        self.hotspot_ssid = generate_ssid(device_uuid)

        logger.info(f"[NetworkManager] Initialized for device {device_uuid}")
        logger.info(f"[NetworkManager] Hotspot SSID will be: {self.hotspot_ssid}")

    def get_current_mode(self) -> str:
        """
        Detect current network mode.

        Returns:
            NetworkMode.AP if hotspot is active
            NetworkMode.CLIENT if connected to WiFi
            NetworkMode.UNKNOWN if neither
        """
        if is_hotspot_active():
            logger.debug("[NetworkManager] Current mode: Access Point")
            return NetworkMode.AP

        if is_connected():
            logger.debug("[NetworkManager] Current mode: Client")
            return NetworkMode.CLIENT

        logger.debug("[NetworkManager] Current mode: Unknown")
        return NetworkMode.UNKNOWN

    def is_in_ap_mode(self) -> bool:
        """Check if currently in Access Point mode."""
        return is_hotspot_active()

    def switch_to_ap_mode(self) -> bool:
        """
        Switch to Access Point (hotspot) mode.

        Stops WiFi client if active, then starts hotspot.

        Returns:
            True if hotspot successfully started
        """
        logger.info(f"[NetworkManager] Switching to AP mode (SSID: {self.hotspot_ssid})")

        # Stop hotspot if already running (cleanup)
        if is_hotspot_active():
            logger.info("[NetworkManager] Hotspot already active, stopping for clean restart")
            if not stop_hotspot():
                logger.warning("[NetworkManager] Failed to stop existing hotspot, proceeding anyway")

        # Small delay to ensure services have stopped
        time.sleep(2)

        # Start hotspot
        success = create_hotspot(self.hotspot_ssid, self.hotspot_password)

        if success:
            logger.info(f"[NetworkManager] Successfully switched to AP mode")
            logger.info(f"[NetworkManager] Clients can connect to: {self.hotspot_ssid}")
        else:
            logger.error(f"[NetworkManager] Failed to switch to AP mode")

        return success

    def switch_to_client_mode(self, ssid: str, password: str, timeout: int = 30) -> Tuple[bool, Optional[str]]:
        """
        Switch to Client (WiFi) mode.

        Stops hotspot if active, then connects to specified WiFi network.

        Args:
            ssid: WiFi network SSID
            password: WiFi network password
            timeout: Connection timeout in seconds (default: 30)

        Returns:
            Tuple of (success: bool, ip_address: Optional[str])
        """
        logger.info(f"[NetworkManager] Switching to Client mode (Network: {ssid})")

        # Stop hotspot if active
        if is_hotspot_active():
            logger.info("[NetworkManager] Stopping hotspot before switching to client mode")
            if not stop_hotspot():
                logger.warning("[NetworkManager] Failed to stop hotspot, proceeding anyway")
                # Small delay to ensure services have time to stop
                time.sleep(3)
        else:
            # Small delay anyway for network stack
            time.sleep(1)

        # Connect to WiFi
        logger.info(f"[NetworkManager] Connecting to WiFi network: {ssid}")
        success = connect_to_wifi(ssid, password, timeout=timeout)

        if not success:
            logger.error(f"[NetworkManager] Failed to connect to {ssid}")
            return False, None

        # Get IP address
        ip_address = get_ip_address()

        if ip_address:
            logger.info(f"[NetworkManager] Successfully connected to {ssid}")
            logger.info(f"[NetworkManager] IP Address: {ip_address}")
        else:
            logger.warning(f"[NetworkManager] Connected but could not get IP address")

        # Test internet connectivity (optional, don't fail if this doesn't work)
        if test_internet_connectivity(timeout=10):
            logger.info(f"[NetworkManager] Internet connectivity confirmed")
        else:
            logger.warning(f"[NetworkManager] No internet connectivity (may be behind captive portal)")

        return success, ip_address

    def cleanup_all_services(self) -> bool:
        """
        Stop all network services.

        Stops hotspot and disconnects from WiFi.
        Useful for error recovery or shutdown.

        Returns:
            True if all services stopped successfully
        """
        logger.info("[NetworkManager] Cleaning up all network services")

        success = True

        # Stop hotspot
        if is_hotspot_active():
            logger.info("[NetworkManager] Stopping hotspot")
            if not stop_hotspot():
                logger.error("[NetworkManager] Failed to stop hotspot")
                success = False
        else:
            logger.debug("[NetworkManager] Hotspot not active, nothing to stop")

        # Note: We don't disconnect WiFi client because that would require
        # stopping wpa_supplicant, which might break the connection permanently.
        # WiFi client will be overridden when switching to AP mode or connecting to different network.

        if success:
            logger.info("[NetworkManager] All network services cleaned up successfully")
        else:
            logger.warning("[NetworkManager] Some network services failed to clean up")

        return success

    def verify_ap_mode(self) -> bool:
        """
        Verify that Access Point mode is active.

        Returns:
            True if hotspot is running
        """
        active = is_hotspot_active()

        if active:
            logger.info(f"[NetworkManager] AP mode verified: {self.hotspot_ssid} is active")
        else:
            logger.warning(f"[NetworkManager] AP mode verification failed: hotspot not active")

        return active

    def verify_client_mode(self) -> Tuple[bool, Optional[str]]:
        """
        Verify that Client mode is active.

        Returns:
            Tuple of (connected: bool, ip_address: Optional[str])
        """
        connected = is_connected()
        ip_address = get_ip_address() if connected else None

        if connected and ip_address:
            logger.info(f"[NetworkManager] Client mode verified: Connected with IP {ip_address}")
        else:
            logger.warning(f"[NetworkManager] Client mode verification failed: Not connected")

        return connected, ip_address

    def __str__(self) -> str:
        """String representation."""
        mode = self.get_current_mode()
        return f"NetworkManager(device={self.device_uuid}, mode={mode})"


def main():
    """Example usage and testing."""
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    print("\n=== Network Manager Test ===")
    print("NOTE: This test requires root privileges and will affect network connectivity!")
    print("Press Ctrl+C to abort...\n")

    try:
        time.sleep(3)  # Give user time to abort
    except KeyboardInterrupt:
        print("\nTest aborted by user")
        sys.exit(0)

    # Test device UUID
    device_uuid = "test-device-uuid-1234-5678"

    # Initialize network manager
    nm = NetworkManager(device_uuid)
    print(f"Network Manager: {nm}\n")

    # Check current mode
    print(f"Current mode: {nm.get_current_mode()}\n")

    # Test AP mode
    print("Testing AP mode...")
    if nm.switch_to_ap_mode():
        print(f"✓ Switched to AP mode")
        print(f"  SSID: {nm.hotspot_ssid}")
        print(f"  Password: {nm.hotspot_password}\n")

        # Verify AP mode
        time.sleep(3)
        if nm.verify_ap_mode():
            print("✓ AP mode verified\n")
        else:
            print("✗ AP mode verification failed\n")
    else:
        print("✗ Failed to switch to AP mode\n")

    # Cleanup
    print("Cleaning up...")
    nm.cleanup_all_services()

    print("\n=== Network Manager Test Complete ===\n")


if __name__ == "__main__":
    main()
