"""Unit tests for SetupService."""

import unittest
from unittest.mock import Mock, MagicMock, patch, call

import sys
from pathlib import Path

# Add parent directory to path so we can import services
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.setup_service import (
    SetupService,
    NetworkCheckResult,
    RegistrationResult
)


class TestSetupService(unittest.TestCase):
    """Test cases for SetupService."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_setup_manager = Mock()
        self.mock_network_manager = Mock()
        self.mock_config_service = Mock()
        self.device_uuid = "test-device-uuid"

        self.service = SetupService(
            device_uuid=self.device_uuid,
            setup_manager=self.mock_setup_manager,
            network_manager=self.mock_network_manager,
            config_service=self.mock_config_service
        )

    def test_initialize(self):
        """Test service initialization."""
        result = self.service.initialize()
        self.assertTrue(result)

    def test_check_network_ethernet_available(self):
        """Test network check when ethernet is available with internet."""
        # Mock ethernet available with IP
        self.mock_network_manager.get_ethernet_status.return_value = (True, "192.168.1.40")
        self.mock_network_manager.test_ethernet_connectivity.return_value = True

        result = self.service.check_network_and_credentials()

        # Should skip WiFi setup
        self.assertTrue(result.should_skip_wifi_setup)
        self.assertEqual(result.connection_type, "ethernet")
        self.assertEqual(result.ip_address, "192.168.1.40")
        self.assertIsNone(result.credentials)

    def test_check_network_ethernet_no_internet(self):
        """Test network check when ethernet exists but has no internet."""
        # Mock ethernet available but no internet
        self.mock_network_manager.get_ethernet_status.return_value = (True, "192.168.1.40")
        self.mock_network_manager.test_ethernet_connectivity.return_value = False

        # Mock saved credentials available
        self.mock_setup_manager.check_saved_credentials.return_value = {
            "ssid": "TestNetwork",
            "password": "testpass123"
        }

        result = self.service.check_network_and_credentials()

        # Should use saved credentials
        self.assertTrue(result.should_skip_wifi_setup)
        self.assertEqual(result.connection_type, "saved_wifi")
        self.assertIsNotNone(result.credentials)

    def test_check_network_saved_credentials(self):
        """Test network check when saved WiFi credentials exist."""
        # Mock no ethernet
        self.mock_network_manager.get_ethernet_status.return_value = (False, None)

        # Mock saved credentials
        self.mock_setup_manager.check_saved_credentials.return_value = {
            "ssid": "TestNetwork",
            "password": "testpass123"
        }

        result = self.service.check_network_and_credentials()

        # Should skip WiFi setup and use saved credentials
        self.assertTrue(result.should_skip_wifi_setup)
        self.assertEqual(result.connection_type, "saved_wifi")
        self.assertEqual(result.credentials["ssid"], "TestNetwork")

    def test_check_network_no_network_or_credentials(self):
        """Test network check when no ethernet or credentials available."""
        # Mock no ethernet
        self.mock_network_manager.get_ethernet_status.return_value = (False, None)

        # Mock no saved credentials
        self.mock_setup_manager.check_saved_credentials.return_value = None

        result = self.service.check_network_and_credentials()

        # Should NOT skip WiFi setup
        self.assertFalse(result.should_skip_wifi_setup)
        self.assertIsNone(result.connection_type)
        self.assertIsNone(result.ip_address)
        self.assertIsNone(result.credentials)

    def test_run_wifi_setup_flow_success(self):
        """Test successful WiFi setup flow."""
        # Mock successful setup
        self.mock_setup_manager.run_wifi_setup.return_value = {
            "ssid": "NewNetwork",
            "password": "newpass123"
        }

        result = self.service.run_wifi_setup_flow(timeout=1800)

        # Should return credentials
        self.assertIsNotNone(result)
        self.assertEqual(result["ssid"], "NewNetwork")
        self.mock_setup_manager.run_wifi_setup.assert_called_once_with(timeout=1800)

    def test_run_wifi_setup_flow_timeout(self):
        """Test WiFi setup flow with timeout."""
        # Mock timeout
        self.mock_setup_manager.run_wifi_setup.return_value = None

        result = self.service.run_wifi_setup_flow(timeout=1800)

        # Should return None
        self.assertIsNone(result)

    def test_run_wifi_setup_flow_exception(self):
        """Test WiFi setup flow with exception."""
        # Mock exception
        self.mock_setup_manager.run_wifi_setup.side_effect = Exception("Setup failed")

        result = self.service.run_wifi_setup_flow()

        # Should return None on exception
        self.assertIsNone(result)

    def test_connect_to_wifi_success(self):
        """Test successful WiFi connection."""
        # Mock successful connection
        self.mock_network_manager.switch_to_client_mode.return_value = (True, "192.168.1.50")

        success, ip = self.service.connect_to_wifi("TestNetwork", "testpass123", timeout=45)

        # Should succeed
        self.assertTrue(success)
        self.assertEqual(ip, "192.168.1.50")
        self.mock_network_manager.switch_to_client_mode.assert_called_once_with(
            ssid="TestNetwork",
            password="testpass123",
            timeout=45
        )

    def test_connect_to_wifi_failure(self):
        """Test failed WiFi connection."""
        # Mock failed connection
        self.mock_network_manager.switch_to_client_mode.return_value = (False, None)

        success, ip = self.service.connect_to_wifi("TestNetwork", "wrongpass")

        # Should fail
        self.assertFalse(success)
        self.assertIsNone(ip)

    def test_connect_to_wifi_exception(self):
        """Test WiFi connection with exception."""
        # Mock exception
        self.mock_network_manager.switch_to_client_mode.side_effect = Exception("Connection error")

        success, ip = self.service.connect_to_wifi("TestNetwork", "testpass123")

        # Should fail
        self.assertFalse(success)
        self.assertIsNone(ip)

    @patch('services.setup_service.get_registration_url')
    def test_get_registration_url(self, mock_get_url):
        """Test getting registration URL."""
        mock_get_url.return_value = "https://streamscene.example.com/setup/test-device-uuid"

        url = self.service.get_registration_url()

        self.assertEqual(url, "https://streamscene.example.com/setup/test-device-uuid")
        mock_get_url.assert_called_once_with(self.device_uuid)

    def test_run_registration_flow_success(self):
        """Test successful registration flow."""
        mock_api_client = Mock()

        # Mock successful registration
        self.mock_setup_manager.run_registration_flow.return_value = True

        result = self.service.run_registration_flow(
            api_client=mock_api_client,
            poll_interval=10,
            timeout=1800
        )

        # Should succeed
        self.assertTrue(result)
        self.mock_setup_manager.run_registration_flow.assert_called_once_with(
            api_client=mock_api_client,
            poll_interval=10,
            timeout=1800
        )

    def test_run_registration_flow_timeout(self):
        """Test registration flow with timeout."""
        mock_api_client = Mock()

        # Mock timeout
        self.mock_setup_manager.run_registration_flow.return_value = False

        result = self.service.run_registration_flow(api_client=mock_api_client)

        # Should fail
        self.assertFalse(result)

    def test_run_registration_flow_exception(self):
        """Test registration flow with exception."""
        mock_api_client = Mock()

        # Mock exception
        self.mock_setup_manager.run_registration_flow.side_effect = Exception("Registration error")

        result = self.service.run_registration_flow(api_client=mock_api_client)

        # Should fail
        self.assertFalse(result)

    def test_is_registered_true(self):
        """Test is_registered when device has API key."""
        self.mock_config_service.is_registered.return_value = True

        result = self.service.is_registered()

        self.assertTrue(result)

    def test_is_registered_false(self):
        """Test is_registered when device has no API key."""
        self.mock_config_service.is_registered.return_value = False

        result = self.service.is_registered()

        self.assertFalse(result)

    def test_verify_registration_complete_no_api_key(self):
        """Test verify_registration_complete when no API key exists."""
        self.mock_config_service.is_registered.return_value = False

        result = self.service.verify_registration_complete()

        # Should fail
        self.assertFalse(result.success)
        self.assertIsNone(result.api_key)
        self.assertIsNotNone(result.error)

    def test_verify_registration_complete_success(self):
        """Test verify_registration_complete when registration succeeded."""
        self.mock_config_service.is_registered.return_value = True
        self.mock_config_service.fetch_initial_config.return_value = {"rotation_enabled": False}

        result = self.service.verify_registration_complete()

        # Should succeed
        self.assertTrue(result.success)
        self.assertEqual(result.api_key, "present")
        self.assertIsNone(result.error)

    def test_verify_registration_complete_config_fetch_failed(self):
        """Test verify_registration_complete when config fetch fails."""
        self.mock_config_service.is_registered.return_value = True
        self.mock_config_service.fetch_initial_config.return_value = None

        result = self.service.verify_registration_complete()

        # Should still succeed (key exists)
        self.assertTrue(result.success)
        self.assertEqual(result.api_key, "present")
        self.assertIsNotNone(result.error)  # But has error message

    def test_verify_registration_complete_exception(self):
        """Test verify_registration_complete when exception occurs."""
        self.mock_config_service.is_registered.return_value = True
        self.mock_config_service.fetch_initial_config.side_effect = Exception("Fetch failed")

        result = self.service.verify_registration_complete()

        # Should still succeed (key exists)
        self.assertTrue(result.success)
        self.assertEqual(result.api_key, "present")
        self.assertIn("Verification error", result.error)

    def test_has_saved_credentials_true(self):
        """Test has_saved_credentials when credentials exist."""
        self.mock_setup_manager.has_saved_credentials.return_value = True

        result = self.service.has_saved_credentials()

        self.assertTrue(result)

    def test_has_saved_credentials_false(self):
        """Test has_saved_credentials when no credentials exist."""
        self.mock_setup_manager.has_saved_credentials.return_value = False

        result = self.service.has_saved_credentials()

        self.assertFalse(result)

    def test_get_saved_ssid_exists(self):
        """Test get_saved_ssid when SSID exists."""
        self.mock_setup_manager.get_saved_ssid.return_value = "TestNetwork"

        result = self.service.get_saved_ssid()

        self.assertEqual(result, "TestNetwork")

    def test_get_saved_ssid_none(self):
        """Test get_saved_ssid when no SSID exists."""
        self.mock_setup_manager.get_saved_ssid.return_value = None

        result = self.service.get_saved_ssid()

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
