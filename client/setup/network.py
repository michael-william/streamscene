"""
Network setup and connectivity management.

Single orchestrator for everything main.py needs to get the device onto a
network: ethernet/WiFi status checks, AP<->client mode switching, the
hotspot+captive-portal setup flow, and registration polling. Replaces what
used to be four stacked wrapper layers (NetworkManager, SetupManager,
NetworkService, SetupService) that each re-logged and re-declared the same
calls without adding independent behavior - which is how a 3-tuple return
value silently became a 2-tuple unpack at the one call site that mattered
(main.py._handle_connecting crashed with "too many values to unpack" instead
of reporting a real connect failure).

The actual protocol logic (wpa_supplicant, hostapd/dnsmasq, the captive
portal HTTP server, registration polling) stays in wifi_client.py,
hotspot.py, portal_server.py and registration.py - this module only
coordinates them.
"""

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .hotspot import create_hotspot, generate_ssid, is_hotspot_active, stop_hotspot
from .portal_server import CaptivePortalServer
from .registration import check_registration, get_registration_url
from .wifi_client import (
    connect_to_wifi as _wifi_connect,
    get_ip_address,
    is_connected,
    load_credentials,
    test_internet_connectivity,
)

# Bare logging.getLogger(__name__) has no file handler here (same issue
# wifi_client.py had) - route through the pre-configured network_logger so
# this module's detail lands in streamscene-wifi.log.
sys.path.append(str(Path(__file__).parent.parent))
from logging_config import network_logger as logger

# Same switch as config.ETHERNET_ENABLED (read here directly so this module does
# not pull in config's device-identity loading). When false the client treats
# eth0 as absent: the debug image uses this so the hotspot/captive-portal flow
# runs while the bench keeps a USB-ethernet link that systemd-networkd owns.
ETHERNET_ENABLED = os.getenv("STREAMSCENE_ETHERNET_ENABLED", "true").lower() == "true"


@dataclass
class NetworkStatus:
    """Network connection status information."""

    connected: bool
    connection_type: Optional[str]  # "ethernet", "wifi", or None
    ip_address: Optional[str]
    interface: Optional[str]  # "eth0", "wlan0", or None
    ssid: Optional[str]


@dataclass
class NetworkCheckResult:
    """Result of the initial network/credential check."""

    should_skip_wifi_setup: bool
    connection_type: Optional[str]  # "ethernet", "saved_wifi", or None
    ip_address: Optional[str]
    credentials: Optional[Dict[str, str]]


