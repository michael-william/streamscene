"""Unit tests for NetworkService."""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import subprocess

import sys
from pathlib import Path

# Add parent directory to path so we can import services
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.network_service import NetworkService, NetworkStatus


class TestNetworkService(unittest.TestCase):
    """Test cases for NetworkService."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_network_manager = Mock()
        self.mock_setup_manager = Mock()

        self.service = NetworkService(
            network_manager=self.mock_network_manager,
            setup_manager=self.mock_setup_manager,
            wifi_timeout=10,
            ethernet_check_timeout=5
        )

    def test_initialize(self):
        """Test service initialization."""
        result = self.service.initialize()
        self.assertTrue(result)

    def test_check_initial_connectivity_ethernet_available(self):
        """Test initial connectivity check when ethernet is available."""
        # Mock ethernet status
        self.mock_network_manager.get_ethernet_status.return_value = (True, "192.168.1.40")
        self.mock_network_manager.test_ethernet_connectivity.return_value = True

        # Check connectivity
        status = self.service.check_initial_connectivity()

        # Verify ethernet was checked
        self.mock_network_manager.get_ethernet_status.assert_called_once()
        self.mock_network_manager.test_ethernet_connectivity.assert_called_once_with(timeout=5)

        # Verify status
        self.assertTrue(status.connected)
        self.assertEqual(status.connection_type, "ethernet")
        self.assertEqual(status.ip_address, "192.168.1.40")
        self.assertEqual(status.interface, "eth0")
        self.assertIsNone(status.ssid)

    def test_check_initial_connectivity_wifi_available(self):
        """Test initial connectivity check when WiFi is available (ethernet not available)."""
        # Mock ethernet not available
        self.mock_network_manager.get_ethernet_status.return_value = (False, None)

        # Mock WiFi credentials available
        self.mock_setup_manager.has_saved_credentials.return_value = True
        self.mock_setup_manager.get_saved_ssid.return_value = "TestNetwork"

        # Mock WiFi status
        self.mock_network_manager.get_wifi_status.return_value = (True, "192.168.1.50")

        # Check connectivity
        status = self.service.check_initial_connectivity()

        # Verify WiFi was checked
        self.mock_network_manager.get_wifi_status.assert_called_once()

        # Verify status
        self.assertTrue(status.connected)
        self.assertEqual(status.connection_type, "wifi")
        self.assertEqual(status.ip_address, "192.168.1.50")
        self.assertEqual(status.interface, "wlan0")
        self.assertEqual(status.ssid, "TestNetwork")

    def test_check_initial_connectivity_no_network(self):
        """Test initial connectivity check when no network is available."""
        # Mock no ethernet
        self.mock_network_manager.get_ethernet_status.return_value = (False, None)

        # Mock no WiFi credentials
        self.mock_setup_manager.has_saved_credentials.return_value = False

        # Check connectivity
        status = self.service.check_initial_connectivity()

        # Verify status
        self.assertFalse(status.connected)
        self.assertIsNone(status.connection_type)
        self.assertIsNone(status.ip_address)
        self.assertIsNone(status.interface)
        self.assertIsNone(status.ssid)

    @patch('services.network_service.subprocess.run')
    @patch('builtins.open', create=True)
    def test_attempt_recovery_ethernet_up_dns_issue(self, mock_open, mock_subprocess):
        """Test recovery when ethernet is up but DNS is broken."""
        # Mock ethernet interface is UP
        mock_subprocess.return_value = Mock(stdout="state UP")

        # Mock DNS file read returns empty (no nameservers)
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = "# Empty resolv.conf"
        mock_open.return_value = mock_file

        # Attempt recovery
        result = self.service.attempt_recovery()

        # Should return True (DNS was fixed)
        self.assertTrue(result)

        # Verify DNS config was written
        self.assertTrue(mock_subprocess.called)

    @patch('setup.wifi_client.load_credentials')
    @patch('services.network_service.subprocess.run')
    def test_attempt_recovery_ethernet_down_wifi_success(self, mock_subprocess, mock_load_creds):
        """Test recovery when ethernet is down and WiFi connection succeeds."""
        # Mock ethernet interface is DOWN
        mock_subprocess.return_value = Mock(stdout="state DOWN")

        # Mock WiFi credentials available
        self.mock_setup_manager.has_saved_credentials.return_value = True
        mock_load_creds.return_value = {
            'ssid': 'TestNetwork',
            'password': 'testpass123'
        }

        # Mock successful WiFi connection
        self.mock_setup_manager.attempt_wifi_connection.return_value = True

        # Attempt recovery
        result = self.service.attempt_recovery()

        # Should return True
        self.assertTrue(result)

        # Verify WiFi connection was attempted
        self.mock_setup_manager.attempt_wifi_connection.assert_called()

    @patch('setup.wifi_client.load_credentials')
    @patch('services.network_service.subprocess.run')
    def test_attempt_recovery_ethernet_down_wifi_fails(self, mock_subprocess, mock_load_creds):
        """Test recovery when ethernet is down and WiFi connection fails."""
        # Mock ethernet interface is DOWN
        mock_subprocess.return_value = Mock(stdout="state DOWN")

        # Mock WiFi credentials available
        self.mock_setup_manager.has_saved_credentials.return_value = True
        mock_load_creds.return_value = {
            'ssid': 'TestNetwork',
            'password': 'testpass123'
        }

        # Mock failed WiFi connection (both attempts)
        self.mock_setup_manager.attempt_wifi_connection.return_value = False

        # Attempt recovery
        result = self.service.attempt_recovery()

        # Should return False
        self.assertFalse(result)

        # Verify WiFi connection was attempted twice
        self.assertEqual(self.mock_setup_manager.attempt_wifi_connection.call_count, 2)

    @patch('services.network_service.subprocess.run')
    def test_attempt_recovery_no_credentials(self, mock_subprocess):
        """Test recovery when no WiFi credentials are available."""
        # Mock ethernet interface is DOWN
        mock_subprocess.return_value = Mock(stdout="state DOWN")

        # Mock no WiFi credentials
        self.mock_setup_manager.has_saved_credentials.return_value = False

        # Attempt recovery
        result = self.service.attempt_recovery()

        # Should return False
        self.assertFalse(result)

        # WiFi connection should not be attempted
        self.mock_setup_manager.attempt_wifi_connection.assert_not_called()

    def test_get_current_status_ethernet(self):
        """Test getting current status when ethernet is connected."""
        # Mock ethernet status
        self.mock_network_manager.get_ethernet_status.return_value = (True, "192.168.1.40")
        self.mock_network_manager.test_ethernet_connectivity.return_value = True

        # Get status
        status = self.service.get_current_status()

        # Verify status
        self.assertTrue(status.connected)
        self.assertEqual(status.connection_type, "ethernet")

    def test_get_current_status_wifi(self):
        """Test getting current status when WiFi is connected (ethernet not available)."""
        # Mock no ethernet
        self.mock_network_manager.get_ethernet_status.return_value = (False, None)

        # Mock WiFi status
        self.mock_network_manager.get_wifi_status.return_value = (True, "192.168.1.50")
        self.mock_setup_manager.get_saved_ssid.return_value = "TestNetwork"

        # Get status
        status = self.service.get_current_status()

        # Verify status
        self.assertTrue(status.connected)
        self.assertEqual(status.connection_type, "wifi")
        self.assertEqual(status.ssid, "TestNetwork")

    def test_get_current_status_no_connection(self):
        """Test getting current status when no connection is available."""
        # Mock no ethernet
        self.mock_network_manager.get_ethernet_status.return_value = (False, None)

        # Mock no WiFi
        self.mock_network_manager.get_wifi_status.return_value = (False, None)

        # Get status
        status = self.service.get_current_status()

        # Verify status
        self.assertFalse(status.connected)
        self.assertIsNone(status.connection_type)

    @patch('services.network_service.subprocess.run')
    def test_is_ethernet_up_true(self, mock_subprocess):
        """Test _is_ethernet_up when interface is UP."""
        mock_subprocess.return_value = Mock(stdout="state UP")

        result = self.service._is_ethernet_up()

        self.assertTrue(result)
        mock_subprocess.assert_called_once()

    @patch('services.network_service.subprocess.run')
    def test_is_ethernet_up_false(self, mock_subprocess):
        """Test _is_ethernet_up when interface is DOWN."""
        mock_subprocess.return_value = Mock(stdout="state DOWN")

        result = self.service._is_ethernet_up()

        self.assertFalse(result)

    @patch('services.network_service.subprocess.run')
    def test_is_ethernet_up_exception(self, mock_subprocess):
        """Test _is_ethernet_up when subprocess raises exception."""
        mock_subprocess.side_effect = subprocess.TimeoutExpired("ip", 5)

        result = self.service._is_ethernet_up()

        self.assertFalse(result)

    @patch('builtins.open', create=True)
    @patch('services.network_service.subprocess.run')
    def test_ensure_dns_configured_already_configured(self, mock_subprocess, mock_open):
        """Test _ensure_dns_configured when DNS is already set."""
        # Mock resolv.conf with nameserver
        mock_open.return_value.__enter__.return_value.read.return_value = "nameserver 8.8.8.8"

        result = self.service._ensure_dns_configured()

        self.assertTrue(result)
        # Should not call subprocess to add DNS
        mock_subprocess.assert_not_called()

    @patch('builtins.open', create=True)
    @patch('services.network_service.subprocess.run')
    def test_ensure_dns_configured_adds_dns(self, mock_subprocess, mock_open):
        """Test _ensure_dns_configured when DNS needs to be added."""
        # Mock empty resolv.conf
        mock_open.return_value.__enter__.return_value.read.return_value = ""

        # Mock successful subprocess call
        mock_subprocess.return_value = Mock()

        result = self.service._ensure_dns_configured()

        self.assertTrue(result)
        # Should call subprocess to add DNS
        mock_subprocess.assert_called_once()

    @patch('builtins.open', create=True)
    def test_ensure_dns_configured_exception(self, mock_open):
        """Test _ensure_dns_configured when an exception occurs."""
        # Mock file operation exception
        mock_open.side_effect = IOError("Permission denied")

        result = self.service._ensure_dns_configured()

        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
