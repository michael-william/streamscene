"""WiFi client mode connection.

This module handles connecting the Raspberry Pi to a WiFi network in client mode.
"""

import subprocess
import json
import time
from typing import Optional, Dict, Tuple
from pathlib import Path
import logging
import os

logger = logging.getLogger(__name__)

WIFI_CONFIG_FILE = Path.home() / "streamscene-client" / "wifi_credentials.json"
WPA_SUPPLICANT_CONF = "/etc/wpa_supplicant/wpa_supplicant.conf"

# The static address wlan0 carries while running as an access point.
# Must match the address hotspot.py assigns. Defined here rather than imported
# from hotspot to avoid a circular import through setup/__init__.py.
HOTSPOT_IP = "192.168.4.1"


def parse_wpa_status(status_output: str) -> Dict[str, str]:
    """
    Parse wpa_cli status output into dictionary.

    Example output:
        wpa_state=SCANNING
        bssid=00:00:00:00:00:00
        ssid=MyNetwork

    Returns:
        Dictionary with parsed key-value pairs
    """
    status = {}
    for line in status_output.strip().split('\n'):
        if '=' in line:
            key, value = line.split('=', 1)
            status[key.strip()] = value.strip()
    return status


def load_credentials() -> Optional[Dict[str, str]]:
    """
    Load WiFi credentials from file.

    Returns:
        Dictionary with 'ssid' and 'password' keys, or None if file not found
    """
    try:
        if not os.path.exists(WIFI_CONFIG_FILE):
            logger.debug(f"Credentials file not found: {WIFI_CONFIG_FILE}")
            return None

        with open(WIFI_CONFIG_FILE, 'r') as f:
            creds = json.load(f)

        if not creds.get('configured'):
            logger.debug("Credentials not configured")
            return None

        return creds
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in credentials file: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading credentials: {e}")
        return None


def save_credentials(ssid: str, password: str) -> bool:
    """
    Save WiFi credentials to file.

    Args:
        ssid: WiFi network name
        password: WiFi password

    Returns:
        True if successful
    """
    try:
        credentials = {
            "ssid": ssid,
            "password": password,
            "configured": True
        }

        # Ensure directory exists
        config_dir = os.path.dirname(WIFI_CONFIG_FILE)
        os.makedirs(config_dir, exist_ok=True)

        with open(WIFI_CONFIG_FILE, 'w') as f:
            json.dump(credentials, f, indent=2)

        logger.info(f"Credentials saved for SSID: {ssid}")
        return True
    except Exception as e:
        logger.error(f"Error saving credentials: {e}")
        return False


def create_wpa_supplicant_config(ssid: str, password: str) -> str:
    """
    Generate wpa_supplicant configuration content.

    Args:
        ssid: WiFi network name
        password: WiFi password (empty string for open network)

    Returns:
        Configuration file content
    """
    if password:
        # Secure network with password
        network_block = f"""network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}
"""
    else:
        # Open network (no password)
        network_block = f"""network={{
    ssid="{ssid}"
    key_mgmt=NONE
}}
"""

    config = f"""# StreamScene WiFi Configuration
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

{network_block}
"""
    return config


