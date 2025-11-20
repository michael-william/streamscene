"""WiFi Access Point (hotspot) management.

This module handles creating and managing a WiFi hotspot for device setup.
"""

import subprocess
import os
import time
import sys
from typing import Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from logging_config import hotspot_logger, log_subprocess_output

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
country_code=US
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
    hotspot_logger.info(f"Creating WiFi hotspot: {ssid}")
    hotspot_logger.info(f"Password: {password}")

    try:
        # Step 1: Stop and mask wpa_supplicant (client mode)
        hotspot_logger.info("Step 1: Stopping wpa_supplicant (WiFi client mode)")
        result = subprocess.run(
            ["sudo", "systemctl", "stop", "wpa_supplicant"],
            check=False,
            capture_output=True,
            timeout=10
        )
        log_subprocess_output(hotspot_logger, result, "systemctl stop wpa_supplicant")

        # Mask it to prevent auto-restart
        hotspot_logger.info("Masking wpa_supplicant to prevent auto-restart")
        result = subprocess.run(
            ["sudo", "systemctl", "mask", "wpa_supplicant"],
            check=False,
            capture_output=True,
            timeout=10
        )
        log_subprocess_output(hotspot_logger, result, "systemctl mask wpa_supplicant")

        # Kill any lingering wpa_supplicant processes
        hotspot_logger.info("Killing any lingering wpa_supplicant processes")
        result = subprocess.run(
            ["sudo", "pkill", "wpa_supplicant"],
            check=False,
            capture_output=True,
            timeout=5
        )
        log_subprocess_output(hotspot_logger, result, "pkill wpa_supplicant")
        time.sleep(1)

        # Step 2: Bring down wlan0
        hotspot_logger.info("Step 2: Bringing down wlan0 interface")
        result = subprocess.run(
            ["sudo", "ip", "link", "set", "wlan0", "down"],
            check=True,
            capture_output=True
        )
        log_subprocess_output(hotspot_logger, result, "ip link set wlan0 down")
        time.sleep(1)

        # Step 3: Configure static IP for wlan0
        hotspot_logger.info("Step 3: Configuring static IP (192.168.4.1/24)")
        hotspot_logger.info("Flushing existing IP addresses on wlan0")
        result = subprocess.run(
            ["sudo", "ip", "addr", "flush", "dev", "wlan0"],
            check=True,
            capture_output=True
        )
        log_subprocess_output(hotspot_logger, result, "ip addr flush dev wlan0")

        hotspot_logger.info("Adding static IP 192.168.4.1/24 to wlan0")
        result = subprocess.run(
            ["sudo", "ip", "addr", "add", "192.168.4.1/24", "dev", "wlan0"],
            check=True,
            capture_output=True
        )
        log_subprocess_output(hotspot_logger, result, "ip addr add 192.168.4.1/24 dev wlan0")

        hotspot_logger.info("Bringing wlan0 interface up")
        result = subprocess.run(
            ["sudo", "ip", "link", "set", "wlan0", "up"],
            check=True,
            capture_output=True
        )
        log_subprocess_output(hotspot_logger, result, "ip link set wlan0 up")
        time.sleep(1)

        # Step 4: Create hostapd configuration
        hotspot_logger.info(f"Step 4: Creating hostapd configuration at {HOSTAPD_CONF}")
        hostapd_content = create_hostapd_config(ssid, password)
        hotspot_logger.info(f"Writing hostapd config to /tmp/hostapd.conf")
        with open("/tmp/hostapd.conf", "w") as f:
            f.write(hostapd_content)

        hotspot_logger.info(f"Copying hostapd config to {HOSTAPD_CONF}")
        result = subprocess.run(
            ["sudo", "cp", "/tmp/hostapd.conf", HOSTAPD_CONF],
            check=True,
            capture_output=True
        )
        log_subprocess_output(hotspot_logger, result, f"cp /tmp/hostapd.conf {HOSTAPD_CONF}")

        hotspot_logger.info("Setting hostapd config permissions to 600")
        result = subprocess.run(
            ["sudo", "chmod", "600", HOSTAPD_CONF],
            check=True,
            capture_output=True
        )
        log_subprocess_output(hotspot_logger, result, f"chmod 600 {HOSTAPD_CONF}")

        # Step 5: Create dnsmasq configuration
        hotspot_logger.info(f"Step 5: Creating dnsmasq configuration at {DNSMASQ_CONF}")
        dnsmasq_content = create_dnsmasq_config()
        hotspot_logger.info("Writing dnsmasq config to /tmp/dnsmasq_streamscene.conf")
        with open("/tmp/dnsmasq_streamscene.conf", "w") as f:
            f.write(dnsmasq_content)

        # Ensure dnsmasq.d directory exists
        hotspot_logger.info("Ensuring /etc/dnsmasq.d directory exists")
        result = subprocess.run(
            ["sudo", "mkdir", "-p", "/etc/dnsmasq.d"],
            check=True,
            capture_output=True
        )
        log_subprocess_output(hotspot_logger, result, "mkdir -p /etc/dnsmasq.d")

        hotspot_logger.info(f"Copying dnsmasq config to {DNSMASQ_CONF}")
        result = subprocess.run(
            ["sudo", "cp", "/tmp/dnsmasq_streamscene.conf", DNSMASQ_CONF],
            check=True,
            capture_output=True
        )
        log_subprocess_output(hotspot_logger, result, f"cp /tmp/dnsmasq_streamscene.conf {DNSMASQ_CONF}")

        # Step 6: Start hostapd
        hotspot_logger.info("Step 6: Starting hostapd service")
        hotspot_logger.info("Unmasking hostapd")
        result = subprocess.run(
            ["sudo", "systemctl", "unmask", "hostapd"],
            check=False,
            capture_output=True,
            timeout=10
        )
        log_subprocess_output(hotspot_logger, result, "systemctl unmask hostapd")

        hotspot_logger.info("Starting hostapd service")
        result = subprocess.run(
            ["sudo", "systemctl", "start", "hostapd"],
            check=True,
            capture_output=True,
            timeout=10
        )
        log_subprocess_output(hotspot_logger, result, "systemctl start hostapd")
        hotspot_logger.info("Waiting 2 seconds for hostapd to stabilize")
        time.sleep(2)

        # Verify hostapd is running
        hotspot_logger.info("Verifying hostapd is active")
        result = subprocess.run(
            ["sudo", "systemctl", "is-active", "hostapd"],
            capture_output=True,
            text=True,
            timeout=5
        )
        log_subprocess_output(hotspot_logger, result, "systemctl is-active hostapd")

        if result.stdout.strip() != "active":
            hotspot_logger.error("hostapd failed to start - service is not active")
            hotspot_logger.error("Check hostapd service status: sudo systemctl status hostapd")
            hotspot_logger.error("Check hostapd logs: sudo journalctl -u hostapd -n 50")
            return False
        hotspot_logger.info("hostapd is running and active")

        # Step 7: Start dnsmasq
        hotspot_logger.info("Step 7: Starting dnsmasq service")
        result = subprocess.run(
            ["sudo", "systemctl", "start", "dnsmasq"],
            check=True,
            capture_output=True,
            timeout=10
        )
        log_subprocess_output(hotspot_logger, result, "systemctl start dnsmasq")
        hotspot_logger.info("Waiting 3 seconds for dnsmasq to stabilize")
        time.sleep(3)

        # Verify dnsmasq is running (with retry logic)
        hotspot_logger.info("Verifying dnsmasq is active")
        dnsmasq_active = False
        for attempt in range(3):  # Try up to 3 times
            result = subprocess.run(
                ["sudo", "systemctl", "is-active", "dnsmasq"],
                capture_output=True,
                text=True,
                timeout=5
            )
            log_subprocess_output(hotspot_logger, result, f"systemctl is-active dnsmasq (attempt {attempt+1}/3)")

            if result.stdout.strip() == "active":
                dnsmasq_active = True
                break

            if attempt < 2:  # Don't sleep on last attempt
                hotspot_logger.warning(f"dnsmasq not active yet, retrying in 2 seconds... (attempt {attempt+1}/3)")
                time.sleep(2)

        if not dnsmasq_active:
            hotspot_logger.error("dnsmasq failed to start after 3 attempts - service is not active")
            hotspot_logger.error("Check dnsmasq service status: sudo systemctl status dnsmasq")
            hotspot_logger.error("Check dnsmasq logs: sudo journalctl -u dnsmasq -n 50")
            return False
        hotspot_logger.info("dnsmasq is running and active")

        hotspot_logger.info("=" * 60)
        hotspot_logger.info(f"Hotspot created successfully!")
        hotspot_logger.info(f"SSID: {ssid}")
        hotspot_logger.info(f"Password: {password}")
        hotspot_logger.info(f"IP Address: 192.168.4.1")
        hotspot_logger.info(f"Portal URL: http://192.168.4.1")
        hotspot_logger.info("=" * 60)
        return True

    except subprocess.CalledProcessError as e:
        hotspot_logger.error(f"Command failed while creating hotspot: {e.cmd}")
        hotspot_logger.error(f"Return code: {e.returncode}")
        if e.stdout:
            stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout
            hotspot_logger.error(f"stdout: {stdout}")
        if e.stderr:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr
            hotspot_logger.error(f"stderr: {stderr}")
        hotspot_logger.error("Hotspot creation failed - check logs above for details")
        return False
    except Exception as e:
        hotspot_logger.error(f"Unexpected error creating hotspot: {e}", exc_info=True)
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
    hotspot_logger.info("Stopping WiFi hotspot...")

    try:
        # Step 1: Stop services (with timeouts to prevent hanging)
        hotspot_logger.info("Step 1: Stopping hostapd service")
        result = subprocess.run(
            ["sudo", "systemctl", "stop", "hostapd"],
            check=False,
            capture_output=True,
            timeout=10
        )
        log_subprocess_output(hotspot_logger, result, "systemctl stop hostapd")

        hotspot_logger.info("Stopping dnsmasq service")
        result = subprocess.run(
            ["sudo", "systemctl", "stop", "dnsmasq"],
            check=False,
            capture_output=True,
            timeout=10
        )
        log_subprocess_output(hotspot_logger, result, "systemctl stop dnsmasq")

        # Step 2: Bring down wlan0
        hotspot_logger.info("Step 2: Bringing down wlan0 interface")
        result = subprocess.run(
            ["sudo", "ip", "link", "set", "wlan0", "down"],
            check=False,
            capture_output=True
        )
        log_subprocess_output(hotspot_logger, result, "ip link set wlan0 down")

        # Step 3: Remove static IP
        hotspot_logger.info("Step 3: Removing static IP from wlan0")
        result = subprocess.run(
            ["sudo", "ip", "addr", "flush", "dev", "wlan0"],
            check=False,
            capture_output=True
        )
        log_subprocess_output(hotspot_logger, result, "ip addr flush dev wlan0")

        # Step 4: Bring up wlan0
        hotspot_logger.info("Step 4: Bringing wlan0 interface back up")
        result = subprocess.run(
            ["sudo", "ip", "link", "set", "wlan0", "up"],
            check=False,
            capture_output=True
        )
        log_subprocess_output(hotspot_logger, result, "ip link set wlan0 up")

        # Step 5: Restart wpa_supplicant (client mode)
        hotspot_logger.info("Step 5: Restarting wpa_supplicant for client mode")
        result = subprocess.run(
            ["sudo", "systemctl", "start", "wpa_supplicant"],
            check=False,
            capture_output=True
        )
        log_subprocess_output(hotspot_logger, result, "systemctl start wpa_supplicant")

        hotspot_logger.info("Waiting 2 seconds for services to stabilize")
        time.sleep(2)

        hotspot_logger.info("Hotspot stopped successfully")
        return True

    except Exception as e:
        hotspot_logger.error(f"Error stopping hotspot: {e}", exc_info=True)
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
        is_active = result.stdout.strip() == "active"
        hotspot_logger.info(f"Hotspot active status: {is_active}")
        return is_active
    except Exception as e:
        hotspot_logger.error(f"Error checking hotspot status: {e}")
        return False


if __name__ == "__main__":
    # Test hotspot creation
    import sys

    # Use centralized logging for tests
    hotspot_logger.info("Starting hotspot test script")

    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        hotspot_logger.info("Stopping hotspot (test mode)")
        stop_hotspot()
    else:
        # Test with a sample UUID
        test_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        test_ssid = generate_ssid(test_uuid)
        hotspot_logger.info(f"Generated SSID: {test_ssid}")
        print(f"Generated SSID: {test_ssid}")

        if create_hotspot(test_ssid):
            print("\n✓ Hotspot created successfully!")
            print(f"  Connect to: {test_ssid}")
            print(f"  Password: streamscene")
            print(f"  Portal: http://192.168.4.1")
            print("\nRun 'python hotspot.py stop' to stop the hotspot")
