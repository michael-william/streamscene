"""WiFi Access Point (hotspot) management.

This module handles creating and managing a WiFi hotspot for device setup.
"""

import subprocess
import os
import time
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Configuration file paths
HOSTAPD_CONF = "/etc/hostapd/hostapd.conf"
DNSMASQ_CONF = "/etc/dnsmasq.d/streamscene.conf"
WPA_SUPPLICANT_CONF = "/etc/wpa_supplicant/wpa_supplicant.conf"


def generate_ssid(device_uuid: str) -> str:
    """
    Generate SSID from device UUID.

    Args:
        device_uuid: Device UUID (with or without dashes)

    Returns:
        SSID in format "StreamScene-XXXX"

    Example:
        >>> generate_ssid("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        'StreamScene-7890'
    """
    # Use last 4 characters of UUID (before last hyphen segment)
    suffix = device_uuid.replace("-", "")[-8:-4].upper()
    return f"StreamScene-{suffix}"


def create_hostapd_config(ssid: str, password: str = "streamscene") -> str:
    """
    Generate hostapd configuration content.

    Args:
        ssid: Network SSID
        password: WiFi password (minimum 8 characters)

    Returns:
        Configuration file content
    """
    if len(password) < 8:
        password = "streamscene"  # Fallback to default

    config = f"""# StreamScene WiFi Hotspot Configuration
interface=wlan0
driver=nl80211
ssid={ssid}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""
    return config


def create_dnsmasq_config() -> str:
    """
    Generate dnsmasq configuration content.

    Returns:
        Configuration file content
    """
    config = """# StreamScene DNS/DHCP Configuration
interface=wlan0
bind-interfaces
server=8.8.8.8
domain-needed
bogus-priv
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h

