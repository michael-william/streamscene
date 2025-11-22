"""Setup coordination service.

Handles device setup flows including WiFi setup and device registration.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from services.base import BaseService
from setup.registration import get_registration_url


@dataclass
class NetworkCheckResult:
    """Result of network and credential check."""
    should_skip_wifi_setup: bool
    connection_type: Optional[str]  # "ethernet", "saved_wifi", or None
    ip_address: Optional[str]
    credentials: Optional[Dict[str, str]]  # For saved_wifi case


@dataclass
class RegistrationResult:
    """Result of registration flow."""
    success: bool
    api_key: Optional[str]
    error: Optional[str]


class SetupService(BaseService):
    """Service for coordinating device setup flows.

    Responsibilities:
    - Coordinate WiFi setup flow
    - Coordinate device registration flow
    - Manage credential checks
    - Provide high-level setup status
    """

    def __init__(
        self,
        device_uuid: str,
        setup_manager,
        network_manager,
        config_service
    ):
        """Initialize setup service.

        Args:
            device_uuid: Device UUID
            setup_manager: SetupManager instance
            network_manager: NetworkManager instance
            config_service: ConfigurationService instance
        """
        super().__init__("streamscene.setup")
        self.device_uuid = device_uuid
        self.setup_manager = setup_manager
        self.network_manager = network_manager
        self.config_service = config_service

    def initialize(self) -> bool:
        """Initialize service.

        Returns:
            True if initialization successful
        """
        self.logger.info("Setup service initializing...")
        return True

    def check_network_and_credentials(self) -> NetworkCheckResult:
        """Check if device can skip WiFi setup.

        Checks in priority order:
        1. Ethernet connectivity (highest priority)
        2. Saved WiFi credentials

        Returns:
            NetworkCheckResult with skip decision and connection details
        """
        self.logger.info("Checking network and credentials...")

        # Priority 1: Check ethernet
        ethernet_available, ethernet_ip = self.network_manager.get_ethernet_status()

        if ethernet_available and ethernet_ip:
            self.logger.info(f"Ethernet detected with IP: {ethernet_ip}")

            # Test internet connectivity before skipping WiFi setup
            if self.network_manager.test_ethernet_connectivity(timeout=10):
                self.logger.info("Ethernet has internet connectivity - can skip WiFi setup")
                return NetworkCheckResult(
                    should_skip_wifi_setup=True,
                    connection_type="ethernet",
                    ip_address=ethernet_ip,
                    credentials=None
                )
            else:
                self.logger.warning("Ethernet available but no internet connectivity")

        # Priority 2: Check for saved WiFi credentials
        saved_credentials = self.setup_manager.check_saved_credentials()

        if saved_credentials:
            self.logger.info(f"Found saved credentials for SSID: {saved_credentials['ssid']}")
            return NetworkCheckResult(
                should_skip_wifi_setup=True,
                connection_type="saved_wifi",
                ip_address=None,  # Will be determined after connection
                credentials=saved_credentials
            )

        # No network available - need WiFi setup
        self.logger.info("No ethernet or saved credentials - WiFi setup required")
        return NetworkCheckResult(
            should_skip_wifi_setup=False,
            connection_type=None,
            ip_address=None,
            credentials=None
        )

    def run_wifi_setup_flow(self, timeout: int = 1800) -> Optional[Dict[str, str]]:
        """Run complete WiFi setup flow.

        Orchestrates:
        1. Hotspot creation
        2. Captive portal
        3. Credential collection

        Args:
            timeout: Maximum time to wait for credentials (default: 30 minutes)

        Returns:
            Dict with {"ssid": "...", "password": "..."} if successful
            None if timeout or error
        """
        self.logger.info(f"Starting WiFi setup flow (timeout: {timeout}s)")

        try:
            credentials = self.setup_manager.run_wifi_setup(timeout=timeout)

            if credentials:
                self.logger.info(f"Successfully obtained credentials for SSID: {credentials['ssid']}")
                return credentials
            else:
                self.logger.error("Failed to obtain WiFi credentials (timeout or error)")
                return None

        except Exception as e:
            self.logger.error(f"Error during WiFi setup: {e}")
            return None

    def connect_to_wifi(
        self,
        ssid: str,
        password: str,
        timeout: int = 30
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Connect to WiFi network.

        Args:
            ssid: Network SSID
            password: Network password
            timeout: Connection timeout in seconds (default: 30)

        Returns:
            Tuple of (success: bool, ip_address: Optional[str], error_reason: Optional[str])
            error_reason can be: "wrong_credentials", "network_not_found", "timeout", "exception", or None
        """
        self.logger.info(f"Connecting to WiFi network: {ssid}")

        try:
            success, ip_address, error_reason = self.network_manager.switch_to_client_mode(
                ssid=ssid,
                password=password,
                timeout=timeout
            )

            if success:
                self.logger.info(f"Successfully connected! IP address: {ip_address}")
                return (True, ip_address, None)
            else:
                self.logger.error(f"Failed to connect to {ssid} (reason: {error_reason})")
                return (False, None, error_reason)

        except Exception as e:
            self.logger.error(f"Error connecting to WiFi: {e}")
            return (False, None, "exception")

    def get_registration_url(self) -> str:
        """Get registration URL for this device.

        Returns:
            Registration URL
        """
        return get_registration_url(self.device_uuid)

    def run_registration_flow(
        self,
        api_client,
        poll_interval: int = 10,
        timeout: int = 1800
    ) -> bool:
        """Run device registration polling flow.

        Polls server until device is registered or timeout occurs.

        Args:
            api_client: API client instance
            poll_interval: Polling interval in seconds (default: 10)
            timeout: Maximum time to wait in seconds (default: 30 minutes)

        Returns:
            True if device registered successfully
        """
        self.logger.info(f"Starting registration polling (interval: {poll_interval}s, timeout: {timeout}s)")

        try:
            success = self.setup_manager.run_registration_flow(
                api_client=api_client,
                poll_interval=poll_interval,
                timeout=timeout
            )

            if success:
                self.logger.info("Device successfully registered!")
                return True
            else:
                self.logger.error("Registration timeout - no response from server")
                return False

        except Exception as e:
            self.logger.error(f"Error during registration: {e}")
            return False

    def is_registered(self) -> bool:
        """Check if device is registered (has API key).

        Returns:
            True if device has API key
        """
        return self.config_service.is_registered()

    def verify_registration_complete(self) -> RegistrationResult:
        """Verify that registration completed successfully.

        Checks for API key and attempts to load it.

        Returns:
            RegistrationResult with status and details
        """
        self.logger.info("Verifying registration completion...")

        if not self.is_registered():
            self.logger.warning("No API key found after registration")
            return RegistrationResult(
                success=False,
                api_key=None,
                error="No API key found - registration may have failed"
            )

        # Try to fetch config to verify API key works
        try:
            config = self.config_service.fetch_initial_config()
            if config:
                self.logger.info("API key verified - device successfully registered")
                return RegistrationResult(
                    success=True,
                    api_key="present",  # Don't expose actual key
                    error=None
                )
            else:
                self.logger.warning("API key present but config fetch failed")
                return RegistrationResult(
                    success=True,  # Key exists, may just be temporary network issue
                    api_key="present",
                    error="Config fetch failed but key exists"
                )
        except Exception as e:
            self.logger.error(f"Error verifying registration: {e}")
            return RegistrationResult(
                success=True,  # If we have a key, consider it successful
                api_key="present",
                error=f"Verification error: {e}"
            )

    def has_saved_credentials(self) -> bool:
        """Check if device has saved WiFi credentials.

        Returns:
            True if saved credentials exist
        """
        return self.setup_manager.has_saved_credentials()

    def get_saved_ssid(self) -> Optional[str]:
        """Get SSID of saved WiFi credentials.

        Returns:
            SSID if credentials exist, None otherwise
        """
        return self.setup_manager.get_saved_ssid()
