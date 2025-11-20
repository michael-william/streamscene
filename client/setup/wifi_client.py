"""WiFi client mode connection.

This module handles connecting the Raspberry Pi to a WiFi network in client mode.
"""

import subprocess
import json
import time
from typing import Optional, Dict
from pathlib import Path
import logging
import os

logger = logging.getLogger(__name__)

WIFI_CONFIG_FILE = Path.home() / "streamscene-client" / "wifi_credentials.json"
WPA_SUPPLICANT_CONF = "/etc/wpa_supplicant/wpa_supplicant.conf"


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


def connect_to_wifi(ssid: str, password: str, timeout: int = 30) -> bool:
    """
    Connect to WiFi network.

    Args:
        ssid: Network name
        password: Network password (empty string for open network)
        timeout: Connection timeout in seconds

    Returns:
        True if successfully connected
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

        # Wait for wpa_supplicant to initialize
        time.sleep(3)

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

        # Request new lease (dhcpcd daemon manages this automatically)
        # Just need to restart dhcpcd or trigger it for wlan0
        subprocess.run(
            ["sudo", "dhcpcd", "-n", "wlan0"],
            check=False,
            capture_output=True,
            timeout=15
        )

        # Step 4: Wait for connection
        logger.debug(f"Waiting for connection (timeout: {timeout}s)...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            if is_connected():
                logger.info(f"✓ Connected to WiFi: {ssid}")
                return True
            time.sleep(2)

        logger.error(f"Connection timeout after {timeout}s")
        return False

    except subprocess.CalledProcessError as e:
        logger.error(f"Error connecting to WiFi: {e}")
        logger.error(f"  stdout: {e.stdout}")
        logger.error(f"  stderr: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error connecting to WiFi: {e}")
        return False


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
                logger.debug("WiFi connected (wpa_state=COMPLETED)")
                return True

        # Method 2: Check if wlan0 has an IP address (also reliable)
        result = subprocess.run(
            ["ip", "addr", "show", "wlan0"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            # Look for inet (IPv4 address) - not localhost
            lines = result.stdout.split('\n')
            for line in lines:
                if "inet " in line and "scope global" in line:
                    logger.debug("WiFi connected (has global IP address)")
                    return True

        return False

    except Exception as e:
        logger.debug(f"Error checking connection: {e}")
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
