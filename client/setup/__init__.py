"""StreamScene WiFi Setup Module.

This module provides WiFi hotspot and captive portal functionality
for setting up StreamScene devices without requiring pre-configured WiFi.
"""

from .hotspot import (
    create_hotspot,
    stop_hotspot,
    generate_ssid,
    is_hotspot_active
)

from .portal_server import CaptivePortalServer

from .wifi_client import (
    connect_to_wifi,
    is_connected,
    load_credentials,
    save_credentials,
    get_current_ssid,
    get_ip_address,
    test_internet_connectivity,
    disconnect_wifi
)

__all__ = [
    # Hotspot management
    'create_hotspot',
    'stop_hotspot',
    'generate_ssid',
    'is_hotspot_active',

    # Captive portal
    'CaptivePortalServer',

    # WiFi client
    'connect_to_wifi',
    'is_connected',
    'load_credentials',
    'save_credentials',
    'get_current_ssid',
    'get_ip_address',
    'test_internet_connectivity',
    'disconnect_wifi',
]