# Captive portal - redirect all DNS queries to ourselves
address=/#/192.168.4.1
"""
    return config


def create_hotspot(ssid: str, password: str = "streamscene") -> bool:
    """
    Create WiFi hotspot.

    This function:
    1. Stops wpa_supplicant (WiFi client mode)
    2. Configures wlan0 with static IP
    3. Creates hostapd and dnsmasq configurations
    4. Starts hostapd and dnsmasq services

    Args:
        ssid: Network name (e.g., "StreamScene-A1B2")
        password: WiFi password (minimum 8 characters)

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Creating WiFi hotspot: {ssid}")

    try:
        # Step 1: Stop and mask wpa_supplicant (client mode)
        logger.debug("Stopping wpa_supplicant...")
        subprocess.run(
            ["sudo", "systemctl", "stop", "wpa_supplicant"],
            check=False,
            capture_output=True,
            timeout=10
        )

        # Mask it to prevent auto-restart
        logger.debug("Masking wpa_supplicant...")
        subprocess.run(
            ["sudo", "systemctl", "mask", "wpa_supplicant"],
            check=False,
            capture_output=True,
            timeout=10
        )

        # Kill any lingering wpa_supplicant processes
        subprocess.run(
            ["sudo", "pkill", "wpa_supplicant"],
            check=False,
            capture_output=True,
            timeout=5
        )
        time.sleep(1)

        # Step 2: Bring down wlan0
        logger.debug("Bringing down wlan0...")
        subprocess.run(
            ["sudo", "ip", "link", "set", "wlan0", "down"],
            check=True,
            capture_output=True
        )
        time.sleep(1)

        # Step 3: Configure static IP for wlan0
        logger.debug("Configuring static IP...")
        subprocess.run(
            ["sudo", "ip", "addr", "flush", "dev", "wlan0"],
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["sudo", "ip", "addr", "add", "192.168.4.1/24", "dev", "wlan0"],
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["sudo", "ip", "link", "set", "wlan0", "up"],
            check=True,
            capture_output=True
        )
        time.sleep(1)

        # Step 4: Create hostapd configuration
        logger.debug(f"Creating hostapd config: {HOSTAPD_CONF}")
        hostapd_content = create_hostapd_config(ssid, password)
        with open("/tmp/hostapd.conf", "w") as f:
            f.write(hostapd_content)
        subprocess.run(
            ["sudo", "mv", "/tmp/hostapd.conf", HOSTAPD_CONF],
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["sudo", "chmod", "600", HOSTAPD_CONF],
            check=True,
            capture_output=True
        )

        # Step 5: Create dnsmasq configuration
        logger.debug(f"Creating dnsmasq config: {DNSMASQ_CONF}")
        dnsmasq_content = create_dnsmasq_config()
        with open("/tmp/dnsmasq_streamscene.conf", "w") as f:
            f.write(dnsmasq_content)

        # Ensure dnsmasq.d directory exists
        subprocess.run(
            ["sudo", "mkdir", "-p", "/etc/dnsmasq.d"],
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["sudo", "mv", "/tmp/dnsmasq_streamscene.conf", DNSMASQ_CONF],
            check=True,
            capture_output=True
        )

        # Step 6: Start hostapd
        logger.debug("Starting hostapd...")
        subprocess.run(
            ["sudo", "systemctl", "unmask", "hostapd"],
            check=False,
            capture_output=True,
            timeout=10
        )
        subprocess.run(
            ["sudo", "systemctl", "start", "hostapd"],
            check=True,
            capture_output=True,
            timeout=10
        )
        time.sleep(2)

        # Verify hostapd is running
        result = subprocess.run(
            ["sudo", "systemctl", "is-active", "hostapd"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.stdout.strip() != "active":
            logger.error("hostapd failed to start")
            return False

        # Step 7: Start dnsmasq
        logger.debug("Starting dnsmasq...")
        subprocess.run(
            ["sudo", "systemctl", "start", "dnsmasq"],
            check=True,
            capture_output=True,
            timeout=10
        )
        time.sleep(1)

        # Verify dnsmasq is running
        result = subprocess.run(
            ["sudo", "systemctl", "is-active", "dnsmasq"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.stdout.strip() != "active":
            logger.error("dnsmasq failed to start")
            return False

        logger.info(f"✓ Hotspot created successfully: {ssid}")
        logger.info(f"  IP Address: 192.168.4.1")
        logger.info(f"  Password: {password}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Error creating hotspot: {e}")
        logger.error(f"  stdout: {e.stdout}")
        logger.error(f"  stderr: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error creating hotspot: {e}")
        return False


def stop_hotspot() -> bool:
    """
    Stop WiFi hotspot and return to client mode.

    This function:
    1. Stops hostapd and dnsmasq
    2. Removes static IP from wlan0
    3. Restarts wpa_supplicant (WiFi client mode)

    Returns:
        True if successful, False otherwise
    """
    logger.info("Stopping WiFi hotspot...")

    try:
        # Step 1: Stop services (with timeouts to prevent hanging)
        logger.debug("Stopping hostapd...")
        subprocess.run(
            ["sudo", "systemctl", "stop", "hostapd"],
            check=False,
            capture_output=True,
            timeout=10
        )

        logger.debug("Stopping dnsmasq...")
        subprocess.run(
            ["sudo", "systemctl", "stop", "dnsmasq"],
            check=False,
            capture_output=True,
            timeout=10
        )

        # Step 2: Bring down wlan0
        logger.debug("Bringing down wlan0...")
        subprocess.run(
            ["sudo", "ip", "link", "set", "wlan0", "down"],
            check=False,
            capture_output=True
        )

        # Step 3: Remove static IP
        logger.debug("Removing static IP...")
        subprocess.run(
            ["sudo", "ip", "addr", "flush", "dev", "wlan0"],
            check=False,
            capture_output=True
        )

        # Step 4: Bring up wlan0
        subprocess.run(
            ["sudo", "ip", "link", "set", "wlan0", "up"],
            check=False,
            capture_output=True
        )

        # Step 5: Restart wpa_supplicant (client mode)
        logger.debug("Restarting wpa_supplicant...")
        subprocess.run(
            ["sudo", "systemctl", "start", "wpa_supplicant"],
            check=False,
            capture_output=True
        )

        time.sleep(2)

        logger.info("✓ Hotspot stopped successfully")
        return True

    except Exception as e:
        logger.error(f"Error stopping hotspot: {e}")
        return False


def is_hotspot_active() -> bool:
    """
    Check if hotspot is currently active.

    Returns:
        True if hostapd is running, False otherwise
    """
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "is-active", "hostapd"],
            capture_output=True,
            text=True
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False


if __name__ == "__main__":
    # Test hotspot creation
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop_hotspot()
    else:
        # Test with a sample UUID
        test_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        test_ssid = generate_ssid(test_uuid)
        print(f"Generated SSID: {test_ssid}")

        if create_hotspot(test_ssid):
            print("\n✓ Hotspot created successfully!")
            print(f"  Connect to: {test_ssid}")
            print(f"  Password: streamscene")
            print(f"  Portal: http://192.168.4.1")
            print("\nRun 'python hotspot.py stop' to stop the hotspot")
