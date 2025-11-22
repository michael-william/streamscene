"""Network service for managing network connections and recovery."""

import subprocess
import time
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass

from .base import BaseService
from setup.network_manager import NetworkManager
from setup.setup_manager import SetupManager


@dataclass
class NetworkStatus:
    """Network connection status information."""

    connected: bool
    connection_type: Optional[str]  # "ethernet", "wifi", or None
    ip_address: Optional[str]
    interface: Optional[str]  # "eth0", "wlan0", or None
    ssid: Optional[str]  # WiFi SSID if connected to WiFi


class NetworkService(BaseService):
    """
    Service for managing network connections and recovery.

    Responsibilities:
    - Check initial network connectivity (ethernet priority, then WiFi)
    - Detect network failures
    - Automatically recover network (ethernet → WiFi fallback)
    - Manage DNS configuration
    - Provide network status information
    """

    def __init__(
        self,
        network_manager: NetworkManager,
        setup_manager: SetupManager,
        wifi_timeout: int = 45,
        ethernet_check_timeout: int = 10
    ):
        """
        Initialize network service.

        Args:
            network_manager: NetworkManager for low-level network operations
            setup_manager: SetupManager for WiFi setup
            wifi_timeout: Timeout for WiFi connection attempts (default: 45s for carrier establishment)
            ethernet_check_timeout: Timeout for ethernet connectivity test (default: 10s)
        """
        super().__init__("streamscene.network")
        self.network_manager = network_manager
        self.setup_manager = setup_manager
        self.wifi_timeout = wifi_timeout
        self.ethernet_check_timeout = ethernet_check_timeout

    def initialize(self) -> bool:
        """
        Initialize network service.

        Returns:
            True if initialization successful
        """
        self.logger.info("NetworkService initialized")
        return True

    def check_initial_connectivity(self) -> NetworkStatus:
        """
        Check initial network connectivity on boot.

        Priority order:
        1. Ethernet (if connected and working)
        2. WiFi (if credentials available)
        3. None (no connection available)

        Returns:
            NetworkStatus with current connection information
        """
        self.logger.info("Checking initial network connectivity...")

        # Check ethernet first (priority)
        ethernet_status = self._check_ethernet()
        if ethernet_status.connected:
            self.logger.info(f"Ethernet connected: {ethernet_status.ip_address}")
            return ethernet_status

        self.logger.info("Ethernet not available, checking WiFi...")

        # Check if WiFi credentials are saved
        if not self.setup_manager.has_saved_credentials():
            self.logger.warning("No WiFi credentials available")
            return NetworkStatus(
                connected=False,
                connection_type=None,
                ip_address=None,
                interface=None,
                ssid=None
            )

        # Try WiFi connection
        ssid = self.setup_manager.get_saved_ssid()
        self.logger.info(f"Found saved WiFi credentials for: {ssid}")

        wifi_status = self._check_wifi()
        if wifi_status.connected:
            self.logger.info(f"WiFi connected: {wifi_status.ip_address}")
            return wifi_status

        self.logger.warning("No network connectivity available")
        return NetworkStatus(
            connected=False,
            connection_type=None,
            ip_address=None,
            interface=None,
            ssid=None
        )

    def attempt_recovery(self) -> Tuple[bool, Optional[str]]:
        """
        Attempt to recover network connection.

        Strategy:
        1. Check if ethernet is still up (maybe just temporary issue)
        2. If ethernet down, try WiFi with saved credentials
        3. Handle DNS configuration

        Returns:
            Tuple of (success: bool, error_reason: Optional[str])
            error_reason can be: "wrong_credentials", "network_not_found", "timeout", "exception",
                                "no_credentials", "dns_error", or None on success
        """
        self.logger.info("Attempting network recovery...")

        # Check ethernet status
        if self.is_ethernet_up():
            self.logger.info("Ethernet is UP - network issue may be temporary (DNS?)")
            # Try to fix DNS
            if self._ensure_dns_configured():
                self.logger.info("DNS reconfigured - testing connectivity")
                time.sleep(2)  # Give DNS time to propagate
                return True, None
            return False, "dns_error"  # Ethernet up but can't fix DNS

        self.logger.warning("Ethernet is DOWN - attempting WiFi fallback")

        # Check for WiFi credentials
        if not self.setup_manager.has_saved_credentials():
            self.logger.error("No WiFi credentials available - cannot recover")
            return False, "no_credentials"

        # Get saved credentials
        from setup.wifi_client import load_credentials
        credentials = load_credentials()

        if not credentials:
            self.logger.error("Failed to load WiFi credentials")
            return False, "no_credentials"

        ssid = credentials['ssid']
        password = credentials['password']

        # Attempt WiFi connection with retries
        self.logger.info(f"Attempting to connect to WiFi: {ssid}")

        last_error_reason = None
        for attempt in range(1, 3):  # Try twice
            self.logger.info(f"WiFi connection attempt {attempt}/2")

            success, error_reason = self.setup_manager.attempt_wifi_connection(
                ssid,
                password,
                timeout=self.wifi_timeout
            )

            if success:
                self.logger.info(f"Successfully connected to WiFi: {ssid}")
                # Ensure DNS is configured
                self._ensure_dns_configured()
                return True, None
            else:
                self.logger.warning(f"WiFi connection attempt {attempt} failed (reason: {error_reason})")
                last_error_reason = error_reason
                if attempt < 2:
                    time.sleep(5)  # Wait before retry

        self.logger.error(f"Failed to connect to WiFi after 2 attempts: {ssid} (final reason: {last_error_reason})")
        return False, last_error_reason

    def get_current_status(self) -> NetworkStatus:
        """
        Get current network status.

        Returns:
            NetworkStatus with current connection information
        """
        # Check ethernet first
        ethernet_status = self._check_ethernet()
        if ethernet_status.connected:
            return ethernet_status

        # Check WiFi
        wifi_status = self._check_wifi()
        if wifi_status.connected:
            return wifi_status

        # No connection
        return NetworkStatus(
            connected=False,
            connection_type=None,
            ip_address=None,
            interface=None,
            ssid=None
        )

    def _check_ethernet(self) -> NetworkStatus:
        """
        Check if ethernet is connected and working.

        Returns:
            NetworkStatus for ethernet connection
        """
        ethernet_available, ethernet_ip = self.network_manager.get_ethernet_status()

        if not ethernet_available or not ethernet_ip:
            return NetworkStatus(
                connected=False,
                connection_type=None,
                ip_address=None,
                interface=None,
                ssid=None
            )

        # Test actual connectivity (can we reach internet?)
        if self.network_manager.test_ethernet_connectivity(timeout=self.ethernet_check_timeout):
            return NetworkStatus(
                connected=True,
                connection_type="ethernet",
                ip_address=ethernet_ip,
                interface="eth0",
                ssid=None
            )
        else:
            self.logger.warning("Ethernet has IP but no internet connectivity")
            return NetworkStatus(
                connected=False,
                connection_type=None,
                ip_address=ethernet_ip,
                interface="eth0",
                ssid=None
            )

    def _check_wifi(self) -> NetworkStatus:
        """
        Check if WiFi is connected and working.

        Returns:
            NetworkStatus for WiFi connection
        """
        wifi_available, wifi_ip = self.network_manager.get_wifi_status()

        if not wifi_available or not wifi_ip:
            return NetworkStatus(
                connected=False,
                connection_type=None,
                ip_address=None,
                interface=None,
                ssid=None
            )

        # Get SSID if connected
        ssid = self.setup_manager.get_saved_ssid()

        return NetworkStatus(
            connected=True,
            connection_type="wifi",
            ip_address=wifi_ip,
            interface="wlan0",
            ssid=ssid
        )

    def is_ethernet_up(self) -> bool:
        """
        Check if ethernet interface is up (has carrier).

        Returns:
            True if ethernet interface is up, False otherwise
        """
        try:
            result = subprocess.run(
                ["ip", "link", "show", "eth0"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if "state UP" in result.stdout:
                self.logger.debug("Ethernet interface is UP")
                return True
            else:
                self.logger.debug("Ethernet interface is DOWN")
                return False

        except Exception as e:
            self.logger.warning(f"Could not check ethernet status: {e}")
            return False

    def _ensure_dns_configured(self) -> bool:
        """
        Ensure DNS servers are configured.

        If /etc/resolv.conf is empty, add Google DNS servers.

        Returns:
            True if DNS is configured, False on error
        """
        try:
            # Check if resolv.conf has nameservers
            with open("/etc/resolv.conf", "r") as f:
                content = f.read()

            if "nameserver" in content:
                self.logger.debug("DNS already configured")
                return True

            # Add Google DNS
            self.logger.warning("No DNS servers configured - adding Google DNS")
            subprocess.run(
                ["sudo", "bash", "-c",
                 'echo "nameserver 8.8.8.8" > /etc/resolv.conf && echo "nameserver 8.8.4.4" >> /etc/resolv.conf'],
                check=True,
                timeout=5
            )

            self.logger.info("DNS servers configured: 8.8.8.8, 8.8.4.4")
            return True

        except Exception as e:
            self.logger.error(f"Failed to configure DNS: {e}")
            return False