class NetworkManager:
    """
    Coordinates network connectivity and the WiFi setup/registration flow.

    error_reason values used throughout: "wrong_credentials",
    "network_not_found", "timeout", "exception", "no_credentials",
    "dns_error", or None on success.
    """

    def __init__(self, device_uuid: str, hotspot_password: str = "streamscene"):
        self.device_uuid = device_uuid
        self.hotspot_password = hotspot_password
        self.hotspot_ssid = generate_ssid(device_uuid)
        logger.info(f"[Network] Initialized for device {device_uuid}, hotspot SSID {self.hotspot_ssid}")

    # -- Ethernet / WiFi status -------------------------------------------------

    def is_ethernet_available(self) -> bool:
        """Check if eth0 has a non-localhost IPv4 address."""
        if not ETHERNET_ENABLED:
            return False
        try:
            result = subprocess.run(
                ["ip", "-4", "addr", "show", "eth0"], capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return False
            return any("inet " in line and "127." not in line for line in result.stdout.split("\n"))
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError) as e:
            logger.debug(f"[Network] Ethernet check failed: {e}")
            return False

    def get_ethernet_ip(self) -> Optional[str]:
        if not ETHERNET_ENABLED:
            return None
        try:
            result = subprocess.run(
                ["ip", "-4", "addr", "show", "eth0"], capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return None
            for line in result.stdout.split("\n"):
                if "inet " in line and "127." not in line:
                    return line.strip().split()[1].split("/")[0]
            return None
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError) as e:
            logger.debug(f"[Network] Failed to get ethernet IP: {e}")
            return None

    def is_ethernet_up(self) -> bool:
        """Check link state (carrier) on eth0, independent of IP assignment."""
        if not ETHERNET_ENABLED:
            return False
        try:
            result = subprocess.run(
                ["ip", "link", "show", "eth0"], capture_output=True, text=True, timeout=5
            )
            return "state UP" in result.stdout
        except Exception as e:
            logger.warning(f"[Network] Could not check ethernet link state: {e}")
            return False

    def _check_ethernet(self) -> NetworkStatus:
        if not self.is_ethernet_available():
            return NetworkStatus(False, None, None, None, None)
        ip_address = self.get_ethernet_ip()
        if not ip_address or not test_internet_connectivity(timeout=10):
            if ip_address:
                logger.warning("[Network] Ethernet has an IP but no internet connectivity")
            return NetworkStatus(False, None, ip_address, "eth0" if ip_address else None, None)
        return NetworkStatus(True, "ethernet", ip_address, "eth0", None)

    def _check_wifi(self) -> NetworkStatus:
        if not is_connected():
            return NetworkStatus(False, None, None, None, None)
        ip_address = get_ip_address()
        if not ip_address:
            return NetworkStatus(False, None, None, None, None)
        return NetworkStatus(True, "wifi", ip_address, "wlan0", self.get_saved_ssid())

    def is_wifi_connected(self) -> bool:
        """wlan0 is associated and has a client IP."""
        return self._check_wifi().connected

    def check_initial_connectivity(self) -> NetworkStatus:
        """Ethernet first, then WiFi with saved credentials, else disconnected."""
        logger.info("[Network] Checking initial network connectivity...")

        ethernet_status = self._check_ethernet()
        if ethernet_status.connected:
            logger.info(f"[Network] Ethernet connected: {ethernet_status.ip_address}")
            return ethernet_status

        logger.info("[Network] Ethernet not available, checking WiFi...")
        if not self.has_saved_credentials():
            logger.warning("[Network] No WiFi credentials available")
            return NetworkStatus(False, None, None, None, None)

        wifi_status = self._check_wifi()
        if wifi_status.connected:
            logger.info(f"[Network] WiFi connected: {wifi_status.ip_address}")
        else:
            logger.warning("[Network] No network connectivity available")
        return wifi_status

    def check_network_and_credentials(self) -> NetworkCheckResult:
        """Decide whether WIFI_SETUP can be skipped (ethernet, or saved creds)."""
        logger.info("[Network] Checking network and credentials...")

        ethernet_available, ethernet_ip = self.is_ethernet_available(), self.get_ethernet_ip()
        if ethernet_available and ethernet_ip and test_internet_connectivity(timeout=10):
            logger.info(f"[Network] Ethernet has internet connectivity: {ethernet_ip}")
            return NetworkCheckResult(True, "ethernet", ethernet_ip, None)

        credentials = load_credentials()
        if credentials:
            logger.info(f"[Network] Found saved credentials for SSID: {credentials['ssid']}")
            return NetworkCheckResult(True, "saved_wifi", None, credentials)

        logger.info("[Network] No ethernet or saved credentials - WiFi setup required")
        return NetworkCheckResult(False, None, None, None)

    def attempt_recovery(self) -> Tuple[bool, Optional[str]]:
        """Recover connectivity: fix DNS if ethernet is up, else retry saved WiFi twice."""
        logger.info("[Network] Attempting network recovery...")

        if self.is_ethernet_up():
            logger.info("[Network] Ethernet is UP - may just be a DNS issue")
            if self._ensure_dns_configured():
                time.sleep(2)
                return True, None
            return False, "dns_error"

        logger.warning("[Network] Ethernet is DOWN - attempting WiFi fallback")
        credentials = load_credentials()
        if not credentials:
            logger.error("[Network] No WiFi credentials available - cannot recover")
            return False, "no_credentials"

        last_error_reason = None
        for attempt in range(1, 3):
            logger.info(f"[Network] WiFi recovery attempt {attempt}/2")
            success, _ip, error_reason = self.connect_to_wifi(
                credentials["ssid"], credentials["password"], timeout=45
            )
            if success:
                self._ensure_dns_configured()
                return True, None
            last_error_reason = error_reason
            if attempt < 2:
                time.sleep(5)

        logger.error(f"[Network] WiFi recovery failed after 2 attempts (reason: {last_error_reason})")
        return False, last_error_reason

    def _ensure_dns_configured(self) -> bool:
        try:
            with open("/etc/resolv.conf", "r") as f:
                content = f.read()
            if "nameserver" in content:
                return True
            logger.warning("[Network] No DNS servers configured - adding Google DNS")
            subprocess.run(
                ["sudo", "bash", "-c",
                 'echo "nameserver 8.8.8.8" > /etc/resolv.conf && echo "nameserver 8.8.4.4" >> /etc/resolv.conf'],
                check=True, timeout=5,
            )
            return True
        except Exception as e:
            logger.error(f"[Network] Failed to configure DNS: {e}")
            return False

    # -- AP <-> client mode -------------------------------------------------

    def is_in_ap_mode(self) -> bool:
        return is_hotspot_active()

    def switch_to_ap_mode(self) -> bool:
        logger.info(f"[Network] Switching to AP mode (SSID: {self.hotspot_ssid})")
        if is_hotspot_active():
            logger.info("[Network] Hotspot already active, stopping for clean restart")
            if not stop_hotspot():
                logger.warning("[Network] Failed to stop existing hotspot, proceeding anyway")
        time.sleep(2)
        success = create_hotspot(self.hotspot_ssid, self.hotspot_password)
        if not success:
            logger.error("[Network] Failed to switch to AP mode")
        return success

    def stop_hotspot(self) -> bool:
        return stop_hotspot()

    def connect_to_wifi(
        self, ssid: str, password: str, timeout: int = 45
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Stop the hotspot if active, then connect as a WiFi client.

        Returns (success, ip_address, error_reason).
        """
        logger.info(f"[Network] Connecting to WiFi: {ssid}")

        if is_hotspot_active():
            logger.info("[Network] Stopping hotspot before switching to client mode")
            if not stop_hotspot():
                logger.warning("[Network] Failed to stop hotspot, proceeding anyway")
            time.sleep(3)
        else:
            time.sleep(1)

        success, error_reason = _wifi_connect(ssid, password, timeout=timeout)
        if not success:
            logger.error(f"[Network] Failed to connect to {ssid} (reason: {error_reason})")
            return False, None, error_reason

        ip_address = get_ip_address()
        if ip_address:
            logger.info(f"[Network] Connected to {ssid}, IP address: {ip_address}")
        else:
            logger.warning(f"[Network] Connected to {ssid} but could not get IP address")

        if not test_internet_connectivity(timeout=10):
            logger.warning("[Network] No internet connectivity (may be behind captive portal)")

        return True, ip_address, None

    # -- Setup flow (hotspot + captive portal) -------------------------------------------------

    def run_wifi_setup_flow(self, timeout: int = 1800) -> Optional[Dict[str, str]]:
        """Run hotspot + captive portal, return {"ssid", "password"} once submitted."""
        logger.info(f"[Network] Starting WiFi setup flow (timeout: {timeout}s)")

        if not self.switch_to_ap_mode():
            logger.error("[Network] Failed to create hotspot")
            return None

        time.sleep(3)
        if not is_hotspot_active():
            logger.error("[Network] Hotspot verification failed")
            return None

        # Port 80, not 8080: captive portal detection on every OS probes port
        # 80 only. The service grants CAP_NET_BIND_SERVICE (see
        # streamscene-client.service), so binding 80 needs neither root nor a
        # NAT rule.
        portal = CaptivePortalServer(port=80)
        try:
            portal.start()
            logger.info(f"[Network] Captive portal running on 192.168.4.1:80 ({self.hotspot_ssid})")
        except Exception as e:
            logger.error(f"[Network] Failed to start captive portal: {e}")
            self._cleanup_ap_services()
            return None

        start_time = time.time()
        credentials = None
        while time.time() - start_time < timeout:
            if portal.has_credentials():
                credentials = portal.get_credentials()
                logger.info(f"[Network] Received credentials for network: {credentials.get('ssid')}")
                break
            time.sleep(2)

        if not credentials:
            logger.warning(f"[Network] Timeout waiting for credentials after {timeout}s")

        try:
            portal.stop()
        except Exception as e:
            logger.warning(f"[Network] Error stopping portal: {e}")
        time.sleep(2)
        self._cleanup_ap_services()

        if not credentials:
            logger.error("[Network] WiFi setup failed - no credentials received")
        return credentials

    def _cleanup_ap_services(self) -> bool:
        """Stop the hotspot if active. WiFi client (wpa_supplicant) is left alone -
        it gets overridden on the next mode switch rather than torn down here."""
        if not is_hotspot_active():
            return True
        if not stop_hotspot():
            logger.error("[Network] Failed to stop hotspot")
            return False
        return True

    # -- Saved credentials -------------------------------------------------

    def has_saved_credentials(self) -> bool:
        return load_credentials() is not None

    def get_saved_ssid(self) -> Optional[str]:
        credentials = load_credentials()
        return credentials.get("ssid") if credentials else None

    def clear_saved_credentials(self) -> bool:
        from .wifi_client import WIFI_CONFIG_FILE

        logger.info("[Network] Clearing saved WiFi credentials")
        try:
            if WIFI_CONFIG_FILE.exists():
                WIFI_CONFIG_FILE.unlink()
                logger.info(f"[Network] Credentials file removed: {WIFI_CONFIG_FILE}")
            return True
        except Exception as e:
            logger.error(f"[Network] Error clearing credentials: {e}")
            return False

    # -- Registration -------------------------------------------------

    def get_registration_url(self) -> str:
        return get_registration_url(self.device_uuid)

    def run_registration_flow(self, api_client, poll_interval: int = 10, timeout: int = 1800) -> bool:
        """Poll the server until the device is registered, or timeout."""
        logger.info(f"[Network] Registration polling: every {poll_interval}s, up to {timeout}s")

        start_time = time.time()
        poll_count = 0
        while time.time() - start_time < timeout:
            poll_count += 1
            if check_registration(api_client):
                elapsed = time.time() - start_time
                logger.info(f"[Network] Device registered after {elapsed:.1f}s ({poll_count} checks)")
                return True
            time.sleep(poll_interval)

        elapsed = time.time() - start_time
        logger.error(f"[Network] Registration timeout after {elapsed:.1f}s ({poll_count} checks)")
        return False

    def __str__(self) -> str:
        return f"NetworkManager(device={self.device_uuid})"