def connect_to_wifi(ssid: str, password: str, timeout: int = 45) -> Tuple[bool, Optional[str]]:
    """
    Connect to WiFi network.

    Args:
        ssid: Network name
        password: Network password (empty string for open network)
        timeout: Connection timeout in seconds (default: 45s for carrier establishment)

    Returns:
        Tuple of (success: bool, error_reason: Optional[str])
        error_reason can be: "wrong_credentials", "network_not_found", "timeout", or None on success
    """
    logger.info(f"Connecting to WiFi: {ssid}")

    try:
        # Step 1: Create wpa_supplicant configuration
        logger.debug("Creating wpa_supplicant configuration...")
        wpa_config = create_wpa_supplicant_config(ssid, password)

        # Write to temporary file first
        temp_conf = "/tmp/wpa_supplicant_streamscene.conf"
        with open(temp_conf, 'w') as f:
            f.write(wpa_config)

        # Copy to system location with sudo
        subprocess.run(
            ["sudo", "cp", temp_conf, WPA_SUPPLICANT_CONF],
            check=True,
            capture_output=True,
            timeout=10
        )
        subprocess.run(
            ["sudo", "chmod", "600", WPA_SUPPLICANT_CONF],
            check=True,
            capture_output=True,
            timeout=10
        )

        # Step 2: Stop systemd's wpa_supplicant and start manually with config
        logger.debug("Stopping systemd wpa_supplicant...")
        subprocess.run(
            ["sudo", "systemctl", "stop", "wpa_supplicant"],
            check=False,
            capture_output=True,
            timeout=10
        )

        # Kill any existing wpa_supplicant processes
        subprocess.run(
            ["sudo", "pkill", "wpa_supplicant"],
            check=False,
            capture_output=True,
            timeout=5
        )
        time.sleep(1)

        # Start wpa_supplicant manually with our config file
        logger.debug(f"Starting wpa_supplicant with config: {WPA_SUPPLICANT_CONF}")
        subprocess.run(
            ["sudo", "wpa_supplicant", "-B", "-i", "wlan0", "-c", WPA_SUPPLICANT_CONF],
            check=True,
            capture_output=True,
            timeout=10
        )

        # Wait for wpa_supplicant to associate with WiFi network
        logger.debug("Waiting for wpa_supplicant to associate with network...")
        association_timeout = 45  # Give wpa_supplicant up to 45s to associate
        association_start = time.time()
        last_state = None
        state_change_time = time.time()
        wrong_password_detected = False
        network_not_found = True  # Assume not found until we see progress

        while time.time() - association_start < association_timeout:
            try:
                result = subprocess.run(
                    ["sudo", "wpa_cli", "-i", "wlan0", "status"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0:
                    # Parse wpa_cli status output
                    status_dict = parse_wpa_status(result.stdout)
                    wpa_state = status_dict.get('wpa_state', 'UNKNOWN')

                    # Log state transitions for diagnostics
                    if wpa_state != last_state:
                        logger.info(f"wpa_state: {last_state} → {wpa_state}")
                        last_state = wpa_state
                        state_change_time = time.time()

                    # Success - WiFi association complete
                    if wpa_state == "COMPLETED":
                        logger.info("✓ WiFi association complete")
                        network_not_found = False
                        break

                    # If we're progressing past SCANNING, network was found
                    if wpa_state in ['ASSOCIATING', '4WAY_HANDSHAKE', 'COMPLETED']:
                        network_not_found = False

                    # Detect wrong password: stuck in 4WAY_HANDSHAKE or DISCONNECTED
                    time_in_state = time.time() - state_change_time
                    if wpa_state in ['4WAY_HANDSHAKE', 'DISCONNECTED'] and time_in_state > 8:
                        logger.error(f"Stuck in {wpa_state} for {time_in_state:.1f}s - likely wrong password")
                        wrong_password_detected = True
                        break

                # Check every 2 seconds
                time.sleep(2)
            except Exception as e:
                logger.debug(f"Error checking wpa_supplicant status: {e}")
                time.sleep(2)
        else:
            # Timeout - log final state for diagnostics
            logger.warning(f"WiFi association timeout after {association_timeout}s (final state: {last_state})")

        # Step 3: Request DHCP lease using dhcpcd (Raspberry Pi OS default)
        logger.debug("Requesting DHCP lease with dhcpcd...")

        # Release any existing lease
        subprocess.run(
            ["sudo", "dhcpcd", "-k", "wlan0"],
            check=False,
            capture_output=True,
            timeout=5
        )
        time.sleep(1)

        # Request a fresh lease. -n/--rebind asks dhcpcd to rebind an
        # EXISTING lease; after -k just released it, there is nothing to
        # rebind and this was silently a no-op. -1/--oneshot requests a new
        # lease and exits once it has one (or fails) - the actual primitive
        # needed here.
        subprocess.run(
            ["sudo", "dhcpcd", "-1", "wlan0"],
            check=False,
            capture_output=True,
            timeout=30
        )

        # Step 4: Wait for connection
        logger.debug(f"Waiting for connection (timeout: {timeout}s)...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            if is_connected():
                logger.info(f"✓ Connected to WiFi: {ssid}")
                return True, None
            time.sleep(2)

        # Connection failed - determine specific error reason
        if wrong_password_detected:
            logger.error("Connection failed: Wrong WiFi credentials (4-way handshake failed)")
            return False, "wrong_credentials"
        elif network_not_found:
            logger.error("Connection failed: Network not found (never progressed past SCANNING)")
            return False, "network_not_found"
        else:
            logger.error(f"Connection timeout after {timeout}s (last state: {last_state})")
            return False, "timeout"

    except subprocess.CalledProcessError as e:
        logger.error(f"Error connecting to WiFi: {e}")
        logger.error(f"  stdout: {e.stdout}")
        logger.error(f"  stderr: {e.stderr}")
        return False, "exception"
    except Exception as e:
        logger.error(f"Unexpected error connecting to WiFi: {e}")
        return False, "exception"


def is_connected() -> bool:
    """
    Check if WiFi is connected.

    Returns:
        True if connected to a network
    """
    try:
        # Method 1: Check wpa_cli status (most reliable)
        result = subprocess.run(
            ["sudo", "wpa_cli", "-i", "wlan0", "status"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            # Check for wpa_state=COMPLETED
            if "wpa_state=COMPLETED" in result.stdout:
                logger.info("WiFi connected (wpa_state=COMPLETED)")
                return True

        # Method 2: Check if wlan0 has an IP address (also reliable)
        #
        # IMPORTANT: the hotspot's own static address (HOTSPOT_IP) is 'scope
        # global' too. Accepting any global address here reported "connected"
        # while the radio was still running as an access point connected to
        # nothing - the device then advanced to registration and polled a
        # server it could not reach, showing a QR code as if all was well.
        # Never treat the hotspot address as connectivity.
        result = subprocess.run(
            ["ip", "addr", "show", "wlan0"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            # Look for inet (IPv4 address) - not localhost, not the hotspot IP
            lines = result.stdout.split('\n')
            for line in lines:
                if "inet " in line and "scope global" in line:
                    addr = line.strip().split()[1].split('/')[0]
                    if addr == HOTSPOT_IP:
                        logger.warning(
                            "wlan0 holds the hotspot address %s - this is AP mode, "
                            "not a client connection", HOTSPOT_IP
                        )
                        continue
                    logger.info("WiFi connected (global IP address %s)", addr)
                    return True

        logger.info("WiFi not connected (no wpa_state=COMPLETED, no client IP)")
        return False

    except Exception as e:
        logger.warning("Error checking connection: %s", e)
        return False


def is_online(host: str = "1.1.1.1", port: int = 53, timeout: int = 3) -> bool:
    """
    Check whether the device can actually reach the network.

    is_connected() only reports link state - an associated interface with an
    address. That is not the same as being able to reach the server, and the
    difference is invisible on an E Ink display. Use this before advancing to
    any state that depends on talking to the API.

    Args:
        host: Address to probe (default: Cloudflare DNS)
        port: TCP port to probe (default: 53)
        timeout: Seconds to wait

    Returns:
        True if a TCP connection can be established
    """
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            logger.info("Network reachable (%s:%s)", host, port)
            return True
    except OSError as e:
        logger.warning("Network unreachable (%s:%s): %s", host, port, e)
        return False


def get_current_ssid() -> Optional[str]:
    """
    Get the SSID of the currently connected network.

    Returns:
        SSID string, or None if not connected
    """
    try:
        result = subprocess.run(
            ["iwgetid", "-r"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            ssid = result.stdout.strip()
            return ssid if ssid else None

        return None

    except Exception as e:
        logger.debug(f"Error getting current SSID: {e}")
        return None


def get_ip_address() -> Optional[str]:
    """
    Get the current IP address of wlan0.

    Returns:
        IP address string, or None if no address
    """
    try:
        result = subprocess.run(
            ["ip", "-4", "addr", "show", "wlan0"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            # Parse output to find inet address
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line.startswith("inet "):
                    # Format: "inet 192.168.1.100/24 brd ..."
                    ip_part = line.split()[1]  # "192.168.1.100/24"
                    ip_addr = ip_part.split('/')[0]  # "192.168.1.100"
                    return ip_addr

        return None

    except Exception as e:
        logger.debug(f"Error getting IP address: {e}")
        return None


def scan_networks() -> list:
    """
    Scan for available WiFi networks.

    Returns:
        List of dicts with network info: [{"ssid": "...", "signal": -26, "encrypted": True}, ...]
        Empty list if scan fails.
    """
    try:
        result = subprocess.run(
            ["sudo", "iwlist", "wlan0", "scan"],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode != 0:
            logger.warning("WiFi scan failed")
            return []

        # Parse scan output
        networks = []
        current_network = {}

        for line in result.stdout.split('\n'):
            line = line.strip()

            # New cell starts
            if 'Cell ' in line and 'Address:' in line:
                if current_network and current_network.get('ssid'):
                    networks.append(current_network)
                current_network = {'ssid': '', 'signal': -100, 'encrypted': False}

            # ESSID
            elif 'ESSID:' in line:
                ssid = line.split('ESSID:')[1].strip().strip('"')
                if ssid:  # Skip empty SSIDs
                    current_network['ssid'] = ssid

            # Signal level
            elif 'Signal level=' in line:
                try:
                    # Format: "Quality=70/70  Signal level=-26 dBm"
                    signal_str = line.split('Signal level=')[1].split()[0]
                    current_network['signal'] = int(signal_str)
                except (IndexError, ValueError):
                    pass

            # Encryption
            elif 'Encryption key:on' in line:
                current_network['encrypted'] = True

        # Add last network
        if current_network and current_network.get('ssid'):
            networks.append(current_network)

        # Sort by signal strength (strongest first)
        networks.sort(key=lambda n: n['signal'], reverse=True)

        # Remove duplicates (keep strongest)
        seen = set()
        unique_networks = []
        for network in networks:
            if network['ssid'] not in seen:
                seen.add(network['ssid'])
                unique_networks.append(network)

        logger.info(f"WiFi scan found {len(unique_networks)} networks")
        return unique_networks

    except Exception as e:
        logger.error(f"Error scanning WiFi networks: {e}")
        return []


def test_internet_connectivity(timeout: int = 10) -> bool:
    """
    Test if device has internet connectivity.

    Args:
        timeout: Timeout in seconds

    Returns:
        True if can reach the internet
    """
    try:
        # Try to ping Google's DNS
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), "8.8.8.8"],
            capture_output=True,
            timeout=timeout + 2
        )

        if result.returncode == 0:
            logger.debug("Internet connectivity confirmed")
            return True

        logger.debug("No internet connectivity")
        return False

    except Exception as e:
        logger.debug(f"Error testing internet connectivity: {e}")
        return False


def disconnect_wifi() -> bool:
    """
    Disconnect from current WiFi network.

    Returns:
        True if successful
    """
    try:
        logger.info("Disconnecting from WiFi...")
        subprocess.run(
            ["sudo", "wpa_cli", "-i", "wlan0", "disconnect"],
            check=True,
            capture_output=True
        )

        # Release DHCP lease
        subprocess.run(
            ["sudo", "dhcpcd", "-k", "wlan0"],
            check=False,
            capture_output=True
        )

        logger.info("✓ Disconnected from WiFi")
        return True

    except Exception as e:
        logger.error(f"Error disconnecting from WiFi: {e}")
        return False


if __name__ == "__main__":
    # Test WiFi client functionality
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("StreamScene WiFi Client Test")
    print("=" * 50)

    # Check if credentials exist
    creds = load_credentials()
    if creds:
        print(f"\n✓ Found saved credentials")
        print(f"  SSID: {creds['ssid']}")
        print(f"  Password: {'*' * len(creds.get('password', ''))}")

        # Check current connection status
        if is_connected():
            current_ssid = get_current_ssid()
            ip_addr = get_ip_address()
            print(f"\n✓ Currently connected")
            print(f"  SSID: {current_ssid}")
            print(f"  IP: {ip_addr}")

            # Test internet
            has_internet = test_internet_connectivity()
            print(f"  Internet: {'✓ Connected' if has_internet else '✗ No connection'}")
        else:
            print("\n✗ Not connected to WiFi")

            # Offer to connect
            if len(sys.argv) > 1 and sys.argv[1] == "connect":
                print("\nAttempting to connect...")
                if connect_to_wifi(creds['ssid'], creds.get('password', '')):
                    print("\n✓ Connection successful!")
                    print(f"  IP: {get_ip_address()}")
                else:
                    print("\n✗ Connection failed")
    else:
        print("\n✗ No saved credentials found")
        print(f"  Expected at: {WIFI_CONFIG_FILE}")
