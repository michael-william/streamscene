"""Unit tests for the merged setup.network.NetworkManager.

Replaces the old separate test_network_service.py / test_setup_service.py,
which mocked NetworkManager/SetupManager objects that this module now
absorbs directly. These tests mock the module-level functions NetworkManager
delegates to (wifi_client, hotspot, registration) instead.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from setup.network import NetworkManager, NetworkStatus, NetworkCheckResult


class TestNetworkManagerConnectivity(unittest.TestCase):
    """check_initial_connectivity / check_network_and_credentials."""

    def setUp(self):
        self.nm = NetworkManager(device_uuid="test-device-uuid")

    @patch("setup.network.test_internet_connectivity", return_value=True)
    @patch.object(NetworkManager, "get_ethernet_ip", return_value="192.168.1.40")
    @patch.object(NetworkManager, "is_ethernet_available", return_value=True)
    def test_check_initial_connectivity_ethernet(self, _avail, _ip, _net):
        status = self.nm.check_initial_connectivity()
        self.assertTrue(status.connected)
        self.assertEqual(status.connection_type, "ethernet")
        self.assertEqual(status.ip_address, "192.168.1.40")

    @patch.object(NetworkManager, "is_ethernet_available", return_value=False)
    @patch.object(NetworkManager, "has_saved_credentials", return_value=False)
    def test_check_initial_connectivity_no_network(self, _creds, _eth):
        status = self.nm.check_initial_connectivity()
        self.assertFalse(status.connected)

    @patch("setup.network.test_internet_connectivity", return_value=True)
    @patch.object(NetworkManager, "get_ethernet_ip", return_value="192.168.1.40")
    @patch.object(NetworkManager, "is_ethernet_available", return_value=True)
    def test_check_network_and_credentials_ethernet_skips_setup(self, _avail, _ip, _net):
        result = self.nm.check_network_and_credentials()
        self.assertTrue(result.should_skip_wifi_setup)
        self.assertEqual(result.connection_type, "ethernet")

    @patch("setup.network.load_credentials", return_value={"ssid": "TestNet", "password": "secret"})
    @patch.object(NetworkManager, "is_ethernet_available", return_value=False)
    def test_check_network_and_credentials_saved_wifi_skips_setup(self, _eth, _creds):
        result = self.nm.check_network_and_credentials()
        self.assertTrue(result.should_skip_wifi_setup)
        self.assertEqual(result.connection_type, "saved_wifi")
        self.assertEqual(result.credentials["ssid"], "TestNet")


class TestNetworkManagerConnect(unittest.TestCase):
    """connect_to_wifi - the path that used to be spread across 4 layers."""

    def setUp(self):
        self.nm = NetworkManager(device_uuid="test-device-uuid")

    @patch("setup.network.test_internet_connectivity", return_value=True)
    @patch("setup.network.get_ip_address", return_value="192.168.1.100")
    @patch("setup.network._wifi_connect", return_value=(True, None))
    @patch("setup.network.is_hotspot_active", return_value=False)
    def test_connect_success_returns_three_tuple(self, _ap, _connect, _ip, _net):
        success, ip_address, error_reason = self.nm.connect_to_wifi("TestNet", "secret", timeout=30)
        self.assertTrue(success)
        self.assertEqual(ip_address, "192.168.1.100")
        self.assertIsNone(error_reason)

    @patch("setup.network._wifi_connect", return_value=(False, "wrong_credentials"))
    @patch("setup.network.is_hotspot_active", return_value=False)
    def test_connect_failure_returns_error_reason(self, _ap, _connect):
        success, ip_address, error_reason = self.nm.connect_to_wifi("TestNet", "wrongpass", timeout=30)
        self.assertFalse(success)
        self.assertIsNone(ip_address)
        self.assertEqual(error_reason, "wrong_credentials")

    @patch("setup.network.stop_hotspot", return_value=True)
    @patch("setup.network._wifi_connect", return_value=(False, "timeout"))
    @patch("setup.network.is_hotspot_active", return_value=True)
    def test_connect_stops_hotspot_first(self, _ap, _connect, mock_stop):
        self.nm.connect_to_wifi("TestNet", "secret", timeout=30)
        mock_stop.assert_called_once()


class TestNetworkManagerRegistration(unittest.TestCase):
    """run_registration_flow polling loop."""

    def setUp(self):
        self.nm = NetworkManager(device_uuid="test-device-uuid")

    @patch("setup.network.check_registration", return_value=True)
    def test_registration_succeeds_immediately(self, _check):
        self.assertTrue(self.nm.run_registration_flow(api_client=MagicMock(), poll_interval=0, timeout=5))

    @patch("setup.network.check_registration", return_value=False)
    def test_registration_times_out(self, _check):
        self.assertFalse(self.nm.run_registration_flow(api_client=MagicMock(), poll_interval=0, timeout=0))


class TestNetworkManagerCredentials(unittest.TestCase):
    """Saved-credential helpers."""

    def setUp(self):
        self.nm = NetworkManager(device_uuid="test-device-uuid")

    @patch("setup.network.load_credentials", return_value={"ssid": "TestNet", "password": "secret"})
    def test_has_saved_credentials_true(self, _load):
        self.assertTrue(self.nm.has_saved_credentials())
        self.assertEqual(self.nm.get_saved_ssid(), "TestNet")

    @patch("setup.network.load_credentials", return_value=None)
    def test_has_saved_credentials_false(self, _load):
        self.assertFalse(self.nm.has_saved_credentials())
        self.assertIsNone(self.nm.get_saved_ssid())


if __name__ == "__main__":
    unittest.main()
